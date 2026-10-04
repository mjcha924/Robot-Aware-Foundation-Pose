"""Choose which frames of a sequence to run the occlusion experiment on."""

import numpy as np

STRATEGIES = ("uniform", "largest")


def select_frames(frame_areas, n, strategy="uniform", min_area=0):
    """Return `n` frame ids, in temporal order.

    `frame_areas` is a temporally ordered list of (frame_id, object mask area in pixels).
    Frames below `min_area` are dropped first. "uniform" spreads the picks evenly over what
    remains (first and last included); "largest" takes the biggest masks.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {STRATEGIES}, got {strategy!r}")
    candidates = [(frame_id, area) for frame_id, area in frame_areas if area >= min_area]
    if n > len(candidates):
        raise ValueError(f"asked for {n} frames but only {len(candidates)} qualify")
    if strategy == "uniform":
        picks = sorted({int(round(p)) for p in np.linspace(0, len(candidates) - 1, n)})
    else:
        order = sorted(range(len(candidates)), key=lambda i: -candidates[i][1])
        picks = sorted(order[:n])
    return [candidates[i][0] for i in picks]
