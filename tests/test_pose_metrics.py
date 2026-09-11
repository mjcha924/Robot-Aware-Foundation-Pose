import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evaluation.pose_metrics import evaluate_records, rotation_error_deg, summarize, translation_error_m


IDENTITY = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
]


class PoseMetricTests(unittest.TestCase):
    def test_translation_error(self):
        estimate = [row[:] for row in IDENTITY]
        estimate[0][3], estimate[1][3] = 0.003, 0.004
        self.assertAlmostEqual(translation_error_m(estimate, IDENTITY), 0.005)

    def test_rotation_error(self):
        estimate = [row[:] for row in IDENTITY]
        estimate[0][:3] = [0.0, -1.0, 0.0]
        estimate[1][:3] = [1.0, 0.0, 0.0]
        self.assertAlmostEqual(rotation_error_deg(estimate, IDENTITY), 90.0)

    def test_rotation_clamps_roundoff(self):
        estimate = [row[:] for row in IDENTITY]
        estimate[0][0] += 1e-12
        self.assertEqual(rotation_error_deg(estimate, IDENTITY), 0.0)

    def test_summary(self):
        self.assertEqual(summarize([1.0, 2.0, 3.0])["median"], 2.0)
        self.assertAlmostEqual(summarize([3.0, 4.0])["rmse"], math.sqrt(12.5))

    def test_evaluate_records(self):
        estimate = [row[:] for row in IDENTITY]
        estimate[2][3] = 0.01
        records = [{"frame_id": "000007", "T_camera_object": estimate, "T_camera_object_gt": IDENTITY}]
        per_frame, summary = evaluate_records(records, "camera")
        self.assertEqual(per_frame[0]["frame_id"], "000007")
        self.assertAlmostEqual(summary["translation_error_m"]["mean"], 0.01)

    def test_rejects_missing_ground_truth(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            evaluate_records([{"frame_id": "000000", "T_camera_object": IDENTITY}], "camera")


if __name__ == "__main__":
    unittest.main()
