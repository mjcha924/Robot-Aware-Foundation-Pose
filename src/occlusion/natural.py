"""Estimate how much of an object is hidden in a real frame, given its ground-truth pose.

`sil` is the object's silhouette rendered at the ground-truth pose (what a clear view would show).
"""

import numpy as np


def occlusion_by_mask(sil, mask):
    """Share of the silhouette missing from the annotated visible-object mask."""
    sil, mask = np.asarray(sil, dtype=bool), np.asarray(mask, dtype=bool)
    total = int(sil.sum())
    if total == 0:
        return float("nan")
    return 1.0 - int((sil & mask).sum()) / total


def occlusion_by_depth(sil, rendered_depth_mm, observed_depth_mm, margin_mm=20):
    """Share of silhouette pixels (with a depth reading) where something sits clearly in front of the model."""
    sil = np.asarray(sil, dtype=bool)
    observed = np.asarray(observed_depth_mm).astype(np.int32)
    valid = sil & (observed > 0)
    if not valid.any():
        return float("nan")
    in_front = observed < np.asarray(rendered_depth_mm).astype(np.int32) - margin_mm
    return int((valid & in_front).sum()) / int(valid.sum())
