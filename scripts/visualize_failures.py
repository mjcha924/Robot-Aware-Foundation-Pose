#!/usr/bin/env python3
"""Show failed and successful frames of one occlusion level: image crop with GT and estimated 3D box.

    python3 scripts/visualize_failures.py \
        --run outputs/occlusion_baseline/front_n100/poses.jsonl \
        --occluded data/occluded/cracker_box_reorient/uniform_front_n100 --level 80

Green box = ground truth, red box = estimate; the extra diagonal marks the model's +z face so a
flipped orientation is visible. Failure = ADD-S >= 10% of the model diameter (as in the analysis).
"""

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt

from analyze_occlusion_baseline import read_records
from pose_eval.gt import gt_pose_paths
from pose_eval.metrics import model_diameter
from pose_eval.report import evaluate_records

GT_COLOR, EST_COLOR = "#1baf7a", "#eb6834"
EDGES = [(0, 1), (1, 3), (3, 2), (2, 0), (4, 5), (5, 7), (7, 6), (6, 4), (0, 4), (1, 5), (2, 6), (3, 7)]


def box_corners(points):
    lo, hi = points.min(axis=0), points.max(axis=0)
    return np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])


def project(corners, pose, K):
    cam = corners @ pose[:3, :3].T + pose[:3, 3]
    uv = cam @ K.T
    return uv[:, :2] / uv[:, 2:3]


def draw_box(ax, uv, color):
    for a, b in EDGES:
        ax.plot([uv[a, 0], uv[b, 0]], [uv[a, 1], uv[b, 1]], color=color, linewidth=1.4)
    # corner order: index bit0 = z, so the +z face is corners 1, 3, 5, 7; mark it with one diagonal
    ax.plot([uv[1, 0], uv[7, 0]], [uv[1, 1], uv[7, 1]], color=color, linewidth=1.0, linestyle=":")


def pick(rows, count):
    if not rows:
        return []
    rows = sorted(rows, key=lambda r: r["adds_mm"])
    idx = np.unique(np.linspace(0, len(rows) - 1, min(count, len(rows))).round().astype(int))
    return [rows[i] for i in idx]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--occluded", type=Path, required=True, help="folder holding vXXX scene folders")
    p.add_argument("--level", type=int, default=80)
    p.add_argument("--n-fail", type=int, default=6)
    p.add_argument("--n-ok", type=int, default=3)
    p.add_argument("--model-points", type=Path, default=ROOT / "data/models/CADmodels/003_cracker_box/points.xyz")
    p.add_argument("--scene", type=Path, default=ROOT / "data/ycbineoat/cracker_box_reorient")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    points = np.loadtxt(args.model_points)[:, :3]
    threshold = 0.10 * model_diameter(points) * 1000
    corners = box_corners(points)
    K = np.loadtxt(args.scene / "cam_K.txt").reshape(3, 3)
    gt_files = gt_pose_paths(args.scene)

    records = read_records(args.run)
    gt = {r["frame_id"]: np.loadtxt(gt_files[r["frame_id"]]).reshape(4, 4) for r in records}
    rows = evaluate_records(records, gt, points)
    pose_of = {(r["frame_id"], r["level"]): np.asarray(r["pose"]) for r in records if r["pose"] is not None}
    at_level = [r for r in rows if r["level"] == args.level and r["ok"]]
    failed = [r for r in at_level if r["adds_mm"] >= threshold]
    passed = [r for r in at_level if r["adds_mm"] < threshold]
    chosen = [("FAIL", r) for r in pick(failed, args.n_fail)] + [("ok", r) for r in pick(passed, args.n_ok)]
    print(f"level {args.level}: {len(failed)} failed / {len(passed)} ok of {len(at_level)}; showing {len(chosen)}")

    ncols = 3
    nrows = int(np.ceil(len(chosen) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.6 * ncols, 4.2 * nrows), squeeze=False)
    fig.patch.set_facecolor("#fcfcfb")
    for ax in axes.ravel():
        ax.axis("off")
    scene_dir = args.occluded / f"v{args.level:03d}"
    for ax, (tag, r) in zip(axes.ravel(), chosen):
        fid = r["frame_id"]
        image = mpimg.imread(scene_dir / "rgb" / f"{fid}.png")
        gt_uv = project(corners, gt[fid], K)
        est_uv = project(corners, pose_of[(fid, args.level)], K)
        ax.imshow(image)
        draw_box(ax, gt_uv, GT_COLOR)
        draw_box(ax, est_uv, EST_COLOR)
        lo, hi = gt_uv.min(axis=0), gt_uv.max(axis=0)
        centre, half = (lo + hi) / 2, max(hi - lo) * 0.75
        ax.set_xlim(centre[0] - half, centre[0] + half)
        ax.set_ylim(centre[1] + half, centre[1] - half)
        ax.set_title(f"{tag}  {fid[-6:]}  from {r['side']}\nADD-S {r['adds_mm']:.0f} mm, rot {r['rotation_deg']:.0f}°, "
                     f"visible {r['visible_px']} px", fontsize=9, loc="left", color="#b3261e" if tag == "FAIL" else "#0b0b0b")
        ax.axis("off")
    fig.suptitle(f"{args.run.parent.name}, {args.level}% hidden   green = ground truth, red/orange = estimate "
                 f"(failure: ADD-S >= {threshold:.0f} mm)", fontsize=11, x=0.01, ha="left")
    fig.tight_layout()
    out = args.out or ROOT / "outputs/analysis" / f"failures_{args.run.parent.name}_v{args.level:03d}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
