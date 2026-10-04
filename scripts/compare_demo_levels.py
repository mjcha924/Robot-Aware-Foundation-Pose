#!/usr/bin/env python3
"""Compare run_demo.py poses across occlusion levels, frame by frame.

Reads outputs/occ_demo/vNNN/ob_in_cam/<frame>.txt (4x4 object-in-camera poses). Prints, per level,
how far each pose is from the same frame's v000 pose, and (as a side check) from ground truth.
"""
import glob
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from evaluation.pose_metrics import rotation_error_deg, translation_error_m

RUNS = ROOT / "outputs/occ_demo"
SCENE = ROOT / "data/occluded/cracker_box_reorient/uniform_zero_n100"
GT_DIR = ROOT / "data/ycbineoat/cracker_box_reorient/annotated_poses"


def load(path):
    return np.loadtxt(path).reshape(4, 4)


def stats(values):
    v = np.asarray(values)
    return f"{v.mean():7.1f} {np.median(v):7.1f} {np.percentile(v, 90):7.1f} {v.max():7.1f}"


def main():
    frames = [f["frame_id"] for f in json.loads((SCENE / "selection.json").read_text())["frames"]]
    all_gt = sorted(GT_DIR.glob("*.txt")) or sorted(GT_DIR.glob("*"))
    gt = {p.stem: load(p) for p in all_gt}
    levels = sorted(p.name for p in RUNS.iterdir() if p.name.startswith("v"))
    ref = {f: load(RUNS / "v000/ob_in_cam" / f"{f}.txt") for f in frames}

    print("A. difference from the same frame at v000 (no added occlusion)")
    print(f"{'level':>6} {'hidden%':>8} | translation mm: mean median p90 max | rotation deg: mean median p90 max | >20mm >10deg")
    for lv in levels:
        meta = json.loads((SCENE / lv / "meta.json").read_text())["frames"]
        hidden = np.mean([m["achieved_occluded"] for m in meta.values()]) * 100
        dt, dr = [], []
        for f in frames:
            p = load(RUNS / lv / "ob_in_cam" / f"{f}.txt")
            dt.append(translation_error_m(p, ref[f]) * 1000)
            dr.append(rotation_error_deg(p, ref[f]))
        print(f"{lv:>6} {hidden:8.1f} | {stats(dt)} | {stats(dr)} | {sum(x > 20 for x in dt):4d} {sum(x > 10 for x in dr):6d}")

    print("\nB. error against ground truth (annotated_poses), for reference")
    print(f"{'level':>6} | translation mm: mean median p90 max | rotation deg: mean median p90 max | >25mm >20deg")
    for lv in levels:
        et, er = [], []
        for f in frames:
            p = load(RUNS / lv / "ob_in_cam" / f"{f}.txt")
            et.append(translation_error_m(p, gt[f]) * 1000)
            er.append(rotation_error_deg(p, gt[f]))
        print(f"{lv:>6} | {stats(et)} | {stats(er)} | {sum(x > 25 for x in et):4d} {sum(x > 20 for x in er):6d}")


if __name__ == "__main__":
    main()
