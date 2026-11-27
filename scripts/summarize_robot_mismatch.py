#!/usr/bin/env python3
"""Tables for the robot-state mismatch control (plan: outputs/omy_validation_5080_005/plan.json).

gap_removed = (perturbed - geometry_none) / (cad_only_004 - geometry_none) on a
group mean, per seed. 1.0 means the corruption brings geometry down to the
seed-matched cad-only error; 0 means no effect. Negative means it got better.
"""
import argparse
import csv
import json
from pathlib import Path
import numpy as np

EASY = ('asymmetric_A_04', 'asymmetric_B_04', 'asymmetric_C_04', 'box_A_04', 'box_B_04', 'box_C_04', 'cylinder_B_04')
GROUPS = {'all9': None, 'easy7': EASY, 'cylinder_A_04': ('cylinder_A_04',), 'cylinder_C_04': ('cylinder_C_04',)}


def load(root):
    return {d.name: json.loads((d/'summary.json').read_text()) for d in sorted(root.iterdir()) if (d/'summary.json').is_file()}


def group(runs, names, key='mean_error_m'):
    sel = [r[key] for n, r in runs.items() if names is None or n in names]
    if names is None and len(sel) != 9: raise ValueError('incomplete run set')
    return float(np.mean(sel))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mismatch', type=Path, required=True)
    p.add_argument('--reference-evaluation', type=Path, required=True, help='004 evaluation dir (seed-*/geometry, seed-*/cad-only)')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seeds', nargs='+', default=['42', '43', '44'])
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    rows, table = [], []
    specs = None
    for seed in a.seeds:
        base = a.mismatch/f'geometry-s{seed}'
        specs = specs or [d.name for d in sorted(base.iterdir())]
        ref_geo = load(a.reference_evaluation/f'seed-{seed}'/'geometry')
        ref_cad = load(a.reference_evaluation/f'seed-{seed}'/'cad-only')
        none = load(base/'none')
        # The matched rerun must reproduce 004 geometry under the new code.
        rerun_diff = max(abs(none[n]['mean_error_m']-ref_geo[n]['mean_error_m']) for n in ref_geo)
        sha = {r['checkpoint_sha256'] for r in ref_geo.values()} | {r['checkpoint_sha256'] for r in none.values()}
        if len(sha) != 1: raise ValueError('checkpoint mismatch for seed '+seed)
        for spec in ['none']+[s for s in specs if s != 'none']:
            runs = load(base/spec)
            for n, r in runs.items():
                rows.append(dict(seed=int(seed), perturbation=spec, sequence=n, mean_error_m=r['mean_error_m'],
                                 final_error_m=r['final_error_m'], failure_fraction_10pct_diameter=r['failure_fraction_10pct_diameter'],
                                 source_commit=r['source_commit'], donor=(r.get('robot_perturbation') or {}).get('donor_sequence')))
            entry = dict(seed=int(seed), perturbation=spec, rerun_max_abs_diff_vs_004_m=rerun_diff)
            for g, names in GROUPS.items():
                v, g0, c0 = group(runs, names), group(none, names), group(ref_cad, names)
                entry[g+'_mm'] = v*1000
                entry[g+'_final_mm'] = group(runs, names, 'final_error_m')*1000
                entry[g+'_cad_only_mm'] = c0*1000
                entry[g+'_gap_removed'] = (v-g0)/(c0-g0) if abs(c0-g0) > 1e-9 else float('nan')
            entry['lost_final_gt_50mm'] = sum(r['final_error_m'] > .05 for r in runs.values())
            table.append(entry)
    with (a.output/'mismatch_per_sequence.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    (a.output/'mismatch_groups.json').write_text(json.dumps(table, indent=2))
    commits = sorted({r['source_commit'] for r in rows})
    L = ['# Robot-state mismatch control (geometry checkpoints from 004, inference-only corruption)', '',
         f'Rollout commit(s): {", ".join(commits)}. Oracle-first-frame, 9 validation sequences, frame 0 excluded. mm.', '',
         'gap removed = (perturbed − geometry none) / (cad-only − geometry none), seed-matched; 1 = as bad as cad-only.', '',
         '| seed | perturbation | all9 | easy7 | cyl_A_04 | cyl_A gap removed | cyl_C_04 | cyl_C final | lost |', '|---|---|---|---|---|---|---|---|---|']
    for e in table:
        L.append(f"| {e['seed']} | {e['perturbation']} | {e['all9_mm']:.2f} | {e['easy7_mm']:.2f} | {e['cylinder_A_04_mm']:.2f} | "
                 f"{e['cylinder_A_04_gap_removed']:+.2f} | {e['cylinder_C_04_mm']:.2f} | {e['cylinder_C_04_final_mm']:.2f} | {e['lost_final_gt_50mm']}/9 |")
    L += ['', 'Seed-matched cad-only (004): ' + ', '.join(
        f"s{e['seed']} cyl_A {e['cylinder_A_04_cad_only_mm']:.2f} / all9 {e['all9_cad_only_mm']:.2f}" for e in table if e['perturbation'] == 'none'), '',
        'Matched rerun vs 004 geometry (max |Δ mean| over sequences, m): ' + ', '.join(
        f"s{e['seed']} {e['rerun_max_abs_diff_vs_004_m']:.2e}" for e in table if e['perturbation'] == 'none'), '']
    L += ['## Seed mean [min–max]', '', '| perturbation | all9 | easy7 | cyl_A_04 | cyl_A gap removed | cyl_C_04 | lost runs |', '|---|---|---|---|---|---|---|']
    for spec in ['none']+[s for s in specs if s != 'none']:
        es = [e for e in table if e['perturbation'] == spec]
        f = lambda k, d=2: f"{np.mean([e[k] for e in es]):.{d}f} [{min(e[k] for e in es):.{d}f}–{max(e[k] for e in es):.{d}f}]"
        L.append(f"| {spec} | {f('all9_mm')} | {f('easy7_mm')} | {f('cylinder_A_04_mm')} | {f('cylinder_A_04_gap_removed')} | {f('cylinder_C_04_mm')} | {sum(e['lost_final_gt_50mm'] for e in es)}/{9*len(es)} |")
    (a.output/'mismatch_tables.md').write_text('\n'.join(L)+'\n')
    print('\n'.join(L))


if __name__ == '__main__': main()
