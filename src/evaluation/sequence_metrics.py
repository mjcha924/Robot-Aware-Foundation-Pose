"""Motion and visibility diagnostics for synchronized simulator captures."""

from __future__ import annotations

import math
import statistics

from .pose_metrics import evaluate_records, rotation_error_deg, summarize, translation_error_m


def require_sweep_tracking(frames: list[dict], limit_m: float) -> float:
    """Reject inaccurate or missing tool tracking before publishing a capture."""
    if not math.isfinite(limit_m) or limit_m <= 0:
        raise ValueError("tool command error limit must be finite and positive")
    if not frames or any("effector_command_error_m" not in frame for frame in frames):
        raise ValueError("sweep requires command error for every frame")
    errors = [float(frame["effector_command_error_m"]) for frame in frames]
    if any(not math.isfinite(error) or error < 0 for error in errors):
        raise ValueError("tool command errors must be finite and non-negative")
    maximum = max(errors)
    if maximum > limit_m:
        raise ValueError(f"sweep command error {maximum:.4f} m exceeds {limit_m:.4f} m")
    return maximum


def analyze_sequence(frames: list[dict], records: list[dict] | None = None) -> dict:
    if not frames:
        raise ValueError("sequence contains no frames")
    ids = [frame["frame_id"] for frame in frames]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate sequence frame IDs")
    timestamps = [float(frame["timestamp_s"]) for frame in frames]
    if not all(math.isfinite(value) for value in timestamps) or any(
        right <= left for left, right in zip(timestamps, timestamps[1:])
    ):
        raise ValueError("sequence timestamps must be finite and strictly increasing")
    result = {"frame_count": len(frames), "duration_s": timestamps[-1] - timestamps[0], "motion": {}}
    for name in ("camera", "effector", "object_gt"):
        key = f"T_world_{name}"
        if not all(key in frame for frame in frames):
            continue
        poses = [frame[key] for frame in frames]
        motion = {
            "translation_from_first_m": summarize(translation_error_m(pose, poses[0]) for pose in poses),
            "rotation_from_first_deg": summarize(rotation_error_deg(pose, poses[0]) for pose in poses),
        }
        if len(poses) > 1:
            motion["step_translation_m"] = summarize(
                translation_error_m(right, left) for left, right in zip(poses, poses[1:])
            )
        result["motion"][name] = motion
    if all("effector_command_error_m" in frame for frame in frames):
        result["effector_command_error_m"] = summarize(frame["effector_command_error_m"] for frame in frames)

    ratios = None
    if all("visible_mask_pixels" in frame for frame in frames):
        pixels = [frame["visible_mask_pixels"] for frame in frames]
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in pixels):
            raise ValueError("visible_mask_pixels must be non-negative integers")
        # The initial stationary phase provides a less noisy reference than
        # one image. For older captures use the first frame only.
        reference = [frame["visible_mask_pixels"] for frame in frames if frame.get("motion_progress", 1.0) < 0.15]
        reference_pixels = statistics.median(reference or pixels[:1])
        if reference_pixels <= 0:
            raise ValueError("initial visibility reference must be nonzero")
        ratios = [value / reference_pixels for value in pixels]
        result["visibility"] = {
            "reference_pixels": reference_pixels,
            "pixels": summarize(pixels),
            "min_frame_id": ids[pixels.index(min(pixels))],
            "min_relative_area": min(ratios),
            "frames_below_half_reference_area": sum(value < 0.5 for value in ratios),
            "note": "Relative visible mask area, not an amodal occlusion fraction; object motion can change projected area.",
        }

    if records is not None:
        if [record["frame_id"] for record in records] != ids:
            raise ValueError("pose result frame IDs/order do not match the capture")
        if any(abs(float(record["timestamp_s"]) - timestamp) > 1e-6 for record, timestamp in zip(records, timestamps)):
            raise ValueError("pose result timestamps do not match the capture")
        result["pose"] = evaluate_records(records, "camera")[1]
        if ratios is not None:
            result["pose_by_visible_area"] = {}
            for name, select in (
                ("below_half_reference", lambda ratio: ratio < 0.5),
                ("at_least_half_reference", lambda ratio: ratio >= 0.5),
            ):
                selected = [record for record, ratio in zip(records, ratios) if select(ratio)]
                if selected:
                    result["pose_by_visible_area"][name] = evaluate_records(selected, "camera")[1]
        result["inference_s"] = {}
        for operation in ("register", "track"):
            times = [record["inference_s"] for record in records if record.get("operation") == operation and "inference_s" in record]
            if times:
                result["inference_s"][operation] = summarize(times)
    return result
