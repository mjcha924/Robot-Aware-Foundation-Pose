# Effector-aware registration filtering

Implementation: 2026-09-22. This is an opt-in, training-free prototype outside
the pinned FoundationPose submodule. The default runner still uses unchanged
FoundationPose. Candidate filtering changes registration; ordinary single-pose
tracking is unchanged. It does not yet implement automatic recovery.

## Method

`FilteredFoundationPose` overrides only the upstream proposal-generation hook.
The initial 252 rotations, mask/depth-based translation estimate, pretrained
refiner, learned scorer, and tracking implementation remain upstream.

1. Generate the original pose hypotheses in FoundationPose's centered mesh frame.
2. Render each candidate at reduced resolution (120 x 216 for our 480 x 848
   camera; dimensions are rounded to multiples of eight for the CUDA rasterizer).
3. For effector mode, render all known robot links into the same camera.
   Trust a robot pixel only when its depth agrees with measured scene depth
   within 10 mm. A candidate bottle surface more than 5 mm behind that robot
   surface is hidden and excluded from its predicted visible silhouette.
4. Rank candidates by `1 - visible IoU + 0.25 * depth residual`. IoU compares
   the predicted visible bottle silhouette with the supplied visible object
   mask. The mean absolute depth residual is measured on their intersection,
   divided by 30 mm, and clipped to one. An empty intersection receives the
   maximum depth penalty. Lower scores are better.
5. Retain the best 64 candidates in their original order, then run unchanged
   refinement and learned scoring. No fixed bottle-to-gripper pose is assumed.

If fewer than 16 masked valid-depth pixels remain at screening resolution,
the best candidate IoU is below 0.05, or all scores are effectively equal,
screening falls back to all candidates. This is a conservative heuristic,
not a guarantee that the correct candidate will survive. The filter currently
does not model robot/object solid-volume penetration or contact constraints.

Separate rasterizer contexts prevent the robot's large mesh and the upstream
252-pose batches from inflating each other's retained GPU scratch buffers.
Both paths completed on the 8 GB RTX 3070 after this correction.

## Inputs and truth boundary

Filtering receives only the object model, RGB-D/visible object mask, camera
calibration, robot-link geometry, and robot poses. It does not receive object
ground truth or simulator robot semantic masks. Robot poses are currently ideal
simulator state. Registration trials use simulator-provided visible **object**
masks equally for every method; they are an oracle-segmentation experiment,
not a demonstration with a real segmentation system.

The bottle remains free, not grasped. Robot occlusion does not reveal hidden
free-object motion. Independently registering after occlusion is not the same
as demonstrating improved temporal tracking or automatic recovery.

## Run filtering

Use the calibrated geometry capture from [ROBOT_GEOMETRY.md](ROBOT_GEOMETRY.md).
All commands use new output directories; generated artifacts remain ignored.

```bash
./scripts/run_isaac_foundationpose.sh \
  data/isaac_exports/omy_robot_geometry_calibrated_20260922 \
  --candidate-filter effector --filter-keep 64 --screening-scale 4 \
  --output /workspace/outputs/ea_filtered_sequence_20260922 --save-vis
```

The first registration is filtered; subsequent frames use upstream tracking.
`poses.jsonl` records retained candidate IDs/count, screening scores, fallback
reason, maximum visible IoU and filtering time. Registration timing includes
robot/object rendering and candidate selection, but excludes loading, input
decoding and visualization. No end-to-end or tracking speedup is implied.

Other `--candidate-filter` modes are `none` (the default original estimator),
`random` (seeded random selection) and `geometry` (same screening score without
robot occlusion). `--filter-seed` controls random selection.

## Matched registration experiment

```bash
./scripts/run_isaac_foundationpose.sh \
  data/isaac_exports/omy_robot_geometry_calibrated_20260922 \
  --benchmark-filtering --filter-keep 64 --trial-repeats 3 \
  --output /workspace/outputs/ea_filter_comparison_20260922
```

Default preselected frame indices:
`0,48,72,84,90,96,99,100,101,102,103,106,108,109,110,112,118,132,168,191`.
Every method registers independently with the same inputs and five refinement
iterations. Variants are original, random, geometry-only, effector-aware, and
effector-aware with a 10 mm camera-X error in robot projection only. The random
control matches the effector method's retained count, including fallbacks.

All methods are warmed on the same first frame; warmup timings are excluded.
EA runs first to determine the matched random count, which is a timing-order
limitation. Three repeats vary random subsets; they are not independent scenes.
Success is fixed at <=20 mm translation AND <=15 degrees raw rotation error.
Rows with fewer than 16 full-resolution valid masked depth pixels are marked
unobservable for every method and excluded from attempted-trial success rates.
They are not counted as successful estimates.

The report includes timings with filtering overhead, success counts, pose
errors, nearest-initial-rotation retention, input/code hashes, and per-trial
diagnostics. Nearest-rotation retention is evaluation-only and does not prove
final pose accuracy. Ground truth is read only after each estimation call.

This is a single-sequence exploratory experiment, not a held-out benchmark.
Do not claim a benefit specific to robot awareness unless it outperforms the
geometry-only control. Future work includes separate held-out captures, broader
calibration noise, real segmentation, and explicit temporal recovery trials.

## Completed experiment

All five variants completed the default 20-frame / three-repeat experiment.
Five preselected frames had insufficient observations, leaving **45 attempted
registrations per method** (15 unique observable frames), plus 15 unobservable
trial records per method. These repeats are not 45 independent scenes.

| Method | Successes / 45 | Median registration | Mean translation error | Mean rotation error |
| --- | ---: | ---: | ---: | ---: |
| Original, 252 candidates | 30 | 2.327 s | 9.581 mm | 21.004 degrees |
| Random, matched count | 31 | 0.634 s | 9.607 mm | 22.004 degrees |
| Geometry-only screening | 30 | 0.664 s | 9.611 mm | 21.401 degrees |
| Effector-aware screening | 30 | 0.680 s | 9.607 mm | 20.972 degrees |
| Effector-aware, 10 mm calibration offset | 30 | 0.674 s | 9.592 mm | 21.010 degrees |

Effector-aware screening used 64 candidates in 39/45 attempted trials and
fell back to 252 on frames `000101` and `000110` (six trials). Random counts
matched in every trial. Median screening overhead was 48.1 ms, including
robot/candidate rendering and selection. Registration was about 3.42x faster
than the full baseline on this test; no end-to-end or tracking speedup follows.

Robot awareness changed the retained candidate sets relative to geometry-only
in 21/45 trials (seven unique frames). The nearest initial rotation to ground
truth survived all EA and geometry trials, versus 40% of matched random trials.
Nevertheless, final success rates were **not better** than geometry-only or
random selection. Higher-visible-area trials succeeded 24/24 for all methods;
lower-visible-area trials succeeded 6/21 for original/geometry/EA and 7/21 for
random. This implements genuine robot-conditioned filtering but does **not**
yet establish an accuracy benefit specific to effector awareness.

The normal filtered-registration-then-tracking path also completed all 192
frames. Its first registration retained 64 candidates; later calls still used
one pose. Overall mean error was 5.233 mm / 4.745 degrees, compared with the
unchanged run's 5.332 mm / 4.671 degrees. Treat this as an integration check,
not evidence of improved tracking: initialization changed, the tracker did not.

Local artifacts:

- `outputs/ea_filter_comparison_20260922/benchmark.json`: protocol, hashes and summaries.
- `outputs/ea_filter_comparison_20260922/trials.jsonl`: all 300 trial records.
- `outputs/ea_filtered_sequence_20260922`: 192-frame poses, overlays and metrics.

```text
f3b528b63769da7a19ea56c784fcff932fff36b1b78108039fa844dc9d71cd07  benchmark.json
b844f362648c46523e6110b4df62e361cea6425ca4078595ba5cc770c8d19686  trials.jsonl
d05db6488cd7d4dbe429eb5c30d48d751e05e1511601b603c4e9e868b51e16c2  filtered_sequence/poses.jsonl
```

The report stores the exact tested implementation hashes. A subsequent guard
fix ensures empty-depth upstream early returns expose a complete zero-candidate
trace; this path was not entered by the attempted benchmark trials. The guard
is exercised by the CUDA regression test. Earlier smoke runs that failed CUDA
image alignment or memory allocation are diagnostics, not accepted results.

All 49 tests pass in the FoundationPose GPU environment, including robot-induced
ranking changes, calibration disagreement, weak/empty evidence, deterministic
selection, CUDA resolution alignment, and upstream early-return telemetry.
Locally without PyTorch, 40 tests pass and nine dependency-specific tests skip.

```bash
python3 -m unittest discover -s tests -v
docker run --rm --gpus all \
  --volume "$PWD:/workspace" --workdir /workspace/third_party/FoundationPose \
  foundationpose:latest python -m unittest discover -s /workspace/tests -v
```
