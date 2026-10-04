import sys
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from occlusion.apply import apply_occlusion


def scene():
    rng = np.random.default_rng(0)
    rgb = rng.integers(1, 255, size=(20, 30, 3), dtype=np.uint8)
    depth = np.full((20, 30), 600, dtype=np.uint16)
    obj = np.zeros((20, 30), dtype=bool)
    obj[5:15, 8:22] = True
    depth[obj] = 500
    occ = np.zeros((20, 30), dtype=bool)
    occ[:, 10:16] = True
    return rgb, depth, obj, occ


class ApplyOcclusionTests(unittest.TestCase):
    def test_rgb_inside_the_block_is_the_colour_and_outside_is_untouched(self):
        rgb, depth, obj, occ = scene()
        out_rgb, _ = apply_occlusion(rgb, depth, occ)
        self.assertTrue(np.all(out_rgb[occ] == 0))
        self.assertTrue(np.array_equal(out_rgb[~occ], rgb[~occ]))

    def test_custom_colour(self):
        rgb, depth, obj, occ = scene()
        out_rgb, _ = apply_occlusion(rgb, depth, occ, color=(10, 20, 30))
        self.assertTrue(np.all(out_rgb[occ] == np.array([10, 20, 30], dtype=np.uint8)))

    def test_inputs_are_not_modified(self):
        rgb, depth, obj, occ = scene()
        rgb0, depth0 = rgb.copy(), depth.copy()
        apply_occlusion(rgb, depth, occ)
        apply_occlusion(rgb, depth, occ, depth_mode="front", obj_mask=obj)
        self.assertTrue(np.array_equal(rgb, rgb0))
        self.assertTrue(np.array_equal(depth, depth0))

    def test_zero_mode_clears_depth_inside_the_block_only(self):
        rgb, depth, obj, occ = scene()
        _, out_depth = apply_occlusion(rgb, depth, occ, depth_mode="zero")
        self.assertTrue(np.all(out_depth[occ] == 0))
        self.assertTrue(np.array_equal(out_depth[~occ], depth[~occ]))
        self.assertEqual(out_depth.dtype, np.uint16)

    def test_front_mode_puts_the_block_in_front_of_the_object(self):
        rgb, depth, obj, occ = scene()
        _, out_depth = apply_occlusion(
            rgb, depth, occ, depth_mode="front", front_offset_mm=100, obj_mask=obj
        )
        self.assertTrue(np.all(out_depth[occ] == 400))  # object median 500 mm minus 100 mm
        self.assertTrue(np.array_equal(out_depth[~occ], depth[~occ]))
        self.assertEqual(out_depth.dtype, np.uint16)

    def test_front_mode_reference_ignores_invalid_depth(self):
        rgb, depth, obj, occ = scene()
        depth[obj] = 0
        depth[6:10, 8:22] = 500
        _, out_depth = apply_occlusion(rgb, depth, occ, depth_mode="front", obj_mask=obj)
        self.assertTrue(np.all(out_depth[occ] == 400))

    def test_front_mode_never_goes_to_zero_or_below(self):
        rgb, depth, obj, occ = scene()
        _, out_depth = apply_occlusion(
            rgb, depth, occ, depth_mode="front", front_offset_mm=5000, obj_mask=obj
        )
        self.assertTrue(np.all(out_depth[occ] == 1))

    def test_front_mode_needs_object_depth(self):
        rgb, depth, obj, occ = scene()
        with self.assertRaises(ValueError):
            apply_occlusion(rgb, depth, occ, depth_mode="front")
        depth[obj] = 0
        with self.assertRaises(ValueError):
            apply_occlusion(rgb, depth, occ, depth_mode="front", obj_mask=obj)

    def test_rejects_bad_arguments(self):
        rgb, depth, obj, occ = scene()
        with self.assertRaises(ValueError):
            apply_occlusion(rgb, depth, occ, depth_mode="blur")
        with self.assertRaises(ValueError):
            apply_occlusion(rgb, depth[:, :-1], occ)
        with self.assertRaises(ValueError):
            apply_occlusion(rgb, depth, occ[:-1])


if __name__ == "__main__":
    unittest.main()
