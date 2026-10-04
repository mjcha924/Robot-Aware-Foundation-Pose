"""Oracle for "what if FoundationPose knew where the occluder is": blank that region on both sides.

FoundationPose compares, for every pose hypothesis, a crop of the rendered model (A) with the same
crop of the observed frame (B). Where an occluder hides the object these disagree even for the true
pose. Here the known occluder region is zeroed in A and B (RGB, depth and xyz maps) just before the
network input is built, by wrapping `dataset.transform_batch`; the upstream code is not edited.
"""

_TENSORS = ("rgbAs", "rgbBs", "xyz_mapAs", "xyz_mapBs", "depthAs", "depthBs")


class OracleHolder:
    """Carries the current frame's occluder mask (bool tensor, full image) into the wrapped transform."""

    occ = None


def blank_occluded(batch, occ):
    """Zero the occluded pixels in every per-crop tensor of `batch` (both rendered and observed sides)."""
    import kornia
    import torch

    reference = batch.rgbAs
    count, _, height, width = reference.shape
    occ_image = occ.to(reference.device, torch.float)[None, None].expand(count, -1, -1, -1)
    occ_crop = kornia.geometry.transform.warp_perspective(
        occ_image, batch.tf_to_crops.to(reference.device), dsize=(height, width), mode="nearest", align_corners=False
    ) > 0.5
    for name in _TENSORS:
        tensor = getattr(batch, name, None)
        if tensor is not None:
            setattr(batch, name, tensor * (~occ_crop).to(tensor.device, tensor.dtype))
    return batch


def wrap_transform(original, holder):
    """transform_batch replacement that blanks the occluder first (no-op when the holder has none)."""

    def wrapped(batch, H_ori, W_ori, bound=1):
        if holder.occ is not None:
            blank_occluded(batch, holder.occ)
        return original(batch, H_ori, W_ori, bound=bound)

    return wrapped


def enable_oracle(estimator):
    """Patch an estimator's refiner and scorer; returns the holder whose `.occ` selects the region per frame."""
    holder = OracleHolder()
    for predictor in (estimator.refiner, estimator.scorer):
        predictor.dataset.transform_batch = wrap_transform(predictor.dataset.transform_batch, holder)
    return holder
