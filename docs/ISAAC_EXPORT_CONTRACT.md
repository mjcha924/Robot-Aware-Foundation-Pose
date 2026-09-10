# Isaac export contract

Contract version: `1.0`

This contract is the boundary between Isaac Sim capture and FoundationPose. It
keeps image/depth interpretation and robot transforms explicit so a successful
vision overlay cannot hide a unit or coordinate-frame mistake.

## Sequence layout

```text
<sequence>/
├── manifest.json
├── frames.jsonl
├── cam_K.txt
├── mesh/
│   └── object.obj
├── rgb/
│   ├── 000000.png
│   └── ...
├── depth/
│   ├── 000000.png
│   └── ...
└── masks/
    ├── 000000.png
    └── ...
```

Every frame ID must resolve to matching RGB and depth filenames. A mask is
required for the first frame. Later masks are optional when
`segmentation.initial_mask_only` is true, matching FoundationPose's
register-then-track workflow.

## Image and geometry rules

- RGB: 8-bit PNG, RGB or RGBA, with no resizing after capture.
- Depth: single-channel 16-bit PNG, aligned pixel-for-pixel with RGB.
- Stored depth unit: unsigned integer millimetres; zero means invalid.
- Mask: single-channel 8-bit PNG; zero is background and nonzero is object.
- Mesh vertices: metres, in the declared object frame.
- Camera: pinhole model with no unmodelled distortion.
- All RGB, depth, and mask images use the dimensions in `manifest.json`.

`cam_K.txt` contains the same row-major 3x3 intrinsic matrix as
`camera.K`. It is retained because upstream `YcbineoatReader` reads this file
directly.

## Coordinate conventions

Transforms use column vectors. `T_A_B` maps coordinates expressed in frame `B`
into frame `A`:

```text
p_A = T_A_B @ p_B
```

The camera frame is OpenCV: +X right, +Y down, +Z forward. Isaac/Usd poses must
be converted to this convention before export; never label an OpenGL/Usd camera
pose as `T_world_camera` without the axis conversion.

Each line of `frames.jsonl` contains:

- `frame_id`: filename stem shared by RGB, depth, and mask.
- `timestamp_s`: simulation time in seconds.
- `T_world_camera`: camera frame to world frame.
- `T_world_effector`: end-effector control frame to world frame.
- `T_world_object_gt`: optional simulation-only object ground truth.

FoundationPose returns `T_camera_object`. The end-effector-relative object pose
used by later EA logic is therefore:

```text
T_effector_object = inverse(T_world_effector)
                  @ T_world_camera
                  @ T_camera_object
```

`mesh.T_object_mesh` maps raw mesh coordinates into the object frame used by
ground truth and evaluation. It must be identity when the exported OBJ is
already expressed in that frame.

## Validation

Validate an export before running FoundationPose:

```bash
python3 scripts/validate_isaac_export.py data/isaac_exports/<sequence>
```

The validator has no third-party Python dependencies. It checks metadata,
matrix rigidity, safe relative paths, frame synchronization, PNG dimensions
and encodings, camera-intrinsic consistency, masks, and the mesh path.

The JSON metadata schema is in
[`../configs/isaac_export.schema.json`](../configs/isaac_export.schema.json),
with a concrete example in
[`../configs/examples/isaac_export_manifest.json`](../configs/examples/isaac_export_manifest.json).
