#!/usr/bin/env python3
"""Validate an EA-FoundationPose Isaac export without third-party packages."""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


FRAME_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_matrix(value: Any, size: int, name: str, errors: list[str]) -> list[list[float]] | None:
    if not isinstance(value, list) or len(value) != size:
        errors.append(f"{name}: expected {size} rows")
        return None
    matrix: list[list[float]] = []
    for row_index, row in enumerate(value):
        if not isinstance(row, list) or len(row) != size or not all(is_number(item) for item in row):
            errors.append(f"{name}[{row_index}]: expected {size} finite numbers")
            return None
        matrix.append([float(item) for item in row])
    return matrix


def determinant3(matrix: list[list[float]]) -> float:
    a, b, c = matrix
    return (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )


def validate_rigid_transform(value: Any, name: str, errors: list[str], tolerance: float = 1e-4) -> None:
    matrix = validate_matrix(value, 4, name, errors)
    if matrix is None:
        return
    expected_last = [0.0, 0.0, 0.0, 1.0]
    if any(abs(actual - expected) > tolerance for actual, expected in zip(matrix[3], expected_last)):
        errors.append(f"{name}: last row must be [0, 0, 0, 1]")
    rotation = [row[:3] for row in matrix[:3]]
    for left in range(3):
        for right in range(3):
            dot = sum(rotation[row][left] * rotation[row][right] for row in range(3))
            expected = 1.0 if left == right else 0.0
            if abs(dot - expected) > tolerance:
                errors.append(f"{name}: rotation is not orthonormal")
                return
    det = determinant3(rotation)
    if abs(det - 1.0) > tolerance:
        errors.append(f"{name}: rotation determinant is {det:.6g}, expected 1")


def safe_relative_path(value: Any, name: str, errors: list[str]) -> Path | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{name}: expected a non-empty relative path")
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        errors.append(f"{name}: absolute paths and '..' are forbidden")
        return None
    return Path(*path.parts)


def png_header(path: Path) -> tuple[int, int, int, int]:
    with path.open("rb") as stream:
        if stream.read(8) != PNG_SIGNATURE:
            raise ValueError("not a PNG file")
        length = struct.unpack(">I", stream.read(4))[0]
        if stream.read(4) != b"IHDR" or length != 13:
            raise ValueError("missing canonical IHDR chunk")
        width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", stream.read(13))
    return width, height, bit_depth, color_type


def validate_png(
    path: Path,
    expected_size: tuple[int, int],
    bit_depth: int,
    color_types: Iterable[int],
    name: str,
    errors: list[str],
) -> None:
    if not path.is_file():
        errors.append(f"{name}: missing {path}")
        return
    try:
        width, height, actual_depth, color_type = png_header(path)
    except (OSError, ValueError, struct.error) as exc:
        errors.append(f"{name}: cannot read PNG header: {exc}")
        return
    if (width, height) != expected_size:
        errors.append(f"{name}: image is {width}x{height}, expected {expected_size[0]}x{expected_size[1]}")
    if actual_depth != bit_depth or color_type not in set(color_types):
        errors.append(f"{name}: PNG bit depth/color type is {actual_depth}/{color_type}")


def validate_manifest(manifest: Any, errors: list[str]) -> None:
    if not isinstance(manifest, dict):
        errors.append("manifest.json: top level must be an object")
        return
    expected_constants = {
        "schema_version": "1.0",
        "frames_file": "frames.jsonl",
    }
    for key, expected in expected_constants.items():
        if manifest.get(key) != expected:
            errors.append(f"manifest.{key}: expected {expected!r}")
    if not isinstance(manifest.get("sequence_id"), str) or not manifest["sequence_id"]:
        errors.append("manifest.sequence_id: expected a non-empty string")
    if not isinstance(manifest.get("frame_count"), int) or manifest["frame_count"] < 1:
        errors.append("manifest.frame_count: expected a positive integer")

    units = manifest.get("units", {})
    if units != {"length": "meter", "depth_encoding": "uint16_mm", "depth_scale_to_m": 0.001}:
        errors.append("manifest.units: expected metre geometry and uint16 millimetre depth")

    image = manifest.get("image", {})
    for key in ("width", "height"):
        if not isinstance(image.get(key), int) or image[key] < 1:
            errors.append(f"manifest.image.{key}: expected a positive integer")
    expected_formats = {
        "rgb_format": "png_rgb8",
        "depth_format": "png_uint16",
        "mask_format": "png_uint8_binary",
    }
    for key, expected in expected_formats.items():
        if image.get(key) != expected:
            errors.append(f"manifest.image.{key}: expected {expected!r}")

    camera = manifest.get("camera", {})
    if camera.get("model") != "pinhole":
        errors.append("manifest.camera.model: expected 'pinhole'")
    if camera.get("convention") != "opencv_x_right_y_down_z_forward":
        errors.append("manifest.camera.convention: expected the OpenCV camera convention")
    intrinsic = validate_matrix(camera.get("K"), 3, "manifest.camera.K", errors)
    if intrinsic is not None:
        if intrinsic[0][0] <= 0 or intrinsic[1][1] <= 0:
            errors.append("manifest.camera.K: focal lengths must be positive")
        if any(abs(a - b) > 1e-9 for a, b in zip(intrinsic[2], [0.0, 0.0, 1.0])):
            errors.append("manifest.camera.K: final row must be [0, 0, 1]")

    mesh = manifest.get("mesh", {})
    safe_relative_path(mesh.get("path"), "manifest.mesh.path", errors)
    if mesh.get("units") != "meter":
        errors.append("manifest.mesh.units: expected 'meter'")
    validate_rigid_transform(mesh.get("T_object_mesh"), "manifest.mesh.T_object_mesh", errors)

    segmentation = manifest.get("segmentation", {})
    if not isinstance(segmentation.get("object_id"), int) or segmentation["object_id"] < 0:
        errors.append("manifest.segmentation.object_id: expected a non-negative integer")
    if not isinstance(segmentation.get("initial_mask_only"), bool):
        errors.append("manifest.segmentation.initial_mask_only: expected a boolean")


def validate_sequence(root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return [f"missing {manifest_path}"]
    try:
        manifest = load_json(manifest_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest.json: {exc}"]
    validate_manifest(manifest, errors)
    if errors:
        return errors

    width = manifest["image"]["width"]
    height = manifest["image"]["height"]
    expected_size = (width, height)

    frames_relative = safe_relative_path(manifest["frames_file"], "manifest.frames_file", errors)
    mesh_relative = safe_relative_path(manifest["mesh"]["path"], "manifest.mesh.path", errors)
    if mesh_relative is not None and not (root / mesh_relative).is_file():
        errors.append(f"mesh: missing {root / mesh_relative}")

    intrinsic_path = root / "cam_K.txt"
    if not intrinsic_path.is_file():
        errors.append(f"camera intrinsics: missing {intrinsic_path}")
    else:
        try:
            values = [float(value) for value in intrinsic_path.read_text(encoding="utf-8").split()]
            expected = [float(value) for row in manifest["camera"]["K"] for value in row]
            if len(values) != 9 or any(abs(a - b) > 1e-6 for a, b in zip(values, expected)):
                errors.append("cam_K.txt: values do not match manifest.camera.K")
        except (OSError, ValueError) as exc:
            errors.append(f"cam_K.txt: {exc}")

    if frames_relative is None or not (root / frames_relative).is_file():
        errors.append(f"frames: missing {root / (frames_relative or Path('frames.jsonl'))}")
        return errors

    frames: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    with (root / frames_relative).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            try:
                frame = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"frames.jsonl:{line_number}: {exc}")
                continue
            if not isinstance(frame, dict):
                errors.append(f"frames.jsonl:{line_number}: expected an object")
                continue
            frame_id = frame.get("frame_id")
            if not isinstance(frame_id, str) or not FRAME_ID_RE.fullmatch(frame_id):
                errors.append(f"frames.jsonl:{line_number}: invalid frame_id")
                continue
            if frame_id in seen_ids:
                errors.append(f"frames.jsonl:{line_number}: duplicate frame_id {frame_id!r}")
            seen_ids.add(frame_id)
            if not is_number(frame.get("timestamp_s")) or frame["timestamp_s"] < 0:
                errors.append(f"frames.jsonl:{line_number}: timestamp_s must be finite and non-negative")
            validate_rigid_transform(frame.get("T_world_camera"), f"frame {frame_id}.T_world_camera", errors)
            validate_rigid_transform(frame.get("T_world_effector"), f"frame {frame_id}.T_world_effector", errors)
            if "T_world_object_gt" in frame:
                validate_rigid_transform(frame["T_world_object_gt"], f"frame {frame_id}.T_world_object_gt", errors)
            frames.append(frame)

    if len(frames) != manifest["frame_count"]:
        errors.append(f"frame_count: manifest says {manifest['frame_count']}, found {len(frames)}")

    initial_mask_only = manifest["segmentation"]["initial_mask_only"]
    for index, frame in enumerate(frames):
        frame_id = frame.get("frame_id")
        if not isinstance(frame_id, str) or not FRAME_ID_RE.fullmatch(frame_id):
            continue
        validate_png(root / "rgb" / f"{frame_id}.png", expected_size, 8, (2, 6), f"RGB {frame_id}", errors)
        validate_png(root / "depth" / f"{frame_id}.png", expected_size, 16, (0,), f"depth {frame_id}", errors)
        if index == 0 or not initial_mask_only:
            validate_png(root / "masks" / f"{frame_id}.png", expected_size, 8, (0,), f"mask {frame_id}", errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sequence", type=Path, help="Isaac export sequence directory")
    args = parser.parse_args()
    root = args.sequence.resolve()
    errors = validate_sequence(root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Validation failed with {len(errors)} error(s).", file=sys.stderr)
        return 1
    print(f"Validated Isaac export: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
