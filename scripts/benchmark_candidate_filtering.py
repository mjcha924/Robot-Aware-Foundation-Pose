"""Matched independent-registration trials; not a temporal recovery benchmark."""

import hashlib
import json
import statistics
import time
from pathlib import Path


def benchmark(sequence, output, manifest, frames, args):
    import cv2
    import numpy as np
    import torch
    import trimesh
    import nvdiffrast.torch as dr
    from estimater import FoundationPose, PoseRefinePredictor, ScorePredictor
    from foundationpose_adapter.filtered_estimator import FilteredFoundationPose
    from urdf_render.robot_depth import RobotDepthRenderer
    from evaluation.pose_metrics import rotation_error_deg, translation_error_m
    from Utils import set_seed

    if "robot_geometry" not in manifest:
        raise ValueError("filtering benchmark requires a calibrated robot-geometry export")
    ids = [int(value) for value in args.trial_frames.split(",")]
    if len(set(ids)) != len(ids) or any(i < 0 or i >= len(frames) for i in ids):
        raise ValueError("trial frames must be unique valid frame indices")
    intrinsic = np.asarray(manifest["camera"]["K"])
    mesh = trimesh.load(sequence / manifest["mesh"]["path"])
    object_mesh_inverse = np.linalg.inv(np.asarray(manifest["mesh"]["T_object_mesh"]))
    set_seed(0)
    start = time.perf_counter()
    context = dr.RasterizeCudaContext()
    scorer, refiner = ScorePredictor(), PoseRefinePredictor()
    common = dict(model_pts=mesh.vertices, model_normals=mesh.vertex_normals, mesh=mesh,
                  scorer=scorer, refiner=refiner, glctx=context, debug=0, debug_dir=str(output))
    original = FoundationPose(**common)
    filtered = FilteredFoundationPose(**common, candidate_keep=args.filter_keep, render_scale=args.screening_scale)
    # Robot topology is much larger than the bottle: sharing a CUDA rasterizer
    # with the 252-pose upstream batches can inflate retained scratch buffers.
    renderer = RobotDepthRenderer(sequence, manifest["robot_geometry"])
    torch.cuda.synchronize()
    initialization_s = time.perf_counter() - start

    def inputs(index):
        frame_id = frames[index]["frame_id"]
        rgb = cv2.imread(str(sequence / "rgb" / f"{frame_id}.png"))
        depth = cv2.imread(str(sequence / "depth" / f"{frame_id}.png"), -1)
        mask = cv2.imread(str(sequence / "masks" / f"{frame_id}.png"), -1)
        if rgb is None or depth is None or mask is None:
            raise ValueError(f"missing trial input for {frame_id}")
        return rgb[..., ::-1].copy(), depth.astype(np.float32) * manifest["units"]["depth_scale_to_m"], mask > 0

    methods = ("effector", "original", "random", "geometry", "effector_shifted_10mm")

    def run(index, method, seed, keep):
        rgb, depth, mask = inputs(index)  # excluded from estimator-call timing
        estimator = original if method == "original" else filtered
        if method != "original":
            filtered.filter_mode = "effector" if method.startswith("effector") else method
            filtered.candidate_keep, filtered.selection_seed = keep, seed
            camera = np.asarray(frames[index]["T_world_camera"]).copy()
            if method == "effector_shifted_10mm":
                # Perturb robot projection only; do not alter observation/GT.
                camera[:3, 3] += camera[:3, 0] * 0.01
            filtered.set_robot_state(renderer, camera, frames[index]["T_world_robot_links"])
        estimator.pose_last = None
        if hasattr(estimator, "poses"):
            del estimator.poses
        torch.cuda.synchronize()
        start = time.perf_counter()
        pose = estimator.register(K=intrinsic, rgb=rgb, depth=depth, ob_mask=mask,
                                  iteration=args.est_refine_iter)
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        trace = dict(filtered.filter_trace) if method != "original" else {
            "proposal_count": len(original.rot_grid),
            "candidate_count": len(original.rot_grid) if hasattr(original, "poses") else 0,
            "selected_indices": list(range(len(original.rot_grid))) if hasattr(original, "poses") else [], "filter_s": 0.0,
            "status": "ok" if hasattr(original, "poses") else "upstream_rejected_input"}
        return pose @ object_mesh_inverse, elapsed, trace

    # Warm every path, including shape-dependent refinement batches. All methods
    # receive the same first frame. No warmup measurements enter trial summaries.
    warmup = []
    for method in methods:
        _, elapsed, _ = run(0, method, args.filter_seed, args.filter_keep)
        warmup.append({"method": method, "inference_s": elapsed})
    rows = []
    reference_pixels = int(inputs(0)[2].sum())
    with (output / "trials.jsonl").open("w") as stream:
        for index in ids:
            frame = frames[index]
            _, depth, mask = inputs(index)
            usable = int(np.count_nonzero(mask & (depth > 0))) >= 16
            for repeat in range(args.trial_repeats):
                seed = args.filter_seed + index * 1009 + repeat
                matched_keep = args.filter_keep
                for method in methods:
                    row = {"frame_id": frame["frame_id"], "timestamp_s": frame["timestamp_s"],
                           "repeat": repeat, "method": method,
                           "seed": seed, "visible_mask_pixels": int(mask.sum()),
                           "visibility_group": "below_half_reference" if mask.sum() < reference_pixels * .5
                           else "at_least_half_reference"}
                    if not usable:
                        row.update(status="unobservable", candidate_count=0, success=False)
                    else:
                        pose, elapsed, trace = run(index, method, seed,
                                                  matched_keep if method == "random" else args.filter_keep)
                        row.update(trace)
                        row.update(inference_s=elapsed, T_camera_object=pose.tolist())
                        if method == "effector":
                            matched_keep = max(1, trace["candidate_count"])
                        # Evaluation-only boundary: object truth is first read
                        # after estimation, never passed to run()/the adapter.
                        gt_world = frame.get("T_world_object_gt")
                        if gt_world is not None:
                            gt = np.linalg.inv(frame["T_world_camera"]) @ np.asarray(gt_world)
                            row["translation_error_m"] = translation_error_m(pose.tolist(), gt.tolist())
                            row["rotation_error_deg"] = rotation_error_deg(pose.tolist(), gt.tolist())
                            row["success"] = (trace["status"] == "ok"
                                              and row["translation_error_m"] <= 0.02
                                              and row["rotation_error_deg"] <= 15)
                            grid = original.rot_grid.detach().cpu().numpy()
                            angles = [rotation_error_deg((p @ object_mesh_inverse).tolist(), gt.tolist()) for p in grid]
                            nearest = {i for i, angle in enumerate(angles) if angle <= min(angles) + 1e-5}
                            row["nearest_rotation_retained"] = bool(nearest.intersection(trace["selected_indices"]))
                        else:
                            row["success"] = None
                    rows.append(row)
                    stream.write(json.dumps(row, separators=(",", ":")) + "\n")
                    stream.flush()
                    print(f"Trial {frame['frame_id']} {repeat} {method}: {row['status']} "
                          f"candidates={row['candidate_count']} success={row.get('success')}", flush=True)
    summary = {}
    for method in methods:
        group = [row for row in rows if row["method"] == method and row["status"] != "unobservable"]
        labeled = [row for row in group if row.get("success") is not None]
        summary[method] = {
            "attempted_trials": len(group),
            "unobservable_trials": sum(row["method"] == method and row["status"] == "unobservable" for row in rows),
            "successes_20mm_15deg": sum(row["success"] for row in labeled),
            "labeled_trials": len(labeled),
            "median_inference_s": statistics.median(row["inference_s"] for row in group) if group else None,
            "mean_candidate_count": statistics.mean(row["candidate_count"] for row in group) if group else None,
            "median_filter_s": statistics.median(row["filter_s"] for row in group) if group else None,
            "fallback_trials": sum(bool(row.get("fallback")) for row in group),
            "mean_translation_error_m": statistics.mean(row["translation_error_m"] for row in labeled) if labeled else None,
            "mean_rotation_error_deg": statistics.mean(row["rotation_error_deg"] for row in labeled) if labeled else None,
            "nearest_rotation_retention_rate": statistics.mean(row["nearest_rotation_retained"] for row in labeled) if labeled else None,
        }
    report = {
        "protocol": "independent registration, oracle visible object masks equally supplied to all methods; not temporal recovery",
        "trial_indices": ids, "repeats": args.trial_repeats, "filter_keep": args.filter_keep,
        "screening_scale": args.screening_scale, "filter_seed": args.filter_seed,
        "refinement_iterations": args.est_refine_iter, "success_thresholds": {"translation_m": 0.02, "rotation_deg": 15},
        "method_order": methods, "order_note": "EA first to match random's candidate count, including fallbacks; fixed order is a timing limitation",
        "initialization_s": initialization_s, "warmup": warmup, "summary": summary,
        "success_by_visible_area": {method: {visibility: {
            "attempted": sum(row["method"] == method and row["visibility_group"] == visibility
                             and row["status"] != "unobservable" for row in rows),
            "successes": sum(row["method"] == method and row["visibility_group"] == visibility
                             and bool(row.get("success")) for row in rows)}
            for visibility in ("at_least_half_reference", "below_half_reference")} for method in methods},
        "input_sha256": {name: hashlib.sha256((sequence / name).read_bytes()).hexdigest()
                         for name in ("manifest.json", "frames.jsonl", manifest["mesh"]["path"])},
        "trial_image_sha256": {frames[i]["frame_id"]: {
            kind: hashlib.sha256((sequence / kind / f"{frames[i]['frame_id']}.png").read_bytes()).hexdigest()
            for kind in ("rgb", "depth", "masks")} for i in sorted(set(ids + [0]))},
        "implementation_sha256": {name: hashlib.sha256((Path(__file__).resolve().parents[1] / name).read_bytes()).hexdigest()
                                  for name in ("scripts/benchmark_candidate_filtering.py",
                                               "src/foundationpose_adapter/filtered_estimator.py",
                                               "src/candidate_pruning/policy.py", "src/candidate_pruning/scoring.py",
                                               "src/urdf_render/robot_depth.py")},
        "foundationpose_commit": "a1b694b83e633c2cb6115b9063d940a687759392",
        "scoring": {"loss": "1 - visible IoU + 0.25 * clipped mean visible depth residual",
                    "depth_clip_m": 0.03, "occlusion_margin_m": 0.005, "robot_depth_tolerance_m": 0.01,
                    "min_screening_depth_pixels": 16, "min_best_iou": 0.05},
        "timing": "warmed CUDA-synchronized register call including robot/object rendering and selection, excluding input I/O, initialization and evaluation",
        "limitations": "Single sequence exploratory test; repeats are not independent scenes. Simulator robot poses are ideal. No tracking or hidden-object recovery benefit established.",
    }
    (output / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
