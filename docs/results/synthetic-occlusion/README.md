# Synthetic-occlusion baseline: interim results (2026-10)

Unmodified pretrained FoundationPose, each frame registered independently, black block
hiding 10-90% of the object mask. Design: `docs/superpowers/specs/2026-10-04-synthetic-occlusion-baseline-design.md`.
Success = ADD-S < 10% of model diameter (cracker_box 268.8 mm -> 26.9 mm). Errors are against YCBInEOAT GT poses.

| Folder | Contents |
|---|---|
| `analysis/zero_n100` | cracker_box, 100 frames, occluder depth = 0 |
| `analysis/zero_vs_front` | zero vs. `front` (occluder depth = object median - 100 mm) |
| `analysis/front_vs_oracle` | front vs. oracle (occluder region blanked in network input) |
| `analysis/mustard_front` | mustard0, front mode |
| `analysis/all_cracker` | zero / front / oracle together, with ADD-S AUC columns and `auc_vs_occlusion.png` |
| `analysis/failures_front_n100_v080.png` | gallery of failed vs ok frames at 80% hidden (green = GT box, orange = estimate) |
| `analysis/partial_check` | early partial run (sanity check) |
| `natural_occlusion/` | per-frame natural occlusion (mask- and depth-based) for 3 sequences |
| `poses/` | per-(frame, level) estimated poses (jsonl) |
| `selection/` | selected frame ids per run |
| `review_samples/` | sample original / occluded / visible-mask review images (full sets are local only) |

Each analysis folder: `*_levels.csv` (per-level table), `*_records.csv` (per-frame), and plots
(`success_vs_occlusion`, `error_vs_occlusion`, `success_by_side`, `success_threshold_sensitivity`, `per_frame_before_after`).
`adds_auc_10cm`: area under accuracy-vs-threshold over 0-100 mm (failed call = wrong). Its ceiling here is
~0.964 because the un-occluded error floor is ~3.6 mm.
Occlusion level in file names = percent of the object mask hidden.

Full occluded scenes (`data/occluded/`) and `outputs/occ_demo` are not committed.
