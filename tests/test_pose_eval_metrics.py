import sys
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pose_eval.metrics import add, add_s, model_diameter


def pose(rotation=None, translation=(0.0, 0.0, 0.0)):
    matrix = np.eye(4)
    if rotation is not None:
        matrix[:3, :3] = rotation
    matrix[:3, 3] = translation
    return matrix


def rot_z(degrees):
    a = np.radians(degrees)
    return np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])


def box_grid(extent=(0.2, 0.1, 0.05), step=0.01):
    """Dense box-surface-like cloud centred at the origin; symmetric under 180 degree turns."""
    axes = [np.arange(-e / 2, e / 2 + 1e-9, step) for e in extent]
    grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
    return grid


class ModelDiameterTests(unittest.TestCase):
    def test_unit_cube_diameter_is_the_space_diagonal(self):
        corners = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], dtype=float)
        self.assertAlmostEqual(model_diameter(corners), np.sqrt(3))

    def test_two_points(self):
        self.assertAlmostEqual(model_diameter(np.array([[0, 0, 0], [0.3, 0.4, 0]])), 0.5)


class AddTests(unittest.TestCase):
    def test_identical_poses_have_zero_error(self):
        points = box_grid()
        self.assertEqual(add(pose(rot_z(30), (0.1, 0.2, 0.5)), pose(rot_z(30), (0.1, 0.2, 0.5)), points), 0.0)

    def test_pure_translation_error_is_the_translation_distance(self):
        points = box_grid()
        value = add(pose(translation=(0.0, 0.0, 0.51)), pose(translation=(0.0, 0.0, 0.5)), points)
        self.assertAlmostEqual(value, 0.01)

    def test_rotation_about_the_centre_moves_points_by_their_radius(self):
        points = np.array([[0.1, 0.0, 0.0], [-0.1, 0.0, 0.0]])
        value = add(pose(rot_z(180)), pose(), points)
        self.assertAlmostEqual(value, 0.2)  # each point lands 0.2 m from where it should be


class AddSTests(unittest.TestCase):
    def test_identical_poses_have_zero_error(self):
        points = box_grid()
        self.assertAlmostEqual(add_s(pose(rot_z(30), (0.1, 0.2, 0.5)), pose(rot_z(30), (0.1, 0.2, 0.5)), points), 0.0)

    def test_never_larger_than_add(self):
        points = box_grid()
        rng = np.random.default_rng(0)
        for _ in range(5):
            est = pose(rot_z(rng.uniform(0, 360)), rng.uniform(-0.05, 0.05, 3) + [0, 0, 0.5])
            gt = pose(rot_z(rng.uniform(0, 360)), [0, 0, 0.5])
            self.assertLessEqual(add_s(est, gt, points), add(est, gt, points) + 1e-12)

    def test_half_turn_of_a_symmetric_box_is_nearly_free_under_add_s_but_not_add(self):
        points = box_grid()
        flipped = pose(rot_z(180), (0.0, 0.0, 0.5))
        truth = pose(translation=(0.0, 0.0, 0.5))
        self.assertLess(add_s(flipped, truth, points), 1e-9)
        self.assertGreater(add(flipped, truth, points), 0.04)

    def test_a_real_translation_error_is_still_visible(self):
        points = box_grid()
        shifted = pose(translation=(0.05, 0.0, 0.5))
        truth = pose(translation=(0.0, 0.0, 0.5))
        self.assertGreater(add_s(shifted, truth, points), 0.005)


if __name__ == "__main__":
    unittest.main()
