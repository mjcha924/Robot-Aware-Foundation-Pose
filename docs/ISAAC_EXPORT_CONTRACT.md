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
- `timestamp_s`: simulation time in seconds, strictly increasing across the sequence.
- `T_world_camera`: camera frame to world frame.
- `T_world_effector`: end-effector control frame to world frame.
- `T_world_object_gt`: optional simulation-only object ground truth.

Optional capture diagnostics are `visible_mask_pixels` (non-negative integer),
`motion_progress` (trajectory progress from 0 to 1), and
`effector_command_error_m` (distance between commanded and measured tool
positions). Visible mask area is not an amodal occlusion fraction: object
motion also changes the projected area. Later masks may be empty during full
occlusion; registration still requires a non-empty first mask.

The OMY exporter renders on the final physics substep of each environment
step and rejects environment resets during capture. A valid file layout alone
does not prove that the robot followed its commanded trajectory. Audit the
exported motion and visibility with:

```bash
python3 scripts/analyze_isaac_sequence.py data/isaac_exports/<sequence> \
  --poses outputs/<run>/poses.jsonl --json-out outputs/<run>/sequence_metrics.json
```

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

## Optional robot-geometry extension (version 1)

With `--export-robot-geometry`, `manifest.json` contains a top-level
`robot_geometry` object. This is an optional extension to contract 1.0; earlier
captures without robot geometry remain valid.

- `version: 1`, `units: "meter"`, `pose_convention: "T_world_link_origin"`.
- `pose_source` states the provenance; current captures use ideal simulated
  link state, not a noisy encoder/FK estimate.
- `links` lists unique `name`, relative OBJ `path`, `sha256`, `vertex_count`,
  and `triangle_count` for each rigid link, including arm, wrist, and fingers.
- OBJ vertices are in that link's origin frame. Files contain geometry-only
  `v` and triangular `f` records with positive one-based indices. Invisible,
  proxy, and guide meshes are excluded, as are descendants of other rigid links.
- Every frame has `T_world_robot_links`, keyed by exactly those link names.
  Render with `T_camera_link = inverse(T_world_camera) @ T_world_robot_links[name]`.
- Optional `validation_mask_dir: "robot_masks"` declares synchronized binary
  Isaac semantic masks for **audit only**. Do not use these as inference inputs.

The validator checks link completeness, transform rigidity, mesh hashes and
counts, finite vertices, triangle indices, path containment (including symlinks),
and audit-mask headers. File validation alone does not prove correct alignment:
run the GPU projection audit described in [ROBOT_GEOMETRY.md](ROBOT_GEOMETRY.md).

Camera poses must be refreshed after reset randomization and on every frame.
The exporter now sets `update_latest_camera_pose=True`. Older captures made
with the default False have a cached-pose calibration caveat; retain them as
historical controls, not as the corrected reference for geometry-aware work.

The schema also permits optional producer metadata: a camera name, mesh source
and triangle/vertex counts, and a top-level `source` object. Consumers must not
derive geometry or coordinate conventions from those provenance fields.

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
