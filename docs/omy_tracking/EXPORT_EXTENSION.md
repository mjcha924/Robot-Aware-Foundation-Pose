# OMY tracking pilot export extension

Status: implementation and sample validation in progress; no accepted pilot yet.
This extends the existing Isaac export contract 1.0 rather than changing its
camera, image or transform units. The diagnostic layout is not the handoff format.

Each sequence retains `manifest.json`, `frames.jsonl`, `cam_K.txt`, `rgb/`,
`depth/`, `masks/`, and a textured `mesh/object.obj` with MTL and texture.
RGB is original RGB8 PNG; depth is optical-axis uint16 millimetres, zero invalid;
the reader converts depth to metres. Masks are explicitly oracle supervision.
The camera is fixed per episode, OpenCV +X right, +Y down, +Z forward.
Transforms use column vectors: `T_A_B` maps B coordinates into A.
Object mesh coordinates match the target rigid-body root, not its centre of mass.

`robot_observations.jsonl` contains only frame ID, timestamp, measured joint
positions/velocities, and camera/base calibration. `previous_robot_state.json`
retains the sample one capture step before the first image. Joint order covers
all six arm joints and four measured gripper joints. `robot/` contains canonical
link meshes, authored joint frames and hashes. The same canonical points must
be transformed in both frames when calculating surface motion.

Ground-truth object/effector/link transforms, phases, contact records, amodal
masks and grasp success remain in `validation/` or the explicitly privileged
legacy `frames.jsonl` used by evaluation tools. The inference reader uses a
whitelist from `robot_observations.jsonl` and a previous estimated object pose
supplied by its caller. It never selects object truth or contact labels.

B and C clips may share a physical parent rollout. Such clips retain the same
parent group and split. No framewise random split is allowed. Failed attempts
remain outside the accepted index with explicit reasons. Acceptance requires
all mandatory checks; absent or unknown checks fail closed.
