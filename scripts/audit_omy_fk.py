#!/usr/bin/env python3
"""Audit measured-joint FK, surface points and velocities against simulator link GT.

Exercises the exact training/evaluation input path (OmySequence: exported
robot_observations + joint_inventory -> omy_kinematics FK -> canonical surface
points -> point_features) and compares it with the independent simulator link
transforms stored in frames.jsonl (T_world_robot_links). The simulator poses are
read only here, as a reference. Writes a new output directory; never modifies
the dataset or caches.
"""
import argparse
import csv
import json
import sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))


def rigid_error(pose):
    pose = np.asarray(pose, dtype=np.float64)
    if pose.shape != (4, 4) or not np.isfinite(pose).all():
        return float('inf')
    return float(max(np.abs(pose[3] - [0, 0, 0, 1]).max(), np.abs(pose[:3, :3].T @ pose[:3, :3] - np.eye(3)).max(),
                     abs(np.linalg.det(pose[:3, :3]) - 1)))


def audit_sequence(path, split, writers, worst):
    import torch
    from robot_conditioned_pose.omy_sequence import OmySequence
    from robot_conditioned_pose.contracts import mesh_diameter
    from robot_conditioned_pose.fk_audit import (link_errors, surface_points, interval_velocity, transform_points)
    seq = OmySequence(path)
    name = path.name
    gt = [json.loads(s) for s in (path / seq.manifest['frames_file']).read_text().splitlines()]
    n = len(seq.frames)
    hard, notes = [], []
    # 1. Alignment, timing, names, units, transforms.
    ids_obs, ids_gt = [f['frame_id'] for f in seq.frames], [f['frame_id'] for f in gt]
    if ids_obs != ids_gt: hard.append('frame_id mismatch between robot_observations and frames')
    if ids_obs != [f'{i:06d}' for i in range(n)]: hard.append('frame ids not contiguous from 000000')
    ts = np.array([f['timestamp_s'] for f in seq.frames])
    ts_gap = float(np.abs(ts - np.array([f['timestamp_s'] for f in gt])).max())
    if ts_gap > 1e-9: hard.append(f'timestamp mismatch {ts_gap}')
    dts = np.diff(np.concatenate(([seq.previous_state['timestamp_s']], ts)))
    if not np.allclose(dts, 1 / 30, atol=1e-6): hard.append(f'dt outside 1/30: min {dts.min()} max {dts.max()}')
    joints = {j['path'].rsplit('/', 1)[-1]: j for j in seq.inventory['joints']}
    movable = set(joints) - {'root_joint'}
    if set(seq.joint_names) != movable: hard.append(f'joint names differ from inventory: {sorted(set(seq.joint_names) ^ movable)}')
    q = np.array([f['joint_positions'] for f in seq.frames] + [seq.previous_state['joint_positions']])
    if q.shape[1] != len(seq.joint_names) or not np.isfinite(q).all(): hard.append('joint position shape/finite failure')
    limit_excess_rad = 0.
    for k, jn in enumerate(seq.joint_names):
        a = joints[jn]['attributes']
        lo, hi = np.deg2rad(float(a['physics:lowerLimit'])), np.deg2rad(float(a['physics:upperLimit']))
        limit_excess_rad = max(limit_excess_rad, float(np.maximum(lo - q[:, k], q[:, k] - hi).max()))
    if limit_excess_rad > 1e-3: hard.append(f'joint limit exceeded by {limit_excess_rad} rad (unit error?)')
    cam_gap = max(float(np.abs(np.asarray(a['T_world_camera']) - np.asarray(b['T_world_camera'])).max()) for a, b in zip(seq.frames, gt))
    base_gap = max(float(np.abs(np.asarray(a['T_world_robot_base']) - np.asarray(b['T_world_robot_base'])).max()) for a, b in zip(seq.frames, gt))
    if cam_gap > 1e-9 or base_gap > 1e-9: hard.append(f'camera/base differ between files: {cam_gap} {base_gap}')
    rigid = max(max(rigid_error(f['T_world_camera']), rigid_error(f['T_world_robot_base']),
                    *(rigid_error(t) for t in g['T_world_robot_links'].values())) for f, g in zip(seq.frames, gt))
    if rigid > 1e-5: hard.append(f'non-rigid transform in export ({rigid})')
    fk_names, gt_names = set(seq._world_links(0)), set(gt[0]['T_world_robot_links'])
    missing = sorted(set(seq.canonical) - gt_names)
    if missing: hard.append(f'links without GT reference: {missing}')
    if set(seq.canonical) - fk_names: hard.append('surface links missing from FK')
    # 2-4, 7. Per-frame comparisons.
    diameter = mesh_diameter(seq.mesh)
    cad_expected = seq.cad.double().numpy() / diameter
    per = dict(position_mm=[], rotation_deg=[], surface_mm=[], velocity_mps=[], norm_xyz_mm=[], norm_vel_mps=[],
               gt_speed_mps=[], shift=[])
    bias = {}
    counts = dict(frames=n, velocity_frames=0, velocity_skipped_frame0=1)
    for i in range(n):
        cam_inv = np.linalg.inv(np.asarray(seq.frames[i]['T_world_camera'], dtype=np.float64))
        fk = seq._world_links(i)
        gl = gt[i]['T_world_robot_links']
        errs = link_errors(fk, gl)
        for link, (tm, rd) in errs.items():
            writers['links'].writerow([name, split, i, link, f'{tm * 1000:.6f}', f'{rd:.6f}'])
            if link in seq.canonical:
                per['position_mm'].append(tm * 1000); per['rotation_deg'].append(rd)
                d = (cam_inv @ np.asarray(fk[link]))[:3, 3] - (cam_inv @ np.asarray(gl[link]))[:3, 3]
                bias.setdefault(link, []).append(d * 1000)
            worst_update(worst, 'position_mm', tm * 1000, name, i, link)
            worst_update(worst, 'rotation_deg', rd, name, i, link)
        positions, normals, prior, dt = seq._surface_pair(i)
        positions, prior = positions.double().numpy(), prior.double().numpy()
        gt_points = surface_points(gl, seq.canonical, cam_inv)
        surf = np.linalg.norm(positions - gt_points, axis=1) * 1000
        per['surface_mm'].append(surf)
        worst_update(worst, 'surface_mm', float(surf.max()), name, i, None)
        # Timing shift diagnosis: FK(i) against GT(i-1), GT(i), GT(i+1).
        if 0 < i < n - 1:
            per['shift'].append([float(np.linalg.norm(positions - surface_points(gt[i + s]['T_world_robot_links'], seq.canonical, cam_inv), axis=1).mean() * 1000) for s in (-1, 0, 1)])
        # Normalized model input with the GT object pose as a representative hypothesis.
        hypothesis = seq.target(i)
        feats = seq.points(i, hypothesis, diameter).double().numpy()
        inv_h = np.linalg.inv(hypothesis.double().numpy())
        robot_rows = feats[:, 9] == 1
        exp_xyz = transform_points(inv_h, gt_points) / diameter
        norm_xyz = np.abs(feats[robot_rows, :3] - exp_xyz).max() * diameter * 1000
        cad_rows = feats[~robot_rows]
        if (~robot_rows).sum() != len(cad_expected) or np.abs(cad_rows[:, :3] - cad_expected).max() > 1e-5 or np.abs(cad_rows[:, 6:]).max() != 0:
            hard.append(f'CAD rows of point_features differ from CAD samples at frame {i}')
        per['norm_xyz_mm'].append(norm_xyz)
        vel_err = norm_vel = speed = None
        if i > 0:
            gt_vel = interval_velocity(gl, gt[i - 1]['T_world_robot_links'], seq.canonical, cam_inv, ts[i] - ts[i - 1])
            fk_vel = (positions - prior) / dt
            vel_err = np.linalg.norm(fk_vel - gt_vel, axis=1)
            speed = np.linalg.norm(gt_vel, axis=1)
            exp_vel = gt_vel @ inv_h[:3, :3].T / diameter
            norm_vel = float(np.abs(feats[robot_rows, 6:9] - exp_vel).max() * diameter)
            per['velocity_mps'].append(vel_err); per['gt_speed_mps'].append(speed); per['norm_vel_mps'].append(norm_vel)
            counts['velocity_frames'] += 1
            worst_update(worst, 'velocity_mps', float(vel_err.max()), name, i, None)
            if not np.allclose(feats[robot_rows, 10], 1): hard.append(f'velocity_valid not set at frame {i}')
        writers['frames'].writerow([name, split, i, f'{ts[i]:.6f}', f'{surf.mean():.6f}', f'{np.percentile(surf, 95):.6f}', f'{surf.max():.6f}',
            *(['', '', ''] if vel_err is None else [f'{vel_err.mean():.8f}', f'{np.percentile(vel_err, 95):.8f}', f'{vel_err.max():.8f}']),
            '' if speed is None else f'{speed.max():.6f}', f'{norm_xyz:.6f}', '' if norm_vel is None else f'{norm_vel:.8f}'])
    shift = np.array(per['shift'])
    record = dict(sequence=name, split=split, frames=n, diameter_m=diameter, hard_failures=sorted(set(hard)),
        checks=dict(timestamp_gap_s=ts_gap, dt_min=float(dts.min()), dt_max=float(dts.max()), joint_limit_excess_rad=limit_excess_rad,
                    camera_gap=cam_gap, base_gap=base_gap, rigid_error=rigid, links_compared=sorted(seq.canonical),
                    fk_links_without_surface=sorted(fk_names - set(seq.canonical))),
        counts=counts, shift_mean_surface_mm={'gt_prev': float(shift[:, 0].mean()), 'gt_same': float(shift[:, 1].mean()), 'gt_next': float(shift[:, 2].mean())},
        bias_mean_camera_mm={k: np.mean(v, 0).round(6).tolist() for k, v in bias.items()})
    return record, per


def worst_update(worst, key, value, seq, frame, link):
    if key not in worst or value > worst[key]['value']:
        worst[key] = dict(value=value, sequence=seq, frame=frame, link=link)


def overlay(path, frame, out_png, title):
    """Left: X-ray (all robot surface points). Right: depth-visible points only. FK green, GT magenta."""
    from PIL import Image, ImageDraw
    from robot_conditioned_pose.omy_sequence import OmySequence
    from omy_robot_surface import canonical_surface_points
    seq = OmySequence(path)
    gt = json.loads((path / seq.manifest['frames_file']).read_text().splitlines()[frame])
    geometry = {v['name']: path / v['path'] for v in seq.manifest['robot_geometry']['links']}
    dense = canonical_surface_points(geometry, points_per_link=600, seed=1)
    cam_inv = np.linalg.inv(np.asarray(seq.frames[frame]['T_world_camera'], dtype=np.float64))
    from robot_conditioned_pose.fk_audit import surface_points
    fk_pts = surface_points(seq._world_links(frame), dense, cam_inv)
    gt_pts = surface_points(gt['T_world_robot_links'], dense, cam_inv)
    rgb, depth = seq.observation(frame)
    K = seq.K
    panels = []
    for visible_only in (False, True):
        img = Image.fromarray(rgb).convert('RGB'); draw = ImageDraw.Draw(img)
        for pts, color, r, hollow in ((gt_pts, (255, 0, 255), 3, True), (fk_pts, (0, 255, 0), 1, False)):
            uvw = pts @ K.T
            u, v = uvw[:, 0] / uvw[:, 2], uvw[:, 1] / uvw[:, 2]
            for x, y, z in zip(u, v, pts[:, 2]):
                xi, yi = int(round(x)), int(round(y))
                if not (0 <= xi < depth.shape[1] and 0 <= yi < depth.shape[0]) or z <= 0: continue
                if visible_only and not (depth[yi, xi] > 0 and z <= depth[yi, xi] + .01): continue
                draw.ellipse((x - r, y - r, x + r, y + r), outline=color if hollow else None, fill=None if hollow else color)
        draw.rectangle((0, 0, 639, 18), fill=(0, 0, 0))
        draw.text((4, 3), f"{title} | {'depth-visible only' if visible_only else 'X-ray (all points)'} | FK green dots, sim GT magenta rings", fill=(255, 255, 255))
        panels.append(img)
    canvas = Image.new('RGB', (1280, 480)); canvas.paste(panels[0], (0, 0)); canvas.paste(panels[1], (640, 0))
    canvas.save(out_png)


def cache_consistency(cache, dataset, stride):
    """Recompute stored cache point features with the audited path."""
    import torch
    from robot_conditioned_pose.omy_sequence import OmySequence
    manifest = json.loads((cache / 'manifest.json').read_text())
    by_seq = {}
    for k in range(0, len(manifest['samples']), stride):
        by_seq.setdefault(manifest['sample_records'][k]['sequence'], []).append(k)
    worst_points = worst_target = 0.
    checked = 0
    for name, ks in by_seq.items():
        seq = OmySequence(dataset / name)
        for k in ks:
            s = torch.load(cache / manifest['samples'][k], weights_only=True)
            i = manifest['sample_records'][k]['frame_index']
            recomputed = seq.points(i, s['hypothesis'], float(s['diameter']))
            worst_points = max(worst_points, float((recomputed - s['points']).abs().max()))
            worst_target = max(worst_target, float((seq.target(i) - s['target']).abs().max()))
            checked += 1
    return dict(cache=str(cache), samples_checked=checked, samples_total=len(manifest['samples']), stride=stride,
                max_abs_point_feature_diff=worst_points, max_abs_target_diff=worst_target)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--sequences', nargs='*', help='Default: every sequence in the pinned pilot manifest')
    p.add_argument('--cache', type=Path, action='append', default=[], help='Prepared cache to cross-check')
    p.add_argument('--cache-stride', type=int, default=10)
    a = p.parse_args()
    from robot_conditioned_pose.fk_audit import THRESHOLDS, investigation_flags, stats
    from robot_conditioned_pose.provenance import source_snapshot
    snapshot = json.loads((ROOT / 'configs/omy_pilot_manifest_20261124.json').read_text())['sequences']
    names = a.sequences or sorted(snapshot)
    a.output.mkdir(parents=True, exist_ok=False); (a.output / 'overlays').mkdir()
    files = {k: (a.output / f).open('w', newline='') for k, f in (('frames', 'per_frame.csv'), ('links', 'per_link.csv'))}
    writers = {k: csv.writer(f) for k, f in files.items()}
    writers['frames'].writerow(['sequence', 'split', 'frame', 'timestamp_s', 'surface_mean_mm', 'surface_p95_mm', 'surface_max_mm',
                                'velocity_err_mean_mps', 'velocity_err_p95_mps', 'velocity_err_max_mps', 'gt_speed_max_mps',
                                'normalized_xyz_max_err_mm', 'normalized_velocity_max_err_mps'])
    writers['links'].writerow(['sequence', 'split', 'frame', 'link', 'position_err_mm', 'rotation_err_deg'])
    worst, records, pooled = {}, [], {}
    for name in names:
        record, per = audit_sequence(a.dataset / snapshot[name]['path'], snapshot[name]['split'], writers, worst)
        records.append(record)
        for key, values in per.items():
            if key != 'shift':
                pooled.setdefault(key, []).append(np.concatenate([np.atleast_1d(v) for v in values]) if values else np.zeros(0))
        print(f"{name}: hard={len(record['hard_failures'])} shift={record['shift_mean_surface_mm']}", flush=True)
    for f in files.values(): f.close()
    pooled = {k: np.concatenate(v) for k, v in pooled.items()}
    flags = investigation_flags(pooled['position_mm'], pooled['rotation_deg'], pooled['surface_mm'], pooled['velocity_mps'])
    hard = {r['sequence']: r['hard_failures'] for r in records if r['hard_failures']}
    caches = [cache_consistency(c, a.dataset, a.cache_stride) for c in a.cache]
    verdict = 'FAIL' if hard else ('INVESTIGATE' if flags else 'PASS')
    summary = dict(verdict=verdict, reference='simulator T_world_robot_links in frames.jsonl (independent of measured-joint FK)',
        audited_path='robot_observations.jsonl + previous_robot_state.json + robot/joint_inventory.json -> omy_kinematics.forward_kinematics -> OmySequence._surface_pair -> point_features',
        thresholds=THRESHOLDS, investigation_flags=flags, hard_failures=hard, sequences=len(records),
        stats={k: stats(v) for k, v in pooled.items()}, worst=worst, caches=caches,
        not_available=['simulator link linear/angular velocities are not exported; velocity compared via GT pose interval differences only',
                       'previous_robot_state.json has no simulator link poses; frame 0 velocity has no independent reference (excluded, counted)'],
        per_sequence=records, **source_snapshot())
    (a.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    # 8. Overlays: one representative middle frame per validation sequence + global worst cases.
    shots = [(n, json.loads((a.dataset / snapshot[n]['path'] / 'manifest.json').read_text())['frame_count'] // 2, 'representative middle frame')
             for n in names if snapshot[n]['split'] == 'validation']
    for key in ('surface_mm', 'velocity_mps', 'rotation_deg'):
        if key in worst: shots.append((worst[key]['sequence'], worst[key]['frame'], f'worst {key}'))
    for n, frame, why in shots:
        overlay(a.dataset / snapshot[n]['path'], frame, a.output / 'overlays' / f"{n}_{frame:06d}_{why.split()[0]}.png", f'{n} f{frame} ({why})')
    print(json.dumps({k: summary[k] for k in ('verdict', 'investigation_flags', 'hard_failures', 'worst', 'caches')}, indent=2))


if __name__ == '__main__':
    main()
