#!/usr/bin/env python3
"""Report capture motion, visible area, and optionally matched pose accuracy/timing."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evaluation.sequence_metrics import analyze_sequence
from evaluate_pose_results import load_records
from validate_isaac_export import validate_sequence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sequence", type=Path)
    parser.add_argument("--poses", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    try:
        errors = validate_sequence(args.sequence)
        if errors:
            raise ValueError("; ".join(errors))
        frames = load_records(args.sequence / "frames.jsonl")
        records = load_records(args.poses) if args.poses else None
        if args.poses and (args.poses.parent / "run.json").is_file():
            run_info = json.loads((args.poses.parent / "run.json").read_text(encoding="utf-8"))
            for name, expected in run_info.get("input_metadata_sha256", {}).items():
                if name not in {"manifest.json", "frames.jsonl"}:
                    raise ValueError(f"unexpected metadata hash key: {name}")
                if hashlib.sha256((args.sequence / name).read_bytes()).hexdigest() != expected:
                    raise ValueError(f"capture {name} does not match the pose run's input hash")
        result = analyze_sequence(frames, records)
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    serialized = json.dumps(result, indent=2) + "\n"
    print(serialized, end="")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(serialized, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
