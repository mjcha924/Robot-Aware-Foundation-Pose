#!/usr/bin/env python3
"""Run FoundationPose on a validated EA-FoundationPose Isaac export."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FOUNDATIONPOSE_ROOT = PROJECT_ROOT / "third_party" / "FoundationPose"
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(FOUNDATIONPOSE_ROOT))

from foundationpose_adapter.transforms import effector_object_transform, matmul4, rigid_inverse  # noqa: E402
from validate_isaac_export import validate_sequence  # noqa: E402


def load_metadata(sequence: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads((sequence / "manifest.json").read_text(encoding="utf-8"))
    frames = [json.loads(line) for line in (sequence / manifest["frames_file"]).read_text(encoding="utf-8").splitlines()]
    return manifest, frames


def prepare_output(path: Path, overwrite: bool) -> None:
    if path.exists() and any(path.iterdir()):
        if not overwrite:
            raise FileExistsError(f"output directory is not empty: {path}; pass --overwrite to replace it")
        shutil.rmtree(path)
    (path / "camera_object").mkdir(parents=True, exist_ok=True)
    (path / "effector_object").mkdir(parents=True, exist_ok=True)
    (path / "track_vis").mkdir(parents=True, exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sequence", type=Path)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "outputs" / "isaac_foundationpose")
    parser.add_argument("--est-refine-iter", type=int, default=5)
    parser.add_argument("--track-refine-iter", type=int, default=2)
    parser.add_argument("--save-vis", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--audit-robot-geometry", action="store_true",
                        help="Validate robot-only projection instead of running object pose inference.")
    args = parser.parse_args()

    sequence = args.sequence.resolve()
    output = args.output.resolve()
    errors = validate_sequence(sequence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    prepare_output(output, args.overwrite)
    if args.audit_robot_geometry:
        from audit_robot_geometry import audit
        manifest, frames = load_metadata(sequence)
        audit(sequence, output, manifest, frames)
        return 0

    # Heavy imports stay below validation so malformed input fails quickly.
    import cv2
    import imageio.v2 as imageio
    import numpy as np
    import nvdiffrast.torch as dr
    import trimesh
    import torch
    from estimater import FoundationPose, PoseRefinePredictor, ScorePredictor
    from Utils import draw_posed_3d_box, draw_xyz_axis, set_logging_format, set_seed

    set_logging_format()
    set_seed(0)
    manifest, frames = load_metadata(sequence)
    intrinsic = np.asarray(manifest["camera"]["K"], dtype=np.float64)
    t_object_mesh = np.asarray(manifest["mesh"]["T_object_mesh"], dtype=np.float64)
    mesh = trimesh.load(sequence / manifest["mesh"]["path"])
    to_origin, extents = trimesh.bounds.oriented_bounds(mesh)
    bbox = np.stack([-extents / 2, extents / 2], axis=0).reshape(2, 3)

    estimator = FoundationPose(
        model_pts=mesh.vertices,
        model_normals=mesh.vertex_normals,
        mesh=mesh,
        scorer=ScorePredictor(),
        refiner=PoseRefinePredictor(),
        debug_dir=str(output),
        debug=0,
        glctx=dr.RasterizeCudaContext(),
    )
    logging.info("estimator initialization done")

    results: list[dict] = []
    for index, frame in enumerate(frames):
        frame_id = frame["frame_id"]
        bgr = cv2.imread(str(sequence / "rgb" / f"{frame_id}.png"), cv2.IMREAD_COLOR)
        depth_mm = cv2.imread(str(sequence / "depth" / f"{frame_id}.png"), cv2.IMREAD_UNCHANGED)
        if bgr is None or depth_mm is None:
            raise RuntimeError(f"failed to decode RGB-D frame {frame_id}")
        rgb = bgr[..., ::-1].copy()
        depth = depth_mm.astype(np.float32) * float(manifest["units"]["depth_scale_to_m"])
        depth[depth < 0.001] = 0.0

        if index == 0:
            mask = cv2.imread(str(sequence / "masks" / f"{frame_id}.png"), cv2.IMREAD_UNCHANGED)
            if mask is None or not np.any(mask):
                raise RuntimeError(f"initial object mask is empty: {frame_id}")

        torch.cuda.synchronize()
        inference_start = time.perf_counter()
        if index == 0:
            t_camera_mesh = estimator.register(
                K=intrinsic,
                rgb=rgb,
                depth=depth,
                ob_mask=mask.astype(bool),
                iteration=args.est_refine_iter,
            )
        else:
            t_camera_mesh = estimator.track_one(
                rgb=rgb,
                depth=depth,
                K=intrinsic,
                iteration=args.track_refine_iter,
            )
        torch.cuda.synchronize()
        inference_s = time.perf_counter() - inference_start

        # The estimator tracks the raw mesh frame. Convert to the declared
        # object frame before composing it with camera and effector poses.
        t_camera_object = t_camera_mesh @ np.linalg.inv(t_object_mesh)
        t_effector_object = np.asarray(
            effector_object_transform(frame["T_world_effector"], frame["T_world_camera"], t_camera_object.tolist())
        )
        np.savetxt(output / "camera_object" / f"{frame_id}.txt", t_camera_object)
        np.savetxt(output / "effector_object" / f"{frame_id}.txt", t_effector_object)

        result = {
            "frame_id": frame_id,
            "timestamp_s": frame["timestamp_s"],
            "T_camera_object": t_camera_object.tolist(),
            "T_effector_object": t_effector_object.tolist(),
            "operation": "register" if index == 0 else "track",
            "candidate_count": len(estimator.rot_grid) if index == 0 else 1,
            "inference_s": inference_s,
        }
        for key in ("visible_mask_pixels", "motion_progress"):
            if key in frame:
                result[key] = frame[key]
        if "T_world_object_gt" in frame:
            t_camera_object_gt = matmul4(rigid_inverse(frame["T_world_camera"]), frame["T_world_object_gt"])
            result["T_camera_object_gt"] = t_camera_object_gt
            result["T_effector_object_gt"] = effector_object_transform(
                frame["T_world_effector"], frame["T_world_camera"], t_camera_object_gt
            )
        results.append(result)

        if args.save_vis:
            center_pose = t_camera_mesh @ np.linalg.inv(to_origin)
            vis = draw_posed_3d_box(intrinsic, img=rgb, ob_in_cam=center_pose, bbox=bbox)
            vis = draw_xyz_axis(
                vis,
                ob_in_cam=center_pose,
                scale=max(float(extents.max()) * 0.5, 0.02),
                K=intrinsic,
                thickness=3,
                transparency=0,
                is_input_rgb=True,
            )
            imageio.imwrite(output / "track_vis" / f"{frame_id}.png", vis)

    with (output / "poses.jsonl").open("w", encoding="utf-8") as stream:
        for result in results:
            stream.write(json.dumps(result, separators=(",", ":")) + "\n")
    run_info = {
        "sequence": str(sequence),
        "frame_count": len(results),
        "est_refine_iter": args.est_refine_iter,
        "track_refine_iter": args.track_refine_iter,
        "foundationpose_commit": "a1b694b83e633c2cb6115b9063d940a687759392",
        "input_metadata_sha256": {
            name: hashlib.sha256((sequence / name).read_bytes()).hexdigest()
            for name in ("manifest.json", "frames.jsonl")
        },
        "timing": "CUDA-synchronized estimator call; excludes image decoding, pose export and visualization",
    }
    (output / "run.json").write_text(json.dumps(run_info, indent=2) + "\n", encoding="utf-8")
    print(f"Processed {len(results)} frames into {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
