"""Inference-only robot-state mismatch controls change only the robot input."""
import json
import sys
from pathlib import Path
import pytest
import torch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tests'))
from robot_conditioned_pose.omy_sequence import OmySequence
from robot_conditioned_pose.robot_perturbation import RobotPerturbation, parse
from test_omy_training_integration import fixture


def reader_with(tmp_path, spec, donor=None):
    reader = OmySequence(tmp_path)
    reader.set_robot_perturbation(RobotPerturbation(spec, 'seq', reader.joint_names, donor))
    return reader


@pytest.fixture
def seq(tmp_path):
    root = tmp_path/'seq'; root.mkdir(); fixture(root); return root


def pts(reader, i):
    return reader.points(i, torch.eye(4), 1.)


def test_none_matches_measured(seq):
    torch.testing.assert_close(pts(reader_with(seq, 'none'), 1), pts(OmySequence(seq), 1))


def test_zero_velocity_keeps_positions(seq):
    clean, zero = pts(OmySequence(seq), 1), pts(reader_with(seq, 'zero-velocity'), 1)
    assert torch.count_nonzero(clean[:512, 6:9]) > 0
    assert torch.all(zero[:512, 6:9] == 0)
    torch.testing.assert_close(zero[:, :6], clean[:, :6])
    torch.testing.assert_close(zero[512:], clean[512:])  # CAD rows untouched


def test_delay_uses_earlier_state(seq):
    clean = OmySequence(seq)
    torch.testing.assert_close(pts(reader_with(seq, 'delay-1'), 1), pts(clean, 0))
    # Before the start only the stored previous state exists: frozen, zero velocity.
    early = pts(reader_with(seq, 'delay-5'), 1)
    assert torch.all(early[:512, 6:9] == 0)


def test_freeze_first(seq):
    clean, frozen = OmySequence(seq), reader_with(seq, 'freeze-first')
    torch.testing.assert_close(pts(frozen, 0), pts(clean, 0))
    later = pts(frozen, 1)
    torch.testing.assert_close(later[:512, :3], pts(clean, 0)[:512, :3])
    assert torch.all(later[:512, 6:9] == 0)


def test_swap_uses_donor_robot(seq, tmp_path):
    donor = tmp_path/'donor'; donor.mkdir(); fixture(donor)
    path = donor/'robot_observations.jsonl'
    rows = [json.loads(s) for s in path.read_text().splitlines()]
    for r in rows: r['joint_positions'] = [r['joint_positions'][0]+.7]
    path.write_text('\n'.join(map(json.dumps, rows)))
    swapped, clean = pts(reader_with(seq, 'swap-sequence', donor), 1), pts(OmySequence(seq), 1)
    torch.testing.assert_close(swapped, pts(OmySequence(donor), 1))
    assert not torch.allclose(swapped[:512, :3], clean[:512, :3])
    with pytest.raises(ValueError, match='different'):
        RobotPerturbation('swap-sequence', 'seq', ('j',), seq)


def test_joint_noise_deterministic_and_restorable(seq):
    a, b = reader_with(seq, 'joint-noise-0.05'), reader_with(seq, 'joint-noise-0.05')
    torch.testing.assert_close(pts(a, 1), pts(b, 1))
    clean = pts(OmySequence(seq), 1)
    assert not torch.allclose(pts(a, 1)[:512, :3], clean[:512, :3])
    a.set_robot_perturbation(None)
    torch.testing.assert_close(pts(a, 1), clean)


def test_camera_and_timing_unchanged(seq):
    reader = reader_with(seq, 'delay-1')
    assert reader.frames[1]['T_world_camera'] == OmySequence(seq).frames[1]['T_world_camera']
    assert reader._surface_pair(1)[3] == OmySequence(seq)._surface_pair(1)[3]


@pytest.mark.parametrize('spec', ['delay-0', 'delay-1.5', 'joint-noise-0', 'shuffle', 'joint-noise-x'])
def test_parse_rejects(spec):
    with pytest.raises(ValueError): parse(spec)


def test_donor_only_for_swap(seq):
    with pytest.raises(ValueError, match='donor'):
        RobotPerturbation('delay-3', 'seq', ('j',), seq)
    with pytest.raises(ValueError, match='donor'):
        RobotPerturbation('swap-sequence', 'seq', ('j',))


def test_cluster_poses_port_matches_reference_semantics():
    import numpy as np
    from scipy.spatial.transform import Rotation
    from robot_conditioned_pose.mycpp_port import cluster_poses
    def rot(deg, axis='z'):
        m = np.eye(4); m[:3, :3] = Rotation.from_euler(axis, deg, degrees=True).as_matrix(); return m
    poses = [rot(0), rot(10), rot(29.9), rot(30.1), rot(45), rot(90), rot(5, 'x')]
    out = cluster_poses(30, 99999, poses, [np.eye(4)])
    # Greedy: 10, 29.9 merge into 0; 30.1 new; 45 merges into 30.1; 90 new; x5 merges into 0.
    assert [round(float(np.degrees(Rotation.from_matrix(o[:3, :3].astype(float)).magnitude()))) for o in out] == [0, 30, 90]
    # A symmetry makes the 180-degree pose a duplicate.
    assert len(cluster_poses(30, 99999, [rot(0), rot(180)], [np.eye(4), rot(180)])) == 1
    # Translation gate: far-apart poses never merge.
    far = rot(0); far[:3, 3] = [1, 0, 0]
    assert len(cluster_poses(30, .5, [rot(0), far], [np.eye(4)])) == 2
