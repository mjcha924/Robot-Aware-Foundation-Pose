#!/usr/bin/env python3
"""Write occluded copies of a YCBInEOAT scene, one scene folder per visibility level.

Each <out>/vNNN/ has the same layout run_demo.py reads (rgb/, depth/, masks/, cam_K.txt)
plus meta.json with the exact visible fraction per frame. masks/ holds the *visible*
object mask. <out>/review/<frame>.png is a contact sheet over the levels for inspection.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from occlusion.scene import build_level, choose_side
from occlusion.select import select_frames

CELL = 192


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scene", type=Path, default=ROOT / "data/ycbineoat/cracker_box_reorient")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--n", type=int, default=100, help="number of frames")
    p.add_argument("--strategy", choices=("uniform", "largest"), default="uniform")
    p.add_argument("--min-area", type=int, default=0, help="drop frames whose object mask is smaller (px)")
    p.add_argument("--levels", default="100,90,80,70,60,50,40,30,20,10",
                   help="visible percentages of the object mask, comma separated")
    p.add_argument("--depth-mode", choices=("zero", "front"), default="zero")
    p.add_argument("--front-offset-mm", type=int, default=100)
    p.add_argument("--color", default="0,0,0", help="block RGB colour")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--tol", type=float, default=0.02)
    p.add_argument("--force", action="store_true", help="replace an existing output folder")
    return p.parse_args()


def read_frame(scene, frame_id):
    rgb = cv2.cvtColor(cv2.imread(str(scene / "rgb" / f"{frame_id}.png")), cv2.COLOR_BGR2RGB)
    depth = cv2.imread(str(scene / "depth" / f"{frame_id}.png"), cv2.IMREAD_UNCHANGED)
    mask = cv2.imread(str(scene / "gt_mask" / f"{frame_id}.png"), cv2.IMREAD_UNCHANGED) > 0
    return rgb, depth, mask


def crop_window(mask, shape, margin=40):
    ys, xs = np.nonzero(mask)
    cy, cx = (ys.min() + ys.max()) // 2, (xs.min() + xs.max()) // 2
    half = max(ys.max() - ys.min(), xs.max() - xs.min()) // 2 + margin
    y0, x0 = np.clip(cy - half, 0, shape[0] - 2 * half), np.clip(cx - half, 0, shape[1] - 2 * half)
    return int(max(y0, 0)), int(max(x0, 0)), int(2 * half)


def depth_vis(depth, ref_mm):
    scaled = np.clip((depth.astype(np.float32) - (ref_mm - 200)) / 400, 0, 1)
    vis = cv2.applyColorMap((scaled * 255).astype(np.uint8), cv2.COLORMAP_JET)
    vis[depth == 0] = 0
    return vis[..., ::-1]


def cell(image, window, visible_mask, label):
    y0, x0, size = window
    crop = image[y0:y0 + size, x0:x0 + size]
    crop = cv2.resize(crop, (CELL, CELL), interpolation=cv2.INTER_NEAREST)
    mask = cv2.resize(visible_mask[y0:y0 + size, x0:x0 + size].astype(np.uint8), (CELL, CELL),
                      interpolation=cv2.INTER_NEAREST)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    crop = np.ascontiguousarray(crop)
    cv2.drawContours(crop, contours, -1, (0, 255, 0), 1)
    cv2.putText(crop, label, (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1, cv2.LINE_AA)
    return crop


def main():
    args = parse_args()
    levels = [int(v) for v in args.levels.split(",")]
    color = tuple(int(v) for v in args.color.split(","))
    scene = args.scene
    frame_ids = sorted(p.stem for p in (scene / "rgb").glob("*.png"))

    areas = [(f, int((cv2.imread(str(scene / "gt_mask" / f"{f}.png"), cv2.IMREAD_UNCHANGED) > 0).sum()))
             for f in frame_ids]
    chosen = select_frames(areas, args.n, strategy=args.strategy, min_area=args.min_area)

    if args.out.exists():
        if not args.force:
            sys.exit(f"{args.out} exists; pass --force to replace it")
        shutil.rmtree(args.out)
    for level in levels:
        for sub in ("rgb", "depth", "masks"):
            (args.out / f"v{level:03d}" / sub).mkdir(parents=True)
        shutil.copy(scene / "cam_K.txt", args.out / f"v{level:03d}" / "cam_K.txt")
    (args.out / "review").mkdir()

    area_of = dict(areas)
    (args.out / "selection.json").write_text(json.dumps({
        "scene": str(scene), "strategy": args.strategy, "min_area": args.min_area, "n": args.n,
        "seed": args.seed, "frames": [{"frame_id": f, "mask_area_px": area_of[f]} for f in chosen],
    }, indent=1))

    meta = {level: {"frames": {}} for level in levels}
    for index, frame_id in enumerate(chosen):
        rgb, depth, obj = read_frame(scene, frame_id)
        side = choose_side(frame_id, args.seed)
        window = crop_window(obj, obj.shape)
        ref_mm = int(np.median(depth[obj & (depth > 0)]))
        top, bottom = [], []
        for level in levels:
            result = build_level(rgb, depth, obj, level / 100, side, color=color,
                                 depth_mode=args.depth_mode, front_offset_mm=args.front_offset_mm,
                                 tol=args.tol)
            d = args.out / f"v{level:03d}"
            cv2.imwrite(str(d / "rgb" / f"{frame_id}.png"), cv2.cvtColor(result["rgb"], cv2.COLOR_RGB2BGR))
            cv2.imwrite(str(d / "depth" / f"{frame_id}.png"), result["depth"])
            cv2.imwrite(str(d / "masks" / f"{frame_id}.png"), result["visible_mask"].astype(np.uint8))
            meta[level]["frames"][frame_id] = {
                "side": side, "target": result["target"], "achieved": result["achieved"],
                "object_px": int(obj.sum()), "visible_px": int(result["visible_mask"].sum()),
            }
            label = f"{level}% ({result['achieved'] * 100:.1f})"
            top.append(cell(result["rgb"], window, result["visible_mask"], label))
            bottom.append(cell(depth_vis(result["depth"], ref_mm), window, result["visible_mask"], side))
        sheet = np.vstack([np.hstack(top), np.hstack(bottom)])
        cv2.imwrite(str(args.out / "review" / f"{frame_id}.png"), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
        print(f"[{index + 1}/{len(chosen)}] {frame_id} side={side}")

    for level in levels:
        (args.out / f"v{level:03d}" / "meta.json").write_text(json.dumps({
            "level_percent": level, "depth_mode": args.depth_mode, "color": color,
            "front_offset_mm": args.front_offset_mm, "tol": args.tol, **meta[level],
        }, indent=1))


if __name__ == "__main__":
    main()
