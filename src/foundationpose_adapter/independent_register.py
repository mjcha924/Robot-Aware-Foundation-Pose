"""Per-frame independent FoundationPose registration (never tracking).

Runs inside the FoundationPose container (needs CUDA and the upstream modules). The setup
mirrors third_party/FoundationPose/run_demo.py so results are comparable to it; the only
difference is that every frame goes through `register`, so no frame sees another's pose.
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

FP_DIR = Path(__file__).resolve().parents[2] / "third_party" / "FoundationPose"


def build_estimator(mesh_file):
    """Return (estimator, mesh) set up exactly like run_demo.py."""
    if str(FP_DIR) not in sys.path:
        sys.path.insert(0, str(FP_DIR))
    from estimater import (FoundationPose, PoseRefinePredictor, ScorePredictor, dr,
                           set_logging_format, trimesh)

    set_logging_format()
    logging.getLogger().setLevel(logging.WARNING)  # upstream logs several MB per register call
    mesh = trimesh.load(mesh_file)
    estimator = FoundationPose(
        model_pts=mesh.vertices, model_normals=mesh.vertex_normals, mesh=mesh,
        scorer=ScorePredictor(), refiner=PoseRefinePredictor(),
        debug_dir=os.path.join(tempfile.gettempdir(), "fp_independent_debug"), debug=0,
        glctx=dr.RasterizeCudaContext(),
    )
    return estimator, mesh


def make_reader(scene_dir):
    """The same reader run_demo.py uses, so image preprocessing is identical."""
    if str(FP_DIR) not in sys.path:
        sys.path.insert(0, str(FP_DIR))
    import numpy as np
    from datareader import YcbineoatReader

    return YcbineoatReader(video_dir=str(scene_dir), shorter_side=None, zfar=np.inf)


def register_frame(estimator, reader, index, iteration=5):
    """Estimate the pose of frame `index` from scratch; returns a 4x4 numpy matrix."""
    return estimator.register(
        K=reader.K, rgb=reader.get_color(index), depth=reader.get_depth(index),
        ob_mask=reader.get_mask(index).astype(bool), iteration=iteration,
    )
