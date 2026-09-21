"""Audit robot-only projections against Isaac depth and audit-only semantics.

Invoked by run_isaac_sequence.py --audit-robot-geometry in the GPU container.
This validates the robot export; it does not estimate the object's pose.
"""

import hashlib
import json
import time


def audit(sequence, output, manifest, frames):
    import cv2
    import numpy as np
    import torch
    from urdf_render.robot_depth import RobotDepthRenderer
    from evaluation.robot_geometry import ROBOT_PROJECTION_GATES, robot_projection_passes

    geometry = manifest.get("robot_geometry")
    if geometry is None or geometry.get("validation_mask_dir") != "robot_masks":
        raise ValueError("audit requires versioned robot geometry and audit-only semantic masks")
    renderer = RobotDepthRenderer(sequence, geometry)
    height, width = manifest["image"]["height"], manifest["image"]["width"]
    rows = []
    selected = {0, len(frames) // 2, len(frames) - 1, 99, 106, 118}
    (output / "overlays").mkdir()
    for index, frame in enumerate(frames):
        frame_id = frame["frame_id"]
        torch.cuda.synchronize()
        start = time.perf_counter()
        rendered = renderer.render(frame["T_world_camera"], frame["T_world_robot_links"],
                                   manifest["camera"]["K"], height, width)
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        rendered = rendered.cpu().numpy()
        observed = cv2.imread(str(sequence / "depth" / f"{frame_id}.png"), cv2.IMREAD_UNCHANGED)
        semantic = cv2.imread(str(sequence / "robot_masks" / f"{frame_id}.png"), cv2.IMREAD_UNCHANGED)
        if observed is None or semantic is None:
            raise ValueError(f"failed to read audit data for frame {frame_id}")
        observed = observed.astype(np.float32) * manifest["units"]["depth_scale_to_m"]
        target = semantic > 0
        predicted = rendered > 0
        # A nearer scene surface can legitimately hide the robot. This uses
        # observed scene depth only, not object truth, to test visible support.
        visible = predicted & (observed > 0) & (rendered <= observed + 0.01)
        union = np.count_nonzero(visible | target)
        overlap = predicted & target & (observed > 0)
        errors = np.abs(rendered[overlap] - observed[overlap])
        row = {
            "frame_id": frame_id,
            "robot_pixels": int(target.sum()),
            "visible_projection_iou": float(np.count_nonzero(visible & target) / max(union, 1)),
            "robot_pixel_coverage": float(np.count_nonzero(predicted & target) / max(target.sum(), 1)),
            "depth_median_abs_error_m": float(np.median(errors)) if errors.size else None,
            "depth_p95_abs_error_m": float(np.percentile(errors, 95)) if errors.size else None,
            "render_s": elapsed,
        }
        rows.append(row)
        if index in selected:
            rgb = cv2.imread(str(sequence / "rgb" / f"{frame_id}.png"))
            overlay = rgb.copy()
            # Cyan = reconstructed visible robot; orange = semantic disagreement.
            overlay[visible] = (0.55 * overlay[visible] + 0.45 * np.array([255, 255, 0])).astype(np.uint8)
            overlay[visible ^ target] = [0, 128, 255]
            if not cv2.imwrite(str(output / "overlays" / f"{frame_id}.png"), overlay):
                raise OSError(f"failed to save robot audit overlay {frame_id}")
        print(f"Robot audit {frame_id}: IoU={row['visible_projection_iou']:.4f}", flush=True)
    # Explicit engineering gates, fixed before looking at this run. These
    # check projection consistency, not effector-aware pose accuracy.
    passed = robot_projection_passes(rows)
    report = {
        "passed": passed, "frame_count": len(rows), "link_count": len(geometry["links"]),
        "gates": ROBOT_PROJECTION_GATES,
        "min_visible_projection_iou": min(row["visible_projection_iou"] for row in rows),
        "min_robot_pixel_coverage": min(row["robot_pixel_coverage"] for row in rows),
        "max_frame_depth_p95_abs_error_m": max(
            (row["depth_p95_abs_error_m"] for row in rows if row["depth_p95_abs_error_m"] is not None), default=None),
        "median_render_s_excluding_first": float(np.median([row["render_s"] for row in rows[1:] or rows])),
        "input_metadata_sha256": {name: hashlib.sha256((sequence / name).read_bytes()).hexdigest()
                                  for name in ("manifest.json", "frames.jsonl")},
        "robot_mesh_sha256": {link["name"]: link["sha256"] for link in geometry["links"]},
        "notes": "Robot geometry and link poses only enter rendering. Scene depth and simulator robot semantics are audit-only. No object pose ground truth is read. Timing excludes mesh loading, readback and audit.",
        "frames": rows,
    }
    (output / "robot_geometry_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "frames"}, indent=2))
    if not passed:
        raise RuntimeError("robot projection audit failed; see robot_geometry_audit.json")
