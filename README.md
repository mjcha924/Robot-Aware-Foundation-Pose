# Effector-Aware FoundationPose

Research workspace for adding robot end-effector context to
[FoundationPose](https://github.com/NVlabs/FoundationPose). The first milestone
is deliberately smaller: reproduce the unchanged pretrained, model-based
FoundationPose demo before implementing or evaluating any method changes.

## Current state

Setup is in progress. See [`SETUP_STATUS.md`](SETUP_STATUS.md) for the exact
checkpoint, machine prerequisites, and next command to run. The upstream
FoundationPose source is pinned as a Git submodule under
`third_party/FoundationPose`.

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

## Clone

```bash
git clone --recurse-submodules <repository-url>
cd effector-aware-foundationpose
```

For an existing clone, initialize the pinned dependency with:

```bash
git submodule update --init --recursive
```

## Licensing and data

FoundationPose is governed by its own NVIDIA license in the submodule. In
particular, review its research/evaluation and redistribution restrictions
before use. Pretrained weights, demo data, simulator exports, and generated
outputs must remain outside Git.
