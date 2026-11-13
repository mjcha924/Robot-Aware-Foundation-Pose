"""Lazy GPU bridge to the pinned upstream; never changes its source files."""
import sys
from pathlib import Path
import torch
from .model import RobotConditionedRefiner
from .geometry import decode_pose


def load_upstream(root):
    root = Path(root).resolve()
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / 'learning/models'))
    from learning.training.predict_pose_refine import PoseRefinePredictor
    from omegaconf import OmegaConf
    predictor = PoseRefinePredictor()
    cfg = OmegaConf.to_container(predictor.cfg, resolve=True)
    if cfg.get('rot_rep') != 'axis_angle' or cfg.get('trans_rep') != 'tracknet':
        raise ValueError('V1 requires tracknet/axis_angle checkpoint')
    return predictor, cfg


class RenderBridge:
    def __init__(self, predictor, mesh):
        from Utils import make_mesh_tensors, compute_mesh_diameter
        import nvdiffrast.torch as dr
        self.predictor, self.mesh = predictor, mesh
        self.mesh_tensors = make_mesh_tensors(mesh)
        self.diameter = float(compute_mesh_diameter(model_pts=mesh.vertices, n_sample=1000))
        self.context = dr.RasterizeCudaContext()

    def pair(self, rgb, depth, intrinsic, hypothesis):
        from learning.training.predict_pose_refine import make_crop_data_batch
        from Utils import depth2xyzmap
        cfg = self.predictor.cfg
        if cfg.use_normal:
            raise ValueError('V1 visual bridge does not support use_normal=True')
        xyz = depth2xyzmap(depth, intrinsic)
        # Upstream crop helpers change the GLOBAL default tensor type to CUDA.
        # Restore it, otherwise subsequent CPU-side pose/point preparation breaks.
        old_type = torch.tensor(0.).type()
        try:
            with torch.no_grad():
                batch = make_crop_data_batch(cfg.input_resize, hypothesis, self.mesh, rgb, depth,
                    intrinsic, cfg.crop_ratio, xyz, mesh_diameter=self.diameter, cfg=cfg,
                    glctx=self.context, mesh_tensors=self.mesh_tensors, dataset=self.predictor.dataset)
        finally:
            torch.set_default_tensor_type(old_type)
        # The upstream crop function uses inference_mode: clone OUTSIDE it to
        # obtain ordinary tensors that may safely participate in autograd.
        a = torch.cat((batch.rgbAs, batch.xyz_mapAs), 1).float().clone()
        b = torch.cat((batch.rgbBs, batch.xyz_mapBs), 1).float().clone()
        return a, b

    def refine(self, model, rgb, depth, intrinsic, hypothesis, build_points, cfg, iterations=2):
        """Inference entry point. build_points(pose) receives no object GT."""
        if iterations < 1:
            raise ValueError('iterations must be positive')
        model.eval()
        pose = hypothesis
        with torch.no_grad():
            for _ in range(iterations):
                a, b = self.pair(rgb, depth, intrinsic, pose)
                points = build_points(pose).to(pose.device)
                result = model(a, b, points)
                pose = decode_pose(result, pose, pose.new_full((len(pose),), self.diameter), cfg)
        return pose
