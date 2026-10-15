"""Statistics for the side-crossed occlusion experiment (same frames, every block side)."""

import numpy as np


def variance_shares(matrix):
    """Split the variance of a frames x sides matrix into frame, side and residual (interaction) shares.

    Two-way decomposition without replication. A constant matrix has no variance to explain.
    """
    values = np.asarray(matrix, dtype=float)
    grand = values.mean()
    frame_means = values.mean(axis=1, keepdims=True)
    side_means = values.mean(axis=0, keepdims=True)
    ss_frame = values.shape[1] * float(((frame_means - grand) ** 2).sum())
    ss_side = values.shape[0] * float(((side_means - grand) ** 2).sum())
    ss_total = float(((values - grand) ** 2).sum())
    if ss_total <= 1e-12:
        return {"frame": 0.0, "side": 0.0, "residual": 0.0}
    frame, side = ss_frame / ss_total, ss_side / ss_total
    return {"frame": frame, "side": side, "residual": max(0.0, 1.0 - frame - side)}


def fail_count_histogram(fails):
    """Number of frames (rows) that fail on exactly k sides (columns), for k = 0..n_sides."""
    fails = np.asarray(fails, dtype=bool)
    counts = fails.sum(axis=1)
    return {k: int((counts == k).sum()) for k in range(fails.shape[1] + 1)}
