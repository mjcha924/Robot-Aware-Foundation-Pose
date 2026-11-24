"""Measured-state OMY adapter. Privileged labels are lazy supervision only."""
import json
import sys
from functools import lru_cache
from pathlib import Path
import numpy as np
import torch
from .geometry import point_features
from .sequence import tensor
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from omy_robot_surface import canonical_surface_points
from omy_kinematics import forward_kinematics


class OmySequence:
    def __init__(self, path):
        import trimesh
        self.path = Path(path)
        self.manifest = json.loads((self.path/'manifest.json').read_text())
        ext = self.manifest['omy_tracking']
        self.frames = [json.loads(s) for s in (self.path/ext['robot_observations_file']).read_text().splitlines()]
        self.previous_state = json.loads((self.path/ext['previous_robot_state_file']).read_text())
        self.inventory = json.loads((self.path/ext['joint_inventory']).read_text())
        self.joint_names = tuple(ext['joint_names'])
        # Per-instance bounded caches: no retained sequences or all-frame images.
        self._world_links = lru_cache(maxsize=3)(self._world_links)
        self._surface_pair = lru_cache(maxsize=1)(self._surface_pair)
        self.observation = lru_cache(maxsize=1)(self.observation)
        if len(self.frames) != self.manifest['frame_count']:
            raise ValueError('Observation count mismatch')
        self.mesh = trimesh.load(self.path/self.manifest['mesh']['path'], force='mesh', process=False)
        # Fixed seed independent of sequence iteration order, shared in training/evaluation.
        state = np.random.get_state(); np.random.seed(0)
        try:
            cad, faces = trimesh.sample.sample_surface(self.mesh, 256)
        finally:
            np.random.set_state(state)
        self.cad, self.cad_normals = tensor(cad), tensor(self.mesh.face_normals[faces])
        self.K = np.asarray(self.manifest['camera']['K'])
        self.symmetries = tensor(self.manifest['mesh'].get('symmetries_mesh', [np.eye(4).tolist()]))
        self.mesh_to_object = tensor(self.manifest['mesh']['T_object_mesh'])
        links = self.manifest['robot_geometry']['links']
        if not 0 < len(links) <= 512:
            raise ValueError('Invalid robot link count')
        geometry = {v['name']: self.path/v['path'] for v in links}
        self.canonical = canonical_surface_points(geometry, points_per_link=(512+len(links)-1)//len(links), seed=0)
        for index, name in enumerate(sorted(self.canonical)):
            count = 512//len(links) + (index < 512 % len(links))
            self.canonical[name] = {k: v[:count] for k, v in self.canonical[name].items()}
        self._targets = None

    def observation(self, i):
        from PIL import Image
        stem = self.frames[i]['frame_id']+'.png'
        with Image.open(self.path/'rgb'/stem) as rgb, Image.open(self.path/'depth'/stem) as depth:
            return (np.asarray(rgb)[:, :, :3].copy(), np.asarray(depth, dtype=np.float32)*.001)

    def _world_links(self, i):
        state = self.previous_state if i == -1 else self.frames[i]
        return forward_kinematics(self.inventory, self.joint_names,
                                 state['joint_positions'], state['T_world_robot_base'])

    def effector_pose(self, i, link):
        """World-frame pose from measured joints; no phase/contact/object labels."""
        links = self._world_links(i)
        if link not in links:
            raise ValueError(f'Unknown effector link {link!r}; available: {sorted(links)}')
        return tensor(links[link])

    def robot_link_poses(self, i):
        """Camera-frame measured FK for diagnostics; never simulator link truth."""
        camera_world = np.linalg.inv(self.frames[i]['T_world_camera'])
        return {name: camera_world @ pose for name, pose in self._world_links(i).items()}

    def _surface_pair(self, i):
        current = self.frames[i]
        previous = self.frames[i-1] if i else self.previous_state
        dt = current['timestamp_s'] - previous['timestamp_s']
        if not np.isclose(dt, 1/30, atol=1e-6):
            raise ValueError('Missing or discontinuous preceding robot state')
        camera_world = np.linalg.inv(current['T_world_camera'])
        now, old = self._world_links(i), self._world_links(i-1)
        positions, prior, normals = [], [], []
        for name, surface in sorted(self.canonical.items()):
            t, prev = camera_world @ now[name], camera_world @ old[name]
            points = surface['points_link_m']
            positions.append(points @ t[:3, :3].T + t[:3, 3])
            prior.append(points @ prev[:3, :3].T + prev[:3, 3])
            normals.append(surface['normals_link'] @ t[:3, :3].T)
        return tensor(np.concatenate(positions)), tensor(np.concatenate(normals)), tensor(np.concatenate(prior)), dt

    def points(self, i, hypothesis, diameter):
        positions, normals, previous, dt = self._surface_pair(i)
        return point_features(positions, normals, previous, dt,
            hypothesis.cpu(), self.cad, self.cad_normals, diameter)

    def target(self, i):
        if self._targets is None:
            self._targets = [json.loads(s) for s in (self.path/self.manifest['frames_file']).read_text().splitlines()]
            if len(self._targets) != len(self.frames) or any(a['frame_id'] != b['frame_id'] for a,b in zip(self._targets,self.frames)):
                raise ValueError('GT/observation alignment mismatch')
        f = self._targets[i]
        return torch.linalg.inv(tensor(self.frames[i]['T_world_camera'])) @ tensor(f['T_world_object_gt']) @ self.mesh_to_object


def open_sequence(path):
    manifest = json.loads((Path(path)/'manifest.json').read_text())
    if 'omy_tracking' in manifest:
        return OmySequence(path)
    from .sequence import IsaacSequence
    return IsaacSequence(path)
