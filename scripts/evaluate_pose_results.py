#!/usr/bin/env python3
"""Evaluate FoundationPose JSONL results against embedded ground truth."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from evaluation.pose_metrics import evaluate_records  # noqa: E402


def load_records(path: Path) -> list[dict]:
    records: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSON on line {line_number}: {error.msg}") from error
        if not isinstance(value, dict):
            raise ValueError(f"line {line_number} is not a JSON object")
        records.append(value)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("poses", type=Path, help="Path to the run's poses.jsonl file.")
    parser.add_argument("--frame", choices=("camera", "effector", "both"), default="both")
    parser.add_argument("--json-out", type=Path, help="Optional path for per-frame metrics and summaries.")
    args = parser.parse_args()

    try:
        records = load_records(args.poses)
        frames = ("camera", "effector") if args.frame == "both" else (args.frame,)
        evaluations = {}
        for frame in frames:
            per_frame, summary = evaluate_records(records, frame)
            evaluations[frame] = {"summary": summary, "per_frame": per_frame}
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    for frame, result in evaluations.items():
        translation = result["summary"]["translation_error_m"]
        rotation = result["summary"]["rotation_error_deg"]
        print(f"{frame}: {result['summary']['frame_count']} frames")
        print(
            "  translation [mm]: "
            f"mean={translation['mean'] * 1000.0:.3f} "
            f"median={translation['median'] * 1000.0:.3f} "
            f"rmse={translation['rmse'] * 1000.0:.3f} "
            f"max={translation['max'] * 1000.0:.3f}"
        )
        print(
            "  rotation [deg]:   "
            f"mean={rotation['mean']:.3f} "
            f"median={rotation['median']:.3f} "
            f"rmse={rotation['rmse']:.3f} "
            f"max={rotation['max']:.3f}"
        )

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(evaluations, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote metrics to {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
