#!/usr/bin/env python3
"""Plan by default; --execute runs an explicit local GPU stage. No cloud provisioning."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]


def verify_checksums(checksums, dataset):
    base = dataset.parent.resolve()
    total = 0
    for line in checksums.read_text().splitlines():
        if not line.strip(): continue
        digest, relative = line.split(maxsplit=1)
        file = (base/relative.lstrip('*')).resolve()
        if dataset.resolve() not in file.parents:
            raise ValueError('Checksum path outside dataset: '+relative)
        h = hashlib.sha256()
        with file.open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
        if h.hexdigest() != digest: raise ValueError('Checksum mismatch: '+relative)
        total += 1
    if not total: raise ValueError('Empty checksum file')
    return total


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True, help='New cache/run parent, outside dataset')
    p.add_argument('--stage', choices=['smoke', 'prepare', 'tiny', 'pilot', 'motion-prepare', 'motion'], default='prepare')
    p.add_argument('--checksums', type=Path, help='Official accepted_checksums.sha256, required to execute preparation')
    p.add_argument('--execute', action='store_true')
    a = p.parse_args()
    a.dataset = a.dataset.resolve(); a.work = a.work.resolve()
    if a.dataset == a.work or a.dataset in a.work.parents:
        p.error('Work directory must be outside the read-only dataset')
    manifest = json.loads((ROOT/'configs/omy_pilot_manifest_20261124.json').read_text())
    from check_omy_training_readiness import summarize
    summarize(manifest,5,4,20)
    splits = {k: [a.dataset/r['path'] for r in manifest['sequences'].values() if r['split']==k]
              for k in ['train','validation']}
    py = sys.executable
    commands = []
    if a.stage in ['smoke','prepare','motion-prepare']:
        commands.append([py, ROOT/'scripts/check_robot_refiner_cuda.py'])
        for split in ([] if a.stage == 'smoke' else splits):
            prefix = 'motion-' if a.stage == 'motion-prepare' else ''
            commands.append([py, ROOT/'scripts/prepare_robot_refiner.py', *splits[split],
                             '--output', a.work/(prefix+split), '--stride','5', '--seed','0',
                             '--hypothesis', 'previous' if prefix else 'perturbed'])
        if a.stage in ['smoke', 'prepare']:
            tiny = [a.dataset/n for n in ['box_A_00','box_B_00','box_C_00']]
            commands.append([py, ROOT/'scripts/prepare_robot_refiner.py', *tiny,
                '--output', a.work/('smoke-train' if a.stage == 'smoke' else 'tiny-train'),'--stride','5','--max-frames-per-sequence','2' if a.stage == 'smoke' else '16'])
    else:
        modes = ['visual','geometry'] if a.stage == 'pilot' else (['visual','geometry','motion'] if a.stage == 'motion' else ['geometry'])
        prefix = 'motion-' if a.stage == 'motion' else ''
        for mode in modes:
            commands.append([py, ROOT/'scripts/train_robot_refiner.py',
                '--train', a.work/('tiny-train' if a.stage=='tiny' else prefix+'train'),
                '--val', a.work/(prefix+'validation'), '--output', a.work/('run-'+a.stage+'-'+mode),
                '--mode',mode,'--epochs','20','--warmup-epochs','20' if a.stage=='tiny' else '0',
                '--batch-size','4','--seed','42'])
    for cmd in commands: print(shlex.join(map(str,cmd)), flush=True)
    if not a.execute:
        print('PLAN ONLY. No training, GPU use, downloads or cloud actions.'); return
    if a.stage in ['smoke','prepare','motion-prepare']:
        if not a.checksums: p.error('--checksums required for preparation execution')
        count = verify_checksums(a.checksums, a.dataset)
        if count != 37654:
            raise ValueError('Expected official 37,654-entry final pilot checksum list')
        print(f'Verified {count} payload checksums', flush=True)
        for name,row in manifest['sequences'].items():
            m=json.loads((a.dataset/row['path']/'manifest.json').read_text())
            ext=m['omy_tracking']
            if m['frame_count'] != row['frames'] or any(ext[k] != row[k] for k in ['split','parent_group']):
                raise ValueError('Dataset selection mismatch: '+name)
    for cmd in commands: subprocess.run(list(map(str,cmd)), cwd=ROOT, check=True)


if __name__ == '__main__': main()
