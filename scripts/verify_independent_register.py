#!/usr/bin/env python3
"""Check that independent register matches run_demo.py and leaks no state between frames.

1. Repro: register of the first frame at v000 must equal run_demo.py's pose for that frame.
2. Leak:  register(A), register(B), register(A) must give the same pose for A both times.
Run inside the container.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evaluation.pose_metrics import rotation_error_deg, translation_error_m
from foundationpose_adapter.independent_register import build_estimator, make_reader, register_frame


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scene-root", type=Path, required=True)
    p.add_argument("--demo-pose-dir", type=Path, required=True, help="run_demo.py ob_in_cam folder for v000")
    p.add_argument("--mesh-file", type=Path, default=ROOT / "data/models/CADmodels/003_cracker_box/textured_simple.obj")
    args = p.parse_args()

    frames = [f["frame_id"] for f in json.loads((args.scene_root / "selection.json").read_text())["frames"]]
    reader = make_reader(args.scene_root / "v000")
    index = {f: i for i, f in enumerate(reader.id_strs)}
    estimator, _ = build_estimator(str(args.mesh_file))

    first, other = frames[0], frames[len(frames) // 2]
    pose_a1 = register_frame(estimator, reader, index[first])
    demo = np.loadtxt(args.demo_pose_dir / f"{first}.txt").reshape(4, 4)
    print(f"repro  (frame {first}): translation diff {translation_error_m(pose_a1, demo) * 1000:.4f} mm, "
          f"rotation diff {rotation_error_deg(pose_a1, demo):.4f} deg vs run_demo.py")

    register_frame(estimator, reader, index[other])
    pose_a2 = register_frame(estimator, reader, index[first])
    print(f"leak   (A,B,A)        : translation diff {translation_error_m(pose_a1, pose_a2) * 1000:.4f} mm, "
          f"rotation diff {rotation_error_deg(pose_a1, pose_a2):.4f} deg between the two A results")


if __name__ == "__main__":
    main()
