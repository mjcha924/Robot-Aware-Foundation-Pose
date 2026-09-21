import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from evaluation.sequence_metrics import analyze_sequence, require_sweep_tracking


class SequenceMetricTests(unittest.TestCase):
    def setUp(self):
        identity = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
        self.frames = [
            {"frame_id": str(i), "timestamp_s": i * 0.1, "T_world_effector": copy.deepcopy(identity),
             "visible_mask_pixels": pixels, "motion_progress": i / 2}
            for i, pixels in enumerate((100, 20, 110))
        ]
        self.records = [
            {"frame_id": str(i), "timestamp_s": i * 0.1, "T_camera_object": copy.deepcopy(identity),
             "T_camera_object_gt": identity, "operation": "register" if i == 0 else "track", "inference_s": 0.1}
            for i in range(3)
        ]

    def test_motion_and_visibility_groups(self):
        self.frames[1]["T_world_effector"][0][3] = 0.2
        self.records[1]["T_camera_object"][0][3] = 0.03
        result = analyze_sequence(self.frames, self.records)
        self.assertAlmostEqual(result["motion"]["effector"]["step_translation_m"]["max"], 0.2)
        self.assertEqual(result["visibility"]["min_frame_id"], "1")
        self.assertEqual(result["visibility"]["frames_below_half_reference_area"], 1)
        self.assertAlmostEqual(result["pose_by_visible_area"]["below_half_reference"]["translation_error_m"]["mean"], 0.03)
        self.assertEqual(result["inference_s"]["track"]["count"], 2)

    def test_rejects_mismatched_results(self):
        with self.assertRaisesRegex(ValueError, "IDs/order"):
            analyze_sequence(self.frames, self.records[::-1])
        self.records[1]["timestamp_s"] = 99
        with self.assertRaisesRegex(ValueError, "timestamps"):
            analyze_sequence(self.frames, self.records)

    def test_rejects_invalid_visibility_reference(self):
        self.frames[0]["visible_mask_pixels"] = 0
        with self.assertRaisesRegex(ValueError, "nonzero"):
            analyze_sequence(self.frames)

    def test_legacy_sequence_without_visibility(self):
        for frame in self.frames:
            del frame["visible_mask_pixels"]
        self.assertNotIn("visibility", analyze_sequence(self.frames))

    def test_sweep_acceptance_boundary(self):
        frames = [{"effector_command_error_m": error} for error in (0.0, 0.03)]
        self.assertEqual(require_sweep_tracking(frames, 0.03), 0.03)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            require_sweep_tracking(frames, 0.029)

    def test_sweep_rejects_missing_or_invalid_error(self):
        for frames in ([], [{}], [{"effector_command_error_m": float("nan")}],
                       [{"effector_command_error_m": -0.1}]):
            with self.assertRaises(ValueError):
                require_sweep_tracking(frames, 0.03)


if __name__ == "__main__":
    unittest.main()
