#!/usr/bin/env python3
"""Plan/execute matched validation rollouts and aggregate sequences equally."""
import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def aggregate(output, labels, sequences):
    metrics = ('mean_error_m', 'final_error_m', 'failure_fraction_10pct_diameter', 'mean_tracking_seconds')
    results, references = {}, {}
    visual_protocol = None
    for label in labels:
        rows = []
        model_identity = None
        for sequence in sequences:
            row = json.loads((output/label/sequence/'summary.json').read_text())
            current_model = {k: row[k] for k in ('method', 'model_mode', 'checkpoint_sha256',
                'pretrained_sha256', 'config', 'iterations', 'effector_link')}
            if model_identity is not None and current_model != model_identity:
                raise ValueError('different models/settings within label: '+label)
            model_identity = current_model
            if row['pretrained_sha256'] is not None:
                current_visual = {k: row[k] for k in ('pretrained_sha256', 'config', 'iterations')}
                if visual_protocol is not None and current_visual != visual_protocol:
                    raise ValueError('incomparable pretrained weights/config/refinement iterations')
                visual_protocol = current_visual
            # Reject accidentally mixing different initial poses, dataset versions,
            # geometry conventions or evaluation sampling across methods.
            identity = {k: row[k] for k in ('protocol_version', 'initial_pose_sha256', 'initialization',
                'inputs', 'mesh_sha256', 'geometry_version', 'diameter_m', 'evaluation_points',
                'evaluation_seed', 'first_frame_policy', 'tracked_frames', 'source_commit')}
            if sequence in references and references[sequence] != identity:
                raise ValueError('incomparable rollout inputs: '+sequence)
            references[sequence] = identity
            row['scenario'] = sequence.rsplit('_', 2)[-2]
            rows.append(row)
        groups = {'all': rows}
        groups.update({s: [r for r in rows if r['scenario']==s] for s in ('A','B','C')})
        results[label] = {name: dict(sequence_count=len(group),
            **{key: sum(r[key] for r in group)/len(group) for key in metrics})
            for name, group in groups.items() if group}
    payload = dict(aggregation='macro average across sequences (equal weight); frame 0 excluded',
        caveat='Validation pilot; A/B/C are clip categories, not per-frame contact phases. B/C may share physical parents.',
        methods=results)
    (output/'comparison.json').write_text(json.dumps(payload, indent=2))
    lines = ['# Matched validation rollouts', '',
        'Equal sequence weight; initialization frame excluded. A/B/C are clip categories, not contact labels.', '',
        '| Method | Group | Sequences | Mean error (mm) | Final error (mm) | Frames > 0.1 diameter (%) | Mean time (ms) |',
        '|---|---|---:|---:|---:|---:|---:|']
    for label, groups in results.items():
        for group, r in groups.items():
            lines.append(f"| {label} | {group} | {r['sequence_count']} | {1000*r['mean_error_m']:.3f} | {1000*r['final_error_m']:.3f} | {100*r['failure_fraction_10pct_diameter']:.2f} | {1000*r['mean_tracking_seconds']:.2f} |")
    (output/'comparison.md').write_text('\n'.join(lines)+'\n')
    return payload


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--initial-poses', type=Path, required=True, help='<sequence>.npy for all 9 validation sequences')
    p.add_argument('--initialization', choices=['external','oracle-first-frame'], required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--methods', nargs='+', choices=['hold','kinematic','visual','kinematic-refine'],
                   default=['hold','kinematic','visual','kinematic-refine'])
    p.add_argument('--checkpoint', action='append', default=[], metavar='LABEL=PATH',
                   help='Repeat for trained visual/geometry/motion models')
    p.add_argument('--iterations', type=int, default=2)
    p.add_argument('--effector-link', default='link6')
    p.add_argument('--execute', action='store_true')
    p.add_argument('--summarize-only', action='store_true', help='Aggregate completed outputs without rerunning')
    a = p.parse_args()
    if a.iterations < 1: p.error('--iterations must be positive')
    if a.execute and a.summarize_only: p.error('choose execute or summarize-only')
    if a.output.resolve() == a.dataset.resolve() or a.dataset.resolve() in a.output.resolve().parents:
        p.error('output must be outside read-only dataset')
    models = [(m, m, None) for m in a.methods]
    for item in a.checkpoint:
        if '=' not in item: p.error('--checkpoint requires LABEL=PATH')
        label, path = item.split('=',1)
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', label): p.error('invalid checkpoint label')
        models.append((label, 'learned', Path(path)))
    labels = [m[0] for m in models]
    if len(labels) != len(set(labels)): p.error('duplicate method/checkpoint labels')
    snapshot = json.loads((ROOT/'configs/omy_pilot_manifest_20261124.json').read_text())
    rows = [r for r in snapshot['sequences'].values() if r['split']=='validation']
    names = [Path(r['path']).name for r in rows]
    if a.summarize_only:
        aggregate(a.output, labels, names); print(a.output/'comparison.md'); return
    commands = []
    for label, method, checkpoint in models:
        for row in rows:
            sequence = a.dataset/row['path']
            command = [sys.executable, ROOT/'scripts/evaluate_robot_tracker.py', sequence,
                '--initial-pose', a.initial_poses/(sequence.name+'.npy'), '--initialization', a.initialization,
                '--method', method, '--output', a.output/label/sequence.name,
                '--iterations', str(a.iterations), '--effector-link', a.effector_link]
            if checkpoint: command += ['--checkpoint', checkpoint]
            commands.append(list(map(str,command)))
    for command in commands: print(shlex.join(command), flush=True)
    if not a.execute:
        print('PLAN ONLY. No GPU use or output writes.'); return
    # Complete preflight before creating or launching any experiment.
    tag = a.initial_poses/'initialization.json'
    if tag.exists() and json.loads(tag.read_text())['initialization'] != a.initialization:
        p.error('initialization label differs from initial-pose provenance')
    for row in rows:
        sequence = a.dataset/row['path']
        manifest = json.loads((sequence/'manifest.json').read_text())
        ext = manifest['omy_tracking']
        if manifest['frame_count'] != row['frames'] or any(ext[k] != row[k] for k in ('split','parent_group')):
            raise ValueError('dataset selection mismatch: '+sequence.name)
        initial = a.initial_poses/(sequence.name+'.npy')
        if not initial.is_file(): raise FileNotFoundError(initial)
    for _, _, checkpoint in models:
        if checkpoint is not None and not checkpoint.is_file(): raise FileNotFoundError(checkpoint)
    a.output.mkdir(parents=True, exist_ok=False)
    (a.output/'plan.json').write_text(json.dumps(dict(commands=commands, labels=labels, sequences=names), indent=2))
    for command in commands: subprocess.run(command, cwd=ROOT, check=True)
    aggregate(a.output, labels, names)
    print(a.output/'comparison.md')


if __name__ == '__main__': main()
