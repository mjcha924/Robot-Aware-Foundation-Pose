#!/usr/bin/env python3
"""GPU sequence rollout. Initial pose must come from an external initializer."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('sequence', type=Path)
    p.add_argument('--initial-pose', type=Path, required=True, help='4x4 .npy T_camera_raw_mesh, NOT object-frame pose')
    p.add_argument('--checkpoint', type=Path, help='Omit for original refiner control')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--iterations', type=int, default=2)
    a = p.parse_args()
    from validate_isaac_export import validate_sequence
    errors = validate_sequence(a.sequence)
    if errors: raise ValueError(errors)
    import numpy as np
    import torch
    from robot_conditioned_pose.omy_sequence import open_sequence
    from robot_conditioned_pose.upstream import load_upstream, RenderBridge
    from robot_conditioned_pose.model import RobotConditionedRefiner
    from robot_conditioned_pose.geometry import pose_loss
    np.random.seed(0); torch.manual_seed(0)
    reader = open_sequence(a.sequence)
    predictor, cfg = load_upstream(ROOT / 'third_party/FoundationPose')
    model = RobotConditionedRefiner(predictor.model, mode='visual').cuda().eval()
    if a.checkpoint:
        saved = torch.load(a.checkpoint, map_location='cuda', weights_only=True)
        weight_hash = hashlib.sha256(Path(cfg['ckpt_dir']).read_bytes()).hexdigest()
        if saved['cfg'] != cfg or saved['provenance']['weight_sha256'] != weight_hash:
            raise ValueError('pretrained checkpoint/config differs from training')
        missing, unexpected = model.load_state_dict(saved['model'], strict=False)
        if unexpected or any(not k.startswith(('upstream.encodeA.', 'upstream.encodeAB.', 'upstream.pos_embed.')) for k in missing):
            raise ValueError((missing, unexpected))
        model.mode = saved['mode']
    bridge = RenderBridge(predictor, reader.mesh)
    pose = torch.as_tensor(np.load(a.initial_pose), dtype=torch.float32, device='cuda')[None]
    if (pose.shape != (1, 4, 4) or not torch.isfinite(pose).all()
        or not torch.allclose(pose[0,3], pose.new_tensor([0,0,0,1]))
        or not torch.allclose(pose[0,:3,:3].T @ pose[0,:3,:3], torch.eye(3,device='cuda'), atol=1e-4)
        or not torch.isclose(torch.linalg.det(pose[0,:3,:3]), pose.new_tensor(1.), atol=1e-4)):
        raise ValueError('expected finite 4x4 initial pose')
    a.output.mkdir(parents=True, exist_ok=False)
    with (a.output / 'poses.jsonl').open('w') as f:
        for i, frame in enumerate(reader.frames):
            rgb, depth = reader.observation(i)
            # Convert previous camera estimate to the current camera BEFORE refinement.
            if i:
                prev_cam = torch.as_tensor(reader.frames[i-1]['T_world_camera'], device='cuda', dtype=torch.float32)
                curr_cam = torch.as_tensor(frame['T_world_camera'], device='cuda', dtype=torch.float32)
                pose = torch.linalg.inv(curr_cam) @ prev_cam @ pose
            pose = bridge.refine(model, rgb, depth, reader.K, pose,
                lambda h: reader.points(i, h[0], bridge.diameter)[None], cfg, a.iterations)
            row = dict(frame_id=frame['frame_id'], T_camera_mesh=pose[0].cpu().tolist())
            if 'T_world_object_gt' in frame or 'omy_tracking' in reader.manifest:
                # GT accessed ONLY after prediction.
                error = pose_loss(pose.cpu(), reader.target(i)[None], reader.cad[None], [reader.symmetries])
                row['symmetry_surface_error_m'] = error.item()
            f.write(json.dumps(row) + '\n'); f.flush()
    print(a.output)
