"""Assemble one occluded frame at a requested visibility level."""

import zlib

from occlusion.apply import apply_occlusion
from occlusion.occluder import SIDES, make_block, visible_fraction


def choose_side(frame_id, seed):
    """Deterministic side for a frame; every level of that frame reuses it."""
    return SIDES[zlib.crc32(f"{seed}:{frame_id}".encode()) % len(SIDES)]


def build_level(rgb, depth, obj_mask, target_visible, side, color=(0, 0, 0),
                depth_mode="zero", front_offset_mm=100, margin_px=8, tol=0.01):
    """Return the occluded rgb/depth, the block, the visible-object mask and the measured fraction."""
    if target_visible >= 1.0:
        occ = obj_mask & False
        out_rgb, out_depth = rgb.copy(), depth.copy()
    else:
        occ, _ = make_block(obj_mask, target_visible, side, margin_px=margin_px, tol=tol)
        out_rgb, out_depth = apply_occlusion(
            rgb, depth, occ, color=color, depth_mode=depth_mode,
            front_offset_mm=front_offset_mm, obj_mask=obj_mask,
        )
    return {
        "rgb": out_rgb,
        "depth": out_depth,
        "occ": occ,
        "visible_mask": obj_mask & ~occ,
        "achieved": visible_fraction(obj_mask, occ),
        "side": side,
        "target": target_visible,
    }
