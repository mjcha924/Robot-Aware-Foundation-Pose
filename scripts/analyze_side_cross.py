#!/usr/bin/env python3
"""Compare block sides on the same frames: per-side tables, frame-vs-side variance, frame categories.

    python3 scripts/analyze_side_cross.py \
        --run left=outputs/occlusion_baseline/cross_front_left_n100/poses.jsonl \
        --run right=... --run top=... --run bottom=...

Success = ADD-S < 10% of the model diameter. "Flip" = rotation error > 150 deg, counted apart from
the ADD-S verdict (a flipped thin box can still pass). Writes CSVs and PNGs to --out.
"""

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analyze_occlusion_baseline import COLORS, MARKERS, MUTED, SURFACE, new_figure, read_records, style
from pose_eval.gt import gt_pose_paths
from pose_eval.metrics import model_diameter
from pose_eval.report import adds_auc, evaluate_records
from pose_eval.side_cross import fail_count_histogram, variance_shares

FLIP_DEG = 150.0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", action="append", required=True, metavar="SIDE=POSES.jsonl")
    p.add_argument("--model-points", type=Path, default=ROOT / "data/models/CADmodels/003_cracker_box/points.xyz")
    p.add_argument("--scene", type=Path, default=ROOT / "data/ycbineoat/cracker_box_reorient")
    p.add_argument("--out", type=Path, default=ROOT / "outputs/analysis/side_cross")
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    points = np.loadtxt(args.model_points)[:, :3]
    threshold = 0.10 * model_diameter(points) * 1000
    gt_files = gt_pose_paths(args.scene)
    rows = {}  # side -> {(level, frame): row}
    for spec in args.run:
        side, path = spec.split("=", 1)
        records = read_records(path)
        gt = {r["frame_id"]: np.loadtxt(gt_files[r["frame_id"]]).reshape(4, 4) for r in records}
        rows[side] = {(r["level"], r["frame_id"]): r for r in evaluate_records(records, gt, points)}
    sides = list(rows)
    levels = sorted({lv for s in sides for lv, _ in rows[s]})
    frames = sorted({f for s in sides for _, f in rows[s]})
    failure = lambda r: (not r["ok"]) or r["adds_mm"] >= threshold

    print(f"fail = ADD-S >= {threshold:.1f} mm; frames={len(frames)} sides={sides}")
    table = []
    for level in levels:
        for side in sides:
            group = [r for (lv, _), r in rows[side].items() if lv == level]
            adds = np.array([r["adds_mm"] for r in group if r["ok"]])
            table.append({
                "level": level, "side": side, "n": len(group),
                "success_10pct": 1 - sum(failure(r) for r in group) / len(group),
                "success_20pct": float(np.mean([r["ok"] and r["adds_mm"] < 2 * threshold for r in group])),
                "adds_median_mm": float(np.median(adds)), "adds_p90_mm": float(np.percentile(adds, 90)),
                "adds_auc": adds_auc(adds, len(group)),
                "flips": int(sum(r["ok"] and r["rotation_deg"] > FLIP_DEG for r in group)),
                "fail_and_flip": int(sum(failure(r) and r["ok"] and r["rotation_deg"] > FLIP_DEG for r in group)),
            })
    with (args.out / "side_levels.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    print("\nlevel side    n  success10  success20  median  p90   AUC  flips(fail&flip)")
    for t in table:
        print(f"{t['level']:>5} {t['side']:<6}{t['n']:>4}  {t['success_10pct']:8.0%} {t['success_20pct']:9.0%} "
              f"{t['adds_median_mm']:7.1f} {t['adds_p90_mm']:5.1f} {t['adds_auc']:6.3f}  {t['flips']:>3} ({t['fail_and_flip']})")

    print("\nframe vs side: share of variance of log ADD-S, and frames failing on k of the sides")
    effects = []
    for level in levels:
        if level == 0:
            continue
        err = np.array([[rows[s][(level, f)]["adds_mm"] for s in sides] for f in frames])
        fails = np.array([[failure(rows[s][(level, f)]) for s in sides] for f in frames])
        shares = variance_shares(np.log(np.maximum(err, 1e-3)))
        hist = fail_count_histogram(fails)
        effects.append({"level": level, **shares, **{f"fail_on_{k}_sides": v for k, v in hist.items()}})
        print(f"  {level}%: frame {shares['frame']:.0%}  side {shares['side']:.0%}  residual {shares['residual']:.0%}"
              f" | frames failing on 0/1/2/3/4 sides: " + "/".join(str(hist[k]) for k in sorted(hist)))
    with (args.out / "frame_vs_side.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(effects[0]))
        writer.writeheader()
        writer.writerows(effects)

    for key, ylabel, fname in (("success_10pct", "success rate (ADD-S < 10% of diameter)", "side_success.png"),
                               ("adds_auc", "ADD-S AUC (0-100 mm)", "side_auc.png")):
        fig, ax = new_figure(figsize=(7, 4.4))
        for i, side in enumerate(sides):
            sub = [t for t in table if t["side"] == side]
            ax.plot([t["level"] for t in sub], [t[key] for t in sub], color=COLORS[i], marker=MARKERS[i],
                    markersize=6, linewidth=2, label=f"block from {side}")
        style(ax, "occlusion (% hidden)", ylabel, "Same 100 frames, every side")
        ax.set_xticks(levels)
        ax.legend(frameon=False, fontsize=9, loc="lower left")
        fig.tight_layout()
        fig.savefig(args.out / fname, dpi=150)
        plt.close(fig)

    level = 80 if 80 in levels else levels[-1]
    err = np.array([[rows[s][(level, f)]["adds_mm"] for s in sides] for f in frames])
    order = np.argsort(err.mean(axis=1))
    fig, ax = new_figure(figsize=(5.2, 8))
    image = ax.imshow(np.log10(np.maximum(err[order], 1.0)), aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(sides)), sides)
    ax.set_ylabel("frames (sorted by mean ADD-S)", fontsize=10, color=MUTED)
    ax.set_title(f"log10 ADD-S (mm) at {level}% hidden", loc="left", fontsize=11)
    fig.colorbar(image, ax=ax, shrink=0.6)
    fig.tight_layout()
    fig.savefig(args.out / f"frame_side_heatmap_v{level:03d}.png", dpi=150)
    plt.close(fig)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
