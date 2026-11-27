"""Line-by-line Python port of upstream mycpp.cluster_poses (mycpp/src/app/pybind_api.cpp).

The native extension is not built on this machine (no Eigen/Boost/pybind11).
Registration only uses it once, to de-duplicate the fixed rotation grid. The
port keeps the greedy order, the float32 arithmetic and the strict comparisons.
"""
import sys
import types
import numpy as np


def _geodesic(r1, r2):
    c = np.float32((np.trace(r1 @ r2.T) - np.float32(1)) / np.float32(2))
    return np.float32(np.arccos(np.clip(c, np.float32(-1), np.float32(1))))


def cluster_poses(angle_diff, dist_diff, poses_in, symmetry_tfs):
    poses = [np.asarray(p, dtype=np.float32) for p in poses_in]
    tfs = [np.asarray(t, dtype=np.float32) for t in symmetry_tfs]
    out = [poses[0]]
    thres = np.float32(angle_diff/180.0*np.pi)
    for cur in poses[1:]:
        isnew = True
        for cluster in out:
            if np.linalg.norm(cluster[:3, 3]-cur[:3, 3]) >= dist_diff:
                continue
            for tf in tfs:
                if _geodesic((cur @ tf)[:3, :3], cluster[:3, :3]) < thres:
                    isnew = False
                    break
            if not isnew:
                break
        if isnew:
            out.append(cur)
    return out


def install():
    """Provide `mycpp` for upstream imports only when the native module is missing."""
    try:
        import mycpp
        if hasattr(mycpp, 'cluster_poses'):
            return 'native'
    except ImportError:
        pass
    module = types.ModuleType('mycpp')
    module.cluster_poses = cluster_poses
    module.__doc__ = __doc__
    sys.modules['mycpp'] = module
    return 'python-port'
