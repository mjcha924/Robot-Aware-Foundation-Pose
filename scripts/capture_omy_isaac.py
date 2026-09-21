#!/usr/bin/env python3
"""Capture an EA-FoundationPose sequence from ROBOTIS Lab's OMY bottle task.

This entry point is intentionally kept in this repository. It reads the
existing ROBOTIS Lab task and assets without modifying that worktree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import traceback
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
parser.add_argument("--export-robot-geometry", action="store_true",
                    help="Export rigid-link visual meshes and synchronized link poses for EA inference.")
parser.add_argument("--diagnose-ik", action="store_true", help="Audit the IK Jacobian by joint perturbations, then exit without a capture.")
parser.add_argument("--max-effector-error-m", type=float, default=0.03,
                    help="Reject a sweep if the tool deviates farther than this from its command.")
parser.add_argument("--sweep-pitch-deg", type=float, default=90.0,
                    help="Pitch the home tool orientation about base +Y during the sweep (90 points fingers down).")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
args_cli.headless = True
args_cli.enable_cameras = True

robotis_package = args_cli.robotis_lab_root.resolve() / "source" / "robotis_lab"
if not (robotis_package / "robotis_lab").is_dir():
    parser.error(f"ROBOTIS Lab Python package not found under {robotis_package}")
sys.path.insert(0, str(robotis_package))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

app_launcher = AppLauncher(vars(args_cli))
simulation_app = app_launcher.app

# Isaac/Omniverse imports must follow application startup.
import cv2  # noqa: E402
import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
import torch  # noqa: E402
from pxr import Usd, UsdGeom, UsdPhysics  # noqa: E402

import robotis_lab  # noqa: E402,F401
from isaaclab.envs import ManagerBasedRLEnv  # noqa: E402
from isaaclab.managers import RecorderManagerBaseCfg  # noqa: E402
from isaaclab_tasks.utils import parse_env_cfg  # noqa: E402
from isaaclab.utils.math import compute_pose_error, matrix_from_quat, quat_apply, quat_mul, subtract_frame_transforms  # noqa: E402
from calibration.isaac_ik import LinkOriginIKAction  # noqa: E402
from evaluation.sequence_metrics import require_sweep_tracking  # noqa: E402


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

    prims = iter(Usd.PrimRange(root))
    for prim in prims:
        if prim != root and prim.HasAPI(UsdPhysics.RigidBodyAPI):
            prims.PruneChildren()
            continue
        if not prim.IsA(UsdGeom.Mesh):
            continue
        imageable = UsdGeom.Imageable(prim)
        if imageable.ComputeVisibility() == UsdGeom.Tokens.invisible:
            continue
        if imageable.ComputePurpose() in (UsdGeom.Tokens.proxy, UsdGeom.Tokens.guide):
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
        stream.write("# Geometry in the declared rigid-link frame, in meters\n")
        for x, y, z in vertices:
            stream.write(f"v {x:.9g} {y:.9g} {z:.9g}\n")
        for a, b, c in triangles:
            stream.write(f"f {a} {b} {c}\n")
    return len(vertices), len(triangles)


def export_robot_geometry(output: Path, robot) -> dict:
    """Export robot-only geometry; never read object poses or segmentation."""
    stage = omni.usd.get_context().get_stage()
    root = stage.GetPrimAtPath(robot.root_physx_view.prim_paths[0])
    paths = {}
    for prim in Usd.PrimRange(root):
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            name = prim.GetName()
            if name in paths:
                raise RuntimeError(f"ambiguous robot link name: {name}")
            paths[name] = str(prim.GetPath())
    directory = output / "robot_meshes"
    directory.mkdir()
    (output / "robot_masks").mkdir()
    links = []
    for name in robot.body_names:
        if name not in paths:
            raise RuntimeError(f"robot rigid link not found in USD: {name}; available: {paths}")
        path = directory / f"{name}.obj"
        vertices, triangles = write_obj_from_stage(path, paths[name])
        links.append({"name": name, "path": str(path.relative_to(output)),
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "vertex_count": vertices, "triangle_count": triangles})
    return {"version": 1, "units": "meter", "pose_convention": "T_world_link_origin",
            "validation_mask_dir": "robot_masks",
            "pose_source": "simulated robot link state (ideal proprioception)", "links": links}


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
    if progress < 0.55:
        blend = smoothstep((progress - 0.40) / 0.15)
        return start + (end - start) * blend
    if progress < 0.70:
        blend = smoothstep((progress - 0.55) / 0.15)
        return end + (start - end) * blend
    if progress < 0.90:
        blend = smoothstep((progress - 0.70) / 0.20)
        return start + (home - start) * blend
    return home


def main() -> int:
    if args_cli.frames < 1 or args_cli.warmup_steps < 0 or args_cli.stride < 1:
        parser.error("--frames and --stride must be positive; --warmup-steps must be non-negative")
    if any(not np.isfinite(value) or value <= 0 for value in (args_cli.sweep_clearance_m, args_cli.sweep_span_m)):
        parser.error("--sweep-clearance-m and --sweep-span-m must be finite and positive")
    if not np.isfinite(args_cli.sweep_pitch_deg):
        parser.error("--sweep-pitch-deg must be finite")
    if not np.isfinite(args_cli.max_effector_error_m) or args_cli.max_effector_error_m <= 0:
        parser.error("--max-effector-error-m must be finite and positive")
    output = args_cli.output.resolve()
    prepare_output(output, args_cli.overwrite)

    env_cfg = parse_env_cfg(TASK, device=args_cli.device, num_envs=1)
    env_cfg.init_action_cfg("mimic_ik" if args_cli.motion == "effector-sweep" else "record")
    if args_cli.motion == "effector-sweep":
        # This Isaac Lab version adds the body-local offset directly to a
        # base-frame Jacobian. Command link6 itself instead, converting the
        # desired tool position below; no upstream patch is necessary.
        env_cfg.actions.arm_action.body_offset = None
        env_cfg.actions.arm_action.class_type = LinkOriginIKAction
        # Use speed-limited, well-damped drives for the controlled sweep.
        # These overrides apply only to this opt-in capture mode.
        for actuator_name in ("DY_80", "DY_70"):
            actuator = env_cfg.scene.robot.actuators[actuator_name]
            actuator.stiffness = 1000.0
            actuator.damping = 100.0
            actuator.velocity_limit_sim = 1.5
    # The task recorder otherwise retains every RGB observation on the GPU.
    # Our synchronized exporter owns recording for this workflow.
    env_cfg.recorders = RecorderManagerBaseCfg()
    env_cfg.seed = args_cli.seed
    env_cfg.scene.num_envs = 1
    env_cfg.scene.replicate_physics = False
    env_cfg.num_rerenders_on_reset = 2
    # Render at the final physics substep so RGB-D and exported poses share
    # the same simulation time (the task defaults to decimation=5, render=2).
    env_cfg.sim.render_interval = env_cfg.decimation
    capture_steps = args_cli.warmup_steps + args_cli.frames * args_cli.stride
    env_cfg.episode_length_s = max(
        env_cfg.episode_length_s, (capture_steps + 2) * env_cfg.decimation * env_cfg.sim.dt
    )

    camera_name = f"cam_{args_cli.camera}"
    unused_camera = "cam_wrist" if args_cli.camera == "top" else "cam_top"
    setattr(env_cfg.scene, unused_camera, None)
    setattr(env_cfg.observations.policy, unused_camera, None)
    if unused_camera == "cam_top":
        env_cfg.events.randomize_top_camera = None
    camera_cfg = getattr(env_cfg.scene, camera_name)
    # Camera reset randomization changes the rendered pose after the sensor's
    # reset cache is populated. The default returns that stale pose forever.
    # Also required for a wrist camera that moves with the robot.
    camera_cfg.update_latest_camera_pose = True
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
    if args_cli.export_robot_geometry:
        env_cfg.scene.robot.spawn.semantic_tags = [("class", "robot")]

    env: ManagerBasedRLEnv = gym.make(TASK, cfg=env_cfg).unwrapped
    env.reset()
    try:
        robot = env.scene["robot"]
        robot_geometry = export_robot_geometry(output, robot) if args_cli.export_robot_geometry else None
        if args_cli.diagnose_ik:
            if args_cli.motion != "effector-sweep":
                raise ValueError("--diagnose-ik requires --motion effector-sweep")
            term = env.action_manager.get_term("arm_action")
            original = robot.data.joint_pos.clone()

            def place_joints(positions):
                robot.write_joint_state_to_sim(positions, torch.zeros_like(positions))
                robot.set_joint_position_target(positions)
                env.scene.write_data_to_sim()
                env.sim.step(render=False)
                env.scene.update(env.physics_dt)

            diagnostics = []
            for joint_id in term._joint_ids:
                place_joints(original)
                before_position, before_quaternion = term._compute_frame_pose()
                before_position, before_quaternion = before_position.clone(), before_quaternion.clone()
                before_joints = robot.data.joint_pos[:, term._joint_ids].clone()
                jacobian = term._compute_frame_jacobian().clone()
                perturbed = original.clone()
                perturbed[:, joint_id] += 0.001
                place_joints(perturbed)
                position, quaternion = term._compute_frame_pose()
                dp, dr = compute_pose_error(before_position, before_quaternion, position, quaternion)
                observed = torch.cat((dp, dr), dim=-1)
                dq = robot.data.joint_pos[:, term._joint_ids] - before_joints
                predicted = (jacobian @ dq.unsqueeze(-1)).squeeze(-1)
                diagnostics.append({"joint": robot.data.joint_names[joint_id], "observed_delta": observed[0].tolist(),
                                    "predicted_delta": predicted[0].tolist(), "jacobian": jacobian[0].tolist()})
            report = {"body_names": robot.body_names, "joint_names": robot.joint_names,
                      "fixed_base": robot.is_fixed_base, "body_index": term._body_idx,
                      "jacobian_body_index": term._jacobi_body_idx, "perturbations": diagnostics}
            report["max_translation_discrepancy_m_per_rad"] = max(
                float(np.linalg.norm(np.asarray(row["observed_delta"][:3]) - row["predicted_delta"][:3])) / 0.001
                for row in diagnostics
            )
            report["passed"] = report["max_translation_discrepancy_m_per_rad"] < 0.001
            (output / "ik_diagnostics.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2), flush=True)
            if not report["passed"]:
                raise RuntimeError("IK Jacobian failed the finite-difference check; see ik_diagnostics.json")
            return 0
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

            half_pitch = np.deg2rad(args_cli.sweep_pitch_deg) / 2.0
            pitch = home_quaternion.new_tensor([[np.cos(half_pitch), 0.0, np.sin(half_pitch), 0.0]])
            sweep_quaternion = quat_mul(pitch, home_quaternion)
            if float(torch.sum(sweep_quaternion * home_quaternion)) < 0:
                sweep_quaternion = -sweep_quaternion

            def orientation_at(progress: float) -> torch.Tensor:
                if progress < 0.4:
                    blend = smoothstep((progress - 0.15) / 0.25)
                else:
                    blend = 1.0 - smoothstep((progress - 0.7) / 0.2)
                return torch.nn.functional.normalize(
                    (1.0 - blend) * home_quaternion + blend * sweep_quaternion, dim=-1
                )

            def action_at(progress: float) -> torch.Tensor:
                position = sweep_position(
                    progress,
                    home_position[0],
                    bottle_position[0],
                    args_cli.sweep_clearance_m,
                    args_cli.sweep_span_m,
                ).unsqueeze(0)
                quaternion = orientation_at(progress)
                tool_offset = position.new_tensor([[0.0, -0.248, 0.0]])
                link_position = position - quat_apply(quaternion, tool_offset)
                return torch.cat((link_position, quaternion, gripper), dim=1)

        action = action_at(0.0)
        if action.shape[1] != env.action_manager.total_action_dim:
            raise RuntimeError(
                f"OMY action dimension changed: assembled {action.shape[1]}, manager expects {env.action_manager.total_action_dim}"
            )

        def checked_step(command: torch.Tensor) -> None:
            _, _, terminated, truncated, _ = env.step(command)
            if bool(terminated.any()) or bool(truncated.any()):
                raise RuntimeError("capture interrupted by an environment reset; refusing discontinuous ground truth")

        for _ in range(args_cli.warmup_steps):
            checked_step(action)

        camera = env.scene[camera_name]
        intrinsic = camera.data.intrinsic_matrices[0].detach().cpu().numpy()
        frames: list[dict] = []
        motion_steps = max(1, args_cli.frames * args_cli.stride - 1)
        for frame_index in range(args_cli.frames):
            for stride_index in range(args_cli.stride):
                motion_step = frame_index * args_cli.stride + stride_index
                checked_step(action_at(motion_step / motion_steps))
            frame_id = f"{frame_index:06d}"
            rgb = camera.data.output["rgb"][0].detach().cpu().numpy()
            depth_m = camera.data.output["distance_to_image_plane"][0, ..., 0].detach().cpu().numpy()
            semantic = camera.data.output["semantic_segmentation"][0].detach().cpu().numpy()
            mask = np.all(semantic[..., :3] == np.asarray(TARGET_RGBA[:3], dtype=np.uint8), axis=-1).astype(np.uint8) * 255
            if frame_index == 0 and not np.any(mask):
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
            if robot_geometry is not None:
                # Simulator semantics are audit-only, never an inference input.
                robot_mask = np.all(semantic[..., :3] == [90, 110, 255], axis=-1).astype(np.uint8) * 255
                if not cv2.imwrite(str(output / "robot_masks" / f"{frame_id}.png"), robot_mask):
                    raise RuntimeError(f"failed to write robot audit mask {frame_id}")

            ee_data = env.scene["ee_frame"].data
            bottle_data = env.scene["bottle"].data
            frames.append(
                {
                    "frame_id": frame_id,
                    "timestamp_s": float(env.episode_length_buf[0].item() * env.step_dt),
                    "visible_mask_pixels": int(np.count_nonzero(mask)),
                    "motion_progress": motion_step / motion_steps,
                    "T_world_camera": pose_matrix(camera.data.pos_w[0], camera.data.quat_w_ros[0]),
                    "T_world_effector": pose_matrix(ee_data.target_pos_w[0, 0], ee_data.target_quat_w[0, 0]),
                    "T_world_object_gt": pose_matrix(bottle_data.root_pos_w[0], bottle_data.root_quat_w[0]),
                }
            )
            if robot_geometry is not None:
                frames[-1]["T_world_robot_links"] = {
                    name: pose_matrix(robot.data.body_link_pos_w[0, index], robot.data.body_link_quat_w[0, index])
                    for index, name in enumerate(robot.body_names)
                }
            if args_cli.motion == "effector-sweep":
                desired = sweep_position(
                    motion_step / motion_steps, home_position[0], bottle_position[0],
                    args_cli.sweep_clearance_m, args_cli.sweep_span_m,
                )
                actual, _ = subtract_frame_transforms(
                    robot.data.root_pos_w, robot.data.root_quat_w, ee_data.target_pos_w[:, 0],
                    ee_data.target_quat_w[:, 0],
                )
                frames[-1]["effector_command_error_m"] = float(torch.linalg.vector_norm(actual[0] - desired).item())
                frames[-1]["effector_command_position_base_m"] = desired.tolist()
                frames[-1]["joint_position_rad"] = robot.data.joint_pos[0].tolist()
            print(f"Captured {frame_id}: visible target pixels={np.count_nonzero(mask)}", flush=True)

        rigid_root_path = env.scene["bottle"].root_physx_view.prim_paths[0]
        vertex_count, triangle_count = write_obj_from_stage(output / "mesh/object.obj", rigid_root_path)
        np.savetxt(output / "cam_K.txt", intrinsic, fmt="%.12g")
        with (output / "frames.jsonl").open("w", encoding="utf-8") as stream:
            for frame in frames:
                stream.write(json.dumps(frame, separators=(",", ":")) + "\n")
        if args_cli.motion == "effector-sweep":
            try:
                require_sweep_tracking(frames, args_cli.max_effector_error_m)
            except ValueError as error:
                raise RuntimeError(
                    f"{error}; "
                    "diagnostic frames were retained but no valid manifest was published"
                ) from error
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
                "joint_names": robot.data.joint_names,
                "motion": args_cli.motion,
                "sweep_path": "home_start_end_start_home" if args_cli.motion == "effector-sweep" else None,
                "active_cameras": [camera_name],
                "update_latest_camera_pose": True,
                "physics_dt_s": env_cfg.sim.dt,
                "render_interval": env_cfg.sim.render_interval,
                "decimation": env_cfg.decimation,
                "stride": args_cli.stride,
                "ik_command_frame": "link6_origin" if args_cli.motion == "effector-sweep" else None,
                "ik_jacobian_point": "link_origin_corrected_from_physx_com" if args_cli.motion == "effector-sweep" else None,
                "sweep_arm_drive": {"stiffness": 1000.0, "damping": 100.0, "velocity_limit_sim": 1.5}
                if args_cli.motion == "effector-sweep" else None,
                "max_effector_error_m": args_cli.max_effector_error_m if args_cli.motion == "effector-sweep" else None,
                "sweep_clearance_m": args_cli.sweep_clearance_m if args_cli.motion == "effector-sweep" else None,
                "sweep_span_m": args_cli.sweep_span_m if args_cli.motion == "effector-sweep" else None,
                "sweep_pitch_deg": args_cli.sweep_pitch_deg if args_cli.motion == "effector-sweep" else None,
            },
        }
        if robot_geometry is not None:
            manifest["robot_geometry"] = robot_geometry
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"Captured {len(frames)} OMY frames into {output}", flush=True)
        return 0
    finally:
        env.close()


if __name__ == "__main__":
    try:
        exit_code = main()
    except BaseException:
        # Kit shutdown can terminate the process with code zero before Python
        # prints a pending exception. Preserve errors for unattended captures.
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
    sys.stdout.flush()
    simulation_app.close()
    raise SystemExit(exit_code)
