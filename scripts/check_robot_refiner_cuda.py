#!/usr/bin/env python3
"""CUDA gate: real checkpoint equivalence, pose decoder parity, backward."""
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', help='Optional trained checkpoint to verify loading')
    args = p.parse_args()
    import torch
    from robot_conditioned_pose.upstream import load_upstream
    from robot_conditioned_pose.model import RobotConditionedRefiner
    from robot_conditioned_pose.geometry import decode_pose
    from robot_conditioned_pose.trainer import CachedHeads
    from robot_conditioned_pose.contracts import check_checkpoint
    predictor, cfg = load_upstream(ROOT / 'third_party/FoundationPose')
    model = RobotConditionedRefiner(predictor.model).cuda().eval()
    h, w = cfg['input_resize']
    a = torch.randn(2, cfg['c_in'], h, w, device='cuda')
    b = torch.randn_like(a)
    points = torch.randn(2, 128, 11, device='cuda') * .1
    with torch.no_grad():
        original = predictor.model(a, b)
        bypass = model(a, b, points, bypass=True)
        for k in original:
            torch.testing.assert_close(original[k], bypass[k], atol=1e-6, rtol=1e-5)
        heads = CachedHeads().cuda().eval()
        heads.load_state_dict({k: v for k, v in predictor.model.state_dict().items()
                               if k.startswith(('trans_head.', 'rot_head.'))}, strict=True)
        tokens = model.encode_visual(a, b)
        torch.testing.assert_close(heads.trans_head(tokens).mean(1), original['trans'])
        from Utils import so3_exp_map, egocentric_delta_pose_to_pose
        pose = torch.eye(4, device='cuda').repeat(2, 1, 1)
        diameter = torch.tensor([.1, .2], device='cuda')
        t = original['trans']
        t = t * diameter[:, None] / 2 if cfg.get('normalize_xyz', False) else t.tanh() * torch.as_tensor(cfg['trans_normalizer'], device='cuda')
        r = so3_exp_map(original['rot'].tanh() * cfg['rot_normalizer']).transpose(1, 2)
        expected = egocentric_delta_pose_to_pose(pose, t, r)
        torch.testing.assert_close(decode_pose(original, pose, diameter, cfg), expected)
    if args.checkpoint:
        saved = torch.load(args.checkpoint, map_location='cuda', weights_only=True)
        check_checkpoint(saved, cfg)
        # Training checkpoints omit the frozen encoder; only those keys may be missing.
        missing, unexpected = model.load_state_dict(saved['model'], strict=False)
        if unexpected or any(not k.startswith(('upstream.encodeA.', 'upstream.encodeAB.', 'upstream.pos_embed.')) for k in missing):
            raise ValueError((missing, unexpected))
        model.mode = saved['mode']
    model.train(); model.set_head_training(model.mode == 'visual')
    result = model(a, b, points)
    sum(v.square().mean() for v in result.values()).backward()
    if model.mode != 'visual':
        assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in model.robot_encoder.parameters())
    assert all(p.grad is None for p in model.upstream.encodeA.parameters())
    print('PASS: upstream equivalence, cached heads, pose decoder and gradient flow')
