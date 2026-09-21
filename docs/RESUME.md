# Current project handoff

Saved: 2026-09-22 (Asia/Seoul)

## Resume from GitHub

Repository: `/home/mjcha/effector-aware-foundationpose`, branch `main`.
This checkpoint adds opt-in candidate filtering on top of `e153272`, which
completed robot-geometry export and projection validation. Use `git log` for
this checkpoint's publication commit. No unfinished source changes are required
to resume from GitHub.

**Effector-aware registration filtering is implemented as an opt-in prototype.**
Read [CANDIDATE_FILTERING.md](CANDIDATE_FILTERING.md) for method details,
matched experiment commands, and limitations. Default inference and ordinary
tracking remain unchanged; automatic recovery is not implemented.
Read [ROBOT_GEOMETRY.md](ROBOT_GEOMETRY.md) for results, hashes, and complete
capture/audit/inference commands. Raw simulator data, meshes, pretrained assets,
and outputs are ignored by Git; a fresh machine must install prerequisites
and regenerate the capture. The selected projection overlay is committed.

## Verified checkpoint

- Filtering comparison: `outputs/ea_filter_comparison_20260922` contains all
  300 trial records and the protocol/hash report. EA vs original: 30/45
  observable successes for both, median registration 0.680 s vs 2.327 s.
  Geometry-only also gets 30/45; random gets 31/45. Do not claim a robot-specific
  accuracy gain. EA changes candidate sets on seven unique observed frames.
- Normal filtered pipeline: `outputs/ea_filtered_sequence_20260922`, all 192
  frames complete, mean error 5.233 mm / 4.745 degrees. Only registration is
  filtered; tracking remains upstream. Treat this as an integration check.
- All 49 tests pass in the GPU environment; 40 pass and nine skip in the
  dependency-free local environment. Upstream remains unchanged. This checkpoint
  includes the filtering implementation, matched benchmark, tests and handoff.

Geometry/baseline checkpoint retained from `e153272`:

- Unchanged FoundationPose submodule: `a1b694b83e633c2cb6115b9063d940a687759392`.
- RTX 3070 / 8 GB, driver 580.178.04; validated Docker images remain
  `robotis/robotis-lab:latest` and `foundationpose:latest`.
- Accepted geometry capture:
  `data/isaac_exports/omy_robot_geometry_calibrated_20260922`.
- Audit: `outputs/omy_robot_geometry_calibrated_20260922_audit`.
- Unchanged estimator: `outputs/omy_robot_geometry_calibrated_20260922_control`.
- All 192 frames and 11 links pass mesh/pose validation and the GPU projection
  audit: minimum visible robot IoU 0.98357, minimum coverage 0.99975, worst
  per-frame depth p95 error 0.477 mm. Median robot render time is 2.77 ms,
  excluding initialization, readback and audit.
- Sweep command error: 4.629 mm mean / 29.165 mm maximum (30 mm gate).
- Six fully hidden frames and 24 below half the initial visible mask area.
- Corrected baseline mean pose error: 5.332 mm / 4.671 degrees overall;
  0.937 mm / 3.090 degrees in the higher-visible-area group;
  36.098 mm / 15.735 degrees in the lower-visible-area group.
- Cold registration: 3.012 s / 252 candidates. Tracking: 23.282 ms mean,
  one pose per call. Estimator-only timings, not end-to-end throughput.
- All 34 offline tests pass; Python compilation and shell/whitespace checks
  pass. Capture, GPU audit, and full unchanged inference completed successfully.

## Important correction

The robot projection audit exposed Isaac Lab's cached camera pose after reset
randomization. `update_latest_camera_pose=True` fixes it. The actual camera
pose differs from the stale export by 10.259 mm / 0.658 degrees. Earlier
static/dynamic error numbers are historical and calibration-biased; they are
not the reference for new EA comparisons. Their raw artifacts are preserved.

`omy_ea_geometry_20260921` is the unversioned prototype export.
`omy_robot_geometry_v1_20260922` is a negative-control diagnostic: its stale
camera projection fails the same acceptance gates passed by the calibrated
capture. Neither should substitute for the accepted geometry capture.

## Next work

1. Use `src/urdf_render/robot_depth.py` to render arm/wrist/finger occlusion from
   robot meshes and link poses. It takes no bottle ground truth or semantic
   robot masks; simulator robot masks are used only by the projection audit.
2. Extend evaluation of the implemented adapter on separate held-out scenes.
   The matched independent-registration benchmark already compares original,
   random, geometry-only, effector-aware and 10 mm perturbed robot projection.
   Include all rendering overhead and weak-evidence fallbacks in comparisons.
3. Establish whether robot context adds benefit beyond geometry-only screening;
   do not equate fewer candidates with an accuracy improvement. Add explicit
   temporal recovery trials, real segmentation, and broader calibration noise.

The gripper occludes a **free bottle**, not a rigidly grasped one. A constant
object-to-effector prior would be invalid. Object ground truth stays
evaluation-only. If simulator object masks are used for registration/recovery,
disclose them and supply them identically to all methods. Ordinary tracking
uses one pose, so candidate pruning is not automatically a tracking speedup.

## Preservation

The shared ROBOTIS Lab checkout has pre-existing user changes; do not reset it.
Neither it nor upstream FoundationPose was edited. The original 737-frame
official demo and old static/dynamic controls remain intact. No simulator or
inference job needs to remain running between sessions.
