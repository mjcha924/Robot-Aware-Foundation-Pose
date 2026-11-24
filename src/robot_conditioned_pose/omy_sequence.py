"""Measured-state OMY adapter. Privileged labels are lazy supervision only."""
import json
import sys
from pathlib import Path
import numpy as np
import torch
from .geometry import point_features
from .sequence import tensor
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from read_omy_tracking_sample import read_tracking_input
from omy_robot_surface import canonical_surface_points, robot_surface_pair


class OmySequence:
    def __init__(self, path):
        import trimesh
        self.path = Path(path)
        self.manifest = json.loads((self.path/'manifest.json').read_text())
        ext = self.manifest['omy_tracking']
        self.frames = [json.loads(s) for s in (self.path/ext['robot_observations_file']).read_text().splitlines()]
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
        return (np.asarray(Image.open(self.path/'rgb'/stem))[:, :, :3],
                np.asarray(Image.open(self.path/'depth'/stem), dtype=np.float32)*.001)

    def points(self, i, hypothesis, diameter):
        # Public reader expects object-root pose, model uses raw mesh pose.
        object_pose = hypothesis.cpu() @ torch.linalg.inv(self.mesh_to_object)
        sample = read_tracking_input(self.path, i, object_pose.numpy())
        features = robot_surface_pair(sample, self.canonical)
        return point_features(tensor(features['positions_camera_m']), tensor(features['normals_camera']),
            tensor(features['previous_positions_camera_m']), sample['timestamp_s']-sample['previous_timestamp_s'],
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
