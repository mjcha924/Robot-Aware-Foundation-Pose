#!/usr/bin/env python3
"""Read-only preparation check. Never installs, connects to AWS, or trains.

Metadata/file-presence checks are not checksum, calibration or CUDA parity tests.
"""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import platform
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def summarize(manifest, stride, batch, epochs):
    rows = manifest['sequences']
    if len(rows) != manifest['sequence_count']:
        raise ValueError('Sequence count mismatch')
    groups, stats = {}, {}
    for name, row in rows.items():
        split = row['split']
        if split not in ('train', 'validation') or row['frames'] <= 0:
            raise ValueError('Invalid split/frame count: ' + name)
        parent = row['parent_group']
        if parent in groups and groups[parent] != split:
            raise ValueError('Physical parent crosses splits: ' + parent)
        groups[parent] = split
        s = stats.setdefault(split, dict(sequences=0, frames=0, samples=0))
        s['sequences'] += 1
        s['frames'] += row['frames']
        s['samples'] += math.ceil(row['frames'] / stride)
    for s in stats.values():
        s['batches_per_epoch'] = math.ceil(s['samples'] / batch)
    return stats


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, default=ROOT/'configs/omy_pilot_manifest_20261124.json')
    p.add_argument('--dataset', type=Path, help='Optional clean dataset/ directory')
    p.add_argument('--stride', type=int, default=5)
    p.add_argument('--batch-size', type=int, default=4)
    p.add_argument('--epochs', type=int, default=20)
    p.add_argument('--cache-seconds-per-sample', type=float)
    p.add_argument('--train-seconds-per-batch', type=float)
    p.add_argument('--val-seconds-per-batch', type=float)
    p.add_argument('--usd-per-hour', type=float, help='User supplied regional price; not a live quote')
    a = p.parse_args()
    if min(a.stride, a.batch_size, a.epochs) < 1:
        p.error('Counts must be positive')
    rates = [a.cache_seconds_per_sample, a.train_seconds_per_batch, a.val_seconds_per_batch, a.usd_per_hour]
    if any(x is not None and (not math.isfinite(x) or x < 0) for x in rates):
        p.error('Timings/prices must be finite and nonnegative')
    manifest = json.loads(a.manifest.read_text())
    stats = summarize(manifest, a.stride, a.batch_size, a.epochs)
    report = dict(platform=platform.platform(), split_summary=stats,
                  assumptions=dict(stride=a.stride, batch_size=a.batch_size,
                                   epochs=a.epochs, hypotheses_per_selected_frame=1),
                  preparation_only=True, training_ready=False)
    report['python_modules_found'] = {m: importlib.util.find_spec(m) is not None
                                      for m in ('torch', 'numpy', 'PIL', 'trimesh', 'nvdiffrast')}
    if shutil.which('nvidia-smi'):
        r = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,driver_version',
                            '--format=csv,noheader'], capture_output=True, text=True, timeout=15)
        report['gpu_inventory'] = r.stdout.strip() if r.returncode == 0 else 'nvidia-smi failed'
    else:
        report['gpu_inventory'] = 'nvidia-smi unavailable; CUDA not validated'
    missing = []
    if a.dataset:
        root = a.dataset.resolve()
        for row in manifest['sequences'].values():
            seq = (root / row['path']).resolve()
            if root not in seq.parents:
                raise ValueError('Sequence path outside dataset')
            for rel in ('manifest.json', 'robot_observations.jsonl', 'previous_robot_state.json',
                        'rgb', 'depth', 'mesh', 'robot'):
                if not (seq/rel).exists():
                    missing.append(str(seq/rel))
        report['dataset_presence'] = dict(missing_count=len(missing), first_missing=missing[:12],
                                           note='Presence only; verify official checksums separately')
    else:
        report['dataset_presence'] = 'Not supplied; manifest is metadata only'
    if all(x is not None for x in rates[:3]):
        samples = sum(s['samples'] for s in stats.values())
        seconds = (samples*a.cache_seconds_per_sample + a.epochs*(
            stats['train']['batches_per_epoch']*a.train_seconds_per_batch +
            stats['validation']['batches_per_epoch']*a.val_seconds_per_batch))
        report['timing_projection'] = dict(hours=seconds/3600,
            excludes='Setup, transfer, initialization, rollout, checkpoint I/O, retries and other runs')
        if a.usd_per_hour is not None:
            report['timing_projection']['compute_usd'] = seconds/3600*a.usd_per_hour
    report['remaining_gates'] = ['New measured-state reader integration', 'Official payload checksums',
        'FoundationPose weights and native CUDA extensions', 'Real CUDA parity and rendering',
        'Tiny-set optimization and sequence rollout']
    print(json.dumps(report, indent=2))
    return 2 if missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
