#!/usr/bin/env python3
"""Capture an EA-FoundationPose sequence from ROBOTIS Lab's OMY bottle task.

This entry point is intentionally kept in this repository. It reads the
existing ROBOTIS Lab task and assets without modifying that worktree.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from isaaclab.app import AppLauncher


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--robotis-lab-root", type=Path, default=Path("/home/mjcha/robotis_lab"))
parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data/isaac_exports/omy_bottle_short")
parser.add_argument("--camera", choices=("top", "wrist"), default="top")
parser.add_argument("--frames", type=int, default=10)
parser.add_argument("--warmup-steps", type=int, default=12)
parser.add_argument("--stride", type=int, default=2, help="Environment steps between exported frames.")
parser.add_argument("--seed", type=int, default=42)
parser.add_argument(
    "--motion",
    choices=("static", "effector-sweep"),
    default="static",
    help="Keep the reset pose or sweep the end effector above the bottle to induce occlusion.",
)
parser.add_argument(
    "--sweep-clearance-m",
    type=float,
    default=0.16,
    help="Effector height above the bottle origin during an effector sweep.",
)
parser.add_argument(
    "--sweep-span-m",
    type=float,
    default=0.16,
    help="Total lateral travel centered over the bottle during an effector sweep.",
)
parser.add_argument("--overwrite", action="store_true")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
args_cli.headless = True
args_cli.enable_cameras = True

robotis_package = args_cli.robotis_lab_root.resolve() / "source" / "robotis_lab"
if not (robotis_package / "robotis_lab").is_dir():
    parser.error(f"ROBOTIS Lab Python package not found under {robotis_package}")
sys.path.insert(0, str(robotis_package))

app_launcher = AppLauncher(vars(args_cli))
simulation_app = app_launcher.app

# Isaac/Omniverse imports must follow application startup.
import cv2  # noqa: E402
import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
import torch  # noqa: E402
from pxr import Usd, UsdGeom  # noqa: E402

import robotis_lab  # noqa: E402,F401
from isaaclab.envs import ManagerBasedRLEnv  # noqa: E402
from isaaclab_tasks.utils import parse_env_cfg  # noqa: E402
from isaaclab.utils.math import matrix_from_quat, subtract_frame_transforms  # noqa: E402


TASK = "RobotisLab-Real-Pick-Place-Bottle-OMY-v0"
TARGET_RGBA = (17, 231, 97, 255)


def prepare_output(root: Path, overwrite: bool) -> None:
    if root.exists() and any(root.iterdir()):
        if not overwrite:
            raise FileExistsError(f"output directory is not empty: {root}; pass --overwrite to replace it")
        shutil.rmtree(root)
    for relative in ("rgb", "depth", "masks", "mesh"):
        (root / relative).mkdir(parents=True, exist_ok=True)


def pose_matrix(position: torch.Tensor, quaternion_wxyz: torch.Tensor) -> list[list[float]]:
    result = torch.eye(4, dtype=torch.float64, device=position.device)
    result[:3, :3] = matrix_from_quat(quaternion_wxyz).to(dtype=torch.float64)
    result[:3, 3] = position.to(dtype=torch.float64)
    return result.cpu().tolist()


def write_obj_from_stage(path: Path, rigid_root_path: str) -> tuple[int, int]:
    """Export visible USD meshes below a rigid-body prim as one geometry-only OBJ."""

    stage = omni.usd.get_context().get_stage()
    root = stage.GetPrimAtPath(rigid_root_path)
    if not root.IsValid():
        raise RuntimeError(f"bottle rigid-body prim does not exist: {rigid_root_path}")
    xforms = UsdGeom.XformCache(Usd.TimeCode.Default())
    root_inverse = xforms.GetLocalToWorldTransform(root).GetInverse()
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []

    for prim in Usd.PrimRange(root):
        if not prim.IsA(UsdGeom.Mesh):
            continue
        imageable = UsdGeom.Imageable(prim)
        if imageable.ComputeVisibility() == UsdGeom.Tokens.invisible:
            continue
        if imageable.ComputePurpose() == UsdGeom.Tokens.proxy:
            continue
        mesh = UsdGeom.Mesh(prim)
        points = mesh.GetPointsAttr().Get()
        counts = mesh.GetFaceVertexCountsAttr().Get()
        indices = mesh.GetFaceVertexIndicesAttr().Get()
        if points is None or counts is None or indices is None:
            continue
        local_to_world = xforms.GetLocalToWorldTransform(prim)
        offset = len(vertices) + 1
        for point in points:
            transformed = root_inverse.Transform(local_to_world.Transform(point))
            vertices.append((float(transformed[0]), float(transformed[1]), float(transformed[2])))
        cursor = 0
        for count in counts:
            face = [offset + int(indices[cursor + index]) for index in range(int(count))]
            cursor += int(count)
            for index in range(1, len(face) - 1):
                triangles.append((face[0], face[index], face[index + 1]))

    if not vertices or not triangles:
        raise RuntimeError(f"no visible triangle meshes found below {rigid_root_path}")
    with path.open("w", encoding="utf-8") as stream:
        stream.write("# Exported from ROBOTIS Lab plastic_bottle.usd\n")
        for x, y, z in vertices:
            stream.write(f"v {x:.9g} {y:.9g} {z:.9g}\n")
        for a, b, c in triangles:
            stream.write(f"f {a} {b} {c}\n")
    return len(vertices), len(triangles)


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def sweep_position(
    progress: float,
    home: torch.Tensor,
    bottle: torch.Tensor,
    clearance_m: float,
    span_m: float,
) -> torch.Tensor:
    """Generate a smooth home-to-bottle-to-home occlusion trajectory."""

    start = bottle.clone()
    start[1] -= span_m * 0.5
    start[2] += clearance_m
    end = start.clone()
    end[1] += span_m
    if progress < 0.15:
        return home
    if progress < 0.40:
        blend = smoothstep((progress - 0.15) / 0.25)
        return home + (start - home) * blend
    if progress < 0.70:
        blend = smoothstep((progress - 0.40) / 0.30)
        return start + (end - start) * blend
    if progress < 0.90:
        blend = smoothstep((progress - 0.70) / 0.20)
        return end + (home - end) * blend
    return home


def main() -> int:
    if args_cli.frames < 1 or args_cli.warmup_steps < 0 or args_cli.stride < 1:
        parser.error("--frames and --stride must be positive; --warmup-steps must be non-negative")
    if args_cli.sweep_clearance_m <= 0.0 or args_cli.sweep_span_m <= 0.0:
        parser.error("--sweep-clearance-m and --sweep-span-m must be positive")
    output = args_cli.output.resolve()
    prepare_output(output, args_cli.overwrite)

    env_cfg = parse_env_cfg(TASK, device=args_cli.device, num_envs=1)
    env_cfg.init_action_cfg("mimic_ik" if args_cli.motion == "effector-sweep" else "record")
    env_cfg.seed = args_cli.seed
    env_cfg.scene.num_envs = 1
    env_cfg.scene.replicate_physics = False
    env_cfg.num_rerenders_on_reset = 2

    camera_name = f"cam_{args_cli.camera}"
    camera_cfg = getattr(env_cfg.scene, camera_name)
    camera_cfg.data_types = ["rgb", "distance_to_image_plane", "semantic_segmentation"]
    camera_cfg.colorize_semantic_segmentation = True
    camera_cfg.semantic_segmentation_mapping = {
        "class:target_object": TARGET_RGBA,
        "class:robot": (90, 110, 255, 255),
        "class:ground": (80, 80, 80, 255),
        "class:UNLABELLED": (0, 0, 0, 255),
        "class:BACKGROUND": (0, 0, 0, 255),
    }
    env_cfg.scene.bottle.spawn.semantic_tags = [("class", "target_object")]

    env: ManagerBasedRLEnv = gym.make(TASK, cfg=env_cfg).unwrapped
    env.reset()
    try:
        robot = env.scene["robot"]
        joint_index = {name: index for index, name in enumerate(robot.data.joint_names)}
        gripper = robot.data.joint_pos[:, joint_index["rh_r1_joint"] : joint_index["rh_r1_joint"] + 1].clone()
        if args_cli.motion == "static":
            # The task's record action is [joint1..joint6, rh_r1_joint].
            # Holding the reset pose produces the deterministic smoke control.
            action_names = [f"joint{index}" for index in range(1, 7)] + ["rh_r1_joint"]
            static_action = torch.stack([robot.data.joint_pos[:, joint_index[name]] for name in action_names], dim=1)

            def action_at(_progress: float) -> torch.Tensor:
                return static_action

        else:
            ee_data = env.scene["ee_frame"].data
            bottle_data = env.scene["bottle"].data
            home_position, home_quaternion = subtract_frame_transforms(
                robot.data.root_pos_w,
                robot.data.root_quat_w,
                ee_data.target_pos_w[:, 0],
                ee_data.target_quat_w[:, 0],
            )
            bottle_position, _ = subtract_frame_transforms(
                robot.data.root_pos_w,
                robot.data.root_quat_w,
                bottle_data.root_pos_w,
                bottle_data.root_quat_w,
            )
            print(
                "Effector sweep: "
                f"home={home_position[0].tolist()}, bottle={bottle_position[0].tolist()}, "
                f"clearance={args_cli.sweep_clearance_m:.3f} m, span={args_cli.sweep_span_m:.3f} m"
            )

            def action_at(progress: float) -> torch.Tensor:
                position = sweep_position(
                    progress,
                    home_position[0],
                    bottle_position[0],
                    args_cli.sweep_clearance_m,
                    args_cli.sweep_span_m,
                ).unsqueeze(0)
                return torch.cat((position, home_quaternion, gripper), dim=1)

        action = action_at(0.0)
        if action.shape[1] != env.action_manager.total_action_dim:
            raise RuntimeError(
                f"OMY action dimension changed: assembled {action.shape[1]}, manager expects {env.action_manager.total_action_dim}"
            )

        for _ in range(args_cli.warmup_steps):
            env.step(action)

        camera = env.scene[camera_name]
        intrinsic = camera.data.intrinsic_matrices[0].detach().cpu().numpy()
        frames: list[dict] = []
        motion_steps = max(1, args_cli.frames * args_cli.stride - 1)
        for frame_index in range(args_cli.frames):
            for stride_index in range(args_cli.stride):
                motion_step = frame_index * args_cli.stride + stride_index
                env.step(action_at(motion_step / motion_steps))
            frame_id = f"{frame_index:06d}"
            rgb = camera.data.output["rgb"][0].detach().cpu().numpy()
            depth_m = camera.data.output["distance_to_image_plane"][0, ..., 0].detach().cpu().numpy()
            semantic = camera.data.output["semantic_segmentation"][0].detach().cpu().numpy()
            mask = np.all(semantic[..., :3] == np.asarray(TARGET_RGBA[:3], dtype=np.uint8), axis=-1).astype(np.uint8) * 255
            if not np.any(mask):
                unique = np.unique(semantic.reshape(-1, semantic.shape[-1]), axis=0)
                raise RuntimeError(f"target mask is empty; semantic colors present: {unique[:20].tolist()}")

            depth_mm = np.zeros(depth_m.shape, dtype=np.uint16)
            valid = np.isfinite(depth_m) & (depth_m > 0.0) & (depth_m < 65.535)
            depth_mm[valid] = np.rint(depth_m[valid] * 1000.0).astype(np.uint16)
            if not cv2.imwrite(str(output / "rgb" / f"{frame_id}.png"), rgb[..., ::-1]):
                raise RuntimeError(f"failed to write RGB frame {frame_id}")
            if not cv2.imwrite(str(output / "depth" / f"{frame_id}.png"), depth_mm):
                raise RuntimeError(f"failed to write depth frame {frame_id}")
            if not cv2.imwrite(str(output / "masks" / f"{frame_id}.png"), mask):
                raise RuntimeError(f"failed to write mask frame {frame_id}")

            ee_data = env.scene["ee_frame"].data
            bottle_data = env.scene["bottle"].data
            frames.append(
                {
                    "frame_id": frame_id,
                    "timestamp_s": float(env.episode_length_buf[0].item() * env.step_dt),
                    "T_world_camera": pose_matrix(camera.data.pos_w[0], camera.data.quat_w_ros[0]),
                    "T_world_effector": pose_matrix(ee_data.target_pos_w[0, 0], ee_data.target_quat_w[0, 0]),
                    "T_world_object_gt": pose_matrix(bottle_data.root_pos_w[0], bottle_data.root_quat_w[0]),
                }
            )

        rigid_root_path = env.scene["bottle"].root_physx_view.prim_paths[0]
        vertex_count, triangle_count = write_obj_from_stage(output / "mesh/object.obj", rigid_root_path)
        np.savetxt(output / "cam_K.txt", intrinsic, fmt="%.12g")
        with (output / "frames.jsonl").open("w", encoding="utf-8") as stream:
            for frame in frames:
                stream.write(json.dumps(frame, separators=(",", ":")) + "\n")
        manifest = {
            "schema_version": "1.0",
            "sequence_id": output.name,
            "frame_count": len(frames),
            "frames_file": "frames.jsonl",
            "units": {"length": "meter", "depth_encoding": "uint16_mm", "depth_scale_to_m": 0.001},
            "image": {
                "width": int(camera.cfg.width),
                "height": int(camera.cfg.height),
                "rgb_format": "png_rgb8",
                "depth_format": "png_uint16",
                "mask_format": "png_uint8_binary",
            },
            "camera": {
                "name": camera_name,
                "model": "pinhole",
                "convention": "opencv_x_right_y_down_z_forward",
                "K": intrinsic.tolist(),
            },
            "mesh": {
                "path": "mesh/object.obj",
                "units": "meter",
                "T_object_mesh": np.eye(4).tolist(),
                "source": str(args_cli.robotis_lab_root.resolve() / "source/robotis_lab/data/object/plastic_bottle.usd"),
                "vertex_count": vertex_count,
                "triangle_count": triangle_count,
            },
            "segmentation": {"object_id": 1, "initial_mask_only": False},
            "source": {
                "task": TASK,
                "robotis_lab_commit": "e32b122d192c2db7fe52cfd3ece74c07f6a418a6",
                "seed": args_cli.seed,
                "end_effector": "OMY/link6 offset [0, -0.248, 0]",
                "motion": args_cli.motion,
                "sweep_clearance_m": args_cli.sweep_clearance_m if args_cli.motion == "effector-sweep" else None,
                "sweep_span_m": args_cli.sweep_span_m if args_cli.motion == "effector-sweep" else None,
            },
        }
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"Captured {len(frames)} OMY frames into {output}")
        return 0
    finally:
        env.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        simulation_app.close()
