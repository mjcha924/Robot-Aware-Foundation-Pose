import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from evaluation.robot_geometry import robot_projection_passes


class RobotProjectionTests(unittest.TestCase):
    def setUp(self):
        self.row = {"robot_pixels": 100, "visible_projection_iou": 0.95,
                    "robot_pixel_coverage": 0.98, "depth_p95_abs_error_m": 0.01}

    def test_accepts_boundary(self):
        self.assertTrue(robot_projection_passes([self.row]))

    def test_rejects_any_bad_frame(self):
        for key, value in (("robot_pixels", 0), ("visible_projection_iou", 0.949),
                           ("robot_pixel_coverage", 0.979), ("depth_p95_abs_error_m", 0.011)):
            self.assertFalse(robot_projection_passes([self.row, dict(self.row, **{key: value})]))

    def test_rejects_empty_missing_and_nonfinite(self):
        self.assertFalse(robot_projection_passes([]))
        self.assertFalse(robot_projection_passes([{}]))
        for value in (None, float("nan"), float("inf"), -1, True):
            self.assertFalse(robot_projection_passes([dict(self.row, depth_p95_abs_error_m=value)]))


if __name__ == "__main__":
    unittest.main()
