import math
import sys
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from occlusion.natural import occlusion_by_depth, occlusion_by_mask


def disk(shape=(60, 60), center=(30, 30), radius=15):
    yy, xx = np.mgrid[:shape[0], :shape[1]]
    return (yy - center[0]) ** 2 + (xx - center[1]) ** 2 <= radius ** 2


class OcclusionByMaskTests(unittest.TestCase):
    def test_fully_visible_object_is_not_occluded(self):
        sil = disk()
        self.assertEqual(occlusion_by_mask(sil, sil.copy()), 0.0)

    def test_half_the_silhouette_missing_from_the_mask_is_half_occluded(self):
        sil = disk()
        mask = sil.copy()
        mask[:, 30:] = False
        self.assertAlmostEqual(occlusion_by_mask(sil, mask), 1 - mask.sum() / sil.sum())
        self.assertAlmostEqual(occlusion_by_mask(sil, mask), 0.5, delta=0.03)

    def test_mask_pixels_outside_the_silhouette_do_not_reduce_the_occlusion(self):
        sil = disk(radius=10)
        mask = disk(radius=20)  # annotation spills past the silhouette
        self.assertEqual(occlusion_by_mask(sil, mask), 0.0)

    def test_nothing_visible_means_fully_occluded(self):
        sil = disk()
        self.assertEqual(occlusion_by_mask(sil, np.zeros_like(sil)), 1.0)

    def test_empty_silhouette_has_no_defined_occlusion(self):
        empty = np.zeros((10, 10), dtype=bool)
        self.assertTrue(math.isnan(occlusion_by_mask(empty, empty)))


class OcclusionByDepthTests(unittest.TestCase):
    def setUp(self):
        self.sil = disk()
        self.rendered = np.where(self.sil, 500, 0).astype(np.uint16)

    def test_matching_depth_is_not_occluded(self):
        self.assertEqual(occlusion_by_depth(self.sil, self.rendered, self.rendered.copy()), 0.0)

    def test_pixels_clearly_in_front_of_the_model_count_as_occluded(self):
        observed = self.rendered.copy()
        observed[:, 30:][self.sil[:, 30:]] = 300  # something 200 mm closer on the right half
        self.assertAlmostEqual(occlusion_by_depth(self.sil, self.rendered, observed), 0.5, delta=0.03)

    def test_small_depth_noise_is_tolerated(self):
        observed = self.rendered.copy()
        observed[self.sil] = 490  # 10 mm closer, inside the 20 mm margin
        self.assertEqual(occlusion_by_depth(self.sil, self.rendered, observed), 0.0)

    def test_pixels_without_a_depth_reading_are_left_out_of_the_fraction(self):
        observed = self.rendered.copy()
        observed[:, :30] = 0                   # no reading on the left half
        observed[:, 30:][self.sil[:, 30:]] = 300   # right half blocked
        self.assertEqual(occlusion_by_depth(self.sil, self.rendered, observed), 1.0)

    def test_no_depth_at_all_is_undefined(self):
        self.assertTrue(math.isnan(occlusion_by_depth(self.sil, self.rendered, np.zeros_like(self.rendered))))


if __name__ == "__main__":
    unittest.main()
