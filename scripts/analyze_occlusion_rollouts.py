#!/usr/bin/env python3
"""Occlusion-conditioned rollout analysis (read-only over finished rollouts).

Visibility comes from measure_omy_visibility.py and is used for analysis only.
Fixed definitions (docs/OMY_NEXT_VALIDATION_HANDOFF.md, task 4):
  bins            >=50%, 20-50%, 5-20%, <5% visible
  severe event    >=3 consecutive frames below 5%
  reappearance    first start, after the event, of >=3 consecutive frames >=50%
  episode         severe events sharing one reappearance frame (merged)
  phases          before = up to 60 frames (2 s) before the episode, during =
                  episode start .. reappearance-1, after = reappearance .. end
  recovery        first start, at/after reappearance, of >=5 consecutive frames
                  with surface error <= 0.1 diameter; frame 0 never counts
Supplementary (added after inspecting earlier runs, not pre-registered): final
object-origin translation error and raw rotation error/axis in the mesh frame,
because the surface metric declares no symmetry for near-cylindrical objects.
Run labels are METHOD or METHOD/SEED; each points at a directory holding
<sequence>/frame_metrics.jsonl and summary.json.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

BINS = (('>=50%', .5, 1e9), ('20-50%', .2, .5), ('5-20%', .05, .2), ('<5%', -1, .05))
COLORS = {'visual': '#9e9e9e', 'kinematic-refine': '#000000', 'visual-ft': '#e08a1e', 'cad-only': '#2e9e57',
          'geometry': '#1f5fbf', 'motion': '#8e44ad'}
DEFINITIONS = dict(bins=[b[0] for b in BINS], severe='>=3 consecutive frames with visibility < 0.05',
                   reappearance='first start of >=3 consecutive frames with visibility >= 0.5 after the event',
                   episode='severe events with the same reappearance frame are merged',
                   phases='before: <=60 frames before episode start (frame 0 excluded); during: start..reappearance-1; after: reappearance..last',
                   recovery='first start at/after reappearance of >=5 consecutive frames with error <= 0.1 diameter',
                   recovery_status=['recovered', 'not_recovered (window exists, never met)',
                                    'insufficient (fewer than 5 frames remain)', 'no_reappearance'])


def runs(mask, minimum):
    out, start = [], None
    for i, m in enumerate(list(mask) + [False]):
        if m and start is None: start = i
        if not m and start is not None:
            if i - start >= minimum: out.append((start, i - 1))
            start = None
    return out


def episodes(vis):
    events = runs(vis < .05, 3)
    good = vis >= .5
    merged = {}
    for s, e in events:
        reappear = next((j for j in range(e + 1, len(vis) - 2) if good[j:j + 3].all()), None)
        key = reappear if reappear is not None else ('none', s)
        if key in merged: merged[key]['events'].append([s, e]); merged[key]['end'] = e
        else: merged[key] = dict(start=s, end=e, reappear=reappear, events=[[s, e]])
    return list(merged.values())


def load_run(directory, sequences):
    out = {}
    for seq in sequences:
        path = Path(directory) / seq / 'frame_metrics.jsonl'
        if not path.exists(): continue
        rows = [json.loads(s) for s in path.read_text().splitlines()]
        summary = json.loads((Path(directory) / seq / 'summary.json').read_text())
        out[seq] = dict(error=np.array([r['symmetry_surface_error_m'] for r in rows]) * 1000,
                        init=np.array([r['initialized'] for r in rows]), diameter_mm=summary['diameter_m'] * 1000)
    return out


def pose_errors(directory, seq, reader):
    """Supplementary (not pre-registered): object-origin translation error (mm) and raw
    rotation error (deg, no symmetry) with its axis expressed in the mesh frame."""
    from scipy.spatial.transform import Rotation
    path = Path(directory) / seq / 'poses.jsonl'
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    out = []
    for i, r in enumerate(rows):
        err = np.linalg.inv(reader.target(i).double().numpy()) @ np.asarray(r['T_camera_mesh'], dtype=float)
        rv = Rotation.from_matrix(err[:3, :3]).as_rotvec()
        out.append((np.linalg.norm(err[:3, 3]) * 1000, np.degrees(np.linalg.norm(rv)), rv / max(np.linalg.norm(rv), 1e-12)))
    return out


def stat(values):
    v = np.asarray(values, dtype=float)
    return dict(n=int(len(v)), mean=float(v.mean()), p95=float(np.percentile(v, 95)), max=float(v.max())) if len(v) else dict(n=0)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--visibility', type=Path, required=True)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--run', action='append', required=True, metavar='LABEL=DIR')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--detail', nargs='+', default=['cylinder_A_04', 'cylinder_C_04'])
    p.add_argument('--figure-seed', default='s42', help='Pre-registered seed for the common timeline figures')
    p.add_argument('--title', default='')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True); (a.output / 'figures').mkdir(exist_ok=True)
    vis_rows = defaultdict(list)
    for r in csv.DictReader(a.visibility.open()): vis_rows[r['sequence']].append(r)
    sequences = sorted(vis_rows)
    vis = {s: np.array([float(r['visibility']) if r['visibility'] else np.nan for r in rs]) for s, rs in vis_rows.items()}
    ts = {s: np.array([float(r['timestamp_s']) for r in rs]) for s, rs in vis_rows.items()}
    eps = {s: episodes(v) for s, v in vis.items()}
    (a.output / 'occlusion_events.json').write_text(json.dumps(dict(definitions=DEFINITIONS, episodes=eps), indent=2))
    labels = [r.split('=', 1)[0] for r in a.run]
    data = {lab: load_run(d, sequences) for lab, d in (r.split('=', 1) for r in a.run)}
    dirs = dict(r.split('=', 1) for r in a.run)
    from robot_conditioned_pose.omy_sequence import OmySequence
    snapshot = json.loads((Path(__file__).resolve().parents[1] / 'configs/omy_pilot_manifest_20261124.json').read_text())['sequences']
    readers = {s: OmySequence(a.dataset / snapshot[s]['path']) for s in sequences if eps[s]}
    decomposition = {}
    bins_out, phase_out, recovery_out = [], [], []
    for lab, rs in data.items():
        method, _, seed = lab.partition('/')
        for name, lo, hi in BINS:
            vals, seqs = [], set()
            for s, r in rs.items():
                m = (~r['init']) & (vis[s] >= lo) & (vis[s] < hi)
                if m.any(): vals.append(r['error'][m]); seqs.add(s)
            st = stat(np.concatenate(vals) if vals else [])
            bins_out.append(dict(label=lab, method=method, seed=seed, bin=name, sequences=len(seqs), **st))
        for s, r in rs.items():
            thr = .1 * r['diameter_mm']
            for k, ep in enumerate(eps[s]):
                start, reappear, n = ep['start'], ep['reappear'], len(r['error'])
                phases = dict(before=range(max(1, start - 60), start), during=range(start, reappear if reappear is not None else n),
                              after=range(reappear, n) if reappear is not None else range(0))
                for ph, idx in phases.items():
                    phase_out.append(dict(label=lab, method=method, seed=seed, sequence=s, episode=k, phase=ph,
                                          **stat(r['error'][list(idx)] if len(idx) else [])))
                row = dict(label=lab, method=method, seed=seed, sequence=s, episode=k, episode_start=start,
                           reappear_frame=reappear, threshold_mm=thr, peak_during_mm=float(r['error'][start:reappear or n].max()))
                if reappear is None:
                    row.update(status='no_reappearance')
                else:
                    ok = r['error'] <= thr
                    hit = next((j for j in range(reappear, n - 4) if ok[j:j + 5].all()), None)
                    row['status'] = 'recovered' if hit is not None else ('insufficient' if n - reappear < 5 else 'not_recovered')
                    row['recovery_s'] = float(ts[s][hit] - ts[s][reappear]) if hit is not None else None
                    row['below_threshold_at_reappearance'] = bool(ok[reappear])
                    for sec in (1, 2):
                        j = reappear + 30 * sec
                        row[f'error_after_{sec}s_mm'] = float(r['error'][j]) if j < n else None
                    row['final_mm'] = float(r['error'][-1]); row['last_1s_mean_mm'] = float(r['error'][-30:].mean())
                    row['max_after_reappear_mm'] = float(r['error'][reappear:].max())
                    pe = decomposition.setdefault((lab, s), pose_errors(dirs[lab], s, readers[s]))
                    row['final_translation_mm'] = float(pe[-1][0]); row['final_rotation_deg'] = float(pe[-1][1])
                    row['final_rotation_axis_mesh'] = ' '.join(f'{x:.2f}' for x in pe[-1][2])
                    row['after_translation_max_mm'] = float(max(x[0] for x in pe[reappear:]))
                    row['after_rotation_mean_deg'] = float(np.mean([x[1] for x in pe[reappear:]]))
                recovery_out.append(row)
    for name, rows in (('visibility_bins', bins_out), ('phase_errors', phase_out), ('recovery_events', recovery_out)):
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with (a.output / f'{name}.csv').open('w', newline='') as f:
            w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(rows)
    figures(a, data, labels, vis, ts, eps, sequences)
    print(a.output)


def figures(a, data, labels, vis, ts, eps, sequences):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from robot_conditioned_pose.omy_sequence import OmySequence
    snapshot = json.loads((Path(__file__).resolve().parents[1] / 'configs/omy_pilot_manifest_20261124.json').read_text())['sequences']
    seed_labels = [l for l in labels if l.partition('/')[2] in ('', a.figure_seed)]
    for s in sequences:
        path = a.dataset / snapshot[s]['path']
        seq = OmySequence(path)
        frames = [json.loads(x) for x in (path / seq.manifest['frames_file']).read_text().splitlines()]
        t = ts[s] - ts[s][0]
        eff = np.array([seq.effector_pose(i, 'link6')[:3, 3].numpy() for i in range(len(frames))])
        obj = np.array([np.asarray(f['T_world_object_gt'])[:3, 3] for f in frames])
        speed = lambda x: np.r_[np.nan, np.linalg.norm(np.diff(x, axis=0), axis=1) / np.diff(t)]
        windows = [('full', 0, len(t) - 1)]
        for k, ep in enumerate(eps[s]):
            end = ep['reappear'] if ep['reappear'] is not None else len(t) - 1
            windows.append((f'transition{k}', max(0, ep['start'] - 30), min(len(t) - 1, end + 90)))
        for tag, lo, hi in windows:
            if tag != 'full' and s not in a.detail: continue
            fig, ax = plt.subplots(3, 1, figsize=(11, 8), sharex=True, gridspec_kw=dict(height_ratios=[1, 2.2, 1.2]))
            sl = slice(lo, hi + 1)
            ax[0].plot(t[sl], 100 * vis[s][sl], color='#444')
            for y in (50, 20, 5): ax[0].axhline(y, color='#bbb', lw=.8, ls=':')
            ax[0].set_ylabel('visible %'); ax[0].set_ylim(-3, 103)
            for ep in eps[s]:
                for axis in ax:
                    axis.axvspan(t[ep['start']], t[ep['events'][-1][1]], color='#d9d9d9', alpha=.5, lw=0)
                    if ep['reappear'] is not None: axis.axvline(t[ep['reappear']], color='#d62728', lw=.9, ls='--')
            for lab in seed_labels:
                if s not in data[lab]: continue
                method = lab.partition('/')[0]
                e = data[lab][s]['error']
                ax[1].plot(t[sl][1 if lo == 0 else 0:], e[sl][1 if lo == 0 else 0:], color=COLORS.get(method, None),
                           ls='--' if method == 'kinematic-refine' else '-', lw=1.4, label=method)
            any_run = next(iter(data.values()))
            if s in any_run: ax[1].axhline(.1 * any_run[s]['diameter_mm'], color='#d62728', lw=.8, ls=':', label='0.1 diameter')
            ax[1].set_yscale('log'); ax[1].set_ylabel('surface error (mm, log)'); ax[1].legend(fontsize=8, ncol=3, loc='upper left')
            ax[2].plot(t[sl], speed(eff)[sl] * 100, color='#555', label='link6 speed (measured-joint FK)')
            ax[2].plot(t[sl], speed(obj)[sl] * 100, color='#8c564b', label='object speed (GT, analysis only)')
            phase = [f['task_phase'] for f in frames]
            for i in range(lo, hi + 1):
                if i == lo or phase[i] != phase[i - 1]:
                    ax[2].text(t[i], ax[2].get_ylim()[1] * .85 if ax[2].get_ylim()[1] > 0 else 1, phase[i], fontsize=7, color='#333')
            ax[2].set_ylabel('cm/s'); ax[2].set_xlabel('time since first frame (s)'); ax[2].legend(fontsize=7, loc='upper right')
            fig.suptitle(f"{a.title} {s} — {tag} (seed {a.figure_seed}; grey band <5% visible, red dashed = reappearance; task_phase = simulator label, analysis only)", fontsize=9)
            fig.tight_layout(); fig.savefig(a.output / 'figures' / f'{s}_{tag}.png', dpi=110); plt.close(fig)
    # Supplementary: translation vs rotation error for the detailed sequences (figure seed).
    for s in a.detail:
        if not eps.get(s): continue
        reader = OmySequence(a.dataset / snapshot[s]['path'])
        fig, ax = plt.subplots(2, 1, figsize=(11, 5.5), sharex=True)
        for lab in seed_labels:
            run_dir = dict(r.split('=', 1) for r in a.run)[lab]
            if not (Path(run_dir) / s / 'poses.jsonl').exists(): continue
            method = lab.partition('/')[0]
            pe = pose_errors(run_dir, s, reader)
            t = ts[s][1:] - ts[s][0]
            ax[0].plot(t, [x[0] for x in pe[1:]], color=COLORS.get(method), ls='--' if method == 'kinematic-refine' else '-', lw=1.3, label=method)
            ax[1].plot(t, [x[1] for x in pe[1:]], color=COLORS.get(method), ls='--' if method == 'kinematic-refine' else '-', lw=1.3)
        for ep in eps[s]:
            for axis in ax:
                axis.axvspan(ts[s][ep['start']] - ts[s][0], ts[s][ep['events'][-1][1]] - ts[s][0], color='#d9d9d9', alpha=.5, lw=0)
                if ep['reappear'] is not None: axis.axvline(ts[s][ep['reappear']] - ts[s][0], color='#d62728', lw=.9, ls='--')
        ax[0].set_yscale('log'); ax[0].set_ylabel('object-origin\ntranslation error (mm)'); ax[0].legend(fontsize=8, ncol=3)
        ax[1].set_ylabel('raw rotation error (deg)\nno symmetry'); ax[1].set_xlabel('time since first frame (s)')
        fig.suptitle(f'{a.title} {s}: supplementary pose-error decomposition (seed {a.figure_seed})', fontsize=9)
        fig.tight_layout(); fig.savefig(a.output / 'figures' / f'{s}_translation_rotation.png', dpi=110); plt.close(fig)
    # All-seed small multiples for the detailed sequences.
    methods = list(dict.fromkeys(l.partition('/')[0] for l in labels))
    for s in a.detail:
        fig, axes = plt.subplots(1, len(methods), figsize=(3.2 * len(methods), 3.2), sharey=True)
        for ax, m in zip(np.atleast_1d(axes), methods):
            for lab in labels:
                if lab.partition('/')[0] != m or s not in data[lab]: continue
                ax.plot(ts[s][1:] - ts[s][0], data[lab][s]['error'][1:], lw=1, label=lab.partition('/')[2] or 'single')
            for ep in eps[s]:
                ax.axvspan(ts[s][ep['start']] - ts[s][0], ts[s][ep['events'][-1][1]] - ts[s][0], color='#d9d9d9', alpha=.6, lw=0)
            ax.set_yscale('log'); ax.set_title(m, fontsize=9); ax.legend(fontsize=7); ax.set_xlabel('s')
        np.atleast_1d(axes)[0].set_ylabel('surface error (mm, log)')
        fig.suptitle(f'{a.title} {s}: every seed per method (grey = <5% visible)', fontsize=9)
        fig.tight_layout(); fig.savefig(a.output / 'figures' / f'{s}_all_seeds.png', dpi=110); plt.close(fig)


if __name__ == '__main__':
    main()
