import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from candidate_pruning.policy import select_candidates, screening_resolution


class CandidatePolicyTests(unittest.TestCase):
    def test_screening_resolution_matches_cuda_alignment(self):
        self.assertEqual(screening_resolution(480, 848, 4), (120, 216))
        self.assertEqual(screening_resolution(1, 1, 4), (8, 8))
        with self.assertRaises(ValueError):
            screening_resolution(480, 848, 0)

    def test_ranked_keeps_best_in_original_order(self):
        self.assertEqual(select_candidates([3., 0., 2., 1.], 2), [1, 3])

    def test_ties_are_deterministic(self):
        self.assertEqual(select_candidates([1., 1., 1.], 2), [0, 1])

    def test_random_is_seeded_without_replacement(self):
        a = select_candidates([0.] * 252, 64, "random", 17)
        self.assertEqual(a, select_candidates([0.] * 252, 64, "random", 17))
        self.assertEqual(len(set(a)), 64)
        self.assertNotEqual(a, select_candidates([0.] * 252, 64, "random", 18))

    def test_fallback_preserves_all_candidates(self):
        self.assertEqual(select_candidates([1., 2., 3.], 1, informative=False), [0, 1, 2])
        self.assertEqual(select_candidates([1., 2., 3.], 1, mode="none"), [0, 1, 2])
        self.assertEqual(select_candidates([1., 2., 3.], 99), [0, 1, 2])

    def test_invalid_inputs(self):
        for values, keep in (([], 1), ([float("nan")], 1), ([float("inf")], 1), ([1.], 0), ([1.], True)):
            with self.assertRaises(ValueError):
                select_candidates(values, keep)
        with self.assertRaises(ValueError):
            select_candidates([1.], 1, "invalid")


if __name__ == "__main__":
    unittest.main()
