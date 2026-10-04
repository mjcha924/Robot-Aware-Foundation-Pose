#!/usr/bin/env python3
"""Summarise independent-register runs: error and success tables per occlusion level, plus figures.

    python3 scripts/analyze_occlusion_baseline.py \
        --run zero=outputs/occlusion_baseline/zero_n100/poses.jsonl \
        --run front=outputs/occlusion_baseline/front_n100/poses.jsonl

Success means ADD-S below a fraction (5%, 10%, 20%) of the model diameter; a failed register call
counts as a failure. Writes CSVs and PNGs to --out and prints the tables.
"""

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter

from pose_eval.metrics import model_diameter
from pose_eval.report import FRACTIONS, evaluate_records, level_table

# Categorical slots 1-4 of the reference palette (blue, orange, aqua, yellow); validated as a set.
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
MARKERS = ["o", "s", "^", "D"]
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e3e2dc", "#fcfcfb"
SIDES = ("left", "right", "top", "bottom")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", action="append", required=True, metavar="LABEL=POSES.jsonl")
    p.add_argument("--model-points", type=Path, default=ROOT / "data/models/CADmodels/003_cracker_box/points.xyz")
    p.add_argument("--gt-dir", type=Path, default=ROOT / "data/ycbineoat/cracker_box_reorient/annotated_poses")
    p.add_argument("--out", type=Path, default=None)
    return p.parse_args()


def read_records(path):
    records, skipped = [], 0
    for line in Path(path).read_text().splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            skipped += 1  # a run still in progress may end on a half-written line
    if skipped:
        print(f"warning: skipped {skipped} unreadable line(s) in {path}", file=sys.stderr)
    return records


def fmt(value, spec="6.1f"):
    return f"{value:{spec}}" if not math.isnan(value) else "   nan"


def print_table(label, table, diameter_m):
    print(f"\n=== {label}  (model diameter {diameter_m * 1000:.1f} mm; "
          f"success = ADD-S < {', '.join(f'{f:.0%}={f * diameter_m * 1000:.1f}mm' for f in FRACTIONS)}) ===")
    print("occ%  hidden  n  fail | ADD-S mm: mean median  p90 | success 5%   10% [95% CI]    20% | rot>90  shift mm")
    for t in table:
        s = t["success"]
        print(f"{t['level']:>3}  {t['hidden_mean'] * 100:5.1f} {t['n']:>3} {t['n_failed_call']:>4} | "
              f"{fmt(t['adds_mean_mm'], '14.1f')} {fmt(t['adds_median_mm'], '6.1f')} {fmt(t['adds_p90_mm'], '5.1f')} | "
              f"{s[0.05][0]:8.0%} {s[0.10][0]:5.0%} [{s[0.10][1]:.0%}-{s[0.10][2]:.0%}] {s[0.20][0]:6.0%} | "
              f"{t['rot_over_90']:>5}  {fmt(t['pose_shift_mean_mm'], '7.1f')}")


def print_comparison(tables):
    labels = list(tables)
    if len(labels) < 2:
        return
    print("\n=== run comparison: success rate at 10% of diameter / median ADD-S (mm) ===")
    print("occ%  " + "  ".join(f"{l:>18}" for l in labels))
    levels = sorted({t["level"] for tb in tables.values() for t in tb})
    for level in levels:
        cells = []
        for label in labels:
            hit = next((t for t in tables[label] if t["level"] == level), None)
            cells.append(f"{hit['success'][0.10][0]:6.0%} / {hit['adds_median_mm']:7.1f}" if hit else "                n/a")
        print(f"{level:>3}   " + "  ".join(f"{c:>18}" for c in cells))


def write_csvs(out, label, rows, table):
    with (out / f"{label}_records.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (out / f"{label}_levels.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["occ_level", "hidden_mean", "n", "n_failed_call", "adds_mean_mm", "adds_median_mm",
                         "adds_p90_mm", "translation_mean_mm", "rot_over_90", "pose_shift_mean_mm"]
                        + [f"success_{int(f * 100)}pct" for f in FRACTIONS]
                        + [f"success_{int(f * 100)}pct_{b}" for f in FRACTIONS for b in ("lo", "hi")])
        for t in table:
            writer.writerow([t["level"], t["hidden_mean"], t["n"], t["n_failed_call"], t["adds_mean_mm"],
                             t["adds_median_mm"], t["adds_p90_mm"], t["translation_mean_mm"], t["rot_over_90"],
                             t["pose_shift_mean_mm"]] + [t["success"][f][0] for f in FRACTIONS]
                            + [t["success"][f][i] for f in FRACTIONS for i in (1, 2)])


def style(ax, xlabel, ylabel, title):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    ax.set_xlabel(xlabel, fontsize=10, color=MUTED)
    ax.set_ylabel(ylabel, fontsize=10, color=MUTED)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)


def new_figure(**kwargs):
    fig, axes = plt.subplots(**kwargs)
    fig.patch.set_facecolor(SURFACE)
    return fig, axes


def plot_success(out, tables):
    fig, ax = new_figure(figsize=(7.5, 4.5))
    for i, (label, table) in enumerate(tables.items()):
        x = [t["level"] for t in table]
        rate = np.array([t["success"][0.10][0] for t in table])
        lo = np.array([t["success"][0.10][1] for t in table])
        hi = np.array([t["success"][0.10][2] for t in table])
        ax.errorbar(x, rate, yerr=[rate - lo, hi - rate], color=COLORS[i], marker=MARKERS[i], markersize=6,
                    linewidth=2, capsize=3, label=f"{label} (success: ADD-S < 10% of diameter)")
    style(ax, "occlusion (% of the object hidden)", "success rate", "Independent register: success vs occlusion")
    ax.set_ylim(-0.02, 1.05)
    ax.set_xticks(sorted({t["level"] for tb in tables.values() for t in tb}))
    ax.legend(frameon=False, fontsize=9, loc="lower left")
    fig.text(0.01, 0.01, "bars: 95% Wilson interval", fontsize=8, color=MUTED)
    fig.tight_layout()
    fig.savefig(out / "success_vs_occlusion.png", dpi=150)
    plt.close(fig)


def plot_thresholds(out, tables):
    fig, axes = new_figure(ncols=len(tables), figsize=(5.2 * len(tables), 4.2), squeeze=False, sharey=True)
    for ax, (label, table) in zip(axes[0], tables.items()):
        for i, fraction in enumerate(FRACTIONS):
            ax.plot([t["level"] for t in table], [t["success"][fraction][0] for t in table], color=COLORS[i],
                    marker=MARKERS[i], markersize=6, linewidth=2, label=f"ADD-S < {fraction:.0%} of diameter")
        style(ax, "occlusion (% hidden)", "success rate", f"{label}: how the criterion changes the answer")
        ax.set_ylim(-0.02, 1.05)
        ax.legend(frameon=False, fontsize=9, loc="lower left")
    fig.tight_layout()
    fig.savefig(out / "success_threshold_sensitivity.png", dpi=150)
    plt.close(fig)


def plot_error(out, tables):
    fig, ax = new_figure(figsize=(7.5, 4.5))
    for i, (label, table) in enumerate(tables.items()):
        x = [t["level"] for t in table]
        median = np.array([t["adds_median_mm"] for t in table])
        p90 = np.array([t["adds_p90_mm"] for t in table])
        ax.plot(x, median, color=COLORS[i], marker=MARKERS[i], markersize=6, linewidth=2, label=f"{label} median")
        ax.plot(x, p90, color=COLORS[i], linewidth=1.5, linestyle="--", label=f"{label} 90th percentile")
    style(ax, "occlusion (% of the object hidden)", "ADD-S error (mm, log scale)", "Error vs occlusion")
    ax.set_yscale("log")
    ax.set_xticks(sorted({t["level"] for tb in tables.values() for t in tb}))
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.tight_layout()
    fig.savefig(out / "error_vs_occlusion.png", dpi=150)
    plt.close(fig)


def plot_sides(out, rows_by_run, diameter_m):
    fig, axes = new_figure(ncols=len(rows_by_run), figsize=(5.2 * len(rows_by_run), 4.2), squeeze=False, sharey=True)
    threshold = 0.10 * diameter_m * 1000
    for ax, (label, rows) in zip(axes[0], rows_by_run.items()):
        for i, side in enumerate(SIDES):
            subset = [r for r in rows if r["side"] == side]
            levels = sorted({r["level"] for r in subset})
            rate = [np.mean([r["ok"] and r["adds_mm"] < threshold for r in subset if r["level"] == lv]) for lv in levels]
            n = len([r for r in subset if r["level"] == levels[0]]) if levels else 0
            ax.plot(levels, rate, color=COLORS[i], marker=MARKERS[i], markersize=6, linewidth=2,
                    label=f"block from {side} (n={n} frames)")
        style(ax, "occlusion (% hidden)", "success rate", f"{label}: by side the block enters from")
        ax.set_ylim(-0.02, 1.05)
        ax.legend(frameon=False, fontsize=9, loc="lower left")
    fig.tight_layout()
    fig.savefig(out / "success_by_side.png", dpi=150)
    plt.close(fig)


def plot_scatter(out, rows_by_run, diameter_m):
    fig, axes = new_figure(ncols=len(rows_by_run), figsize=(5.2 * len(rows_by_run), 4.8), squeeze=False)
    threshold = 0.10 * diameter_m * 1000
    for i, (ax, (label, rows)) in enumerate(zip(axes[0], rows_by_run.items())):
        top = max(r["level"] for r in rows)
        base = {r["frame_id"]: r["adds_mm"] for r in rows if r["level"] == 0 and r["ok"]}
        pairs = [(base[r["frame_id"]], r["adds_mm"]) for r in rows
                 if r["level"] == top and r["ok"] and r["frame_id"] in base]
        if pairs:
            xs, ys = zip(*pairs)
            ax.scatter(xs, ys, s=28, color=COLORS[i], alpha=0.8, edgecolor=SURFACE, linewidth=0.8)
        ax.axhline(threshold, color=MUTED, linestyle=":", linewidth=1.2)
        ax.text(0.99, threshold * 1.08, "10% of diameter", ha="right", fontsize=8, color=MUTED,
                transform=ax.get_yaxis_transform())
        style(ax, "ADD-S with no occlusion (mm)", f"ADD-S at {top}% occlusion (mm)", f"{label}: each frame, before vs after")
        ax.set_xscale("log")
        ax.set_yscale("log")
        for axis in (ax.xaxis, ax.yaxis):
            axis.set_major_formatter(FormatStrFormatter("%g"))
            axis.set_minor_formatter(FormatStrFormatter("%g"))
        ax.tick_params(which="minor", labelsize=7, colors=MUTED)
    fig.tight_layout()
    fig.savefig(out / "per_frame_before_after.png", dpi=150)
    plt.close(fig)


def main():
    args = parse_args()
    runs = dict(spec.split("=", 1) for spec in args.run)
    out = args.out or ROOT / "outputs/analysis" / "_".join(runs)
    out.mkdir(parents=True, exist_ok=True)
    points = np.loadtxt(args.model_points)[:, :3]
    diameter = model_diameter(points)

    tables, rows_by_run = {}, {}
    for label, path in runs.items():
        records = read_records(path)
        gt = {r["frame_id"]: np.loadtxt(args.gt_dir / f"{r['frame_id']}.txt").reshape(4, 4) for r in records}
        rows = evaluate_records(records, gt, points)
        tables[label], rows_by_run[label] = level_table(rows, diameter), rows
        print_table(label, tables[label], diameter)
        write_csvs(out, label, rows, tables[label])
    print_comparison(tables)

    plot_success(out, tables)
    plot_thresholds(out, tables)
    plot_error(out, tables)
    plot_sides(out, rows_by_run, diameter)
    plot_scatter(out, rows_by_run, diameter)
    print(f"\nwrote tables and figures to {out}")


if __name__ == "__main__":
    main()
