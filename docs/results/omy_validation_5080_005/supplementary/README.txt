Supplementary metrics for finished rollouts: ADD-S, translation and rotation error.

SUPPLEMENTARY ONLY. The primary metric stays the corresponding-point surface
error in summary.json (marker roll matters for this task, so a symmetric
metric must not replace it). ADD-S here is the mean distance from each
predicted surface point to the nearest GT surface point (4096 evaluation
points, same sampling as the primary metric). Frame 0 excluded from aggregates.
