"""Occlusion-aware visible-silhouette/depth score. Lower is better.

Inputs are rendered hypotheses, observed RGB-D segmentation, and optionally
robot-only depth. No ground-truth object transform enters this function.
"""

import torch


@torch.no_grad()
def score_depth_hypotheses(object_depth, observed_depth, mask, robot_depth=None,
                           occlusion_margin_m=0.005, robot_tolerance_m=0.01,
                           depth_clip_m=0.03, depth_weight=0.25):
    if object_depth.ndim != 3 or observed_depth.shape != object_depth.shape[1:] or mask.shape != observed_depth.shape:
        raise ValueError("expected candidate depth [N,H,W] and matching observation/mask [H,W]")
    if robot_depth is not None and robot_depth.shape != observed_depth.shape:
        raise ValueError("robot depth shape must match observation")
    support = object_depth > 0
    visible = support
    if robot_depth is not None:
        # Trust robot occlusion only where its projected depth agrees with RGB-D.
        reliable_robot = ((robot_depth > 0) & (observed_depth > 0)
                          & ((robot_depth - observed_depth).abs() <= robot_tolerance_m))
        hidden = reliable_robot[None] & (object_depth > robot_depth[None] + occlusion_margin_m)
        visible = support & ~hidden
    target = mask.bool()[None]
    intersection = visible & target
    union = visible | target
    iou = intersection.sum(dim=(1, 2)) / union.sum(dim=(1, 2)).clamp(min=1)
    valid_depth = intersection & (observed_depth[None] > 0)
    count = valid_depth.sum(dim=(1, 2))
    residual = ((object_depth - observed_depth[None]).abs() / depth_clip_m).clamp(max=1)
    residual = (residual * valid_depth).sum(dim=(1, 2)) / count.clamp(min=1)
    residual = torch.where(count > 0, residual, torch.ones_like(residual))
    return 1 - iou + depth_weight * residual, iou
