"""Opt-in registration screening without modifying NVIDIA's estimator.

Override only proposal generation: refinement, learned scoring, translation
initialization, and subsequent tracking remain upstream implementations.
"""

import time
import cv2
import numpy as np
import torch
import nvdiffrast.torch as dr
from estimater import FoundationPose
from Utils import nvdiffrast_render
from candidate_pruning.policy import select_candidates, screening_resolution
from candidate_pruning.scoring import score_depth_hypotheses


class FilteredFoundationPose(FoundationPose):
    def __init__(self, *args, filter_mode="none", candidate_keep=64, render_scale=4, **kwargs):
        if filter_mode not in {"none", "random", "geometry", "effector"}:
            raise ValueError("unknown candidate filter")
        if type(candidate_keep) is not int or candidate_keep < 1 or type(render_scale) is not int or render_scale < 1:
            raise ValueError("candidate_keep and render_scale must be positive integers")
        super().__init__(*args, **kwargs)
        self.filter_mode, self.candidate_keep, self.render_scale = filter_mode, candidate_keep, render_scale
        self.robot_renderer = None
        self.robot_camera = self.robot_links = None
        self.selection_seed = 0
        self.filter_trace = {}
        # Keep small screening batches separate from the upstream rasterizer's
        # large learned-scoring batches; its scratch buffers retain capacity.
        self.screening_context = dr.RasterizeCudaContext()

    def set_robot_state(self, renderer, world_camera, world_links):
        # Deliberately take only robot/camera state, never a complete frame dict.
        self.robot_renderer, self.robot_camera, self.robot_links = renderer, world_camera, world_links

    def register(self, *args, **kwargs):
        self.filter_trace = {"proposal_count": 0, "candidate_count": 0, "selected_indices": [],
                             "filter_s": 0.0, "fallback": "upstream_rejected_input",
                             "status": "upstream_rejected_input"}
        return super().register(*args, **kwargs)

    def generate_random_pose_hypo(self, K, rgb, depth, mask, scene_pts=None):
        proposals = super().generate_random_pose_hypo(K, rgb, depth, mask, scene_pts)
        torch.cuda.synchronize()
        start = time.perf_counter()
        count = len(proposals)
        scores, max_iou, fallback = [0.0] * count, None, None
        if self.filter_mode in {"geometry", "effector"}:
            height, width = depth.shape
            h, w = screening_resolution(height, width, self.render_scale)
            intrinsic = np.asarray(K).copy()
            intrinsic[0] *= w / width
            intrinsic[1] *= h / height
            small_mask = cv2.resize(mask.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0
            small_depth = cv2.resize(depth, (w, h), interpolation=cv2.INTER_NEAREST)
            if np.count_nonzero(small_mask & (small_depth > 0)) < 16:
                fallback = "insufficient_visible_depth_at_screening_resolution"
            else:
                observed = torch.as_tensor(small_depth, dtype=torch.float32, device="cuda")
                target = torch.as_tensor(small_mask, device="cuda")
                robot_depth = None
                if self.filter_mode == "effector":
                    if self.robot_renderer is None or self.robot_camera is None or self.robot_links is None:
                        raise ValueError("effector filtering requires robot geometry and synchronized robot/camera poses")
                    robot_depth = self.robot_renderer.render(self.robot_camera, self.robot_links, intrinsic, h, w)
                score_parts, iou_parts = [], []
                for batch in proposals.split(16):
                    _, rendered_depth, _ = nvdiffrast_render(
                        K=intrinsic, H=h, W=w, ob_in_cams=batch, glctx=self.screening_context,
                        mesh_tensors=self.mesh_tensors, extra={})
                    costs, ious = score_depth_hypotheses(rendered_depth, observed, target, robot_depth)
                    score_parts.append(costs)
                    iou_parts.append(ious)
                scores = torch.cat(score_parts).cpu().tolist()
                max_iou = float(torch.cat(iou_parts).max().item())
                if max_iou < 0.05 or max(scores) - min(scores) < 1e-6:
                    fallback = "uninformative_geometry_scores"
        mode = "ranked" if self.filter_mode in {"geometry", "effector"} else self.filter_mode
        indices = select_candidates(scores, self.candidate_keep, mode, self.selection_seed, informative=fallback is None)
        selected = proposals[indices]
        torch.cuda.synchronize()
        self.filter_trace = {
            "mode": self.filter_mode, "proposal_count": count, "candidate_count": len(indices),
            "selected_indices": indices, "screening_scores": scores if mode == "ranked" else None,
            "max_visible_iou": max_iou, "fallback": fallback, "status": "ok",
            "filter_s": time.perf_counter() - start, "selection_seed": self.selection_seed,
            "render_scale": self.render_scale,
        }
        return selected
