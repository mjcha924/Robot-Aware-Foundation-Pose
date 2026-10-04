import sys
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from occlusion.occluder import SIDES, make_block, visible_fraction


def rect_mask(shape=(200, 240), top=60, bottom=140, left=80, right=180):
    mask = np.zeros(shape, dtype=bool)
    mask[top:bottom, left:right] = True
    return mask


class VisibleFractionTests(unittest.TestCase):
    def test_fully_visible_when_nothing_occludes(self):
        mask = rect_mask()
        self.assertEqual(visible_fraction(mask, np.zeros_like(mask)), 1.0)

    def test_counts_only_object_pixels(self):
        mask = rect_mask()
        occ = np.zeros_like(mask)
        occ[:, :130] = True  # covers the left 50 of 100 object columns plus lots of background
        self.assertAlmostEqual(visible_fraction(mask, occ), 0.5)

    def test_occluder_outside_object_changes_nothing(self):
        mask = rect_mask()
        occ = np.zeros_like(mask)
        occ[:10, :10] = True
        self.assertEqual(visible_fraction(mask, occ), 1.0)

    def test_empty_object_mask_is_rejected(self):
        empty = np.zeros((10, 10), dtype=bool)
        with self.assertRaises(ValueError):
            visible_fraction(empty, empty)


class MakeBlockTests(unittest.TestCase):
    TOL = 0.01

    def test_hits_target_on_every_side(self):
        mask = rect_mask()
        for side in SIDES:
            for target in (0.9, 0.7, 0.5, 0.3, 0.1):
                occ, achieved = make_block(mask, target, side, tol=self.TOL)
                self.assertEqual(occ.dtype, bool)
                self.assertEqual(occ.shape, mask.shape)
                self.assertLessEqual(abs(achieved - target), self.TOL, (side, target, achieved))

    def test_reported_fraction_is_the_measured_one(self):
        mask = rect_mask()
        occ, achieved = make_block(mask, 0.6, "left", tol=self.TOL)
        self.assertEqual(achieved, visible_fraction(mask, occ))

    def test_lower_target_gives_a_superset_block(self):
        mask = rect_mask()
        for side in SIDES:
            previous = np.zeros_like(mask)
            for target in (0.9, 0.7, 0.5, 0.3, 0.1):
                occ, _ = make_block(mask, target, side, tol=self.TOL)
                self.assertTrue(np.all(occ[previous]), (side, target))
                previous = occ

    def test_block_extends_past_the_object_in_the_perpendicular_direction(self):
        mask = rect_mask()
        occ, _ = make_block(mask, 0.5, "left", margin_px=8, tol=self.TOL)
        rows = np.where(occ.any(axis=1))[0]
        self.assertEqual(rows.min(), 60 - 8)
        self.assertEqual(rows.max(), 140 - 1 + 8)

    def test_fragmented_mask_is_counted_over_all_fragments(self):
        mask = np.zeros((200, 240), dtype=bool)
        mask[60:100, 60:100] = True
        mask[120:160, 140:200] = True
        for side in SIDES:
            occ, achieved = make_block(mask, 0.5, side, tol=0.02)
            self.assertLessEqual(abs(achieved - 0.5), 0.02, (side, achieved))

    def test_object_touching_the_image_border_is_clipped_not_an_error(self):
        mask = rect_mask(shape=(100, 100), top=0, bottom=60, left=0, right=50)
        for side in SIDES:
            occ, achieved = make_block(mask, 0.5, side, tol=self.TOL)
            self.assertEqual(occ.shape, mask.shape)
            self.assertLessEqual(abs(achieved - 0.5), self.TOL, (side, achieved))

    def test_target_one_means_no_occlusion(self):
        mask = rect_mask()
        occ, achieved = make_block(mask, 1.0, "top")
        self.assertFalse(occ.any())
        self.assertEqual(achieved, 1.0)

    def test_rejects_bad_arguments(self):
        mask = rect_mask()
        with self.assertRaises(ValueError):
            make_block(mask, 0.5, "diagonal")
        with self.assertRaises(ValueError):
            make_block(mask, 1.5, "left")
        with self.assertRaises(ValueError):
            make_block(mask, -0.1, "left")
        with self.assertRaises(ValueError):
            make_block(np.zeros_like(mask), 0.5, "left")


if __name__ == "__main__":
    unittest.main()
