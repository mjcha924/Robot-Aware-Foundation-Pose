#!/usr/bin/env python3
"""Tables for the temporal visual / cad-only / geometry 3-seed comparison.

Reads finished training runs and matched rollouts only. Paired differences are
computed per seed and per sequence: A - B < 0 means A has the smaller error.
"""
import argparse
import csv
import json
from pathlib import Path
import numpy as np

EASY = ('asymmetric_A_04', 'asymmetric_B_04', 'asymmetric_C_04', 'box_A_04', 'box_B_04', 'box_C_04', 'cylinder_B_04')
GROUPS = {'all9': None, 'easy7': EASY, 'cylinder_A_04': ('cylinder_A_04',), 'cylinder_C_04': ('cylinder_C_04',)}
PAIRS = (('geometry', 'cad-only'), ('cad-only', 'visual-ft'), ('geometry', 'visual-ft'), ('cad-only', 'kinematic-refine'),
         ('geometry', 'kinematic-refine'))
METRICS = ('mean_error_m', 'median_error_m', 'p95_error_m', 'final_error_m', 'failure_fraction_10pct_diameter', 'mean_tracking_seconds')


def fmt(values, scale=1., digits=2):
    v = np.asarray(values, dtype=float) * scale
    return f'{v.mean():.{digits}f}' if len(v) == 1 else f'{v.mean():.{digits}f} [{v.min():.{digits}f}–{v.max():.{digits}f}]'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--training', type=Path, required=True)
    p.add_argument('--evaluation', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True, help='pretrained_reference_motion.json')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seeds', nargs='+', default=['42', '43', '44'])
    p.add_argument('--modes', nargs='+', default=['visual', 'cad-only', 'geometry'])
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    label_of = {'visual': 'visual-ft', 'cad-only': 'cad-only', 'geometry': 'geometry'}
    # Training table.
    ref = json.loads(a.reference.read_text())
    ref_val = next(v for k, v in ref.items() if 'validation' in k)
    training = []
    for mode in a.modes:
        for seed in a.seeds:
            run = a.training / f'temporal-{mode}-s{seed}'
            m = [json.loads(s) for s in (run / 'metrics.jsonl').read_text().splitlines()]
            best = min(m, key=lambda r: r['val_surface_error_m'])
            info = json.loads((run / 'run.json').read_text())
            training.append(dict(mode=mode, seed=int(seed), epochs=len(m), pretrained_val_mm=ref_val['pretrained_surface_error_m'] * 1000,
                input_val_mm=ref_val['hypothesis_surface_error_m'] * 1000, epoch0_val_mm=m[0]['val_surface_error_m'] * 1000,
                best_val_mm=best['val_surface_error_m'] * 1000, best_epoch=best['epoch'], last_val_mm=m[-1]['val_surface_error_m'] * 1000,
                last_train_mm=m[-1]['train_surface_error_m'] * 1000, seconds=sum(r['seconds'] for r in m),
                peak_cuda_mib=max(r['peak_cuda_bytes'] for r in m) / 2 ** 20, source_commit=info.get('source_commit'),
                source_dirty=info.get('source_dirty_diff_sha256')))
    # Tracking tables.
    rows, per_seq = [], {}
    for seed in a.seeds:
        root = a.evaluation / f'seed-{seed}'
        for label in sorted(d.name for d in root.iterdir() if d.is_dir()):
            for seq_dir in sorted((root / label).iterdir()):
                s = json.loads((seq_dir / 'summary.json').read_text())
                per_seq[(seed, label, seq_dir.name)] = s
                rows.append(dict(seed=int(seed), method=label, sequence=seq_dir.name, source_commit=s['source_commit'],
                                 lost_final_gt_50mm=s['final_error_m'] > .05, **{k: s[k] for k in METRICS}))
    with (a.output / 'tracking_per_sequence.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    methods = list(dict.fromkeys(r['method'] for r in rows))
    commits = sorted({r['source_commit'] for r in rows})
    groups = {}
    for seed in a.seeds:
        for mth in methods:
            for g, names in GROUPS.items():
                sel = [r for r in rows if r['seed'] == int(seed) and r['method'] == mth and (names is None or r['sequence'] in names)]
                groups[(seed, mth, g)] = dict(sequences=len(sel), lost=sum(r['lost_final_gt_50mm'] for r in sel),
                                              **{k: float(np.mean([r[k] for r in sel])) for k in METRICS})
    paired = []
    for seed in a.seeds:
        for x, y in PAIRS:
            if x not in methods or y not in methods: continue
            for r in rows:
                if r['seed'] == int(seed) and r['method'] == x:
                    other = per_seq[(seed, y, r['sequence'])]
                    paired.append(dict(seed=int(seed), pair=f'{x} - {y}', sequence=r['sequence'],
                                       mean_diff_mm=(r['mean_error_m'] - other['mean_error_m']) * 1000,
                                       final_diff_mm=(r['final_error_m'] - other['final_error_m']) * 1000,
                                       failure_frac_diff_pct=(r['failure_fraction_10pct_diameter'] - other['failure_fraction_10pct_diameter']) * 100))
            for g in GROUPS:
                paired.append(dict(seed=int(seed), pair=f'{x} - {y}', sequence=f'[{g}]',
                                   mean_diff_mm=(groups[(seed, x, g)]['mean_error_m'] - groups[(seed, y, g)]['mean_error_m']) * 1000,
                                   final_diff_mm=(groups[(seed, x, g)]['final_error_m'] - groups[(seed, y, g)]['final_error_m']) * 1000,
                                   failure_frac_diff_pct=(groups[(seed, x, g)]['failure_fraction_10pct_diameter'] - groups[(seed, y, g)]['failure_fraction_10pct_diameter']) * 100))
    with (a.output / 'paired_differences.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, list(paired[0])); w.writeheader(); w.writerows(paired)
    # Markdown.
    L = ['# Temporal visual / cad-only / geometry — matched 3-seed tables', '',
         f'Rollout source commit(s): {", ".join(commits)}. Oracle-first-frame initialization, frame 0 excluded, 9 validation sequences.', '',
         '## Training (one-step validation, temporal cache)', '',
         f"Before training: input hypothesis {training[0]['input_val_mm']:.2f} mm, pretrained one step {training[0]['pretrained_val_mm']:.2f} mm.", '',
         '| mode | seed | epoch-0 val | best val (epoch) | last val | last train | time (s) | peak CUDA (MiB) |', '|---|---|---|---|---|---|---|---|']
    for t in training:
        L.append(f"| {t['mode']} | {t['seed']} | {t['epoch0_val_mm']:.2f} | {t['best_val_mm']:.2f} ({t['best_epoch']}) | {t['last_val_mm']:.2f} | {t['last_train_mm']:.2f} | {t['seconds']:.0f} | {t['peak_cuda_mib']:.0f} |")
    L += ['', '## Tracking per seed (mm unless noted)', '',
          '| seed | method | macro mean | median | p95 | final | >0.1 diam frames (%) | lost (final>50mm) | easy7 | cylinder_A_04 | cylinder_C_04 | ms/frame |',
          '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for seed in a.seeds:
        for mth in methods:
            g = groups[(seed, mth, 'all9')]
            L.append(f"| {seed} | {mth} | {g['mean_error_m']*1000:.2f} | {g['median_error_m']*1000:.2f} | {g['p95_error_m']*1000:.2f} | {g['final_error_m']*1000:.2f} | "
                     f"{g['failure_fraction_10pct_diameter']*100:.2f} | {g['lost']}/9 | {groups[(seed, mth, 'easy7')]['mean_error_m']*1000:.2f} | "
                     f"{groups[(seed, mth, 'cylinder_A_04')]['mean_error_m']*1000:.2f} | {groups[(seed, mth, 'cylinder_C_04')]['mean_error_m']*1000:.2f} | "
                     f"{g['mean_tracking_seconds']*1000:.1f} |")
    L += ['', '## Seed mean [min–max]', '', 'Baselines are deterministic reruns per seed and are not independent repeats.', '',
          '| method | macro mean | p95 | final | >0.1 diam (%) | easy7 | cylinder_A_04 | cylinder_C_04 | cylinder_C_04 final | lost runs |', '|---|---|---|---|---|---|---|---|---|---|']
    for mth in methods:
        v = lambda g, k: [groups[(s, mth, g)][k] for s in a.seeds]
        L.append(f"| {mth} | {fmt(v('all9','mean_error_m'),1000)} | {fmt(v('all9','p95_error_m'),1000)} | {fmt(v('all9','final_error_m'),1000)} | "
                 f"{fmt(v('all9','failure_fraction_10pct_diameter'),100)} | {fmt(v('easy7','mean_error_m'),1000)} | {fmt(v('cylinder_A_04','mean_error_m'),1000)} | "
                 f"{fmt(v('cylinder_C_04','mean_error_m'),1000)} | {fmt(v('cylinder_C_04','final_error_m'),1000)} | {sum(v('all9','lost'))}/{9*len(a.seeds)} |")
    L += ['', '## Paired differences (A − B, mm; negative = A better)', '',
          '| pair | seed | all9 mean | easy7 mean | cylinder_A_04 mean | cylinder_C_04 mean | cylinder_C_04 final | sequences A better (of 9) |', '|---|---|---|---|---|---|---|---|']
    for x, y in PAIRS:
        if x not in methods or y not in methods: continue
        for seed in a.seeds:
            d = {r['sequence']: r for r in paired if r['seed'] == int(seed) and r['pair'] == f'{x} - {y}'}
            better = sum(1 for k, r in d.items() if not k.startswith('[') and r['mean_diff_mm'] < 0)
            L.append(f"| {x} − {y} | {seed} | {d['[all9]']['mean_diff_mm']:+.2f} | {d['[easy7]']['mean_diff_mm']:+.2f} | {d['[cylinder_A_04]']['mean_diff_mm']:+.2f} | "
                     f"{d['[cylinder_C_04]']['mean_diff_mm']:+.2f} | {d['[cylinder_C_04]']['final_diff_mm']:+.2f} | {better} |")
    (a.output / 'summary_tables.md').write_text('\n'.join(L) + '\n')
    (a.output / 'summary_tables.json').write_text(json.dumps(dict(source_commits=commits, training=training,
        groups={f'{s}|{m}|{g}': v for (s, m, g), v in groups.items()}), indent=2))
    print('\n'.join(L))


if __name__ == '__main__':
    main()
