# FoundationPose baseline

Completed: 2026-09-11 (Asia/Seoul)

## Result

The unchanged upstream model-based demo completed successfully on all 737
frames of the YCBInEOAT `mustard0` sequence. Registration used the upstream
defaults of 252 candidates and five refinement iterations; tracking used two
refinement iterations. No out-of-memory, CUDA, display, or inference error was
observed.

Generated local artifacts (ignored by Git):

- `outputs/foundationpose_baseline/ob_in_cam/`: 737 pose matrices
- `outputs/foundationpose_baseline/track_vis/`: 737 overlay images
- `outputs/foundationpose_baseline.log`: complete visualization-run log
- `outputs/foundationpose_baseline.mp4`: 30 FPS review video

The first, middle, and last overlays were inspected. The rendered bounding box
and coordinate axes remain aligned to the bottle through robot-gripper
occlusion. All output matrices are finite rigid transforms. Their rotation
determinants range from 0.999994 to 1.000001; median frame-to-frame translation
is 0.38 mm and the maximum is 16.9 mm.

## Reproducible environment

- GPU: NVIDIA GeForce RTX 3070 (8 GiB)
- NVIDIA driver: 595.91.07
- Host: Ubuntu 22.04.5, kernel 6.8.0-111-generic
- Docker image: `wenbowen123/foundationpose:latest`
- Image digest: `sha256:22837f81c0cfc1906b96daa344f8e80919c7619b816fcab487a024f1f566c215`
- Image ID: `sha256:a0eec34f4b62a13588464ef36086f2f58fc39a36e3265ab06992c573f3a1b218`
- Image size: 20,150,866,548 bytes
- Container Python: 3.8.18
- Container PyTorch: 2.0.0+cu118
- FoundationPose commit: `a1b694b83e633c2cb6115b9063d940a687759392`

The pinned checkout's `mycpp` extension was built successfully with upstream
`build_all.sh`. Kaolin 0.15.0 was installed in editable mode inside the image.
`check_env.py --demo-data` passed every core import, native-extension, weight,
demo-path, and CUDA check.

## Asset provenance and integrity

The official Google Drive folders were temporarily quota-limited. The two
required checkpoint directories were therefore obtained from the public
`gpue/foundationpose-weights` Hugging Face mirror and cross-checked byte for
byte against a separate public FoundationPose bundle:

| File | SHA-256 |
| --- | --- |
| `2023-10-28-18-33-37/config.yml` | `28a6ba94a33230ee5fc3c51939486281578b0972542bd9e38ca6123e75605686` |
| `2023-10-28-18-33-37/model_best.pth` | `774700586ddc435d408fc01c9809c43e151232936369dfbea0f0f964ba471d60` |
| `2024-01-11-20-02-45/config.yml` | `a79db4de3b95885dd5ae86833b37b8698a75dad81e87d1086cd50b2fcd8dda3f` |
| `2024-01-11-20-02-45/model_best.pth` | `81924d384bf5c26c646ee4783104982ae3d1e049c181c36641b6a7aeae494c26` |

The demo sequence came from the authoritative Rutgers YCBInEOAT archive as the
standalone `mustard0.tar.gz`. Its exact 2,478,110,464-byte archive passed gzip
integrity validation before extraction. The scene contains 737 RGB frames and
737 annotated poses. The initial object mask supplied with the sequence was
copied to `masks/<first-frame>.png`, the layout expected by unchanged
`run_demo.py`.

The textured mustard-bottle mesh came from the official YCB Object and Model
Set's Google 16k archive. `textured.obj` is also exposed as
`textured_simple.obj` at the default demo path. YCB data is licensed CC BY 4.0.

FoundationPose code and weights remain subject to NVIDIA's license. Do not
commit or redistribute the checkpoints or demo data.

## Run

The exact default baseline was executed as:

```bash
cd third_party/FoundationPose
python run_demo.py
```

from inside the GPU-enabled `foundationpose:latest` container. From the project
root, the wrapper below performs the same run and forwards any optional
arguments to the upstream script:

```bash
./scripts/run_foundationpose_baseline.sh
```

For saved overlays, use an ignored output directory:

```bash
./scripts/run_foundationpose_baseline.sh \
  --debug 2 \
  --debug_dir /workspace/outputs/foundationpose_baseline
```
