from __future__ import annotations

import importlib.util
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_isaac_export", PROJECT_ROOT / "scripts" / "validate_isaac_export.py"
)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

IDENTITY = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
]


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def write_png(path: Path, width: int, height: int, bit_depth: int, color_type: int) -> None:
    channels = {0: 1, 2: 3, 6: 4}[color_type]
    row_size = width * channels * (bit_depth // 8)
    raw = b"".join(b"\x00" + bytes(row_size) for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        VALIDATOR.PNG_SIGNATURE
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(raw))
        + png_chunk(b"IEND", b"")
    )


class ValidateIsaacExportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        manifest = {
            "schema_version": "1.0",
            "sequence_id": "test",
            "frame_count": 2,
            "frames_file": "frames.jsonl",
            "units": {
                "length": "meter",
                "depth_encoding": "uint16_mm",
                "depth_scale_to_m": 0.001,
            },
            "image": {
                "width": 2,
                "height": 2,
                "rgb_format": "png_rgb8",
                "depth_format": "png_uint16",
                "mask_format": "png_uint8_binary",
            },
            "camera": {
                "model": "pinhole",
                "convention": "opencv_x_right_y_down_z_forward",
                "K": [[100.0, 0.0, 1.0], [0.0, 100.0, 1.0], [0.0, 0.0, 1.0]],
            },
            "mesh": {
                "path": "mesh/object.obj",
                "units": "meter",
                "T_object_mesh": IDENTITY,
            },
            "segmentation": {"object_id": 1, "initial_mask_only": True},
        }
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (self.root / "cam_K.txt").write_text("100 0 1\n0 100 1\n0 0 1\n", encoding="utf-8")
        (self.root / "mesh").mkdir()
        (self.root / "mesh" / "object.obj").write_text("# test mesh\n", encoding="utf-8")
        frames = [
            {
                "frame_id": f"{index:06d}",
                "timestamp_s": index / 30,
                "T_world_camera": IDENTITY,
                "T_world_effector": IDENTITY,
            }
            for index in range(2)
        ]
        (self.root / "frames.jsonl").write_text(
            "".join(json.dumps(frame) + "\n" for frame in frames), encoding="utf-8"
        )
        for frame in frames:
            frame_id = frame["frame_id"]
            write_png(self.root / "rgb" / f"{frame_id}.png", 2, 2, 8, 2)
            write_png(self.root / "depth" / f"{frame_id}.png", 2, 2, 16, 0)
        write_png(self.root / "masks" / "000000.png", 2, 2, 8, 0)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_sequence(self) -> None:
        self.assertEqual(VALIDATOR.validate_sequence(self.root), [])

    def test_rejects_non_rigid_transform(self) -> None:
        frames_path = self.root / "frames.jsonl"
        frames = [json.loads(line) for line in frames_path.read_text(encoding="utf-8").splitlines()]
        frames[0]["T_world_effector"][0][0] = 2.0
        frames_path.write_text("".join(json.dumps(frame) + "\n" for frame in frames), encoding="utf-8")
        errors = VALIDATOR.validate_sequence(self.root)
        self.assertTrue(any("rotation is not orthonormal" in error for error in errors))

    def test_rejects_wrong_depth_encoding(self) -> None:
        write_png(self.root / "depth" / "000001.png", 2, 2, 8, 0)
        errors = VALIDATOR.validate_sequence(self.root)
        self.assertTrue(any("depth 000001" in error and "bit depth" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
