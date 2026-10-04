import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pose_eval.gt import gt_pose_paths


def make_scene(root, frame_ids, pose_names):
    (root / "rgb").mkdir()
    (root / "annotated_poses").mkdir()
    for frame_id in frame_ids:
        (root / "rgb" / f"{frame_id}.png").write_bytes(b"")
    for name in pose_names:
        (root / "annotated_poses" / f"{name}.txt").write_text("1 0 0 0\n0 1 0 0\n0 0 1 0\n0 0 0 1\n")


class GtPosePathsTests(unittest.TestCase):
    def test_poses_named_after_the_frame_ids_are_matched_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_scene(root, ["b200", "a100", "c300"], ["c300", "a100", "b200"])
            paths = gt_pose_paths(root)
            self.assertEqual({k: v.name for k, v in paths.items()},
                             {"a100": "a100.txt", "b200": "b200.txt", "c300": "c300.txt"})

    def test_poses_named_by_index_are_matched_in_sorted_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_scene(root, ["1581120424213", "1581120424100", "1581120424148"], ["0000002", "0000000", "0000001"])
            paths = gt_pose_paths(root)
            self.assertEqual(paths["1581120424100"].name, "0000000.txt")
            self.assertEqual(paths["1581120424148"].name, "0000001.txt")
            self.assertEqual(paths["1581120424213"].name, "0000002.txt")

    def test_mismatched_counts_with_unmatched_names_are_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_scene(root, ["a", "b", "c"], ["0", "1"])
            with self.assertRaises(ValueError):
                gt_pose_paths(root)


if __name__ == "__main__":
    unittest.main()
