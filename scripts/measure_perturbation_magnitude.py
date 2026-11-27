#!/usr/bin/env python3
"""How far each robot perturbation moves the refiner's robot surface points (camera frame).

Reports, per sequence and perturbation, the mean over frames of the mean
point distance between perturbed and measured robot surface points, and the
same for the robot surface points nearest the object (closest 64 of 512 to
the GT object centre, chosen per frame; GT used for this diagnostic only).
"""
import argparse, csv, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--donors', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--perturbations', nargs='+', default=['delay-3', 'delay-15', 'freeze-first', 'swap-sequence', 'joint-noise-0.002', 'joint-noise-0.02'])
    a = p.parse_args()
    import numpy as np
    from robot_conditioned_pose.omy_sequence import open_sequence
    from robot_conditioned_pose.robot_perturbation import RobotPerturbation
    donors = json.loads(a.donors.read_text()); rows = []
    for name in sorted(donors):
        clean = open_sequence(a.dataset/name)
        ref = [clean._surface_pair(i)[0].numpy() for i in range(len(clean.frames))]
        centre = [clean.target(i).numpy()[:3, 3] for i in range(len(clean.frames))]
        near = [np.argsort(np.linalg.norm(r-c, axis=1))[:64] for r, c in zip(ref, centre)]
        dist_obj = float(np.mean([np.linalg.norm(r[n]-c, axis=1).mean() for r, n, c in zip(ref, near, centre)]))
        for spec in a.perturbations:
            reader = open_sequence(a.dataset/name)
            reader.set_robot_perturbation(RobotPerturbation(spec, name, reader.joint_names,
                                          a.dataset/donors[name] if spec == 'swap-sequence' else None))
            d_all, d_near = [], []
            for i in range(len(reader.frames)):
                q = reader._surface_pair(i)[0].numpy(); e = np.linalg.norm(q-ref[i], axis=1)
                d_all.append(e.mean()); d_near.append(e[near[i]].mean())
            rows.append(dict(sequence=name, perturbation=spec, donor=donors[name] if spec == 'swap-sequence' else '',
                             mean_shift_all_mm=1000*float(np.mean(d_all)), mean_shift_near_object_mm=1000*float(np.mean(d_near)),
                             max_shift_near_object_mm=1000*float(np.max(d_near)), near_points_to_object_centre_mm=1000*dist_obj))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    for r in rows: print({k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == '__main__': main()
