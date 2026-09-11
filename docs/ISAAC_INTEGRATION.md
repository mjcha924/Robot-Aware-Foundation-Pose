# Isaac/OMY integration checkpoint

Last verified: 2026-09-11 (Asia/Seoul)

## Local scene selected

The capture adapter targets the existing ROBOTIS Lab task
`RobotisLab-Real-Pick-Place-Bottle-OMY-v0` at commit
`e32b122d192c2db7fe52cfd3ece74c07f6a418a6`. That task already provides the
required semantic pieces:

- OMY robot: `source/robotis_lab/data/robots/OMY/OMY.usd`
- target object: `source/robotis_lab/data/object/plastic_bottle.usd`
- top and wrist pinhole cameras at 848 x 480
- end-effector control frame: `OMY/link6` with offset `[0, -0.248, 0]` metres

The ROBOTIS Lab worktree had unrelated local modifications when inspected. The
adapter only imports it and does not edit or commit anything there.

## Added entry points

Capture ten stable frames from the top camera:

```bash
./scripts/run_omy_isaac_capture.sh
```

The capture script adds depth and target-object semantic segmentation to the
selected camera, saves RGB/depth/masks and world transforms, and extracts the
visible bottle geometry from the USD stage as an OBJ in the rigid object's
frame. Its output is validated with:

```bash
python3 scripts/validate_isaac_export.py data/isaac_exports/omy_bottle_short
```

Run FoundationPose on a valid export:

```bash
./scripts/run_isaac_foundationpose.sh \
  data/isaac_exports/omy_bottle_short \
  --output /workspace/outputs/omy_bottle_short \
  --save-vis
```

The runner performs registration on the first mask, tracks later RGB-D frames,
and writes both `T_camera_object` and `T_effector_object`. It converts the raw
mesh frame through `T_object_mesh` before composing robot transforms.

## Verification completed

- Six dependency-free unit tests pass: three export-validator tests and three
  rigid-transform tests.
- Python compilation and Bash syntax checks pass.
- A three-frame contract fixture made from the already-installed mustard
  sequence passed the export validator.
- The new contract runner completed real pretrained registration and tracking
  for all three frames in the official FoundationPose container.
- It wrote three camera poses, three effector-relative poses, JSONL results,
  and three visually aligned overlays under `outputs/isaac_contract_smoke/`.

The temporary YCB smoke export and all inference results are ignored by Git.

## Current simulator blocker

The installed stack is Isaac Sim 5.1.0.0, Isaac Lab 2.3.2, driver 595.91.07,
and an RTX 3070. The simulator detects the GPU, but both a minimal launch and
Isaac Lab's unchanged `run_usd_camera.py --headless --enable_cameras` crash in
`librtx.scenedb.plugin.so` before scene code runs. This reproduces a
[reported Isaac Sim 5.1 failure on the 595 driver
branch](https://github.com/isaac-sim/IsaacLab/issues/6785). NVIDIA's
[current 5.1 documentation](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_workstation.html)
also marks that release unsupported in favor of newer versions.

No driver, kernel, Isaac installation, or ROBOTIS Lab source was changed. The
capture code is ready but cannot be runtime-validated until the renderer stack
is moved to a compatible Isaac Sim/driver combination.

The existing `env_isaaclab` also has package-version conflicts reported by
`pip check` (including Isaac Sim's `packaging==23.0`/`numpy==1.26.0` pins and a
mismatched TorchAudio build). Those were left untouched because repairing the
shared environment should be done together with the renderer-version decision.
