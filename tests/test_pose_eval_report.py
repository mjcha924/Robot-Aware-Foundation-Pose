import math
import sys
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pose_eval.report import evaluate_records, level_table, wilson_interval


def pose_list(tx=0.0, ty=0.0, tz=0.5, rot_z_deg=0.0):
    a = math.radians(rot_z_deg)
    return [[math.cos(a), -math.sin(a), 0, tx], [math.sin(a), math.cos(a), 0, ty], [0, 0, 1, tz], [0, 0, 0, 1]]


def record(frame, level, pose, side="left"):
    return {"frame_id": frame, "level": level, "side": side, "achieved_occluded": level / 100,
            "visible_px": 1000, "depth_mode": "zero", "pose": pose, "error": None, "seconds": 2.0}


ORIGIN = np.zeros((1, 3))  # one model point at the object origin: ADD/ADD-S = position error


class WilsonIntervalTests(unittest.TestCase):
    def test_known_values(self):
        low, high = wilson_interval(5, 10)
        self.assertAlmostEqual(low, 0.2366, places=3)
        self.assertAlmostEqual(high, 0.7634, places=3)
        low, high = wilson_interval(0, 10)
        self.assertAlmostEqual(low, 0.0, places=6)
        self.assertAlmostEqual(high, 0.2775, places=3)

    def test_interval_always_brackets_the_observed_rate_even_at_the_extremes(self):
        for n in (1, 7, 10, 100):
            for k in range(n + 1):
                low, high = wilson_interval(k, n)
                self.assertLessEqual(low, k / n, (k, n))
                self.assertGreaterEqual(high, k / n, (k, n))
        self.assertEqual(wilson_interval(10, 10)[1], 1.0)
        self.assertEqual(wilson_interval(0, 10)[0], 0.0)

    def test_empty_sample_is_rejected(self):
        with self.assertRaises(ValueError):
            wilson_interval(0, 0)


class EvaluateRecordsTests(unittest.TestCase):
    def test_errors_against_ground_truth_and_against_the_unoccluded_estimate(self):
        gt = {"f1": np.array(pose_list())}
        records = [
            record("f1", 0, pose_list(tz=0.504)),
            record("f1", 50, pose_list(tz=0.524, rot_z_deg=10)),
        ]
        rows = {r["level"]: r for r in evaluate_records(records, gt, ORIGIN)}
        self.assertAlmostEqual(rows[0]["translation_mm"], 4.0)
        self.assertAlmostEqual(rows[0]["adds_mm"], 4.0)
        self.assertAlmostEqual(rows[0]["pose_shift_mm"], 0.0)
        self.assertAlmostEqual(rows[50]["translation_mm"], 24.0)
        self.assertAlmostEqual(rows[50]["rotation_deg"], 10.0, places=6)
        self.assertAlmostEqual(rows[50]["pose_shift_mm"], 20.0)

    def test_a_failed_register_call_is_kept_as_a_failure(self):
        gt = {"f1": np.array(pose_list())}
        bad = record("f1", 50, None)
        bad["error"] = "RuntimeError: boom"
        rows = {r["level"]: r for r in evaluate_records([record("f1", 0, pose_list()), bad], gt, ORIGIN)}
        self.assertFalse(rows[50]["ok"])
        self.assertTrue(math.isnan(rows[50]["adds_mm"]))
        self.assertTrue(rows[0]["ok"])

    def test_frame_without_a_level_zero_record_has_no_shift(self):
        gt = {"f1": np.array(pose_list())}
        rows = evaluate_records([record("f1", 50, pose_list(tz=0.51))], gt, ORIGIN)
        self.assertTrue(math.isnan(rows[0]["pose_shift_mm"]))


def row(level, adds_mm, ok=True, rotation=0.0, translation=None):
    return {"level": level, "ok": ok, "adds_mm": adds_mm if ok else float("nan"),
            "rotation_deg": rotation, "translation_mm": adds_mm if translation is None else translation,
            "pose_shift_mm": 0.0, "achieved_occluded": level / 100}


class LevelTableTests(unittest.TestCase):
    def test_success_rate_counts_errors_strictly_below_the_diameter_fraction(self):
        rows = [row(50, 5.0), row(50, 10.0), row(50, 30.0), row(50, 0, ok=False)]
        table = {t["level"]: t for t in level_table(rows, diameter_m=0.2)}[50]
        self.assertEqual(table["n"], 4)
        self.assertEqual(table["n_failed_call"], 1)
        self.assertEqual(table["success"][0.05][0], 0.25)   # < 10 mm: only the 5 mm one
        self.assertEqual(table["success"][0.10][0], 0.5)    # < 20 mm
        self.assertEqual(table["success"][0.20][0], 0.75)   # < 40 mm; the failed call never counts

    def test_error_statistics_ignore_failed_calls_and_are_per_level(self):
        rows = [row(0, 2.0), row(0, 4.0), row(90, 100.0), row(90, 300.0), row(90, 0, ok=False)]
        table = {t["level"]: t for t in level_table(rows, diameter_m=0.2)}
        self.assertEqual(sorted(table), [0, 90])
        self.assertAlmostEqual(table[0]["adds_mean_mm"], 3.0)
        self.assertAlmostEqual(table[90]["adds_median_mm"], 200.0)

    def test_counts_half_turns_by_rotation_error(self):
        rows = [row(90, 5.0, rotation=175.0), row(90, 5.0, rotation=3.0)]
        table = level_table(rows, diameter_m=0.2)[0]
        self.assertEqual(table["rot_over_90"], 1)

    def test_success_interval_brackets_the_rate(self):
        rows = [row(10, 1.0)] * 8 + [row(10, 100.0)] * 2
        success = level_table(rows, diameter_m=0.2)[0]["success"][0.10]
        rate, low, high = success
        self.assertEqual(rate, 0.8)
        self.assertLess(low, rate)
        self.assertGreater(high, rate)


if __name__ == "__main__":
    unittest.main()
