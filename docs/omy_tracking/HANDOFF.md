# OMY sample handoff

**45/45 accepted capture sequences: 36 train, 9 validation.**
Use `outputs/omy_pilot/dataset`, which contains only the final selections.
[Full results and all video links](PILOT_RESULTS.md) ·
[80.4-second representative MP4](../../outputs/omy_pilot/pilot_demo.mp4).

The final cohort independently passes finite-state/joint-limit checks, physical
task checks, RGB-D and geometry alignment, visibility, model equivalence,
reader isolation, parent/split consistency, and MP4 decoding/frame counts.

## Representative sequences

| Sequence | Frames | Seconds | Visibility range | Videos |
|---|---:|---:|---:|---|
| box_A_00 | 240 | 8.00 | 0.196–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_A_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_A_00/validation/geometry_overlay.mp4) |
| box_B_00 | 300 | 10.00 | 0.400–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_B_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_B_00/validation/geometry_overlay.mp4) |
| box_C_00 | 257 | 8.57 | 0.000–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_C_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_C_00/validation/geometry_overlay.mp4) |
| cylinder_A_00 | 240 | 8.00 | 0.265–1.000 | [RGB](../../outputs/omy_pilot/dataset/cylinder_A_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_A_00/validation/geometry_overlay.mp4) |
| cylinder_B_00 | 300 | 10.00 | 0.380–1.000 | [RGB](../../outputs/omy_pilot/dataset/cylinder_B_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_B_00/validation/geometry_overlay.mp4) |
| cylinder_C_00 | 260 | 8.67 | 0.000–1.002 | [RGB](../../outputs/omy_pilot/dataset/cylinder_C_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_C_00/validation/geometry_overlay.mp4) |
| asymmetric_A_00 | 240 | 8.00 | 0.325–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_A_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_A_00/validation/geometry_overlay.mp4) |
| asymmetric_B_00 | 300 | 10.00 | 0.465–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_B_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_B_00/validation/geometry_overlay.mp4) |
| asymmetric_C_00 | 275 | 9.17 | 0.107–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_C_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_C_00/validation/geometry_overlay.mp4) |

A is clear → noncontact robot occlusion → clear. B physically grasps, lifts,
holds, translates and rotates. C starts already held, places, releases and
retreats. Its first second is partially visible (at least the declared 40%
threshold); actual FoundationPose initialization remains untested.

## Portable reader

The clean export includes `reader/requirements.txt` and the reader/surface/FK
modules. The simulator installation is not required to load these observations.

```python
import sys
sys.path.insert(0, "outputs/omy_pilot/dataset/reader")
from read_omy_tracking_sample import read_tracking_input

# Initialize frame 0 externally using the CAD and a declared mask protocol.
# estimated_T_camera_object_0 is that estimated pose, not a GT label.
sample = read_tracking_input(
    "outputs/omy_pilot/dataset/cylinder_B_00",
    index=1,
    previous_estimated_pose=estimated_T_camera_object_0,
)
```

```python
from omy_robot_surface import canonical_surface_points, robot_surface_pair
canonical = canonical_surface_points(sample["robot_geometry"], points_per_link=1024, seed=0)
# Reuse these canonical points for subsequent frames.
robot_features = robot_surface_pair(sample, canonical)
```

The reader supplies current RGB-D, previous estimated object pose, current and
previous measured arm/gripper states, velocities, calibration, canonical robot
meshes/joint frames and textured object CAD. It does not open privileged
`frames.jsonl` or `validation/` files. `oracle_mask=True` is a separately labelled
oracle-segmentation comparison; use the same protocol for all compared methods.
Do not feed contact, phase, grasp-success or object-GT labels to the tracker.

Depth is uint16 optical-axis millimetres, zero invalid; the reader converts it
to float metres. Joints use radians and timestamps simulated seconds. Camera
axes are OpenCV (+X right, +Y down, +Z forward). Transforms use column vectors:
T_A_B maps B into A. `previous_robot_state.json` supplies the state before image 0.
Object OBJ coordinates are in the target root frame, not the centre of mass.
Robot link geometry uses body-local origins, reproduced by the authored joint
inventory and measured joint order. Reuse the same surface samples across time.

## Selection and provenance

`dataset_manifest.json` lists all 45 entries. Each sequence has original RGB,
depth, masks, model/robot geometry, calibration, measured observations,
privileged labels, validation evidence, and RGB/overlay MP4s. Pilot selection is
recorded in `validation/pilot_acceptance.json`; the immutable technical report
predates selection and may retain `accepted_pilot_sequence: false`.

Ten initial C clips were withdrawn after a passive-finger joint-limit defect was
found. The corrected low-grasp release freezes the control reference, opens
smoothly, and lifts only after robot contact clears while table support remains.
All ten replacements pass the added postflight check. Valid earlier B clips were
retained, so replacement C clips have their own physical parent groups while
preserving the variant's split. No physical parent crosses train/validation.

Earlier handoff directories and withdrawn selections are preserved as history;
they are not the authoritative final dataset. Use the clean `dataset/` folder
and current index. Checksums are in `outputs/omy_pilot/accepted_checksums.sha256`.

The user explicitly authorized proceeding while partner format review was
pending (`configs/omy_tracking/review_decision_20261113.json`). Partner loading
confirmation, FoundationPose initialization and tracking accuracy have not been
claimed. No 720-sequence main dataset was generated.
