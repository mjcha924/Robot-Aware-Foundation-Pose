import sys
from pathlib import Path
import pytest
import torch
from torch import nn
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from robot_conditioned_pose.model import RobotConditionedRefiner, SetAbstraction
from robot_conditioned_pose.geometry import point_features, axis_angle_matrix, pose_loss, decode_pose


class SmallRefiner(nn.Module):
    def __init__(self):
        super().__init__()
        self.encodeA = nn.Sequential(nn.Conv2d(3, 8, 1), nn.BatchNorm2d(8))
        self.encodeAB = nn.Conv2d(16, 32, 1)
        self.pos_embed = nn.Identity()
        self.trans_head = nn.Linear(32, 3)
        self.rot_head = nn.Linear(32, 3)

    def forward(self, a, b):
        x = self.encodeA(torch.cat((a, b)))
        z = self.encodeAB(torch.cat(x.chunk(2), 1)).flatten(2).transpose(1, 2)
        return self.trans_head(z).mean(1)


def test_equivalence_gradient_and_checkpoint(tmp_path):
    torch.manual_seed(3)
    model = RobotConditionedRefiner(SmallRefiner(), dim=32, counts=(8, 4)).eval()
    a, b, points = torch.randn(2, 3, 4, 4), torch.randn(2, 3, 4, 4), torch.randn(2, 24, 11) * .1
    torch.testing.assert_close(model(a, b, points, bypass=True)['trans'], model.upstream(a, b))
    model.train(); model.set_head_training(False)
    assert not model.upstream.encodeA.training
    model(a, b, points)['trans'].square().sum().backward()
    assert all(p.grad is None for p in model.upstream.encodeA.parameters())
    assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in model.robot_encoder.parameters())
    model.eval()
    torch.save(model.state_dict(), tmp_path / 'm.pt')
    other = RobotConditionedRefiner(SmallRefiner(), dim=32, counts=(8, 4)).eval()
    other.load_state_dict(torch.load(tmp_path / 'm.pt', weights_only=True))
    torch.testing.assert_close(model(a, b, points)['trans'], other(a, b, points)['trans'])


def test_coordinate_and_velocity():
    pose = torch.eye(4); pose[:3, 3] = torch.tensor([1., 2., 3.])
    robot = torch.tensor([[1., 2., 3.]])
    normals = torch.tensor([[1., 0., 0.]])
    f = point_features(robot, normals, robot - .1, .1, pose, torch.zeros(1, 3), normals, .5)
    torch.testing.assert_close(f[0, :3], torch.zeros(3))
    torch.testing.assert_close(f[0, 6:9], torch.full((3,), 2.))
    assert f[1, 10] == 0
    with pytest.raises(ValueError):
        point_features(robot, normals, robot, 0, pose, robot, normals, .5)


def test_sparse_neighbors_and_symmetry():
    sa = SetAbstraction(1, 8, 2, .001)
    _, features = sa(torch.tensor([[[0., 0., 0.], [100., 0., 0.]]]), torch.ones(1, 2, 1))
    assert torch.isfinite(features).all()
    pose = torch.eye(4)[None]
    symmetry = torch.eye(4); symmetry[0, 0] = symmetry[1, 1] = -1
    cad = torch.tensor([[[1., 0., 0.], [0., 1., 0.]]])
    assert pose_loss(symmetry[None], pose, cad, [torch.stack((torch.eye(4), symmetry))]) == 0


def test_zero_rotation_gradients():
    v = torch.zeros(2, 3, requires_grad=True)
    axis_angle_matrix(v).sum().backward()
    assert torch.isfinite(v.grad).all()
    cfg = dict(trans_rep='tracknet', rot_rep='axis_angle', trans_normalizer=.1, rot_normalizer=.2)
    out = dict(trans=torch.zeros(2, 3), rot=torch.zeros(2, 3))
    pose = torch.eye(4).repeat(2, 1, 1)
    torch.testing.assert_close(decode_pose(out, pose, torch.ones(2), cfg), pose)


def test_decode_rotation_matches_upstream_transpose():
    # Upstream: so3_exp_map(tanh(rot) * rot_normalizer).permute(0, 2, 1) @ R_hyp,
    # where so3_exp_map is the standard Rodrigues exp([v]x). Checked on CPU with
    # an independent Rodrigues implementation so no pytorch3d/CUDA is needed.
    from scipy.spatial.transform import Rotation
    cfg = dict(trans_rep='tracknet', rot_rep='axis_angle', trans_normalizer=.1, rot_normalizer=.35)
    rot = torch.tensor([[0., 0., 1.], [.4, -.7, .9]])
    out = dict(trans=torch.zeros(2, 3), rot=rot)
    hypothesis = torch.eye(4).repeat(2, 1, 1)
    hypothesis[1, :3, :3] = torch.as_tensor(Rotation.from_rotvec([.2, .1, -.3]).as_matrix(), dtype=torch.float32)
    v = (rot.tanh() * cfg['rot_normalizer']).double().numpy()
    delta = torch.as_tensor(Rotation.from_rotvec(v).as_matrix(), dtype=torch.float32).transpose(1, 2)
    decoded = decode_pose(out, hypothesis, torch.ones(2), cfg)
    torch.testing.assert_close(decoded[:, :3, :3], delta @ hypothesis[:, :3, :3])


def test_tiny_overfit():
    torch.manual_seed(8); torch.set_num_threads(1)
    m = RobotConditionedRefiner(SmallRefiner(), dim=32, counts=(8, 4))
    m.set_head_training(False)
    tokens, points = torch.randn(2, 8, 32), torch.randn(2, 24, 11) * .1
    target = torch.tensor([[.1, -.2, .3], [-.2, .1, -.1]])
    opt = torch.optim.Adam([p for p in m.parameters() if p.requires_grad], lr=.005)
    errors = []
    for _ in range(50):
        opt.zero_grad()
        loss = (m.forward_tokens(tokens, points)['trans'] - target).square().mean()
        errors.append(loss.item()); loss.backward(); opt.step()
    assert errors[-1] < errors[0] * .15


def test_training_entrypoint(tmp_path):
    import json
    from argparse import Namespace
    from robot_conditioned_pose.trainer import CachedHeads, run
    torch.set_num_threads(1)
    cfg = dict(trans_rep='tracknet', rot_rep='axis_angle', trans_normalizer=.1, rot_normalizer=.2)
    base = CachedHeads()
    for split in ('train', 'val'):
        folder = tmp_path / split; folder.mkdir()
        pose = torch.eye(4)
        sample = dict(visual=torch.randn(4, 512), points=torch.randn(16, 11) * .1,
            hypothesis=pose, target=pose, cad=torch.randn(8, 3) * .1,
            diameter=torch.tensor(.2), symmetries=pose[None])
        torch.save(sample, folder / '0.pt')
        torch.save(base.state_dict(), folder / 'heads.pt')
        (folder / 'manifest.json').write_text(json.dumps(dict(samples=['0.pt'], cfg=cfg,
            upstream_commit='test', weight_sha256='test', sequence_ids=[split],
            geometry_version='exact-vertex-diameter-v1')))
    args = Namespace(train=str(tmp_path/'train'), val=str(tmp_path/'val'), output=str(tmp_path/'run'),
        epochs=1, batch_size=1, warmup_epochs=1, seed=1, device='cpu', mode='motion', lr=1e-4,
        head_lr=1e-5, resume=None)
    run(args)
    ckpt = torch.load(tmp_path/'run'/'best.pt', weights_only=True)
    assert ckpt['epoch'] == 0 and ckpt['best'] >= 0
    try:
        import tensorboard  # noqa: F401
    except ImportError:
        pass  # logging is optional; training above must still succeed
    else:
        assert list((tmp_path/'run'/'tensorboard').glob('events.out.tfevents.*'))
    off = Namespace(**{**vars(args), 'output': str(tmp_path/'no-tb'), 'tensorboard': False})
    run(off)
    assert not (tmp_path/'no-tb'/'tensorboard').exists()
    args.output = str(tmp_path/'resumed'); args.resume = str(tmp_path/'run'/'last.pt'); args.epochs = 2
    run(args)
    assert torch.load(tmp_path/'resumed'/'last.pt', weights_only=True)['epoch'] == 1


def _mixed_points(batch=2, robot=20, cad=12, seed=5):
    g = torch.Generator().manual_seed(seed)
    r = torch.randn(batch, robot, 11, generator=g) * .1
    r[..., 9], r[..., 10] = 1, 1
    c = torch.randn(batch, cad, 11, generator=g) * .1
    c[..., 6:] = 0  # CAD rows: zero velocity, is_robot and validity
    return r, c


def test_cad_only_ignores_robot_rows_and_selects_cad_by_flag():
    from robot_conditioned_pose.model import select_cad_rows
    torch.manual_seed(11)
    model = RobotConditionedRefiner(SmallRefiner(), dim=32, counts=(8, 4), mode='cad-only').eval()
    tokens = torch.randn(2, 6, 32)
    robot, cad = _mixed_points()
    reference = model.forward_tokens(tokens, torch.cat((robot, cad), 1))
    # Only CAD rows reach the encoder, in their original order.
    torch.testing.assert_close(select_cad_rows(torch.cat((robot, cad), 1)), cad)
    torch.testing.assert_close(model.forward_tokens(tokens, cad), reference)
    # Moving, reversing or re-timing robot rows, or placing CAD first, changes nothing.
    moved = robot.clone(); moved[..., :3] += 5; moved[..., 6:9] *= -30
    torch.testing.assert_close(model.forward_tokens(tokens, torch.cat((moved.flip(1), cad), 1)), reference)
    torch.testing.assert_close(model.forward_tokens(tokens, torch.cat((cad, robot), 1)), reference)
    # It is a real geometric branch, unlike the visual bypass.
    assert not torch.allclose(reference['trans'], model.forward_tokens(tokens, cad, bypass=True)['trans'])


def test_cad_only_rejects_ambiguous_inputs():
    from robot_conditioned_pose.model import select_cad_rows
    robot, cad = _mixed_points()
    uneven = torch.cat((robot, cad), 1)
    uneven[0, -1, 9] = 1  # one sample loses a CAD row
    with pytest.raises(ValueError):
        select_cad_rows(uneven)
    with pytest.raises(ValueError):
        select_cad_rows(robot)  # no CAD rows at all
    fractional = torch.cat((robot, cad), 1); fractional[0, 0, 9] = .5
    with pytest.raises(ValueError):
        select_cad_rows(fractional)


def test_cad_only_trains_encoder_and_fusion():
    torch.manual_seed(12)
    model = RobotConditionedRefiner(SmallRefiner(), dim=32, counts=(8, 4), mode='cad-only')
    model.set_head_training(False)
    robot, cad = _mixed_points()
    model.forward_tokens(torch.randn(2, 6, 32), torch.cat((robot, cad), 1))['trans'].square().sum().backward()
    for module in (model.robot_encoder, model.attention):
        assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in module.parameters())
    assert model.residual_scale.grad is not None and model.residual_scale.grad.abs() > 0


def test_existing_modes_unchanged_by_cad_only():
    torch.manual_seed(13)
    tokens = torch.randn(2, 6, 32)
    robot, cad = _mixed_points()
    points = torch.cat((robot, cad), 1)
    geometry = RobotConditionedRefiner(SmallRefiner(), dim=32, counts=(8, 4), mode='geometry').eval()
    zeroed = points.clone(); zeroed[..., 6:9] = 0; zeroed[..., 10] = 0
    memory = geometry.robot_norm(geometry.robot_encoder(zeroed))
    extra, _ = geometry.attention(geometry.visual_norm(tokens), memory, memory, need_weights=False)
    fused = tokens + geometry.residual_scale * extra
    torch.testing.assert_close(geometry.forward_tokens(tokens, points)['trans'], geometry.upstream.trans_head(fused).mean(1))
    visual = RobotConditionedRefiner(SmallRefiner(), dim=32, counts=(8, 4), mode='visual').eval()
    torch.testing.assert_close(visual.forward_tokens(tokens, points)['trans'], visual.upstream.trans_head(tokens).mean(1))


def test_cad_only_checkpoint_mode_roundtrip(tmp_path):
    import json
    from argparse import Namespace
    from robot_conditioned_pose.model import MODES
    from robot_conditioned_pose.trainer import CachedHeads, run
    assert 'cad-only' in MODES
    torch.set_num_threads(1)
    cfg = dict(trans_rep='tracknet', rot_rep='axis_angle', trans_normalizer=.1, rot_normalizer=.2)
    robot, cad = _mixed_points(batch=1, robot=24, cad=16)
    for split in ('train', 'val'):
        folder = tmp_path / split; folder.mkdir()
        pose = torch.eye(4)
        torch.save(dict(visual=torch.randn(4, 512), points=torch.cat((robot, cad), 1)[0],
            hypothesis=pose, target=pose, cad=torch.randn(8, 3) * .1, diameter=torch.tensor(.2),
            symmetries=pose[None]), folder / '0.pt')
        torch.save(CachedHeads().state_dict(), folder / 'heads.pt')
        (folder / 'manifest.json').write_text(json.dumps(dict(samples=['0.pt'], cfg=cfg,
            upstream_commit='test', weight_sha256='test', sequence_ids=[split],
            geometry_version='exact-vertex-diameter-v1')))
    args = Namespace(train=str(tmp_path/'train'), val=str(tmp_path/'val'), output=str(tmp_path/'run'),
        epochs=1, batch_size=1, warmup_epochs=0, seed=1, device='cpu', mode='cad-only', lr=1e-4,
        head_lr=1e-5, resume=None, tensorboard=False)
    run(args)
    saved = torch.load(tmp_path/'run'/'best.pt', weights_only=True)
    assert saved['mode'] == 'cad-only'
    restored = RobotConditionedRefiner(CachedHeads(), mode=saved['mode'])
    restored.load_state_dict(saved['model'])
    record = json.loads((tmp_path/'run'/'run.json').read_text())
    assert record['mode'] == 'cad-only' and 'source_commit' in record
