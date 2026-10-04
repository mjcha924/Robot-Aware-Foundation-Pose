import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    import kornia  # noqa: F401
    import torch
except ImportError:  # these tests need the FoundationPose container
    torch = None


@unittest.skipIf(torch is None, "needs torch and kornia (FoundationPose container)")
class BlankOccludedTests(unittest.TestCase):
    def setUp(self):
        from foundationpose_adapter.oracle_occlusion import blank_occluded

        self.blank = blank_occluded
        self.H, self.W, self.C = 40, 50, 8   # source image and an 8x8 crop
        self.occ = torch.zeros(self.H, self.W, dtype=torch.bool)
        self.occ[12:16, 14:18] = True

    def batch(self, x0, y0, scale=1.0, with_xyz_b=True, with_depth=False):
        # crop pixel (u, v) shows source pixel (x0 + u/scale, y0 + v/scale)
        tf = torch.tensor([[scale, 0, -x0 * scale], [0, scale, -y0 * scale], [0, 0, 1.0]]).expand(2, 3, 3).clone()
        c = self.C
        ones = lambda ch: torch.ones(2, ch, c, c)
        return SimpleNamespace(
            tf_to_crops=tf, rgbAs=ones(3), rgbBs=ones(3), xyz_mapAs=ones(3),
            xyz_mapBs=ones(3) if with_xyz_b else None,
            depthAs=ones(1) if with_depth else None, depthBs=ones(1) if with_depth else None,
        )

    def test_blanks_the_occluded_pixels_of_every_present_tensor_on_both_sides(self):
        b = self.batch(x0=10, y0=8, with_depth=True)
        self.blank(b, self.occ)
        # source rows 12-15 / cols 14-17  ->  crop rows 4-7 / cols 4-7
        for name in ("rgbAs", "rgbBs", "xyz_mapAs", "xyz_mapBs", "depthAs", "depthBs"):
            tensor = getattr(b, name)
            self.assertTrue(torch.all(tensor[:, :, 4:8, 4:8] == 0), name)
            outside = tensor.clone()
            outside[:, :, 4:8, 4:8] = 1
            self.assertTrue(torch.all(outside == 1), f"{name} changed outside the occluder")

    def test_missing_optional_tensors_are_left_alone(self):
        b = self.batch(x0=10, y0=8, with_xyz_b=False)
        self.blank(b, self.occ)
        self.assertIsNone(b.xyz_mapBs)
        self.assertIsNone(b.depthAs)

    def test_a_crop_that_misses_the_occluder_is_unchanged(self):
        b = self.batch(x0=30, y0=20)
        self.blank(b, self.occ)
        self.assertTrue(torch.all(b.rgbAs == 1) and torch.all(b.rgbBs == 1))

    def test_follows_a_zoomed_crop(self):
        # 2x zoom: the crop covers exactly the 4x4 source block; edge pixels sit on the rounding boundary,
        # so check the interior
        b = self.batch(x0=14, y0=12, scale=2.0)
        self.blank(b, self.occ)
        self.assertTrue(torch.all(b.rgbBs[:, :, 1:7, 1:7] == 0))


@unittest.skipIf(torch is None, "needs torch and kornia (FoundationPose container)")
class WrapTransformTests(unittest.TestCase):
    def test_blanks_before_calling_the_original_and_passes_its_arguments_through(self):
        from foundationpose_adapter.oracle_occlusion import OracleHolder, wrap_transform

        seen = {}

        def original(batch, H_ori, W_ori, bound=1):
            seen.update(rgb_sum=float(batch.rgbAs.sum()), H=H_ori, W=W_ori, bound=bound)
            return batch

        occ = torch.zeros(40, 50, dtype=torch.bool)
        occ[:, :] = True
        holder = OracleHolder()
        holder.occ = occ
        wrapped = wrap_transform(original, holder)
        batch = SimpleNamespace(tf_to_crops=torch.eye(3).expand(1, 3, 3).clone(), rgbAs=torch.ones(1, 3, 8, 8),
                                rgbBs=torch.ones(1, 3, 8, 8), xyz_mapAs=None, xyz_mapBs=None, depthAs=None, depthBs=None)
        wrapped(batch=batch, H_ori=40, W_ori=50, bound=1)
        self.assertEqual(seen["rgb_sum"], 0.0)
        self.assertEqual((seen["H"], seen["W"], seen["bound"]), (40, 50, 1))

    def test_without_an_occluder_the_batch_is_untouched(self):
        from foundationpose_adapter.oracle_occlusion import OracleHolder, wrap_transform

        seen = {}
        wrapped = wrap_transform(lambda batch, H_ori, W_ori, bound=1: seen.update(sum=float(batch.rgbAs.sum())),
                                 OracleHolder())
        batch = SimpleNamespace(tf_to_crops=torch.eye(3).expand(1, 3, 3).clone(), rgbAs=torch.ones(1, 3, 8, 8),
                                rgbBs=torch.ones(1, 3, 8, 8), xyz_mapAs=None, xyz_mapBs=None, depthAs=None, depthBs=None)
        wrapped(batch, 40, 50)  # positional call, as predict_score.py does
        self.assertEqual(seen["sum"], 3 * 8 * 8)


if __name__ == "__main__":
    unittest.main()
