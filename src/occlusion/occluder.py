"""Pick a rectangular occluder that hides a chosen fraction of an object mask.

Pure numpy. The block enters from one side of the object's bounding box and spans the
whole box (plus a margin) in the other direction, so the number of object pixels it hides
depends only on how far it reaches in. That makes the achieved fraction exact and
nested: a smaller target always gives a superset block on the same side.
"""

import numpy as np

SIDES = ("left", "right", "top", "bottom")


def visible_fraction(obj_mask, occ):
    """Fraction of object pixels not covered by `occ`."""
    obj = np.asarray(obj_mask, dtype=bool)
    total = int(obj.sum())
    if total == 0:
        raise ValueError("object mask is empty")
    return int((obj & ~np.asarray(occ, dtype=bool)).sum()) / total


def make_block(obj_mask, target_visible, side, margin_px=8, tol=0.01):
    """Return (occ, achieved): a block hiding the object down to ~`target_visible`.

    `achieved` is measured on the returned block, not the request. Raises ValueError when
    the object's pixel layout cannot get within `tol` of the target.
    """
    obj = np.asarray(obj_mask, dtype=bool)
    if side not in SIDES:
        raise ValueError(f"side must be one of {SIDES}, got {side!r}")
    if not 0.0 <= target_visible <= 1.0:
        raise ValueError("target_visible must be within [0, 1]")
    total = int(obj.sum())
    if total == 0:
        raise ValueError("object mask is empty")

    height, width = obj.shape
    ys, xs = np.nonzero(obj)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1

    if side in ("left", "right"):
        counts = obj[:, x0:x1].sum(axis=0)
    else:
        counts = obj[y0:y1, :].sum(axis=1)
    if side in ("right", "bottom"):
        counts = counts[::-1]
    visible = 1.0 - np.concatenate([[0], np.cumsum(counts)]) / total
    depth = int(np.argmin(np.abs(visible - target_visible)))

    occ = np.zeros_like(obj)
    if depth > 0:
        rows = slice(max(y0 - margin_px, 0), min(y1 + margin_px, height))
        cols = slice(max(x0 - margin_px, 0), min(x1 + margin_px, width))
        if side == "left":
            occ[rows, max(x0 - margin_px, 0):x0 + depth] = True
        elif side == "right":
            occ[rows, x1 - depth:min(x1 + margin_px, width)] = True
        elif side == "top":
            occ[max(y0 - margin_px, 0):y0 + depth, cols] = True
        else:
            occ[y1 - depth:min(y1 + margin_px, height), cols] = True

    achieved = visible_fraction(obj, occ)
    if abs(achieved - target_visible) > tol:
        raise ValueError(
            f"cannot reach visible fraction {target_visible:.3f} within {tol}: best {achieved:.3f}"
        )
    return occ, achieved
