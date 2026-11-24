"""Portable model identity and deterministic geometry shared by all stages."""
import hashlib
import numpy as np

GEOMETRY_VERSION = 'exact-vertex-diameter-v1'


def semantic_config(cfg):
    # Only the weight location is machine-local. All other settings remain strict.
    return {k: v for k, v in cfg.items() if k != 'ckpt_dir'}


def portable_provenance(manifest):
    return dict(manifest, cfg=semantic_config(manifest['cfg']))


def check_checkpoint(saved, cfg):
    from pathlib import Path
    if semantic_config(saved['cfg']) != semantic_config(cfg):
        raise ValueError('pretrained config differs from training')
    if saved['provenance']['weight_sha256'] != hashlib.sha256(Path(cfg['ckpt_dir']).read_bytes()).hexdigest():
        raise ValueError('pretrained weight content differs from training')
    if saved['provenance'].get('geometry_version') != GEOMETRY_VERSION:
        raise ValueError('old geometry convention: rebuild caches and retrain')


def mesh_diameter(mesh):
    """Exact farthest vertex distance in metres, with bounded pairwise memory.

    Convex hull reduction accelerates ordinary 3D CADs; degenerate meshes fall
    back to the same exact computation. No RNG or sampled diameter is involved.
    """
    from scipy.spatial import ConvexHull, QhullError
    from scipy.spatial.distance import cdist
    vertices = np.unique(np.asarray(mesh.vertices, dtype=np.float64), axis=0)
    if vertices.ndim != 2 or vertices.shape[1] != 3 or not np.isfinite(vertices).all() or len(vertices) < 2:
        raise ValueError('mesh must have finite, distinct 3D vertices')
    try:
        vertices = vertices[ConvexHull(vertices).vertices]
    except QhullError:
        pass
    squared = 0.
    for i in range(0, len(vertices), 512):
        for j in range(i, len(vertices), 512):
            squared = max(squared, float(cdist(vertices[i:i+512], vertices[j:j+512], 'sqeuclidean').max()))
    if squared <= 0:
        raise ValueError('mesh diameter must be positive')
    return squared ** .5


def geometry_record(mesh, diameter):
    digest = hashlib.sha256()
    for data, dtype in ((mesh.vertices, '<f8'), (mesh.faces, '<i8')):
        array = np.asarray(data, dtype=dtype)
        digest.update(str(array.shape).encode()); digest.update(array.tobytes())
    return dict(geometry_version=GEOMETRY_VERSION, mesh_sha256=digest.hexdigest(), diameter_m=diameter)


def evaluation_surface(mesh, count=4096, seed=2026):
    """Independent, deterministic area-weighted samples; does not touch global RNG."""
    if count < 1:
        raise ValueError('evaluation point count must be positive')
    triangles = np.asarray(mesh.triangles)
    areas = np.asarray(mesh.area_faces)
    if not np.isfinite(areas).all() or areas.sum() <= 0:
        raise ValueError('mesh has no finite surface area')
    rng = np.random.default_rng(seed)
    indices = rng.choice(len(triangles), count, p=areas/areas.sum())
    u, v = np.sqrt(rng.random(count)), rng.random(count)
    weights = np.stack((1-u, u*(1-v), u*v), axis=1)
    return (triangles[indices] * weights[..., None]).sum(axis=1)
