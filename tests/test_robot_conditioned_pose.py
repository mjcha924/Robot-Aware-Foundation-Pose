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
    args.output = str(tmp_path/'resumed'); args.resume = str(tmp_path/'run'/'last.pt'); args.epochs = 2
    run(args)
    assert torch.load(tmp_path/'resumed'/'last.pt', weights_only=True)['epoch'] == 1
