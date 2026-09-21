# Current project handoff

Saved: 2026-09-21 (Asia/Seoul)

## Workspace and verified checkpoint

- Repository: `/home/mjcha/effector-aware-foundationpose`.
- Branch: `main`. This checkpoint records the validated dynamic-control
  milestone built on `84d34d8`; use `git log` for its publication commit.
  Experimental robot-geometry export work is excluded from this milestone.
- FoundationPose submodule remains unchanged at
  `a1b694b83e633c2cb6115b9063d940a687759392`.
- GPU remains RTX 3070 / 8 GB with working driver 580.178.04.
- The original 737-frame upstream baseline and ten-frame Isaac static control
  remain intact. Static error still reproduces 8.117 mm / 1.196 degrees.
- New accepted dynamic export:
  `data/isaac_exports/omy_sweep_retrace_20260921`.
- New unchanged-estimator results:
  `outputs/omy_sweep_retrace_20260921_control`.
- All 192 frames passed export validation and inference. The capture contains
  six fully hidden frames and 24 frames below half the initial reference mask
  area. Tool-command error is 4.629 mm mean / 29.165 mm maximum, below the
  30 mm capture gate.
- Mean pose error: 12.347 mm / 4.343 degrees. Peak: 106.435 mm / 34.207 degrees.
  At frame 118, error is back to 8.690 mm / 3.924 degrees.
- Cold registration takes 3.026 s for 252 candidates; tracking averages
  23.984 ms per call (CUDA-synchronized estimator time only).
- All 19 offline tests pass. Capture, inference, and error-reporting paths
  were exercised on the GPU.

See [ISAAC_DYNAMIC_CONTROL.md](ISAAC_DYNAMIC_CONTROL.md) for reproduction
commands, artifact hashes, metrics, limitations and the results plot.

## Fixes made

The sweep draft exposed two coordinate issues: PhysX provides a COM Jacobian
while the task action uses link-origin poses, and the action's tool offset was
not rotated into the Jacobian frame. Our local IK action and link-origin
commands fix those issues. All six joint perturbation checks passed; maximum
translational Jacobian discrepancy dropped from 0.10324 to 0.000133 m/rad.

The accepted trajectory pitches the fingers downward, sweeps out and back,
then retraces its approach home. Direct-return trajectories failed the motion
gate even after slowing them; retain those attempts only as diagnostics.

Capture now uses one camera, disables the redundant recorder, renders at the
final physics substep, detects resets, measures motion, and rejects bad sweeps
without publishing a valid manifest. Python errors are printed and return
nonzero before Kit shutdown can mask them. The pose runner records operation,
candidate count, timing and input metadata hashes. New analysis and plotting
entry points summarize motion, visibility, pose error and timing.

## Next work

1. Preserve both accepted controls and add explicit registration/recovery
   trials. Normal FoundationPose tracking uses one pose; candidate pruning
   affects the 252-candidate registration search.
2. Define an effector-aware pruning rule with a valid source of constraints.
   In this sequence the gripper occludes a free bottle; a constant
   object-to-effector transform is not valid. Use robot geometry, or create
   a separately verified grasped-object experiment.
3. Implement and ablate pruning in this repository. Ground-truth object
   transforms must remain evaluation-only.

Candidate pruning has not yet been implemented. The dynamic-control milestone
is complete; no long-running simulator or inference job is needed to resume.

## Preservation notes

The shared ROBOTIS Lab checkout has pre-existing user edits; do not reset it.
It and the upstream FoundationPose source were not edited in this session.
Generated captures/results and pretrained assets remain ignored. The selected
results plot is under `docs/assets/isaac_omy_dynamic_control.png`.
