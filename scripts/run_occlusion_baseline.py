#!/usr/bin/env python3
"""Independent per-frame FoundationPose registration over occlusion levels (run in the container).

For every (occlusion level, frame) it calls `register` from scratch with that frame's visible
object mask, and appends one JSON line to <out>/poses.jsonl. Already-recorded pairs are skipped,
so an interrupted run can be restarted with the same command.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from foundationpose_adapter.independent_register import build_estimator, make_reader, register_frame
from occlusion.occluder import make_block
from occlusion.scene import choose_side


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scene-root", type=Path, required=True, help="folder holding v000, v010, ... and selection.json")
    p.add_argument("--mesh-file", type=Path, default=ROOT / "data/models/CADmodels/003_cracker_box/textured_simple.obj")
    p.add_argument("--levels", default="0,10,20,30,40,50,60,70,80,90", help="occlusion percentages")
    p.add_argument("--limit-frames", type=int, default=0, help="use N evenly spaced frames of the selection (0 = all)")
    p.add_argument("--est-refine-iter", type=int, default=5)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--oracle", action="store_true",
                   help="blank the (known) occluder region on both sides of the network comparison")
    p.add_argument("--source-scene", type=Path, default=ROOT / "data/ycbineoat/cracker_box_reorient",
                   help="original scene whose gt_mask the blocks were built on (oracle mode)")
    p.add_argument("--seed", type=int, default=0, help="seed the scene was generated with (oracle mode)")
    p.add_argument("--tol", type=float, default=0.02, help="tolerance the scene was generated with (oracle mode)")
    return p.parse_args()


def oracle_block(args, scene, level, frame_id):
    """Rebuild the occluder of a generated frame and check it reproduces the saved visible mask."""
    obj = cv2.imread(str(args.source_scene / "gt_mask" / f"{frame_id}.png"), cv2.IMREAD_UNCHANGED) > 0
    occ = np.zeros_like(obj)
    if level > 0:
        occ, _ = make_block(obj, 1 - level / 100, choose_side(frame_id, args.seed), tol=args.tol)
    saved = cv2.imread(str(scene / "masks" / f"{frame_id}.png"), cv2.IMREAD_UNCHANGED) > 0
    if not np.array_equal(obj & ~occ, saved):
        raise SystemExit(f"rebuilt occluder does not match the saved mask for level {level} frame {frame_id}")
    return occ


def pick_frames(frame_ids, limit):
    if limit <= 0 or limit >= len(frame_ids):
        return frame_ids
    return [frame_ids[i] for i in np.unique(np.linspace(0, len(frame_ids) - 1, limit).round().astype(int))]


def main():
    args = parse_args()
    selection = json.loads((args.scene_root / "selection.json").read_text())
    frame_ids = pick_frames([f["frame_id"] for f in selection["frames"]], args.limit_frames)
    levels = [int(v) for v in args.levels.split(",")]

    args.out.mkdir(parents=True, exist_ok=True)
    results = args.out / "poses.jsonl"
    done = set()
    if results.exists():
        for line in results.read_text().splitlines():
            record = json.loads(line)
            done.add((record["level"], record["frame_id"]))

    estimator, _ = build_estimator(str(args.mesh_file))
    holder = None
    if args.oracle:
        import torch
        from foundationpose_adapter.oracle_occlusion import enable_oracle

        holder = enable_oracle(estimator)
    total = len(levels) * len(frame_ids)
    count = 0
    with results.open("a") as sink:
        for level in levels:
            scene = args.scene_root / f"v{level:03d}"
            reader = make_reader(scene)
            index_of = {frame_id: i for i, frame_id in enumerate(reader.id_strs)}
            meta = json.loads((scene / "meta.json").read_text())
            for frame_id in frame_ids:
                count += 1
                if (level, frame_id) in done:
                    continue
                info = meta["frames"][frame_id]
                record = {"frame_id": frame_id, "level": level, "side": info["side"],
                          "achieved_occluded": info["achieved_occluded"],
                          "visible_px": info["visible_px"], "object_px": info["object_px"],
                          "depth_mode": meta["depth_mode"], "pose": None, "seconds": None, "error": None}
                if holder is not None:
                    holder.occ = torch.as_tensor(oracle_block(args, scene, level, frame_id), device="cuda")
                    record["oracle"] = True
                start = time.perf_counter()
                try:
                    record["pose"] = np.asarray(register_frame(
                        estimator, reader, index_of[frame_id], iteration=args.est_refine_iter)).reshape(4, 4).tolist()
                except Exception as exc:  # keep going; the failure is part of the record
                    record["error"] = f"{type(exc).__name__}: {exc}"
                record["seconds"] = time.perf_counter() - start
                sink.write(json.dumps(record) + "\n")
                sink.flush()
                print(f"[{count}/{total}] level={level} frame={frame_id} {record['seconds']:.2f}s"
                      + (f" ERROR {record['error']}" if record["error"] else ""), flush=True)


if __name__ == "__main__":
    main()
