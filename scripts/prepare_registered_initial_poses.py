#!/usr/bin/env python3
"""Frame-0 poses from upstream FoundationPose registration (no pose GT).

Input to registration: frame-0 RGB, depth, K, CAD mesh and the dataset's frame-0
object mask. The mask is the dataset's oracle visible mask (manifest protocol
'oracle_visible_mask_for_equal_method_comparison'), so this removes the pose
oracle but not the segmentation oracle. One registration per sequence, fixed
seed, no retries and no selection. Frame-0 errors against GT are computed only
after every pose has been written, for reporting.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--iterations', type=int, default=5, help='Upstream register refinement iterations (upstream default 5)')
    a = p.parse_args()
    import numpy as np
    import torch
    import trimesh
    from PIL import Image
    manifest = json.loads((ROOT/'configs/omy_pilot_manifest_20261124.json').read_text())
    sequences = [a.dataset/r['path'] for r in manifest['sequences'].values() if r['split'] == 'validation']
    for path in sequences:
        if not (path/'manifest.json').is_file(): raise FileNotFoundError(path)
    a.output.mkdir(parents=True, exist_ok=False)
    up = ROOT/'third_party/FoundationPose'
    sys.path.insert(0, str(up)); sys.path.insert(0, str(up/'learning/models'))
    import nvdiffrast.torch as dr
    from robot_conditioned_pose.mycpp_port import install
    mycpp_impl = install()
    from estimater import FoundationPose, PoseRefinePredictor, ScorePredictor
    from Utils import set_logging_format, set_seed
    from robot_conditioned_pose.omy_sequence import open_sequence
    set_logging_format()
    scorer, refiner, glctx = ScorePredictor(), PoseRefinePredictor(), dr.RasterizeCudaContext()
    records = {}
    for path in sequences:
        reader = open_sequence(path)
        mesh = reader.mesh
        rgb, depth = reader.observation(0)
        depth = depth.copy(); depth[depth < .001] = 0.
        frame_id = reader.frames[0]['frame_id']
        with Image.open(path/'masks'/(frame_id+'.png')) as m:
            mask = np.asarray(m) > 0
        if not mask.any(): raise RuntimeError('empty frame-0 mask: '+path.name)
        set_seed(0)
        estimator = FoundationPose(model_pts=mesh.vertices, model_normals=mesh.vertex_normals, mesh=mesh,
                                   scorer=scorer, refiner=refiner, glctx=glctx, debug=0,
                                   debug_dir=str(a.output/'debug'/path.name))
        pose = estimator.register(K=reader.K, rgb=rgb, depth=depth, ob_mask=mask, iteration=a.iterations)
        np.save(a.output/(path.name+'.npy'), np.asarray(pose, dtype=np.float64), allow_pickle=False)
        records[path.name] = dict(frame_id=frame_id, mask_pixels=int(mask.sum()))
        torch.cuda.empty_cache()
    weights = {d.name: hashlib.sha256((d/'model_best.pth').read_bytes()).hexdigest() for d in sorted((up/'weights').iterdir())}
    (a.output/'initialization.json').write_text(json.dumps(dict(initialization='external',
        method='upstream FoundationPose.register on frame 0',
        mask='dataset oracle visible object mask, frame 0 only (segmentation oracle; no pose GT)',
        register_iterations=a.iterations, seed=0, mycpp_cluster_poses=mycpp_impl, retries=0, weights_sha256=weights,
        note='One registration per sequence; shared by every method and seed. Frame-0 errors in registration_error.json were computed after all poses were saved and were not used for any choice.',
        sequences=[p.name for p in sequences], inputs=records), indent=2))
    # Reporting only, after all poses are fixed on disk.
    from robot_conditioned_pose.contracts import evaluation_surface, mesh_diameter
    from robot_conditioned_pose.geometry import pose_loss
    errors = {}
    for path in sequences:
        reader = open_sequence(path)
        pred = torch.as_tensor(np.load(a.output/(path.name+'.npy')), dtype=torch.float32)
        gt = reader.target(0)
        cad = torch.as_tensor(evaluation_surface(reader.mesh, 4096), dtype=torch.float32)[None]
        surface = pose_loss(pred[None], gt[None], cad, [reader.symmetries]).item()
        rel = torch.linalg.inv(gt) @ pred
        angle = float(np.degrees(np.arccos(np.clip((torch.trace(rel[:3, :3]).item()-1)/2, -1, 1))))
        d = mesh_diameter(reader.mesh)
        errors[path.name] = dict(surface_error_m=surface, translation_error_m=float(torch.linalg.norm(pred[:3, 3]-gt[:3, 3])),
                                 rotation_error_deg=angle, diameter_m=d, exceeds_10pct_diameter=surface > .1*d)
    (a.output/'registration_error.json').write_text(json.dumps(errors, indent=2))
    print(json.dumps(errors, indent=2))


if __name__ == '__main__': main()
