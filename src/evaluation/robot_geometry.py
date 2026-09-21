"""Fixed acceptance gates for robot geometry projection, not pose estimation."""

import math


ROBOT_PROJECTION_GATES = {
    "min_visible_projection_iou": 0.95,
    "min_robot_pixel_coverage": 0.98,
    "max_depth_p95_abs_error_m": 0.01,
}


def robot_projection_passes(rows):
    if not rows:
        return False
    for row in rows:
        values = [row.get(key) for key in (
            "robot_pixels", "visible_projection_iou", "robot_pixel_coverage", "depth_p95_abs_error_m")]
        if any(not isinstance(value, (int, float)) or isinstance(value, bool)
               or not math.isfinite(value) for value in values):
            return False
        pixels, iou, coverage, depth_error = values
        if not (pixels > 0 and 0.95 <= iou <= 1.0 and 0.98 <= coverage <= 1.0
                and 0.0 <= depth_error <= 0.01):
            return False
    return True
