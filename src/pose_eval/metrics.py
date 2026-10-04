"""6D pose error metrics over a model point cloud (poses are 4x4 object-in-camera, metres)."""

import numpy as np
from scipy.spatial import ConvexHull, cKDTree
from scipy.spatial.distance import pdist


def _transform(pose, points):
    pose = np.asarray(pose, dtype=float)
    return np.asarray(points, dtype=float) @ pose[:3, :3].T + pose[:3, 3]


def model_diameter(points):
    """Largest distance between two model points (exact; convex-hull shortcut for big clouds)."""
    points = np.asarray(points, dtype=float)
    if len(points) > 3000:
        points = points[ConvexHull(points).vertices]
    return float(pdist(points).max())


def add(estimate, truth, points):
    """Mean distance between corresponding model points placed by the two poses."""
    return float(np.linalg.norm(_transform(estimate, points) - _transform(truth, points), axis=1).mean())


def add_s(estimate, truth, points):
    """Symmetry-tolerant ADD: each estimated point is matched to its closest true-pose point."""
    distances, _ = cKDTree(_transform(truth, points)).query(_transform(estimate, points))
    return float(distances.mean())
