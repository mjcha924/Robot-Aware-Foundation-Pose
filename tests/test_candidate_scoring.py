"""Run in the FoundationPose image; skipped if PyTorch is unavailable."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    import torch
    from candidate_pruning.scoring import score_depth_hypotheses
except ImportError:
    torch = None


@unittest.skipIf(torch is None, "PyTorch scoring tests require the FoundationPose environment")
class CandidateScoringTests(unittest.TestCase):
    def test_perfect_visible_match(self):
        depth = torch.ones((2, 2))
        score, iou = score_depth_hypotheses(depth[None], depth, depth.bool())
        self.assertAlmostEqual(score.item(), 0.)
        self.assertAlmostEqual(iou.item(), 1.)

    def test_robot_occlusion_changes_candidate_ranking(self):
        # Candidate 0 has a real hidden extension; candidate 1 explains only
        # two visible pixels. Robot awareness should preserve candidate 0.
        candidates = torch.tensor([[[1., 1., 1., 1., 1., 1.]], [[1., 1., 0., 0., 0., 0.]]])
        observed = torch.tensor([[1., 1., 1., .5, .5, .5]])
        mask = torch.tensor([[True, True, True, False, False, False]])
        robot = torch.tensor([[0., 0., 0., .5, .5, .5]])
        ordinary, _ = score_depth_hypotheses(candidates, observed, mask)
        aware, _ = score_depth_hypotheses(candidates, observed, mask, robot)
        self.assertLess(ordinary[1].item(), ordinary[0].item())
        self.assertLess(aware[0].item(), aware[1].item())

    def test_robot_behind_object_does_not_hide_it(self):
        depth = torch.ones((2, 2))
        a, _ = score_depth_hypotheses(depth[None], depth, depth.bool())
        b, _ = score_depth_hypotheses(depth[None], depth, depth.bool(), depth * 2)
        self.assertTrue(torch.equal(a, b))

    def test_inconsistent_robot_depth_is_not_trusted(self):
        depth = torch.ones((2, 2))
        score, iou = score_depth_hypotheses(depth[None], depth, depth.bool(), depth * .5)
        self.assertAlmostEqual(score.item(), 0.)
        self.assertAlmostEqual(iou.item(), 1.)

    def test_empty_overlap_stays_finite(self):
        depth = torch.ones((2, 2))
        score, _ = score_depth_hypotheses(torch.zeros((1, 2, 2)), depth, depth.bool())
        self.assertTrue(torch.isfinite(score).all())
        self.assertGreater(score.item(), 1.)

    def test_completely_hidden_candidate_is_not_a_perfect_match(self):
        robot = torch.full((2, 2), .5)
        score, iou = score_depth_hypotheses(torch.ones((1, 2, 2)), robot,
                                          torch.zeros((2, 2), dtype=torch.bool), robot)
        self.assertEqual(iou.item(), 0.)
        self.assertGreater(score.item(), 1.)

    def test_zero_robot_depth_equals_geometry_only(self):
        depth = torch.ones((2, 2))
        a, _ = score_depth_hypotheses(depth[None], depth, depth.bool())
        b, _ = score_depth_hypotheses(depth[None], depth, depth.bool(), torch.zeros_like(depth))
        self.assertTrue(torch.equal(a, b))

    def test_mismatched_shapes_rejected(self):
        with self.assertRaises(ValueError):
            score_depth_hypotheses(torch.zeros((1, 2, 2)), torch.ones((3, 3)), torch.ones((3, 3)))

    @unittest.skipUnless(torch is not None and torch.cuda.is_available(), "requires CUDA/upstream environment")
    def test_upstream_rejected_registration_clears_filter_trace(self):
        import numpy as np
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "third_party/FoundationPose"))
        from foundationpose_adapter.filtered_estimator import FilteredFoundationPose
        estimator = FilteredFoundationPose.__new__(FilteredFoundationPose)
        estimator.debug = 0
        estimator.glctx = object()  # no rasterization occurs on this early-return path
        estimator.filter_trace = {"candidate_count": 64, "selected_indices": [1, 2]}
        pose = estimator.register(K=np.eye(3), rgb=np.zeros((16, 16, 3), dtype=np.uint8),
                                  depth=np.zeros((16, 16), dtype=np.float32),
                                  ob_mask=np.zeros((16, 16), dtype=bool))
        self.assertEqual(estimator.filter_trace["candidate_count"], 0)
        self.assertEqual(estimator.filter_trace["selected_indices"], [])
        self.assertEqual(estimator.filter_trace["filter_s"], 0.)
        self.assertTrue(np.array_equal(pose, np.eye(4)))


if __name__ == "__main__":
    unittest.main()
