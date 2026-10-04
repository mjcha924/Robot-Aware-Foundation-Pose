"""Turn raw per-frame pose records into per-occlusion-level error and success tables."""

import math

import numpy as np

from evaluation.pose_metrics import rotation_error_deg, translation_error_m
from pose_eval.metrics import add, add_s

FRACTIONS = (0.05, 0.10, 0.20)


def wilson_interval(successes, n, z=1.96):
    """95% Wilson score interval for a success rate."""
    if n <= 0:
        raise ValueError("need at least one trial")
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    # float rounding can leave the bound a hair inside p (e.g. 0.9999999999999999 at 10/10)
    return max(0.0, min(centre - half, p)), min(1.0, max(centre + half, p))


def evaluate_records(records, gt_poses, points):
    """One row per record: errors against ground truth and the shift from that frame's level-0 pose.

    A record whose register call failed (pose None) stays in the output with ok=False and NaN errors.
    """
    reference = {r["frame_id"]: np.asarray(r["pose"]) for r in records if r["level"] == 0 and r["pose"] is not None}
    rows = []
    for rec in records:
        row = {key: rec[key] for key in ("frame_id", "level", "side", "achieved_occluded", "visible_px", "depth_mode")}
        row["ok"] = rec["pose"] is not None
        nan = float("nan")
        row.update(translation_mm=nan, rotation_deg=nan, add_mm=nan, adds_mm=nan, pose_shift_mm=nan)
        if row["ok"]:
            estimate, truth = np.asarray(rec["pose"]), np.asarray(gt_poses[rec["frame_id"]])
            row["translation_mm"] = translation_error_m(estimate, truth) * 1000
            row["rotation_deg"] = rotation_error_deg(estimate, truth)
            row["add_mm"] = add(estimate, truth, points) * 1000
            row["adds_mm"] = add_s(estimate, truth, points) * 1000
            if rec["frame_id"] in reference:
                row["pose_shift_mm"] = add_s(estimate, reference[rec["frame_id"]], points) * 1000
        rows.append(row)
    return rows


def level_table(rows, diameter_m, fractions=FRACTIONS):
    """Per occlusion level: error statistics and success rates (ADD-S < fraction of the diameter).

    A failed register call counts as a failure in the success rate and is left out of the error statistics.
    """
    table = []
    for level in sorted({r["level"] for r in rows}):
        group = [r for r in rows if r["level"] == level]
        good = [r for r in group if r["ok"]]
        adds = np.array([r["adds_mm"] for r in good])
        shifts = np.array([r["pose_shift_mm"] for r in good if not math.isnan(r["pose_shift_mm"])])
        success = {}
        for fraction in fractions:
            threshold_mm = round(fraction * diameter_m * 1000, 9)
            hits = int(sum(r["adds_mm"] < threshold_mm for r in good))
            success[fraction] = (hits / len(group), *wilson_interval(hits, len(group)))
        stat = lambda fn, values: float(fn(values)) if len(values) else float("nan")
        table.append({
            "level": level,
            "n": len(group),
            "n_failed_call": len(group) - len(good),
            "hidden_mean": float(np.mean([r["achieved_occluded"] for r in group])),
            "adds_mean_mm": stat(np.mean, adds),
            "adds_median_mm": stat(np.median, adds),
            "adds_p90_mm": stat(lambda v: np.percentile(v, 90), adds),
            "translation_mean_mm": stat(np.mean, [r["translation_mm"] for r in good]),
            "rot_over_90": int(sum(r["rotation_deg"] > 90 for r in good)),
            "pose_shift_mean_mm": stat(np.mean, shifts),
            "success": success,
        })
    return table
