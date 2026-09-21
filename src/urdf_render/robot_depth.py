"""Depth-only rasterization of exported robot links using ideal proprioception.

No RGB, object masks, object poses, or simulator semantic masks enter this
renderer. Import inside the FoundationPose GPU environment after validating
the sequence with validate_isaac_export.py.
"""

import numpy as np
import torch
import trimesh
import nvdiffrast.torch as dr


class RobotDepthRenderer:
    def __init__(self, sequence, geometry, context=None):
        self.context = context if context is not None else dr.RasterizeCudaContext()
        self.vertices = {}
        faces = []
        offset = 0
        for link in geometry["links"]:
            mesh = trimesh.load(sequence / link["path"], force="mesh", process=False)
            # USD visual assets repeat triangle vertices; merge for runtime only.
            mesh.merge_vertices()
            vertices = np.asarray(mesh.vertices, dtype=np.float32)
            self.vertices[link["name"]] = torch.as_tensor(vertices, device="cuda")
            faces.append(np.asarray(mesh.faces, dtype=np.int32) + offset)
            offset += len(vertices)
        self.faces = torch.as_tensor(np.concatenate(faces), dtype=torch.int32, device="cuda")

    @torch.no_grad()
    def render(self, world_camera, world_links, intrinsic, height, width):
        if set(world_links) != set(self.vertices):
            raise ValueError("robot pose names do not match geometry")
        camera_world = np.linalg.inv(np.asarray(world_camera, dtype=np.float64))
        parts = []
        for name, vertices in self.vertices.items():
            transform = torch.as_tensor(camera_world @ np.asarray(world_links[name]),
                                        dtype=torch.float32, device="cuda")
            parts.append(vertices @ transform[:3, :3].T + transform[:3, 3])
        points = torch.cat(parts)
        k = np.asarray(intrinsic)
        near, far = 0.001, 100.0
        z = points[:, 2]
        # OpenCV (+Y down, +Z forward) to OpenGL clip coordinates.
        clip = torch.stack((
            2 * (k[0, 0] * points[:, 0] + k[0, 1] * points[:, 1]) / width
            + (2 * k[0, 2] / width - 1) * z,
            -2 * k[1, 1] * points[:, 1] / height + (1 - 2 * k[1, 2] / height) * z,
            (far + near) / (far - near) * z - 2 * far * near / (far - near),
            z,
        ), dim=-1)[None].contiguous()
        raster, _ = dr.rasterize(self.context, clip, self.faces, resolution=[height, width])
        depth, _ = dr.interpolate(z[None, :, None].contiguous(), raster, self.faces)
        return torch.flip(depth[0, ..., 0], dims=[0])
