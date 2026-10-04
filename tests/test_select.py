import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from occlusion.select import select_frames


def areas(values):
    return [(f"f{i:03d}", value) for i, value in enumerate(values)]


class SelectFramesTests(unittest.TestCase):
    def test_uniform_spans_the_sequence_in_order(self):
        frames = areas(range(100, 200))
        chosen = select_frames(frames, 5, strategy="uniform")
        positions = [int(name[1:]) for name in chosen]
        self.assertEqual(len(chosen), 5)
        self.assertEqual((positions[0], positions[-1]), (0, 99))
        self.assertEqual(positions, sorted(set(positions)))
        gaps = [b - a for a, b in zip(positions, positions[1:])]
        self.assertLessEqual(max(gaps) - min(gaps), 1)

    def test_largest_takes_the_biggest_masks_in_temporal_order(self):
        frames = areas([5, 90, 10, 80, 70, 1])
        self.assertEqual(select_frames(frames, 3, strategy="largest"), ["f001", "f003", "f004"])

    def test_min_area_filters_before_selecting(self):
        frames = areas([5, 90, 10, 80, 70, 1])
        self.assertEqual(
            select_frames(frames, 2, strategy="uniform", min_area=50), ["f001", "f004"]
        )

    def test_asking_for_more_frames_than_available_is_an_error(self):
        with self.assertRaises(ValueError):
            select_frames(areas([1, 2, 3]), 4, strategy="uniform")
        with self.assertRaises(ValueError):
            select_frames(areas([1, 2, 3]), 2, strategy="uniform", min_area=3)

    def test_unknown_strategy_is_an_error(self):
        with self.assertRaises(ValueError):
            select_frames(areas([1, 2, 3]), 2, strategy="random")


if __name__ == "__main__":
    unittest.main()
