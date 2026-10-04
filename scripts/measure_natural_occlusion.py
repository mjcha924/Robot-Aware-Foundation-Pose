#!/usr/bin/env python3
"""How occluded is the object in the real frames of a YCBInEOAT sequence? (run in the container)

Renders the CAD model at each frame's ground-truth pose to get the silhouette a clear view would
show, then compares it with the annotated visible mask (and, as a cross-check, with the depth
image). Writes one CSV row per frame and prints the distribution.
"""

import argparse
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "third_party/FoundationPose"))

from occlusion.natural import occlusion_by_depth, occlusion_by_mask
from pose_eval.gt import gt_pose_paths


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scene", type=Path, required=True)
    p.add_argument("--mesh-file", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--batch", type=int, default=16)
    return p.parse_args()


def main():
    args = parse_args()
    import torch
    import trimesh
    import nvdiffrast.torch as dr
    from Utils import make_mesh_tensors, nvdiffrast_render

    scene = args.scene
    ids = sorted(p.stem for p in (scene / "rgb").glob("*.png"))
    K = np.loadtxt(scene / "cam_K.txt").reshape(3, 3)
    pose_file = gt_pose_paths(scene)
    mesh = trimesh.load(str(args.mesh_file))
    tensors, glctx = make_mesh_tensors(mesh), dr.RasterizeCudaContext()
    height, width = cv2.imread(str(scene / "depth" / f"{ids[0]}.png"), cv2.IMREAD_UNCHANGED).shape

    rows = []
    for start in range(0, len(ids), args.batch):
        chunk = ids[start:start + args.batch]
        poses = np.stack([np.loadtxt(pose_file[i]).reshape(4, 4) for i in chunk])
        _, depth, _ = nvdiffrast_render(K=K, H=height, W=width, ob_in_cams=torch.as_tensor(poses, dtype=torch.float, device="cuda"),
                                        glctx=glctx, mesh_tensors=tensors, extra={})
        rendered_mm = (depth.detach().cpu().numpy() * 1000).round().astype(np.int32)
        for frame_id, rendered in zip(chunk, rendered_mm):
            sil = rendered > 0
            mask = cv2.imread(str(scene / "gt_mask" / f"{frame_id}.png"), cv2.IMREAD_UNCHANGED) > 0
            observed = cv2.imread(str(scene / "depth" / f"{frame_id}.png"), cv2.IMREAD_UNCHANGED)
            rows.append({
                "frame_id": frame_id, "silhouette_px": int(sil.sum()), "mask_px": int(mask.sum()),
                "occ_by_mask": occlusion_by_mask(sil, mask),
                "occ_by_depth": occlusion_by_depth(sil, rendered, observed),
            })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    occ = np.array([r["occ_by_mask"] for r in rows])
    dep = np.array([r["occ_by_depth"] for r in rows])
    ok = ~np.isnan(occ) & ~np.isnan(dep)
    print(f"{scene.name}: {len(rows)} frames, silhouette median {int(np.median([r['silhouette_px'] for r in rows]))} px")
    print("occlusion by mask : mean %.1f%%  median %.1f%%  p90 %.1f%%  max %.1f%%" % (
        np.nanmean(occ) * 100, np.nanmedian(occ) * 100, np.nanpercentile(occ, 90) * 100, np.nanmax(occ) * 100))
    for level in (10, 30, 50, 70, 80, 90):
        print(f"  frames with >= {level}% hidden: {np.nansum(occ >= level / 100):4d} / {len(rows)} ({np.nanmean(occ >= level / 100) * 100:4.1f}%)")
    print("occlusion by depth: mean %.1f%%  median %.1f%%" % (np.nanmean(dep) * 100, np.nanmedian(dep) * 100))
    if ok.sum() > 2:
        print("correlation of the two estimates: %.2f" % np.corrcoef(occ[ok], dep[ok])[0, 1])


if __name__ == "__main__":
    main()
