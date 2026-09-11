# Isaac/OMY static control

Validated: 2026-09-11 (Asia/Seoul)

## Outcome

The first real Isaac/OMY-to-FoundationPose control passed end to end after the
host returned from NVIDIA driver 595.91.07 to 580.178.04.

- Running kernel: 6.8.0-138-generic
- GPU: NVIDIA GeForce RTX 3070, 8 GB
- Host and container driver: 580.178.04
- Isaac image: `robotis/robotis-lab:latest`
- FoundationPose image: `foundationpose:latest`
- Camera: `cam_top`, 848 x 480
- Frames: 10, timestamps 0.7 through 1.6 seconds
- Export: `data/isaac_exports/omy_bottle_short` (ignored)
- Results: `outputs/omy_bottle_short` (ignored)

The capture contains synchronized RGB8, uint16-mm depth, binary object masks,
camera intrinsics, world/camera/end-effector/object transforms, and a bottle OBJ
with 12,502 vertices and 25,000 triangles. The strict export validator passed.
Every object-mask pixel had valid depth; masks contained 10,312 to 10,469 pixels
with median target depth of 431 to 432 mm.

## FoundationPose accuracy

FoundationPose registered frame `000000` with the unchanged 252 candidates and
tracked the remaining nine frames. Errors compare `T_camera_object` directly
against the synchronized Isaac ground truth:

| Metric | Mean | Median | Maximum |
| --- | ---: | ---: | ---: |
| Translation | 8.117 mm | 8.102 mm | 8.288 mm |
| Rotation | 1.196 degrees | 1.322 degrees | 1.522 degrees |

First, middle, and last overlays were inspected and remained visually aligned
with the bottle. All ten camera-relative and end-effector-relative output
matrices were written successfully.

Artifact hashes:

```text
1e28a0eab8f797671e9a92ca927a24cc2ff30f473b5169d37297608577238f4e  mesh/object.obj
99f4c454374541d6cb3463b51c4d54800ba7f9859325d31a33415b7ff8837ccc  manifest.json
9c2a64c88824591987e0e8d225c9eac6dbecb524f1afef2e003d8e69f3853f0e  poses.jsonl
```

## Commands

```bash
./scripts/run_omy_isaac_capture_docker.sh --overwrite
python3 scripts/validate_isaac_export.py data/isaac_exports/omy_bottle_short
./scripts/run_isaac_foundationpose.sh \
  data/isaac_exports/omy_bottle_short \
  --output /workspace/outputs/omy_bottle_short \
  --save-vis \
  --overwrite
```

## Limitation and next experiment

This is a short, nearly static sequence intended to prove renderer recovery,
sensor export, coordinate composition, mesh handling, and inference plumbing.
It is not sufficient to measure robustness under large robot/object motion or
occlusion. The next control should deliberately move the end effector through
partial bottle occlusions before candidate pruning is implemented and ablated.
