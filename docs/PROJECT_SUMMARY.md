# EA-FoundationPose project summary

Last updated: 2026-09-21 (Asia/Seoul)

## Latest milestone

The 192-frame OMY dynamic/occlusion control is validated end to end. It
contains six fully hidden frames; unchanged FoundationPose reaches 106.435 mm
maximum translation error during occlusion and returns to 8.690 mm by frame
118. The capture now corrects the PhysX COM/link-origin Jacobian mismatch,
synchronizes image rendering with poses, checks commanded robot motion, and
reports failures reliably. All 19 offline tests pass. Full details and
reproduction commands are in [`ISAAC_DYNAMIC_CONTROL.md`](ISAAC_DYNAMIC_CONTROL.md).

This checkpoint packages the validated September 21 dynamic-control milestone.
Experimental robot-geometry export work is excluded; effector-aware inference
is not implemented in this milestone. Historical Git checkpoints below describe
earlier milestones; use `git log` for the current publication history.

## Goal

Extend the model-based FoundationPose pipeline with robot end-effector context,
while preserving the unchanged pretrained pipeline as an experimental control.
The intended first EA feature is end-effector-aware pose-candidate pruning.

## Work completed

### Reproducible FoundationPose baseline

- Initialized this repository on `main` and pinned NVIDIA FoundationPose as a
  Git submodule at `a1b694b83e633c2cb6115b9063d940a687759392`.
- Verified the RTX 3070, driver 595.91.07, Docker 29.4.0, NVIDIA Container
  Toolkit 1.19.0, and CUDA container access.
- Pulled the official FoundationPose image, compiled the pinned `mycpp`
  extension, and verified the CUDA/PyTorch/NVDiffRast model path.
- Downloaded both pretrained checkpoint sets and independently verified their
  hashes against two public mirrors. Downloaded and validated the complete
  737-frame YCBInEOAT mustard sequence and official YCB mustard mesh.
- Ran unchanged upstream `run_demo.py` over all 737 frames with its default 252
  registration candidates, five registration refinements, and two tracking
  refinements. All frames completed without OOMs or inference errors.
- Repeated the run with visualization output, inspected representative first,
  middle, and last overlays, and numerically checked every output transform.
  The detailed provenance and hashes are in `docs/BASELINE.md`.

### Isaac/robot interface

- Defined contract version 1.0 for synchronized RGB8, uint16-mm depth, masks,
  intrinsics, object mesh, and world/camera/end-effector transforms.
- Added a strict JSON schema and dependency-free export validator. It checks
  transform rigidity, file synchronization, safe paths, image sizes and PNG
  encodings, intrinsics, frame counts, and required masks.
- Located and reused the existing ROBOTIS Lab OMY bottle pick-and-place task,
  including its top/wrist cameras, plastic bottle USD, and end-effector frame
  (`link6` plus `[0, -0.248, 0]` metre offset). The ROBOTIS Lab repository was
  not modified.
- Added an OMY capture entry point that configures RGB, aligned depth, semantic
  object masks, ground-truth poses, and USD-to-OBJ bottle extraction.
- Added a contract-to-FoundationPose runner. It validates input, registers on
  the initial mask, tracks later frames, applies `T_object_mesh`, and exports
  both `T_camera_object` and `T_effector_object`.
- Added dependency-free rigid-transform composition code and tests.

### Verification history

- The initial six unit tests passed.
- Python compilation, Bash syntax, JSON Schema validation, and Git whitespace
  checks pass.
- A three-frame contract fixture built from the installed mustard sequence
  passed validation and completed real pretrained registration/tracking in the
  FoundationPose GPU container.
- The smoke test produced three camera poses, three effector-relative poses,
  JSONL results, and three visually aligned overlays.
- After restoring driver 580.178.04, the isolated Isaac/OMY path captured ten
  valid 848 x 480 top-camera frames and FoundationPose processed all ten.
- Against Isaac ground truth, that control achieved 8.12 mm mean translation
  error and 1.20 degree mean rotation error. Representative overlays remained
  aligned; see `docs/ISAAC_CONTROL.md`.
- Added a dependency-free pose evaluator that reports per-frame and aggregate
  translation/rotation error in camera and end-effector coordinates. It
  reproduces the recorded control values; that checkpoint's 12 unit tests passed.
- Initially drafted an opt-in end-effector sweep; its first simulator run was
  stopped before completion. The corrected and validated 192-frame sweep now
  supersedes that draft (see Latest milestone above); all 19 tests pass.
- Downloaded data and generated outputs remain ignored by Git.

## Git state

The functional milestones preceding the handoff-only documentation commits are:

```text
8351de3 feat: add OMY Isaac capture adapter
ee6bd24 feat: define Isaac export contract
1858e97 docs: record passing FoundationPose baseline
299de39 chore: initialize EA-FoundationPose workspace
```

The upstream submodule remains unchanged. `origin` is configured as
`https://github.com/mjcha924/Effector-Aware-Foundation-Pose.git`. The remote's
initial placeholder history was integrated without discarding either history,
and `main` was originally pushed at merge commit `774c34f`.

## Current blocker

The native renderer crash is resolved: driver 580.178.04 consistently replaced
595.91.07, Docker sees the GPU, and the real camera capture completed. The host
RTX 3070 with 8 GB remains below NVIDIA's published RTX 4080/16 GB minimum, so
future scenes must stay conservative about environments, sensors, and VRAM.
The shared Isaac Conda environment also retains pre-existing dependency
conflicts and should not be used; the isolated ROBOTIS image is the validated
capture path.

Historical local logs provide a direct recovery lead: the same Isaac Sim 5.1
installation reached `app ready` and `Isaac Sim Full App is loaded` under driver
580.126.09 in March 2026. See `docs/ISAAC_CRASH_RECOVERY.md` for the evidence,
recovery procedure, and acceptance gates.

No shared-environment dependency or ROBOTIS Lab source was changed.

## Next steps

1. Keep the static and accepted dynamic controls fixed for comparison.
2. Add registration/recovery trials on the dynamic sequence, with explicit
   prior assumptions and no simulator-truth leakage.
3. Implement and ablate end-effector-aware candidate pruning without changing
   the pinned upstream FoundationPose submodule. Tracking already uses one
   pose, so pruning should be evaluated on registration/recovery searches.
