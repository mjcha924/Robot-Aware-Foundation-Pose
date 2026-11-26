"""Measured-joint FK versus independent simulator link poses (audit only).

The simulator link transforms are used here as the *reference* and nowhere
else; nothing in this module feeds model inputs. All comparisons are written
with plain numpy so the expected values do not reuse point_features.
"""
import numpy as np
from scipy.spatial.transform import Rotation

# Investigation thresholds from docs/OMY_NEXT_VALIDATION_HANDOFF.md (not a data spec).
THRESHOLDS = dict(position_p95_mm=1.0, position_max_mm=5.0, rotation_p95_deg=.5, rotation_max_deg=2.,
                  surface_p95_mm=1.0, surface_max_mm=5.0, velocity_p95_mps=.02, velocity_max_mps=.1)


def transform_points(pose, points):
    pose = np.asarray(pose, dtype=np.float64)
    return points @ pose[:3, :3].T + pose[:3, 3]


def rotation_angle_deg(a, b):
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    return float(np.rad2deg(Rotation.from_matrix(a[:3, :3] @ b[:3, :3].T).magnitude()))


def link_errors(predicted, reference):
    """Per-link translation (m) and rotation (deg) for links present in both."""
    out = {}
    for name in sorted(set(predicted) & set(reference)):
        p, r = np.asarray(predicted[name], dtype=np.float64), np.asarray(reference[name], dtype=np.float64)
        out[name] = (float(np.linalg.norm(p[:3, 3] - r[:3, 3])), rotation_angle_deg(p, r))
    return out


def surface_points(links, canonical, camera_inv):
    """Camera-frame surface points: identical canonical samples per link, sorted by name."""
    return np.concatenate([transform_points(camera_inv @ np.asarray(links[name], dtype=np.float64),
                                            canonical[name]['points_link_m']) for name in sorted(canonical)])


def interval_velocity(now_links, prev_links, canonical, camera_inv_now, dt):
    """Interval-mean surface velocity (m/s); both instants in the CURRENT camera frame."""
    if not dt > 0:
        raise ValueError('dt must be positive')
    return (surface_points(now_links, canonical, camera_inv_now)
            - surface_points(prev_links, canonical, camera_inv_now)) / dt


def stats(values):
    v = np.asarray(values, dtype=np.float64).ravel()
    finite = v[np.isfinite(v)]
    if not len(finite):
        return dict(count=0, nonfinite=int(len(v)))
    return dict(count=int(len(finite)), nonfinite=int(len(v) - len(finite)), mean=float(finite.mean()),
                median=float(np.median(finite)), p95=float(np.percentile(finite, 95)), max=float(finite.max()))


def investigation_flags(position_mm, rotation_deg, surface_mm, velocity_mps):
    t, flags = THRESHOLDS, []
    for label, values, p95, peak in (('position_mm', position_mm, t['position_p95_mm'], t['position_max_mm']),
                                     ('rotation_deg', rotation_deg, t['rotation_p95_deg'], t['rotation_max_deg']),
                                     ('surface_mm', surface_mm, t['surface_p95_mm'], t['surface_max_mm']),
                                     ('velocity_mps', velocity_mps, t['velocity_p95_mps'], t['velocity_max_mps'])):
        s = stats(values)
        if s['count'] == 0:
            flags.append(f'{label}: no finite values'); continue
        if s['p95'] > p95: flags.append(f"{label}: p95 {s['p95']:.4g} > {p95}")
        if s['max'] > peak: flags.append(f"{label}: max {s['max']:.4g} > {peak}")
    return flags
