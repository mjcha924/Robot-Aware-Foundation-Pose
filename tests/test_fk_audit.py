"""Synthetic regressions for the FK audit: the reference chain is composed by hand,
not with omy_kinematics, so agreement is not a self-check."""
import sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src')); sys.path.insert(0, str(ROOT / 'scripts'))
from omy_kinematics import forward_kinematics
from robot_conditioned_pose.fk_audit import (link_errors, surface_points, interval_velocity,
                                             investigation_flags, stats)

R0 = Rotation.from_euler('x', 30, degrees=True)  # non-identity joint frame exercises quaternion order
W, X, Y, Z = R0.as_quat(scalar_first=True)
INVENTORY = {'joints': [
    {'path': '/World/Robot/OMY/joints/j1', 'attributes': {'physics:axis': 'Z', 'physics:localPos0': '(0, 0, 0.1)',
     'physics:localPos1': '(0, 0, 0)', 'physics:localRot0': '(1, 0, 0, 0)', 'physics:localRot1': '(1, 0, 0, 0)'},
     'relationships': {'physics:body0': ['/World/Robot/OMY/world'], 'physics:body1': ['/World/Robot/OMY/link1']}},
    {'path': '/World/Robot/OMY/joints/j2', 'attributes': {'physics:axis': 'Y', 'physics:localPos0': '(0, 0.05, 0.2)',
     'physics:localPos1': '(0, 0, 0)', 'physics:localRot0': f'({W}, {X}, {Y}, {Z})', 'physics:localRot1': '(1, 0, 0, 0)'},
     'relationships': {'physics:body0': ['/World/Robot/OMY/link1'], 'physics:body1': ['/World/Robot/OMY/link2']}}]}
NAMES = ('j1', 'j2')


def T(rotation=None, translation=(0, 0, 0)):
    t = np.eye(4); t[:3, 3] = translation
    if rotation is not None: t[:3, :3] = rotation.as_matrix()
    return t


def reference_links(q, base):
    link1 = base @ T(None, (0, 0, .1)) @ T(Rotation.from_euler('z', q[0]))
    link2 = link1 @ T(R0, (0, .05, .2)) @ T(Rotation.from_euler('y', q[1]))
    return {'world': base, 'link1': link1, 'link2': link2}


rng = np.random.default_rng(0)
CANONICAL = {k: {'points_link_m': rng.normal(scale=.05, size=(20, 3))} for k in ('link1', 'link2')}
BASE = T(Rotation.from_euler('z', .3), (.1, -.2, .9))
CAMERA = T(Rotation.from_euler('xyz', (2.4, .1, -.4)), (.6, -.6, 2.5))


def fk(q, base=BASE):
    return forward_kinematics(INVENTORY, NAMES, q, base)


def flags_for(fk_links, ref_links, fk_prev=None, ref_prev=None, dt=1/30, camera=CAMERA):
    cam_inv = np.linalg.inv(camera)
    errs = link_errors({k: fk_links[k] for k in CANONICAL}, ref_links)
    pos = [e[0] * 1000 for e in errs.values()]; rot = [e[1] for e in errs.values()]
    surf = np.linalg.norm(surface_points(fk_links, CANONICAL, cam_inv) - surface_points(ref_links, CANONICAL, cam_inv), axis=1) * 1000
    vel = np.zeros(1)
    if fk_prev is not None:
        vel = np.linalg.norm(interval_velocity(fk_links, fk_prev, CANONICAL, cam_inv, dt)
                             - interval_velocity(ref_links, ref_prev, CANONICAL, cam_inv, dt), axis=1)
    return investigation_flags(pos, rot, surf, vel)


def test_fk_matches_hand_composed_chain():
    for q in ([0., 0.], [.7, -1.1], [-2.5, .4]):
        errs = link_errors(fk(q), reference_links(q, BASE))
        assert max(e[0] for e in errs.values()) < 1e-12 and max(e[1] for e in errs.values()) < 1e-6
    assert flags_for(fk([.7, -1.1]), reference_links([.7, -1.1], BASE)) == []


def test_static_robot_has_no_spurious_velocity_even_with_camera_motion():
    q = [.4, .2]
    moved_camera = CAMERA @ T(Rotation.from_euler('y', .2), (.05, 0, 0))
    v = interval_velocity(fk(q), fk(q), CANONICAL, np.linalg.inv(moved_camera), 1/30)
    assert np.abs(v).max() < 1e-12  # both instants expressed in the current camera frame


def test_rotation_and_base_motion_velocity_matches_reference():
    q0, q1 = [.40, .20], [.43, .17]
    base1 = BASE @ T(None, (.002, 0, 0))  # base moves 2 mm in one frame
    fk_v = interval_velocity(fk(q1, base1), fk(q0), CANONICAL, np.linalg.inv(CAMERA), 1/30)
    ref_v = interval_velocity(reference_links(q1, base1), reference_links(q0, BASE), CANONICAL, np.linalg.inv(CAMERA), 1/30)
    assert np.linalg.norm(fk_v - ref_v, axis=1).max() < 1e-9 and np.linalg.norm(ref_v, axis=1).min() > 1e-3
    assert flags_for(fk(q1, base1), reference_links(q1, base1), fk(q0), reference_links(q0, BASE)) == []


def test_degree_unit_error_is_flagged():
    q = np.array([.4, .2])
    assert flags_for(fk(np.rad2deg(q)), reference_links(q, BASE))


def test_sign_flip_is_flagged():
    q = [.4, .2]
    assert flags_for(fk([.4, -.2]), reference_links(q, BASE))


def test_one_frame_delay_is_flagged_and_localized():
    qs = [[.40 + .02 * k, .20 - .03 * k] for k in range(3)]
    delayed_now, delayed_prev = fk(qs[1]), fk(qs[0])  # measured state lags one frame
    assert flags_for(delayed_now, reference_links(qs[2], BASE), delayed_prev, reference_links(qs[1], BASE))
    cam_inv = np.linalg.inv(CAMERA)
    shift = [np.linalg.norm(surface_points(delayed_now, CANONICAL, cam_inv)
                            - surface_points(reference_links(qs[k], BASE), CANONICAL, cam_inv), axis=1).mean() for k in (1, 2)]
    assert shift[0] < 1e-9 < shift[1]  # the audit's shift diagnosis points at the previous frame


def test_velocity_time_unit_error_is_flagged():
    q0, q1 = [.40, .20], [.43, .17]
    cam_inv = np.linalg.inv(CAMERA)
    wrong = interval_velocity(fk(q1), fk(q0), CANONICAL, cam_inv, 1000 / 30)  # dt in ms
    right = interval_velocity(reference_links(q1, BASE), reference_links(q0, BASE), CANONICAL, cam_inv, 1/30)
    assert investigation_flags([0.], [0.], [0.], np.linalg.norm(wrong - right, axis=1))


def test_stats_counts_nonfinite():
    s = stats([1., np.nan, 3.])
    assert s['count'] == 2 and s['nonfinite'] == 1 and s['max'] == 3.
