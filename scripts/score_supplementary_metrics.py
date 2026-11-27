#!/usr/bin/env python3
"""Supplementary metrics for finished rollouts: ADD-S, translation and rotation error.

SUPPLEMENTARY ONLY. The primary metric stays the corresponding-point surface
error in summary.json (marker roll matters for this task, so a symmetric
metric must not replace it). ADD-S here is the mean distance from each
predicted surface point to the nearest GT surface point (4096 evaluation
points, same sampling as the primary metric). Frame 0 excluded from aggregates.
"""
import argparse
import csv
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--root', type=Path, action='append', required=True, help='Directory searched for */poses.jsonl')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    import numpy as np
    import torch
    from scipy.spatial import cKDTree
    from robot_conditioned_pose.omy_sequence import open_sequence
    from robot_conditioned_pose.contracts import evaluation_surface, mesh_diameter
    a.output.mkdir(parents=True, exist_ok=False)
    cache, rows = {}, []
    runs = sorted(q.parent for r in a.root for q in r.rglob('poses.jsonl'))
    for run in runs:
        info = json.loads((run/'summary.json').read_text())
        name = info['sequence']
        if name not in cache:
            reader = open_sequence(a.dataset/name)
            pts = evaluation_surface(reader.mesh, info['evaluation_points']).astype(np.float64)
            cache[name] = (reader, pts, mesh_diameter(reader.mesh), [reader.target(i).double().numpy() for i in range(len(reader.frames))])
        reader, pts, diameter, targets = cache[name]
        poses = [np.asarray(json.loads(s)['T_camera_mesh'], dtype=np.float64) for s in (run/'poses.jsonl').read_text().splitlines()]
        adds, trans, rot = [], [], []
        for i in range(1, len(poses)):
            pred, gt = pts @ poses[i][:3, :3].T + poses[i][:3, 3], pts @ targets[i][:3, :3].T + targets[i][:3, 3]
            adds.append(cKDTree(gt).query(pred)[0].mean())
            trans.append(np.linalg.norm(poses[i][:3, 3]-targets[i][:3, 3]))
            r = targets[i][:3, :3].T @ poses[i][:3, :3]
            rot.append(np.degrees(np.arccos(np.clip((np.trace(r)-1)/2, -1, 1))))
        adds, trans, rot = map(np.asarray, (adds, trans, rot))
        rows.append(dict(run=str(run), sequence=name, method=info['method'], model_mode=info.get('model_mode'),
            checkpoint_sha256=info.get('checkpoint_sha256'), initialization=info['initialization'],
            robot_perturbation=(info.get('robot_perturbation') or {}).get('spec', 'none'),
            primary_mean_error_m=info['mean_error_m'], primary_final_error_m=info['final_error_m'],
            adds_mean_m=float(adds.mean()), adds_final_m=float(adds[-1]), adds_frac_10pct_diameter=float((adds > .1*diameter).mean()),
            translation_mean_m=float(trans.mean()), translation_final_m=float(trans[-1]),
            rotation_mean_deg=float(rot.mean()), rotation_final_deg=float(rot[-1]), diameter_m=diameter))
    with (a.output/'supplementary_per_run.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    (a.output/'README.txt').write_text(__doc__)
    print(a.output/'supplementary_per_run.csv', len(rows))


if __name__ == '__main__': main()
