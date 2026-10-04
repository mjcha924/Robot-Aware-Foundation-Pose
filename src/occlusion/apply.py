"""Paint an occluder mask into an RGB image and its aligned uint16-millimetre depth map."""

import numpy as np

DEPTH_MODES = ("zero", "front")


def apply_occlusion(rgb, depth, occ, color=(0, 0, 0), depth_mode="zero",
                    front_offset_mm=100, obj_mask=None):
    """Return copies of (rgb, depth) with the `occ` region replaced.

    depth_mode "zero": depth 0 inside the block (the sensor saw nothing there).
    depth_mode "front": depth inside the block is the object's median valid depth minus
    `front_offset_mm`, as if a solid object sat in front of it. Needs `obj_mask`.
    """
    occ = np.asarray(occ, dtype=bool)
    if depth_mode not in DEPTH_MODES:
        raise ValueError(f"depth_mode must be one of {DEPTH_MODES}, got {depth_mode!r}")
    if rgb.shape[:2] != occ.shape or depth.shape != occ.shape:
        raise ValueError("rgb, depth and occ must share the same height and width")

    out_rgb = rgb.copy()
    out_rgb[occ] = np.asarray(color, dtype=rgb.dtype)

    out_depth = depth.copy()
    if depth_mode == "zero":
        out_depth[occ] = 0
    else:
        if obj_mask is None:
            raise ValueError("depth_mode 'front' needs obj_mask")
        valid = np.asarray(obj_mask, dtype=bool) & (depth > 0)
        if not valid.any():
            raise ValueError("object has no valid depth to place the block in front of")
        front = int(np.median(depth[valid])) - int(front_offset_mm)
        out_depth[occ] = max(front, 1)
    return out_rgb, out_depth
