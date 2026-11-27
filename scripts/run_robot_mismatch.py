#!/usr/bin/env python3
"""Robot-state mismatch control: existing checkpoints, inference-only corruption.

For every checkpoint and validation sequence, roll out once per perturbation.
'none' reruns the unperturbed model under the same code as a matched reference.
swap-sequence donors are fixed in advance: the next validation sequence in
sorted order (cyclic).
"""
import argparse
import shlex
import subprocess
import sys
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
DEFAULT = ['none', 'delay-3', 'delay-15', 'zero-velocity', 'freeze-first', 'swap-sequence',
           'joint-noise-0.002', 'joint-noise-0.02']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--initial-poses', type=Path, required=True)
    p.add_argument('--initialization', choices=['external', 'oracle-first-frame'], required=True)
    p.add_argument('--checkpoint', action='append', required=True, metavar='LABEL=PATH')
    p.add_argument('--perturbations', nargs='+', default=DEFAULT)
    p.add_argument('--branch-ablations', nargs='+', default=['none'], help='none | drop-robot-rows | bypass-branch')
    p.add_argument('--iterations', type=int, default=2)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--execute', action='store_true')
    a = p.parse_args()
    from robot_conditioned_pose.robot_perturbation import parse
    for spec in a.perturbations: parse(spec)
    snapshot = json.loads((ROOT/'configs/omy_pilot_manifest_20261124.json').read_text())
    names = sorted(Path(r['path']).name for r in snapshot['sequences'].values() if r['split'] == 'validation')
    donors = {n: names[(i+1) % len(names)] for i, n in enumerate(names)}
    tag = json.loads((a.initial_poses/'initialization.json').read_text())['initialization']
    if tag != a.initialization: p.error('initialization label differs from initial-pose provenance')
    commands = []
    for item in a.checkpoint:
        label, path = item.split('=', 1)
        if not Path(path).is_file(): raise FileNotFoundError(path)
        for spec, ablation in [(s, b) for b in a.branch_ablations for s in a.perturbations]:
            for name in names:
                if not (a.initial_poses/(name+'.npy')).is_file(): raise FileNotFoundError(name)
                c = [sys.executable, ROOT/'scripts/evaluate_robot_tracker.py', a.dataset/name,
                     '--initial-pose', a.initial_poses/(name+'.npy'), '--initialization', a.initialization,
                     '--method', 'learned', '--checkpoint', path, '--iterations', str(a.iterations),
                     '--robot-perturbation', spec, '--branch-ablation', ablation,
                     '--output', a.output/label/(spec if ablation == 'none' else ablation)/name]
                if ablation != 'none' and spec != 'none': p.error('combine ablations only with perturbation none')
                if spec == 'swap-sequence': c += ['--robot-donor', a.dataset/donors[name]]
                commands.append(list(map(str, c)))
    for c in commands: print(shlex.join(c), flush=True)
    if not a.execute:
        print(f'PLAN ONLY: {len(commands)} rollouts'); return
    a.output.mkdir(parents=True, exist_ok=True)
    (a.output/'donors.json').write_text(json.dumps(donors, indent=2))
    for c in commands:
        subprocess.run(c, check=True, stdout=subprocess.DEVNULL)
        print('DONE', c[-1] if '--robot-donor' not in c else c[-3], flush=True)


if __name__ == '__main__': main()
