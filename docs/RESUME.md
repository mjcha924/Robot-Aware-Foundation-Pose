# Current project handoff

Saved: 2026-09-22 (Asia/Seoul)

## Resume from GitHub

Repository: `/home/mjcha/effector-aware-foundationpose`, branch `main`.
This checkpoint completes robot-geometry export and projection validation on
top of `65203c9` (the previous dynamic-control milestone). Use `git log` for
the publication commit. No unfinished source changes are required to resume.

**Effector-aware candidate filtering is not implemented yet.** The reusable
robot depth renderer and corrected-calibration control are ready for it.
Read [ROBOT_GEOMETRY.md](ROBOT_GEOMETRY.md) for results, hashes, and complete
capture/audit/inference commands. Raw simulator data, meshes, pretrained assets,
and outputs are ignored by Git; a fresh machine must install prerequisites
and regenerate the capture. The selected projection overlay is committed.

## Verified checkpoint

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
2. Implement conservative candidate screening in our adapter, leaving upstream
   untouched. Account for candidate bottle surfaces hidden behind the robot;
   do not mistake missing visual evidence there for a bad pose.
3. Add registration/recovery trials and compare original FoundationPose,
   matched-count random candidates, geometry-only screening, and robot-aware
   screening. Include geometry overhead, candidate retention, pose errors,
   failures, and recovery latency. Test calibration perturbations and separate
   tuning sequences from held-out evaluation.

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
