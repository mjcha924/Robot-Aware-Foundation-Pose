# EA-FoundationPose setup status

Last updated: 2026-09-22 (Asia/Seoul)

## Current checkpoint

- Project workspace: `/home/mjcha/effector-aware-foundationpose`
- Existing FoundationPose checkout: `third_party/FoundationPose`
- Pinned upstream commit: `a1b694b83e633c2cb6115b9063d940a687759392`
- Physical GPU: NVIDIA GeForce RTX 3070 (not the RTX 3060 initially assumed)
- Ubuntu 22.04.5, running kernel 6.8.0-138-generic
- NVIDIA driver/DKMS 580.178.04 is installed and loaded consistently
- Docker 29.4.0 and NVIDIA Container Toolkit 1.19.0 are installed
- System CUDA compiler (`nvcc`) is absent
- About 281 GiB disk space and 31 GiB RAM were available
- Both required FoundationPose checkpoint sets are downloaded and verified
- The 737-frame `mustard0` RGB-D demo and textured mesh are installed locally
- Opt-in robot-occlusion-aware registration filtering is implemented; default
  inference remains unchanged. See `docs/CANDIDATE_FILTERING.md` for evaluation.
- The official FoundationPose image is pulled and tagged `foundationpose:latest`
- The pinned checkout's native `mycpp` extension is built
- The unchanged pretrained model-based demo passed on all 737 frames
- The native Isaac Sim 5.1/driver-595 `librtx.scenedb.plugin.so` crash was fixed
  by restoring the host to the 580 driver branch
- The isolated ROBOTIS Lab Isaac image captured and validated ten OMY frames
- FoundationPose processed the ten-frame OMY capture successfully with mean
  errors of 8.12 mm translation and 1.20 degrees rotation against Isaac truth
- A dependency-free pose evaluator reproduces those control metrics in both
  camera and end-effector coordinates; all 49 tests pass in the GPU environment
  (40 pass locally without PyTorch; nine dependency-specific tests skip)
- A 192-frame dynamic OMY control now passes motion and export validation,
  with six fully occluded frames. FoundationPose completes all frames: mean
  errors 12.347 mm / 4.343 degrees; maximum 106.435 mm / 34.207 degrees.
- Corrected the simulator COM/link-origin Jacobian mismatch, tool offsets,
  capture synchronization, camera/recorder overhead, and hidden failure exits.
  See `docs/ISAAC_DYNAMIC_CONTROL.md` for the verified diagnosis and results.
- Added opt-in robot-link mesh/pose export, strict validation, and a GPU
  projection audit. The audit exposed a cached camera pose after randomization;
  new captures use live camera poses. Earlier pose-error figures above carry
  this calibration caveat. See `docs/ROBOT_GEOMETRY.md` for the new checkpoint.
- Corrected geometry: all 192 frames / 11 links pass projection validation
  (minimum IoU 0.98357; worst depth p95 error 0.477 mm). The unchanged estimator
  completes the new capture: overall mean 5.332 mm / 4.671 degrees; visible-area
  groups average 0.937 mm versus 36.098 mm translation error.
- Candidate filtering completed 300 benchmark records across five methods and
  a separate 192-frame filtered-registration/tracking integration run. EA and
  original both succeed in 30/45 observable trials; EA median registration is
  0.680 s versus 2.327 s. Geometry-only also gets 30/45 and random gets 31/45:
  no robot-specific accuracy gain is established on this single sequence.

## Repository progress

- Initialized the project as a local Git repository on branch `main`
- Registered `third_party/FoundationPose` as a submodule at the pinned commit
- Added the minimal README, directory scaffold, and artifact exclusions
- Defined the versioned Isaac export contract and added a dependency-free
  validator with passing unit tests
- Added an OMY bottle capture entry point using the existing ROBOTIS Lab task
- Added a contract-to-FoundationPose runner that emits camera- and
  end-effector-relative poses
- Passed an end-to-end three-frame contract smoke test with the pretrained
  FoundationPose models
- Passed the first real ten-frame Isaac/OMY control capture and FoundationPose
  run; see `docs/ISAAC_CONTROL.md`
- Downloaded weights, demo data, simulator exports, and generated outputs are
  excluded from Git
- Recovered the established local GitHub identity from existing repository
  history and used it only for this repository
- Maintains a documented local milestone history on `main`
- Configured `origin` as
  `https://github.com/mjcha924/Effector-Aware-Foundation-Pose.git`
- Installed checksum-verified GitHub CLI 2.100.0 under `~/.local/bin`
- Integrated the GitHub repository's initial history and continued pushing
  project milestones; local and remote reached `7ced941` before the final
  resume-handoff update

A consolidated history and execution roadmap is maintained in
`docs/PROJECT_SUMMARY.md`.

The authoritative current-session handoff is `docs/RESUME.md`.
`docs/RESUME_AFTER_REBOOT.md` is retained as historical crash-recovery context.

The Codex sandbox does not expose `/dev/nvidia*`, the Docker socket, or the
user's supplementary groups. The host gate was therefore rerun with host access
and passed on 2026-09-10.

## Decisions so far

1. First milestone is an unchanged pretrained, model-based FoundationPose demo.
2. The official Docker route is the smallest reliable starting path because
   upstream recommends it and local Conda would require installing CUDA plus
   compiling PyTorch3D and NVDiffRast.
3. Keep FoundationPose isolated as a pinned Git submodule in our own project.
4. Create a private GitHub repository for collaboration with the user's friend.
5. Do not begin Isaac Sim integration or candidate pruning until the baseline
   demo passes and later URDF/camera overlay alignment is trustworthy.

## Baseline passed

The host and container checks completed successfully:

```bash
cd /home/mjcha/effector-aware-foundationpose
nvidia-smi
id
docker info
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

The native and containerized checks both detected an NVIDIA GeForce RTX 3070
with driver 595.91.07. Docker Engine 29.4.0 is running, the user is in the
`docker` group, the NVIDIA runtime/CDI devices are registered, and the CUDA
12.4.1 container successfully ran `nvidia-smi`.

The unchanged `python run_demo.py` baseline then completed all 737 frames using
the default 252 pose candidates, five registration refinements, and two tracking
refinements. A second visualization-enabled run saved 737 overlays and poses
under `outputs/foundationpose_baseline/`; representative first, middle, and last
frames were visually aligned. See `docs/BASELINE.md` for provenance, hashes,
environment versions, and numerical validation.

## Next actions

1. Preserve both the ten-frame static control and the accepted 192-frame
   `omy_sweep_retrace_20260921` dynamic control. Other September 21 sweeps are
   diagnostic attempts; see the dynamic-control record before using them.
2. Define and implement candidate pruning for registration/recovery, where
   the 252-candidate search actually occurs. Normal tracking uses one pose.
   The current gripper is an occluder, not a rigid grasp: do not assume a
   fixed object-to-effector transform or use object ground truth as a prior.
3. Preserve the upstream baseline as the control; place all new method code in
   this repository rather than modifying the FoundationPose submodule.

## License warning

FoundationPose uses the NVIDIA Source Code License, including a non-commercial
research/evaluation limitation and redistribution conditions. Do not commit or
redistribute its downloaded pretrained weights or demo data.
