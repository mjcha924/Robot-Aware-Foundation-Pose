# EA-FoundationPose project summary

Last updated: 2026-09-11 (Asia/Seoul)

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

### Verification

- All six unit tests pass.
- Python compilation, Bash syntax, JSON Schema validation, and Git whitespace
  checks pass.
- A three-frame contract fixture built from the installed mustard sequence
  passed validation and completed real pretrained registration/tracking in the
  FoundationPose GPU container.
- The smoke test produced three camera poses, three effector-relative poses,
  JSONL results, and three visually aligned overlays.
- Downloaded data and generated outputs remain ignored by Git.

## Git state

The functional milestones preceding the handoff-only documentation commits are:

```text
8351de3 feat: add OMY Isaac capture adapter
ee6bd24 feat: define Isaac export contract
1858e97 docs: record passing FoundationPose baseline
299de39 chore: initialize EA-FoundationPose workspace
```

The worktree and submodule are clean. `origin` is configured as
`https://github.com/mjcha924/Effector-Aware-Foundation-Pose.git`. The initial
push is pending because the host has no GitHub CLI, HTTPS token, or SSH key.

## Current blocker

The installed Isaac Sim 5.1.0.0 renderer crashes in
`librtx.scenedb.plugin.so` before project code executes. The same crash occurs
with Isaac Lab's unchanged headless camera tutorial. The host has driver
595.91.07, while Isaac Sim 5.1's published tested Linux driver is 580.65.06;
the 5.1 documentation now marks the release unsupported. Its published minimum
GPU is also an RTX 4080 with 16 GB VRAM, above this host's RTX 3070 with 8 GB,
so even a driver-compatible 5.1 setup would remain outside NVIDIA's supported
hardware envelope. The shared Isaac environment also has pre-existing
dependency conflicts reported by `pip check`.

Historical local logs provide a direct recovery lead: the same Isaac Sim 5.1
installation reached `app ready` and `Isaac Sim Full App is loaded` under driver
580.126.09 in March 2026. See `docs/ISAAC_CRASH_RECOVERY.md` for the evidence,
recovery procedure, and acceptance gates.

No driver, kernel, simulator package, or shared-environment dependency was
changed during this work.

## Next steps

1. Restore the previously working renderer family: move the host from driver
   595.91.07 back to the 580 branch, then use
   `scripts/run_omy_isaac_capture_docker.sh` with ROBOTIS Lab's pinned Isaac Sim
   5.1/Isaac Lab 2.3.x image. A separate Isaac Sim 6.0.1/Isaac Lab 3.0 environment
   is the longer-term option but requires checking and likely migrating ROBOTIS
   Lab APIs.
2. Re-run the unchanged Isaac Lab camera tutorial as the renderer gate.
3. Run `scripts/run_omy_isaac_capture_docker.sh`, then validate the generated
   sequence with `scripts/validate_isaac_export.py`.
4. Run `scripts/run_isaac_foundationpose.sh` on that capture and verify RGB-D,
   mesh, camera, object, and end-effector overlays.
5. Freeze that run as the Isaac control, define quantitative pose/occlusion
   metrics, and only then implement end-effector-aware candidate pruning.
6. Authenticate GitHub and push `main` to the configured `origin`. Do not push
   weights, datasets, or outputs.
