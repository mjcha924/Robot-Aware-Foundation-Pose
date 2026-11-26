#!/usr/bin/env python3
"""One-step reference errors on prepared caches, before any training.

For each cache reports (same surface-error loss as the trainer, mean over samples):
  hypothesis  - the perturbed input pose, no correction at all
  pretrained  - one step of the unchanged pretrained heads (visual mode, no robot input)
This is the "epoch -1" line for reading tiny/pilot/motion curves. It is a one-step
cache metric, not a tracking result. Writes JSON; never modifies the caches.
"""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def evaluate(cache, device, batch_size):
    import torch
    from torch.utils.data import DataLoader
    from robot_conditioned_pose.data import FeatureDataset, collate
    from robot_conditioned_pose.geometry import pose_loss
    from robot_conditioned_pose.model import RobotConditionedRefiner
    from robot_conditioned_pose.trainer import CachedHeads, batch_loss, device_batch
    data = FeatureDataset(cache)
    heads = CachedHeads()
    heads.load_state_dict(torch.load(Path(cache) / 'heads.pt', weights_only=True, map_location='cpu'), strict=True)
    model = RobotConditionedRefiner(heads, mode='visual').to(device).eval()
    cfg = data.manifest['cfg']
    totals = dict(hypothesis=0., pretrained=0.)
    with torch.no_grad():
        for raw in DataLoader(data, batch_size=batch_size, collate_fn=collate):
            b = device_batch(raw, device)
            n = len(b['visual'])
            totals['hypothesis'] += pose_loss(b['hypothesis'], b['target'], b['cad'], b['symmetries']).item() * n
            totals['pretrained'] += batch_loss(model, b, cfg).item() * n
    return dict(samples=len(data), **{k + '_surface_error_m': v / len(data) for k, v in totals.items()})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('caches', nargs='+', type=Path)
    p.add_argument('--output', type=Path, required=True, help='New JSON file')
    p.add_argument('--device', default='cuda')
    p.add_argument('--batch-size', type=int, default=16)
    a = p.parse_args()
    if a.output.exists():
        p.error('output exists; choose a new path')
    result = {str(c): evaluate(c, a.device, a.batch_size) for c in a.caches}
    for cache, r in result.items():
        print(f"{Path(cache).name}: n={r['samples']} input {r['hypothesis_surface_error_m']*1000:.2f} mm"
              f" -> pretrained one-step {r['pretrained_surface_error_m']*1000:.2f} mm")
    a.output.write_text(json.dumps(result, indent=2))
