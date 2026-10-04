import sys
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from occlusion.occluder import SIDES, visible_fraction
from occlusion.scene import build_level, choose_side


def scene():
    rng = np.random.default_rng(1)
    rgb = rng.integers(1, 255, size=(120, 160, 3), dtype=np.uint8)
    depth = np.full((120, 160), 700, dtype=np.uint16)
    obj = np.zeros((120, 160), dtype=bool)
    obj[30:90, 50:120] = True
    depth[obj] = 500
    return rgb, depth, obj


class BuildLevelTests(unittest.TestCase):
    def test_visible_mask_is_the_object_minus_the_block(self):
        rgb, depth, obj = scene()
        result = build_level(rgb, depth, obj, 0.6, "left", tol=0.02)
        self.assertTrue(np.array_equal(result["visible_mask"], obj & ~result["occ"]))

    def test_reports_the_measured_visible_fraction(self):
        rgb, depth, obj = scene()
        result = build_level(rgb, depth, obj, 0.6, "top", tol=0.02)
        self.assertEqual(result["achieved"], visible_fraction(obj, result["occ"]))
        self.assertAlmostEqual(result["achieved"], 0.6, delta=0.02)
        self.assertEqual(result["side"], "top")
        self.assertEqual(result["target"], 0.6)

    def test_rgb_and_depth_are_painted_inside_the_block(self):
        rgb, depth, obj = scene()
        result = build_level(rgb, depth, obj, 0.5, "right", depth_mode="front", tol=0.02)
        occ = result["occ"]
        self.assertTrue(np.all(result["rgb"][occ] == 0))
        self.assertTrue(np.all(result["depth"][occ] == 400))
        self.assertTrue(np.array_equal(result["rgb"][~occ], rgb[~occ]))

    def test_full_visibility_level_changes_nothing(self):
        rgb, depth, obj = scene()
        result = build_level(rgb, depth, obj, 1.0, "left")
        self.assertTrue(np.array_equal(result["rgb"], rgb))
        self.assertTrue(np.array_equal(result["depth"], depth))
        self.assertTrue(np.array_equal(result["visible_mask"], obj))
        self.assertEqual(result["achieved"], 1.0)
        self.assertFalse(result["occ"].any())


class ChooseSideTests(unittest.TestCase):
    def test_is_deterministic_for_a_frame_and_seed(self):
        self.assertEqual(choose_side("1579908945563078571", 0), choose_side("1579908945563078571", 0))

    def test_returns_a_valid_side_and_uses_all_of_them(self):
        seen = {choose_side(f"frame{i}", 0) for i in range(200)}
        self.assertEqual(seen, set(SIDES))

    def test_seed_changes_the_choice(self):
        base = [choose_side(f"frame{i}", 0) for i in range(50)]
        other = [choose_side(f"frame{i}", 1) for i in range(50)]
        self.assertNotEqual(base, other)


if __name__ == "__main__":
    unittest.main()
