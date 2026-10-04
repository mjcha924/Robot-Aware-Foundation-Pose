# Synthetic-occlusion baseline for FoundationPose — design

Branch: `baseline/synthetic-occlusion`. Date: 2026-10-04.

## Goal

Measure how the **unchanged** pretrained FoundationPose degrades as a known fraction of the
target object is hidden by a synthetic occluder. This is the baseline for the project
"robot/effector-aware FoundationPose": before any robot-aware method is built, we need to know
whether (and how fast) the unmodified estimator fails under controlled occlusion.

Out of scope here: any change to FoundationPose, robot geometry, candidate filtering, tracking
experiments, Isaac Sim. The earlier Isaac/candidate-filter code on `main` is left untouched and
is not used.

## Understanding (agreed with the user)

- Occluder: a black block first; object-in-front depth variant second.
- Occlusion is quantified exactly: percentage of the frame's object-mask pixels hidden, counted
  in pixels, and every generated image is saved so the user can inspect it.
- Evaluation: each frame is registered independently (`register`, not `track_one`), so errors do
  not carry across frames. Compare occluded result against (a) ground truth and (b) the same
  frame's un-occluded result.
- Data: public YCBInEOAT `cracker_box_reorient` (375 frames, larger object than mustard0), with the
  per-frame visible-object masks (`gt_mask/`) and GT poses (`annotated_poses/`) it ships with.
- Start with about 100 frames, verify visually, then extend to all frames.

## Facts established about the data and FoundationPose

- `register(K, rgb, depth, ob_mask)` uses the mask only to guess the initial translation
  (`estimater.py: guess_translation`). The networks see RGB + xyz-map crops of rendered vs. observed
  views; no mask is given to them. Depth 0 is treated as "no measurement".
- `gt_mask` is the visible region and the real sequence already contains robot occlusion, so
  "100% visible" does not exist; percentages are relative to each frame's own `gt_mask`.
  cracker_box_reorient mask area: median 7781 px (2.5% of the image), max 13333 px; only 47/375
  frames exceed 60% of the max area.
- The YCBInEOAT ground truth uses the se3-TrackNet CAD models (`YCB_models_with_ply.zip`), not the
  YCB google_16k mesh. Using google_16k gave a constant ~84 mm translation offset on mustard0
  (stable to ~1.3 mm), which equals the bbox-centre difference between the two meshes. Use
  `data/models/CADmodels/<object>/textured_simple.obj`.
- Unmodified `run_demo.py` on mustard0 completes 737/737 frames in about a minute on the RTX 3070.

## Layout

```
data/                                   (git-ignored)
  ycbineoat/cracker_box_reorient/       original scene
  models/CADmodels/003_cracker_box/     GT-consistent mesh
  occluded/cracker_box_reorient/
    selection.json                      chosen frame ids and why
    v100/ v090/ ... v010/               one scene folder per visibility level, same layout as the original
      rgb/ depth/ masks/ meta.json      masks = visible mask; meta = exact visible %, side, seed

src/occlusion/   occluder.py  apply.py  select.py     pure numpy, no GPU
src/pose_eval/   metrics.py (ADD, ADD-S)  report.py
scripts/         make_occluded_scene.py  run_occlusion_baseline.py  analyze_occlusion_baseline.py  fp_shell.sh
tests/           test_occluder.py test_apply.py test_select.py test_metrics.py
outputs/occlusion_baseline/<run_id>/    poses.jsonl results.csv summary.json figs/
```

## Interfaces

```python
visible_fraction(obj_mask, occ) -> float
make_block(obj_mask, target_visible, side, margin_px=8, tol=0.005) -> (occ, achieved)
apply_occlusion(rgb, depth, occ, color=(0,0,0), depth_mode="zero"|"front",
                front_offset_m=0.10, obj_mask=None) -> (rgb, depth)
select_frames(mask_areas, n, ...) -> [frame_id]
add_s(est, gt, model_pts); add(est, gt, model_pts, sym_tfs)
```

- `make_block`: an axis-aligned rectangle growing from one side (top/bottom/left/right) of the
  object's bbox, extending `margin_px` beyond the object. Its size is found by bisection so the
  fraction of object pixels still visible is within `tol` of the target. Counting uses object
  pixels only. Direction and seed are fixed per (frame, level); within one frame the same side is
  used for all levels so occlusion grows monotonically.
- `apply_occlusion`: RGB inside the block is set to `color`. Depth mode `zero` sets depth to 0;
  mode `front` sets it to (median object depth - `front_offset_m`).
- `register` receives the **visible** mask: `gt_mask & ~occ`. A full-GT-mask variant is a later
  ablation to separate "bad initial translation" from "bad network input".
- Colour other than black (grey, copied background texture) is an option for a later ablation, not
  part of the first run.

## Evaluation

Per (frame, level) record: `frame_id, level, side, achieved_visible, T_est, T_gt, T_ref`,
translation error (mm), rotation error (deg), ADD-S, and the same measured against the frame's
own un-occluded result `T_ref` (level v100, computed once per frame and reused).

- Success is derived from continuous errors: ADD(-S) < 10% of the object diameter as the main
  threshold, with 5% and 20% reported alongside. Primary result is the curve over visibility
  level, not a single threshold.
- The scorer's score is not used for success (it is only a relative ranking between candidates).
- Cracker box is not rotationally symmetric in general; symmetry transforms must be checked
  before using ADD or rotation error; ADD-S is the default.
- Frames where the un-occluded result is already far from GT are flagged and analysed separately,
  since their error is not caused by the added block.
- `set_seed(0)` as in upstream; block side is seeded per frame/level.

## Steps and checkpoints

1. Data layout; run unmodified `run_demo.py` on cracker_box_reorient. Checkpoint: user inspects.
2. Mask-area distribution and frame selection (~100). Checkpoint: user approves the criterion.
3. `occluder.py` test-first. Tests: hits target within tol, monotone in target, fragmented masks,
   all four sides, object touching the image border.
4. `apply.py` and review images (original | occluded | visible mask + numbers). Checkpoint: user
   inspects the images before any pose is computed.
5. Small run: 10 frames x all levels end to end; sanity-check the numbers.
6. Full ~100 frames, then all 375; analysis and curves.

## Risks and open items

- Large objects may still be only a few percent of the image, so a block at the high-occlusion end
  can hide nearly all of the object; very low levels (<=10% visible) may be unrecoverable by design.
- Unmodified-run errors on this sequence are not yet known; step 1 provides them.
- `erode_depth` may react to block boundaries in depth mode `front`; both depth modes are run.
- ADD-S needs model points; `points.xyz` shipped with the CAD models is the intended source.
- Docker runs as root, so generated output directories are root-owned.
