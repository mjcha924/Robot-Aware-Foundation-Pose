#!/usr/bin/env python3
"""Comparable sequence rollouts; first-frame pose is supplied and never refined."""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
METHODS = ('hold', 'kinematic', 'visual', 'kinematic-refine', 'learned')


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rollout(reader, initial_pose, method, refine=None, effector_link='link6'):
    """Inference only. No target(), phase, contact, or object truth access."""
    import torch
    from robot_conditioned_pose.motion_prior import propagate_pose, validate_pose
    if method not in METHODS:
        raise ValueError('unknown method')
    if method in ('visual', 'kinematic-refine', 'learned') and refine is None:
        raise ValueError('visual methods require a refiner')
    use_motion = method in ('kinematic', 'kinematic-refine')
    if use_motion and not hasattr(reader, 'effector_pose'):
        raise ValueError('kinematic baseline requires measured-state OMY data')
    pose = initial_pose.clone()
    validate_pose(pose)
    with torch.no_grad():
        for i, frame in enumerate(reader.frames):
            if pose.is_cuda: torch.cuda.synchronize()
            start = time.perf_counter()
            if i:
                previous_camera = pose.new_tensor(reader.frames[i-1]['T_world_camera'])
                current_camera = pose.new_tensor(frame['T_world_camera'])
                previous_effector = reader.effector_pose(i-1, effector_link).to(pose) if use_motion else None
                current_effector = reader.effector_pose(i, effector_link).to(pose) if use_motion else None
                pose = propagate_pose(pose, previous_camera, current_camera, previous_effector, current_effector)
                if refine is not None:
                    pose = refine(i, pose)
                validate_pose(pose)
            if pose.is_cuda: torch.cuda.synchronize()
            seconds = time.perf_counter()-start
            yield dict(frame_id=frame['frame_id'], frame_index=i, initialized=(i == 0),
                       T_camera_mesh=pose.cpu().tolist(), tracking_seconds=seconds if i else 0.)


def score_predictions(reader, rows, diameter, count=4096):
    """GT is accessed only after the complete prediction pass has finished."""
    import numpy as np
    import torch
    from robot_conditioned_pose.contracts import evaluation_surface
    from robot_conditioned_pose.geometry import pose_loss
    cad = torch.as_tensor(evaluation_surface(reader.mesh, count), dtype=torch.float32)[None]
    records = []
    for i, row in enumerate(rows):
        pose = torch.tensor(row['T_camera_mesh'], dtype=torch.float32)[None]
        error = pose_loss(pose, reader.target(i)[None], cad, [reader.symmetries]).item()
        records.append(dict(frame_id=row['frame_id'], frame_index=i, initialized=(i == 0),
                            symmetry_surface_error_m=error, exceeds_10pct_diameter=bool(error > .1*diameter)))
    errors = np.asarray([r['symmetry_surface_error_m'] for r in records[1:]])
    times = np.asarray([r['tracking_seconds'] for r in rows[1:]])
    if len(errors) == 0:
        raise ValueError('tracking evaluation needs at least two frames')
    return records, dict(tracked_frames=len(errors), initial_error_m=records[0]['symmetry_surface_error_m'],
        mean_error_m=float(errors.mean()), median_error_m=float(np.median(errors)),
        p95_error_m=float(np.percentile(errors, 95)), final_error_m=float(errors[-1]),
        failure_fraction_10pct_diameter=float((errors > .1*diameter).mean()),
        mean_tracking_seconds=float(times.mean()),
        timing_note='Includes frame I/O and inference; excludes setup, scoring and output writes. Not a GPU-only latency benchmark.',
        metric_note='Mean corresponding surface distance minimized over declared mesh symmetries; not ADD-S or BOP AR.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('sequence', type=Path)
    p.add_argument('--initial-pose', type=Path, required=True, help='Frame 0: 4x4 .npy T_camera_raw_mesh')
    p.add_argument('--initialization', choices=['external', 'oracle-first-frame'], required=True)
    p.add_argument('--method', choices=METHODS, help='Default: learned with checkpoint, otherwise visual')
    p.add_argument('--effector-link', default='link6', help='Rigid wrist/tool carrier, NOT a moving finger')
    p.add_argument('--checkpoint', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--iterations', type=int, default=2)
    p.add_argument('--evaluation-points', type=int, default=4096)
    a = p.parse_args()
    method = a.method or ('learned' if a.checkpoint else 'visual')
    if (method == 'learned') != bool(a.checkpoint):
        p.error('only --method learned accepts/requires --checkpoint')
    if a.iterations < 1 or a.evaluation_points < 1:
        p.error('iterations and evaluation-points must be positive')
    from validate_isaac_export import validate_sequence
    errors = validate_sequence(a.sequence)
    if errors: raise ValueError(errors)
    import numpy as np
    import torch
    from robot_conditioned_pose.omy_sequence import open_sequence
    from robot_conditioned_pose.contracts import mesh_diameter, geometry_record, check_checkpoint, semantic_config
    from robot_conditioned_pose.motion_prior import validate_pose
    np.random.seed(0); torch.manual_seed(0)
    reader = open_sequence(a.sequence)
    if len(reader.frames) < 2: raise ValueError('need at least two frames')
    diameter = mesh_diameter(reader.mesh)
    initial = torch.as_tensor(np.load(a.initial_pose, allow_pickle=False), dtype=torch.float32)
    validate_pose(initial)
    refine, cfg, model_mode = None, None, None
    visual = method in ('visual', 'kinematic-refine', 'learned')
    if visual:
        from robot_conditioned_pose.upstream import load_upstream, RenderBridge
        from robot_conditioned_pose.model import RobotConditionedRefiner
        predictor, cfg = load_upstream(ROOT / 'third_party/FoundationPose')
        model = RobotConditionedRefiner(predictor.model, mode='visual').cuda().eval()
        if a.checkpoint:
            saved = torch.load(a.checkpoint, map_location='cuda', weights_only=True)
            check_checkpoint(saved, cfg)
            missing, unexpected = model.load_state_dict(saved['model'], strict=False)
            if unexpected or any(not k.startswith(('upstream.encodeA.', 'upstream.encodeAB.', 'upstream.pos_embed.')) for k in missing):
                raise ValueError((missing, unexpected))
            model.mode = saved['mode']
        model_mode = model.mode
        bridge = RenderBridge(predictor, reader.mesh)
        initial = initial.cuda()
        def refine(i, pose):
            rgb, depth = reader.observation(i)
            # Visual controls do not need robot meshes/FK during refinement.
            def points(h):
                return (h.new_zeros((1, 1, 11)) if model.mode == 'visual' else
                        reader.points(i, h[0], diameter)[None])
            return bridge.refine(model, rgb, depth, reader.K, pose[None], points, cfg, a.iterations)[0]
    if method in ('kinematic', 'kinematic-refine'):
        reader.effector_pose(0, a.effector_link)  # fail early on wrong link
    a.output.mkdir(parents=True, exist_ok=False)
    input_files = [a.sequence/'manifest.json', a.sequence/reader.manifest['frames_file']]
    ext = reader.manifest.get('omy_tracking', {})
    input_files += [a.sequence/ext[k] for k in ('robot_observations_file', 'previous_robot_state_file', 'joint_inventory') if k in ext]
    metadata = dict(protocol_version=2, method=method, model_mode=model_mode, sequence=a.sequence.name,
        initialization=a.initialization, initial_pose_sha256=file_hash(a.initial_pose),
        effector_link=a.effector_link if 'kinematic' in method else None,
        iterations=a.iterations if visual else 0, evaluation_points=a.evaluation_points, evaluation_seed=2026,
        checkpoint_sha256=file_hash(a.checkpoint) if a.checkpoint else None,
        pretrained_sha256=file_hash(cfg['ckpt_dir']) if cfg else None,
        config=semantic_config(cfg) if cfg else None,
        source_commit=subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
        inputs={str(f.relative_to(a.sequence)): file_hash(f) for f in input_files},
        split=ext.get('split', 'legacy'), parent_group=ext.get('parent_group'),
        first_frame_policy='supplied pose unchanged; frame 0 excluded from tracking aggregates',
        **geometry_record(reader.mesh, diameter))
    (a.output/'run.json').write_text(json.dumps(metadata, indent=2))
    rows = []
    with (a.output/'poses.jsonl').open('w') as stream:
        for row in rollout(reader, initial, method, refine, a.effector_link):
            rows.append(row); stream.write(json.dumps(row)+'\n'); stream.flush()
    scores, metrics = score_predictions(reader, rows, diameter, a.evaluation_points)
    (a.output/'frame_metrics.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in scores))
    (a.output/'summary.json').write_text(json.dumps(dict(**metadata, **metrics), indent=2))
    print(json.dumps(dict(output=str(a.output), **metrics), indent=2))


if __name__ == '__main__':
    main()
