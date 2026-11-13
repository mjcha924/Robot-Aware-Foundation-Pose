# Robot-conditioned FoundationPose refiner — V1

Implemented on `feat/robot-conditioned-refiner`. Upstream is unchanged and pinned
by the existing submodule. This is an implementation, **not a measured pose
accuracy improvement**. No real OMY training data or CUDA runtime was available
in the authoring environment.

## Architecture

Frozen upstream `encodeA → encodeAB → pos_embed` produces visual tokens.
Two local PointNet++-style set-abstraction layers produce robot/object tokens;
a projection and 3D positional embedding map them to 512 dimensions.
Residual cross-attention (visual queries, robot keys/values) feeds the pretrained
translation/rotation heads. The residual scale starts at 0.01. The bypass path
preserves original inference exactly, subject to the CUDA parity gate below.

The tensor-only reference point backend introduces no additional custom CUDA
extension. It is intentionally small; benchmark sampling before optimizing.
Grouping uses masked radius neighborhoods and max pooling. Coordinates and
radii are normalized by object diameter; normals are rotated, not scaled.
Point channels: `[xyz(3), normal(3), velocity(3), is_robot, velocity_valid]`.
Object velocity is unknown and masked. Robot samples are fixed on each link.
Current and previous samples are expressed in the *same current camera frame*
before velocity calculation, then transformed to the hypothesis frame.

Current data uses **ideal simulation link transforms**, not noisy encoder FK.
No tactile measurements, contact labels or semantic robot masks enter the model.
All model geometry is in the raw mesh frame; `T_object_mesh` is explicitly
composed into training targets. CAD and initial pose conventions must agree.

## Why prepared visual-feature caches?

The visual encoder is frozen. Preparing features once avoids repeatedly rendering
identical perturbations during early training, and separates rendering failures
from learning failures. Cache generation runs on CUDA with the original
checkpoint/preprocessing. PointNet++, attention, and heads still train jointly.

This is a fixed set of pose perturbations, NOT online augmentation or temporal
backpropagation. Generate more perturbations/sequences for a larger experiment.
Never mix caches from different pretrained weights/configs. Validation uses
separate full sequences; the trainer rejects equal frame-file content hashes.
Hold out entire object IDs yourself for novel-object tests.

## CUDA environment and first gate

Use the repository's existing working FoundationPose GPU environment with its
weights. Do not replace its torch/CUDA stack to install this extension. Run from
repo root. Scripts import the pinned submodule automatically.

```bash
python scripts/check_robot_refiner_cuda.py
```

This checks original-vs-bypass outputs, cached head weights, upstream pose decoder
parity, and backward through the frozen heads into the robot branch. Rendering
is checked separately by cache preparation. V1 explicitly supports the original
`tracknet` + `axis_angle` config, without `use_normal`; unsupported configs fail.

## Prepare train and validation caches

Each export must pass `validate_isaac_export.py`, contain `robot_geometry`, object
GT, depth and RGB. Choose DIFFERENT sequences below. Paths are examples.

```bash
python scripts/prepare_robot_refiner.py data/isaac_exports/train_sequence \
  --output data/robot_refiner/train --stride 5 --seed 0
python scripts/prepare_robot_refiner.py data/isaac_exports/val_sequence \
  --output data/robot_refiner/val --stride 5 --seed 1
```

Use multiple sequence positional arguments to combine exports. Defaults use
10 mm translation and 10 degree rotation standard deviations. Initial pose GT
is used only to construct supervised perturbations. Each sample stores frozen
visual tokens, hypothesis-relative point features, hypothesis, target and CAD.
The manifest records original weight SHA-256, upstream commit, config and seed.
Output folders must not already exist; existing caches/runs are never overwritten.

Optional `manifest.mesh.symmetries_mesh` is a list of 4x4 symmetry transforms in
raw mesh coordinates (including identity). If absent, identity is used; do NOT
call this symmetry-aware evaluation for a symmetric object until supplied.
The loss minimizes mean corresponding CAD-point distance over supplied symmetries.
No tactile attraction or penetration losses are used.

## Train

```bash
python scripts/train_robot_refiner.py \
  --train data/robot_refiner/train --val data/robot_refiner/val \
  --output outputs/robot_refiner_motion --mode motion --epochs 20 --batch-size 4
```

Run the same caches with `--mode visual` and `--mode geometry` in different output
folders for ablations. Geometry mode zeros velocity AND its validity channel.
Default first epoch freezes pretrained heads; subsequent epochs fine-tune heads
at 1e-5 while the new branch uses 1e-4. Visual-only trains heads immediately.
FP32 first; do not put rasterization/pose geometry into BF16 without validation.

Outputs: `run.json`, `metrics.jsonl`, `best.pt`, `last.pt`. Resume into a NEW folder:

```bash
python scripts/train_robot_refiner.py \
  --train data/robot_refiner/train --val data/robot_refiner/val \
  --output outputs/robot_refiner_resumed --resume outputs/robot_refiner_motion/last.pt \
  --epochs 30
```

Resume restores model, optimizer, epoch, torch CPU/CUDA RNG and checks provenance.
Use the same batch size and settings to preserve the intended experiment.

## Sequence rollout

Generate the initial estimate using original FoundationPose registration and
save it as a 4x4 NumPy array **T_camera_raw_mesh**. Do not use object GT for a normal
tracking comparison. If using oracle initialization, label it and provide it
identically to every method. A centered-mesh estimate must be converted back to
the raw mesh frame first (the normal public estimator return does this).

```bash
python scripts/evaluate_robot_tracker.py data/isaac_exports/test_sequence \
  --initial-pose data/initial_pose.npy \
  --checkpoint outputs/robot_refiner_motion/best.pt \
  --output outputs/robot_refiner_rollout
```

Omit `--checkpoint` for the original visual-refiner control. This runner shares
the same renderer/preprocessing across methods; it is not a claim of exact parity
with every preprocessing step of upstream `track_one`. It rebuilds robot/object
features after every refinement, and propagates predictions, never GT. Camera
motion is compensated. GT is read only AFTER prediction to report surface error.
All frames, including full occlusions, are retained. No automatic recovery or
confidence head is implemented. Initialization remains an external step.

## Verification and limits

```bash
python -m pytest tests/test_robot_conditioned_pose.py -q
python scripts/check_robot_refiner_cuda.py --checkpoint outputs/robot_refiner_motion/best.pt
```

Local tests cover a small surrogate visual encoder's bypass parity, gradient flow,
frozen normalization, checkpoint round-trip, coordinates/velocity, sparse neighbors,
symmetry loss, zero-angle gradients, tiny-set optimization, and trainer save/resume.
These tests do NOT establish GPU compatibility or real FoundationPose performance.
Run the real CUDA gate and a small OMY cache/training/rollout before large jobs.

## Sources and implementation choices

- FoundationPose original pretrained encoder/heads, rendering and pose convention:
  https://github.com/NVlabs/FoundationPose (existing submodule license applies).
- V-HOP training-flow and geometry-fusion reference:
  https://github.com/brown-ivl/v-hop . No V-HOP source is vendored.
- PointNet++ hierarchical local features: Qi et al., NeurIPS 2017,
  https://arxiv.org/abs/1706.02413 . Small tensor-only abstraction independently
  implemented here; it is not a reproduction of V-HOP's global pooled encoder.

Known next experiments: camera/projected positional features, normalized radius
sensitivity, shuffled robot-state controls, on-policy perturbations, broader
calibration noise and actual encoder/FK observations. None is claimed completed.

Implementation verification (local, no CUDA): `54 passed, 1 skipped` for the
repository test suite. Syntax compilation passed. The skipped existing test
requires CUDA. Surface diameter uses a bounded 1,000-vertex sample; it is an
approximation and shared by this implementation's training and inference paths.
The renderer bridge restores upstream's global default-tensor-type side effect.
