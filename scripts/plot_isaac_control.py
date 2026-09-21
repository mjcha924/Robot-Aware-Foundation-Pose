#!/usr/bin/env python3
"""Plot visibility, pose error and tool command error for a matched Isaac run.

Requires matplotlib (available in the FoundationPose container).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evaluation.pose_metrics import evaluate_records
from evaluation.sequence_metrics import analyze_sequence
from evaluate_pose_results import load_records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sequence", type=Path)
    parser.add_argument("poses", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    frames = load_records(args.sequence / "frames.jsonl")
    records = load_records(args.poses)
    audit = analyze_sequence(frames, records)
    errors, _ = evaluate_records(records, "camera")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    has_command = "effector_command_error_m" in audit
    fig, axes = plt.subplots(4 if has_command else 3, 1, figsize=(10, 8), sharex=True)
    time = [frame["timestamp_s"] - frames[0]["timestamp_s"] for frame in frames]
    if "visibility" in audit:
        reference = audit["visibility"]["reference_pixels"]
        axes[0].plot(time, [frame["visible_mask_pixels"] / reference for frame in frames], color="#377eb8")
        axes[0].axhline(0.5, color="#888888", linestyle="--", linewidth=1)
        axes[0].set_ylabel("Visible mask area\n/ initial reference")
    axes[1].plot(time, [row["translation_error_m"] * 1000 for row in errors], color="#e66101")
    axes[1].set_ylabel("Translation error (mm)")
    axes[2].plot(time, [row["rotation_error_deg"] for row in errors], color="#5e3c99")
    axes[2].set_ylabel("Rotation error (deg)")
    if has_command:
        axes[3].plot(time, [frame["effector_command_error_m"] * 1000 for frame in frames], color="#1b9e77")
        axes[3].set_ylabel("Tool command error (mm)")
    for axis in axes:
        axis.grid(alpha=0.2)
        axis.set_ylim(bottom=0)
    axes[-1].set_xlabel("Time since first exported frame (s)")
    fig.suptitle(f"FoundationPose control — {len(frames)} frames\n{args.sequence.name}")
    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=160)
    plt.close(fig)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
