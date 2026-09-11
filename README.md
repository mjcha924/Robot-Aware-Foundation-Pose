# Effector-Aware FoundationPose

Research workspace for adding robot end-effector context to
[FoundationPose](https://github.com/NVlabs/FoundationPose). The first milestone
is deliberately smaller: reproduce the unchanged pretrained, model-based
FoundationPose demo before implementing or evaluating any method changes.

## Current state

The unchanged, pretrained model-based FoundationPose demo has passed on the
project machine's RTX 3070. It produced poses for all 737 frames of the mustard
bottle sequence. See [`docs/BASELINE.md`](docs/BASELINE.md) for the reproducible
run record and [`SETUP_STATUS.md`](SETUP_STATUS.md) for the current project
checkpoint.

The upstream FoundationPose source is pinned as a Git submodule under
`third_party/FoundationPose`; downloaded assets and generated results are kept
outside Git.

## Repository layout

- `configs/`: experiment and runtime configuration
- `data/isaac_exports/`: local simulator exports (not committed)
- `docs/`: design notes and handoffs
- `experiments/`: experiment definitions and summaries
- `outputs/`: generated results (not committed)
- `scripts/`: setup, conversion, and evaluation entry points
- `src/foundationpose_adapter/`: integration with upstream FoundationPose
- `src/calibration/`: camera and robot-frame calibration
- `src/masks/`: segmentation-mask preparation
- `src/urdf_render/`: URDF-based geometry rendering
- `src/candidate_pruning/`: end-effector-aware pose candidate filtering
- `src/evaluation/`: metrics and evaluation support

Isaac Sim captures must follow the versioned
[`docs/ISAAC_EXPORT_CONTRACT.md`](docs/ISAAC_EXPORT_CONTRACT.md). Validate a
capture before inference with:

```bash
python3 scripts/validate_isaac_export.py data/isaac_exports/<sequence>
```

The OMY bottle capture and contract-to-FoundationPose entry points are now in
place. Their verification state and the installed renderer compatibility
blocker are recorded in
[`docs/ISAAC_INTEGRATION.md`](docs/ISAAC_INTEGRATION.md).

For a single consolidated record of completed work, Git checkpoints, blockers,
and prioritized next steps, see
[`docs/PROJECT_SUMMARY.md`](docs/PROJECT_SUMMARY.md).

## Clone

```bash
git clone --recurse-submodules <repository-url>
cd effector-aware-foundationpose
```

For an existing clone, initialize the pinned dependency with:

```bash
git submodule update --init --recursive
```

After installing the upstream image, weights, demo data, and native extension
described in the baseline record, reproduce the unchanged demo with:

```bash
./scripts/run_foundationpose_baseline.sh
```

## Licensing and data

FoundationPose is governed by its own NVIDIA license in the submodule. In
particular, review its research/evaluation and redistribution restrictions
before use. Pretrained weights, demo data, simulator exports, and generated
outputs must remain outside Git.
