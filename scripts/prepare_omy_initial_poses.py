#!/usr/bin/env python3
"""Explicit oracle-initialization diagnostic; never used by the tracker internally."""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--oracle-first-frame', action='store_true', required=True,
                   help='Explicitly use frame-0 GT for a tracking-only diagnostic')
    a = p.parse_args()
    import numpy as np
    from robot_conditioned_pose.omy_sequence import open_sequence
    manifest = json.loads((ROOT/'configs/omy_pilot_manifest_20261124.json').read_text())
    sequences = [a.dataset/r['path'] for r in manifest['sequences'].values() if r['split']=='validation']
    # Validate all paths before creating a partial output directory.
    for path in sequences:
        if not (path/'manifest.json').is_file(): raise FileNotFoundError(path)
    a.output.mkdir(parents=True, exist_ok=False)
    for path in sequences:
        np.save(a.output/(path.name+'.npy'), open_sequence(path).target(0).numpy(), allow_pickle=False)
    (a.output/'initialization.json').write_text(json.dumps(dict(initialization='oracle-first-frame',
        note='Frame-0 GT only. Tracking diagnostic, not end-to-end deployment performance.',
        sequences=[p.name for p in sequences]), indent=2))
    print(a.output)


if __name__ == '__main__': main()
