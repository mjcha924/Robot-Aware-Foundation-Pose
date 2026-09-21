"""Deterministic candidate selection, independent of GPU/estimator packages."""

import math
import random


def screening_resolution(height, width, scale):
    """CUDA rasterizer requires dimensions divisible by eight."""
    if any(type(value) is not int or value < 1 for value in (height, width, scale)):
        raise ValueError("image dimensions and scale must be positive integers")
    return tuple(max(8, 8 * ((value + scale * 8 - 1) // (scale * 8))) for value in (height, width))


def select_candidates(scores, keep, mode="ranked", seed=0, informative=True):
    if type(keep) is not int or keep < 1:
        raise ValueError("keep must be a positive integer")
    if mode not in {"ranked", "random", "none"}:
        raise ValueError("unknown selection mode")
    if not scores or any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in scores):
        raise ValueError("scores must be non-empty and finite")
    count = len(scores)
    if mode == "none" or not informative or keep >= count:
        return list(range(count))
    if mode == "random":
        return sorted(random.Random(seed).sample(range(count), keep))
    # Preserve upstream order among survivors; score is only a screening rule.
    return sorted(sorted(range(count), key=lambda i: (scores[i], i))[:keep])
