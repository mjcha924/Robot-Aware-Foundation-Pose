"""Dependency-free rigid-pose error metrics."""

from __future__ import annotations

import math
import statistics
from typing import Iterable, Sequence


Matrix = Sequence[Sequence[float]]


def _matrix4(value: Matrix) -> list[list[float]]:
    if len(value) != 4 or any(len(row) != 4 for row in value):
        raise ValueError("expected a 4x4 pose matrix")
    matrix = [[float(item) for item in row] for row in value]
    if not all(math.isfinite(item) for row in matrix for item in row):
        raise ValueError("pose matrix contains a non-finite value")
    return matrix


def translation_error_m(estimate: Matrix, truth: Matrix) -> float:
    """Return Euclidean translation error in metres."""

    estimate_matrix = _matrix4(estimate)
    truth_matrix = _matrix4(truth)
    return math.sqrt(sum((estimate_matrix[index][3] - truth_matrix[index][3]) ** 2 for index in range(3)))


def rotation_error_deg(estimate: Matrix, truth: Matrix) -> float:
    """Return the geodesic SO(3) error in degrees."""

    estimate_matrix = _matrix4(estimate)
    truth_matrix = _matrix4(truth)
    # trace(R_estimate * R_truth^T) without introducing NumPy as a dependency.
    relative_trace = sum(
        estimate_matrix[row][column] * truth_matrix[row][column]
        for row in range(3)
        for column in range(3)
    )
    cosine = max(-1.0, min(1.0, (relative_trace - 1.0) * 0.5))
    return math.degrees(math.acos(cosine))


def summarize(values: Iterable[float]) -> dict[str, float | int]:
    """Summarize a non-empty metric series."""

    samples = [float(value) for value in values]
    if not samples:
        raise ValueError("cannot summarize an empty metric series")
    if not all(math.isfinite(value) for value in samples):
        raise ValueError("metric series contains a non-finite value")
    return {
        "count": len(samples),
        "mean": statistics.fmean(samples),
        "median": statistics.median(samples),
        "rmse": math.sqrt(statistics.fmean(value * value for value in samples)),
        "max": max(samples),
    }


def evaluate_records(records: Iterable[dict], frame: str) -> tuple[list[dict], dict]:
    """Evaluate predicted and ground-truth poses for one coordinate frame."""

    if frame not in {"camera", "effector"}:
        raise ValueError("frame must be 'camera' or 'effector'")
    estimate_key = f"T_{frame}_object"
    truth_key = f"T_{frame}_object_gt"
    per_frame: list[dict] = []
    for index, record in enumerate(records):
        if estimate_key not in record or truth_key not in record:
            frame_id = record.get("frame_id", index)
            raise ValueError(f"record {frame_id!r} is missing {estimate_key!r} or {truth_key!r}")
        per_frame.append(
            {
                "frame_id": str(record.get("frame_id", index)),
                "timestamp_s": record.get("timestamp_s"),
                "translation_error_m": translation_error_m(record[estimate_key], record[truth_key]),
                "rotation_error_deg": rotation_error_deg(record[estimate_key], record[truth_key]),
            }
        )
    if not per_frame:
        raise ValueError("pose result contains no records")
    summary = {
        "frame": frame,
        "frame_count": len(per_frame),
        "translation_error_m": summarize(item["translation_error_m"] for item in per_frame),
        "rotation_error_deg": summarize(item["rotation_error_deg"] for item in per_frame),
    }
    return per_frame, summary
