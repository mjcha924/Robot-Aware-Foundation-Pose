import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pose_eval.side_cross import fail_count_histogram, variance_shares


class VarianceSharesTests(unittest.TestCase):
    def test_pure_frame_effect(self):
        matrix = np.array([[1.0] * 4, [2.0] * 4, [5.0] * 4])
        shares = variance_shares(matrix)
        self.assertAlmostEqual(shares["frame"], 1.0)
        self.assertAlmostEqual(shares["side"], 0.0)
        self.assertAlmostEqual(shares["residual"], 0.0)

    def test_pure_side_effect(self):
        matrix = np.tile(np.array([1.0, 2.0, 3.0, 9.0]), (5, 1))
        shares = variance_shares(matrix)
        self.assertAlmostEqual(shares["side"], 1.0)
        self.assertAlmostEqual(shares["frame"], 0.0)

    def test_shares_sum_to_one_with_interaction(self):
        rng = np.random.default_rng(0)
        shares = variance_shares(rng.normal(size=(20, 4)))
        self.assertAlmostEqual(sum(shares.values()), 1.0)
        self.assertGreater(shares["residual"], 0.0)

    def test_constant_matrix_has_no_variance(self):
        shares = variance_shares(np.ones((3, 4)))
        self.assertEqual(shares, {"frame": 0.0, "side": 0.0, "residual": 0.0})


class FailCountTests(unittest.TestCase):
    def test_histogram_counts_frames_by_number_of_failing_sides(self):
        fails = np.array([[0, 0, 0, 0], [1, 0, 0, 0], [1, 1, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0]], dtype=bool)
        self.assertEqual(fail_count_histogram(fails), {0: 2, 1: 1, 2: 1, 3: 0, 4: 1})


if __name__ == "__main__":
    unittest.main()
