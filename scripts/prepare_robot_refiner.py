#!/usr/bin/env python3
"""GPU: validated Isaac exports -> fixed-perturbation frozen-visual-feature cache."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('sequences', type=Path, nargs='+')
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--stride', type=int, default=5)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--translation-std', type=float, default=.01)
    p.add_argument('--rotation-std-deg', type=float, default=10)
    a = p.parse_args()
    if a.stride < 1 or a.translation_std < 0 or a.rotation_std_deg < 0:
        p.error('invalid sampling/perturbation settings')
    from validate_isaac_export import validate_sequence
    for seq in a.sequences:
        errors = validate_sequence(seq)
        if errors:
            raise ValueError(str(errors))
    import numpy as np
    import torch
    from robot_conditioned_pose.geometry import axis_angle_matrix
    from robot_conditioned_pose.model import RobotConditionedRefiner
    from robot_conditioned_pose.upstream import load_upstream, RenderBridge
    torch.manual_seed(a.seed)
    np.random.seed(a.seed)
    a.output.mkdir(parents=True, exist_ok=False)
    predictor, cfg = load_upstream(ROOT / 'third_party/FoundationPose')
    model = RobotConditionedRefiner(predictor.model).cuda().eval()
    weight = Path(cfg['ckpt_dir'])
    meta = dict(format_version=1, cfg=cfg, sequence_ids=[], samples=[],
        upstream_commit=subprocess.check_output(['git', '-C', str(ROOT / 'third_party/FoundationPose'), 'rev-parse', 'HEAD'], text=True).strip(),
        weight_sha256=hashlib.sha256(weight.read_bytes()).hexdigest(), seed=a.seed,
        translation_std_m=a.translation_std, rotation_std_deg=a.rotation_std_deg,
        provenance='ideal simulator link poses; no encoder-noise/FK experiment',
        symmetry_note='identity unless mesh.symmetries_mesh explicitly supplied')
    count = 0
    from robot_conditioned_pose.sequence import IsaacSequence
    for seq in a.sequences:
        reader = IsaacSequence(seq)
        # Content identity catches copied sequences at different paths.
        frames_path = seq / reader.manifest['frames_file']
        meta['sequence_ids'].append(hashlib.sha256(frames_path.read_bytes()).hexdigest())
        bridge = RenderBridge(predictor, reader.mesh)
        for i in range(0, len(reader.frames), a.stride):
            gt = reader.target(i)
            hypothesis = gt.clone()
            hypothesis[:3, :3] = axis_angle_matrix(torch.randn(1, 3) * np.deg2rad(a.rotation_std_deg))[0] @ gt[:3, :3]
            hypothesis[:3, 3] += torch.randn(3) * a.translation_std
            if hypothesis[2, 3] <= 0:
                continue
            points = reader.points(i, hypothesis, bridge.diameter)
            rgb, depth = reader.observation(i)
            va, vb = bridge.pair(rgb, depth, reader.K, hypothesis[None].cuda())
            visual = model.encode_visual(va, vb).cpu()[0]
            sample = dict(visual=visual, points=points, hypothesis=hypothesis, target=gt,
                cad=reader.cad, diameter=torch.tensor(bridge.diameter), symmetries=reader.symmetries)
            name = f'{count:07d}.pt'; torch.save(sample, a.output / name)
            meta['samples'].append(name); count += 1
    if not count:
        raise ValueError('no samples generated')
    torch.save({k: v.cpu() for k, v in predictor.model.state_dict().items()
                if k.startswith(('trans_head.', 'rot_head.'))}, a.output / 'heads.pt')
    (a.output / 'manifest.json').write_text(json.dumps(meta, indent=2))
    print(f'Prepared {count} examples in {a.output}')

if __name__ == '__main__':
    main()
