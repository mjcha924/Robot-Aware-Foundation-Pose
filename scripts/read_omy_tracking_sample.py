"""Load inference-available RGB-D and robot observations from a packaged sample.

The previous T_camera_object estimate is supplied by the estimator. This module
never opens frames.jsonl, contact records, phase labels or simulator object truth.
"""
import json
from pathlib import Path
import numpy as np
from PIL import Image


def read_tracking_input(root, index, previous_estimated_pose, *, oracle_mask=False):
    root = Path(root)
    manifest = json.loads((root / 'manifest.json').read_text())
    extension = manifest['omy_tracking']
    rows = [json.loads(line) for line in (root / extension['robot_observations_file']).read_text().splitlines()]
    if not 0 <= index < len(rows):
        raise IndexError(index)
    current = rows[index]
    previous = rows[index-1] if index else json.loads((root / extension['previous_robot_state_file']).read_text())
    pose = np.asarray(previous_estimated_pose, dtype=np.float64)
    if (pose.shape != (4, 4) or not np.isfinite(pose).all()
            or not np.allclose(pose[3], [0, 0, 0, 1])
            or not np.allclose(pose[:3, :3].T @ pose[:3, :3], np.eye(3), atol=1e-5)
            or not np.isclose(np.linalg.det(pose[:3, :3]), 1, atol=1e-5)):
        raise ValueError('Supply a rigid caller-estimated T_camera_object, not a simulator label')
    if not np.isclose(current['timestamp_s']-previous['timestamp_s'], 1/30, atol=1e-6):
        raise ValueError('Missing or discontinuous preceding robot state')
    stem = current['frame_id']+'.png'
    sample = {
        'rgb': np.asarray(Image.open(root/'rgb'/stem))[:, :, :3],
        'depth_m': np.asarray(Image.open(root/'depth'/stem), dtype=np.float32)*.001,
        'previous_estimated_T_camera_object': pose,
        'joint_names': tuple(extension['joint_names']),
        'joint_positions': np.asarray(current['joint_positions']),
        'previous_joint_positions': np.asarray(previous['joint_positions']),
        'joint_velocities': np.asarray(current['joint_velocities']),
        'timestamp_s': current['timestamp_s'], 'previous_timestamp_s': previous['timestamp_s'],
        'K': np.asarray(manifest['camera']['K']),
        'T_world_camera': np.asarray(current['T_world_camera']),
        'T_world_robot_base': np.asarray(current['T_world_robot_base']),
        'robot_geometry': {link['name']: root/link['path'] for link in manifest['robot_geometry']['links']},
        'robot_joint_inventory': root/extension['joint_inventory'],
        'object_model': root/manifest['mesh']['path'],
    }
    if oracle_mask:
        sample['oracle_visible_mask'] = np.asarray(Image.open(root/'masks'/stem))>0
    return sample
