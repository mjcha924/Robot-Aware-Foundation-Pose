"""Isaac geometry export reader. Inference inputs are separate from GT access."""
import json
import numpy as np
import torch
from .geometry import transform, point_features


def tensor(x):
    return torch.as_tensor(np.asarray(x), dtype=torch.float32)


class IsaacSequence:
    def __init__(self, path):
        import trimesh
        self.path = path
        self.manifest = json.loads((path / 'manifest.json').read_text())
        self.frames = [json.loads(s) for s in (path / self.manifest['frames_file']).read_text().splitlines()]
        self.mesh = trimesh.load(path / self.manifest['mesh']['path'], force='mesh', process=False)
        cad, faces = trimesh.sample.sample_surface(self.mesh, 256)
        self.cad, self.cad_normals = tensor(cad), tensor(self.mesh.face_normals[faces])
        self.K = np.asarray(self.manifest['camera']['K'])
        links = self.manifest['robot_geometry']['links']
        if not 0 < len(links) <= 512:
            raise ValueError('expected 1..512 robot links')
        self.samples = {}
        for i, link in enumerate(links):
            lm = trimesh.load(path / link['path'], force='mesh', process=False)
            count = 512 // len(links) + (i < 512 % len(links))
            pts, fs = trimesh.sample.sample_surface(lm, count)
            self.samples[link['name']] = tensor(pts), tensor(lm.face_normals[fs])
        self.symmetries = tensor(self.manifest['mesh'].get('symmetries_mesh', [np.eye(4).tolist()]))
        if self.symmetries.ndim != 3 or self.symmetries.shape[1:] != (4, 4):
            raise ValueError('symmetries_mesh must contain 4x4 transforms in raw mesh frame')

    def observation(self, i):
        import imageio.v2 as imageio
        fid = self.frames[i]['frame_id']
        rgb = imageio.imread(self.path / 'rgb' / (fid + '.png'))[..., :3]
        depth = imageio.imread(self.path / 'depth' / (fid + '.png')).astype(np.float32)
        return rgb, depth * self.manifest['units']['depth_scale_to_m']

    def points(self, i, hypothesis, diameter):
        f, previous = self.frames[i], self.frames[max(0, i - 1)]
        cam_inv = torch.linalg.inv(tensor(f['T_world_camera']))
        robot, normals, old = [], [], []
        for name, (pts, ns) in self.samples.items():
            current = cam_inv @ tensor(f['T_world_robot_links'][name])
            prior = cam_inv @ tensor(previous['T_world_robot_links'][name])
            robot.append(transform(pts, current)); normals.append(ns @ current[:3, :3].T)
            old.append(transform(pts, prior))
        return point_features(torch.cat(robot), torch.cat(normals), torch.cat(old) if i else None,
            f['timestamp_s'] - previous['timestamp_s'] if i else 1., hypothesis.cpu(),
            self.cad, self.cad_normals, diameter)

    def target(self, i):
        """Evaluation/training supervision only. Never called by points()."""
        f = self.frames[i]
        return torch.linalg.inv(tensor(f['T_world_camera'])) @ tensor(f['T_world_object_gt']) @ tensor(self.manifest['mesh']['T_object_mesh'])
