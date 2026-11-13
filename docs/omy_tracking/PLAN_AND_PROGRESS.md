# OMY tracking dataset — living plan and progress

Last updated: 2026-11-13 (Asia/Seoul).
Working branch: `feature/omy-tracking-dataset`.
Authoritative implementation brief: `../../OMY_Dataset_Codex_Prompt.md`.

**Pilot complete: 45/45 accepted.** [Final results and videos](PILOT_RESULTS.md).
The chronological log below preserves earlier failures and superseded counts.

## Objective and current scope

Deliver the **45-sequence pilot**: three objects × three tasks × five episodes.
User explicitly confirmed this scope and requested as many iterations as needed to reach 45 accepted sequences. Continue implementation autonomously;
report material errors and decisions. Do not launch the 720-sequence dataset.
Use headless generation and provide MP4s/screenshots. Keep the realistic OMY,
NVIDIA table and textured targets; background is a simple floor and wall.
The warehouse is superseded and remains only in historical previews.

Pilot execution is authorized. Validation gates below determine when a run
qualifies as pilot data; failed attempts remain separately labeled. The user explicitly instructed us to proceed while partner format review is
pending; the decision is recorded in `configs/omy_tracking/review_decision_20261113.json`.
Partner loading and tracking performance remain unverified.

## Current evidence — do not overstate progress

| Area | Status | Evidence / limitation |
|---|---|---|
| Branch and upstream | Checked | Feature branch at 2474ef6; fetch found main already contained at time of inspection. New work is uncommitted. |
| Hardware | Checked | RTX 5080, 16 GB VRAM; 62 GiB RAM; approximately 222 GiB free at initial inspection. Recheck before pilot. |
| Runtime | Startup/render passed | Isaac Sim 6.2.0.0, Isaac Lab 3.0.0, Python 3.12.3; user accepted NVIDIA EULA. |
| OMY source | Located and pinned | cyclo_lab a44392325d2ccb250ba77ece3237b55ba1f206e1; upstream targets Sim 5.1 / Lab 2.3. |
| Static scene | Rendered | Preview 007: table, OMY, gelatin box, simple floor/wall. |
| Target candidates | Calibration in progress | Native-scale gelatin box, marker and banana selected; can/drill attempts preserved as rejected candidates. |
| Lab articulation | Failed | Reset fails in Warp: expected array, received ProxyArray. Import success was not dynamics validation. |
| Native PhysX motion | Measured-state capture works | Wrist FK passes 1,500 frames; sampled replay depth agrees within 0.48 mm p95. |
| Grasp | Three objects physically demonstrated | Marker A/B/C and box/banana B/C pass every technical check. |
| Dataset export | Packaged handoff validated | RGB-D, geometry, measured state, provenance, independent replay and inference truth-boundary checks pass on handoff 002. |
| Validated A / B / C handoff | **1 / 1 / 1** | Handoff 002 passes technical acceptance; C has explicitly partial held-object preroll. FoundationPose initialization is untested. |
| Accepted pilot sequences | **45 / 45** | From the accepted index; 5 rejected attempts retained. See PILOT_RUN_STATUS.md. |

Current artifacts (paths relative to repository):

- `outputs/omy_workstation_preview_007/overview.png`, `sensor.png`, `workstation.usda`.
- `outputs/omy_motion_check_002/motion_30fps.mp4`: reviewed 4-second, 640×480, 30-fps motion preview; decode verified.
- `outputs/omy_motion_check_002/diagnostics.json`: commands and USD transforms; not full measured robot observations.
- `outputs/omy_articulation_check_002/error.txt`: unresolved Isaac Lab error.
- `configs/omy_tracking/assets.json`: preliminary manifest; dependency hashes and terms incomplete.
- `configs/omy_tracking/preview.json`: current machine paths and simple background.

The MP4 was converted from a GIF; it is a review artifact, not original RGB data.
Future capture must encode review videos directly from original PNG frames.

## Operating rules and update procedure

- Update this file after every meaningful implementation, capture, validation,
  failure, or user scope change. Update counts only from accepted run manifests.
- Each update records date, action, exact artifact/run path, result, remaining
  limitation, and next action. Keep failed run directories and explain rejection.
- Check off a gate only with recorded evidence; distinguish implemented, executed,
  and validated. Never treat a closed gripper or moving arm as grasp success.
- Preserve existing results and source USDs. Use references and local overrides.
- Keep assets and outputs outside Git; retain code, compact plans/configs/manifests.
- Keep work on the feature branch; no reset/clean/force push or unauthorized push.
- Preserve the current environment. Prefer the working native PhysX path for the
  next bounded experiment; isolate dependency changes if runtime repair is needed.

## Milestone 1 — reliable robot and object physics

- [x] Load OMY visual model and render the scene.
- [x] Demonstrate a small native PhysX joint-drive motion.
- [x] Read measured joint positions/velocities through the native articulation API.
  Evidence: `outputs/omy_gripper_probe_002/diagnostics.json` (90 frames).
- [x] Record joint names/order, limits, drive units, fixed-base constraint, finger
  coupling/mimic mechanism, and effector frame from the pinned USD.
- [x] Run a two-second hold and compare commanded versus measured joints; check
  root drift, nonfinite state, limit violations, and self-collision warnings.
- [x] Resolve camera/render state freshness against those measured states.
- [x] Inspect target rigid-body root, mass, inertia, COM, collision approximation,
  friction and restitution; log effective values rather than assume defaults.
- [x] Configure table/floor as static colliders. Settle the target and verify that
  it rests on the tabletop without tunneling, penetration, or excessive drift.
- [x] Measure physical finger clearance across commanded opening and closing.

Acceptance: finite measured states, fixed base, reproducible hold and target
settling, valid joint limits, no unresolved critical PhysX errors. Save report
and short video. Proposed initial hold tolerance: 0.05 rad maximum joint error;
base drift <1 mm. These are engineering gates, not measured results.

## Milestone 2 — one real grasp, lift and release

Completed on the three selected objects; retain the steps as the reproducible grasp procedure.

1. Position the selected target inside measured reachable workspace at true scale.
2. Define a grasp frame using the narrow dimension and actual finger geometry.
3. Reuse calibrated link-origin IK (`src/calibration/isaac_ik.py`) where compatible;
   otherwise adapt its frame math to native PhysX. Audit Jacobians/FK before use.
4. Interpolate approach waypoints with velocity/acceleration limits and collision
   clearance. Start above the object with open fingers.
5. Descend, close fingers through drives, wait for contact to settle, then lift.
6. Hold, translate and rotate smoothly; log actual object and effector transforms.
7. Lower to the table, open fingers, retreat, and allow the object to settle.
8. Save an MP4 plus diagnostics marking phase transitions and failures.

- [ ] Approach is reachable without touching the table or unintended robot links.
- [x] Finger contact is physical; no hidden fixed joint or object teleportation.
- [x] Target lifts at least 50 mm above settled starting height.
- [x] During a one-second hold, relative pose drift stays below proposed initial
  limits of 10 mm / 10 degrees; report actual maximums and symmetry convention.
- [x] Translation and rotation produce measurable object motion.
- [x] After release, target settles while the gripper retreats independently.
- [x] Failed grasps are explicitly rejected with reason and retained diagnostics.

Thresholds may be revised based on object geometry before acceptance; record any
revision and re-evaluate affected runs. A diagnostic attachment must be labeled
and cannot pass this milestone.

## Milestone 3 — synchronized export and asset model

- [x] Extend existing contract deliberately; preserve v1 units and camera axes.
- [x] Use 120-Hz physics / 30-Hz captures initially: four physics steps per image.
- [x] Render RGB, optical-axis depth, and visible target mask at the same final
  physics state as measured joints and poses. Reject stale buffers and resets.
- [x] Capture robot state preceding the first usable image.
- [x] Export original RGB PNG; uint16 depth in mm with zero invalid; masks including
  valid empty masks under complete occlusion. Record camera K and calibration.
- [x] Record monotonically increasing frame IDs and simulation timestamps, joint
  names/q/dq, T_world_camera/base/effector and validation-only T_world_object_gt.
- [x] Separate inference observations from GT, contacts, phases and success labels.
- [x] Record source revisions/hashes, seed, parent group, split, physics/lighting,
  target scale, symmetry, origin/mesh/COM offsets and grasp mechanism/status.
- [x] Export matching textured mesh, UVs and materials for FoundationPose. Existing
  geometry-only OBJ exporter is insufficient. Compare known-pose renders.
- [x] Export canonical robot link geometry and reproduce selected poses with FK.
- [x] Write a sample reader returning current RGB-D, previous estimated pose,
  current/previous measured joints and robot geometry without privileged labels.

## Milestone 4 — validated A/B/C first handoff

| Task | Required behavior | Specific checks |
|---|---|---|
| A | Clear → noncontact robot occlusion → clear | Target drift <2 mm / 2 degrees initially; no finger/arm target contact; measure visibility change. |
| B | Approach → physical grasp → lift → hold → translate/rotate | Lift and hold gates from milestone 2; measured state agrees with images. |
| C | Carry → place → release → retreat | Target settles on table and separates from fingers; visible preroll for initialization. |

- [x] One accepted example per task; B/C shared parents remain in the same split.
- [x] Run the existing `scripts/validate_isaac_export.py` plus the explicit OMY extension checks in `validate_omy_sample.py`.
- [x] Validate file completeness, transform rigidity, units and capture cadence.
- [x] Render GT object overlays throughout motion, not just the first frame.
- [x] Run all-link FK and exported-geometry audits using `audit_omy_all_link_fk.py`
  and `audit_omy_exported_geometry.py`; retain RGB/depth alignment evidence.
- [x] Render object-only/amodal masks at identical camera/pose for visibility.
  Record truncation and zero denominator separately; distinguish total versus
  robot-specific occlusion. Do not use mask area alone as visible fraction.
- [x] Save RGB, object-overlay and robot-overlay videos with acceptance report.
- [ ] Have partner load the sample and confirm intended model inputs and format.

## Milestone 5 — prepare and generate the 45-sequence pilot

Three distinct opaque rigid objects: one box, one cylinder/container, one
asymmetric object. Selected native-scale NVIDIA YCB assets are gelatin box, large marker, and banana.
Their matching textured meshes and physical grasps have been validated.
Do not scale oversized warehouse props down to graspable toys.

| Object | A: noncontact | B: grasp/move | C: place/release | Accepted total |
|---|---:|---:|---:|---:|
| Box (gelatin box) | 5 / 5 | 5 / 5 | 5 / 5 | 15 / 15 |
| Cylinder (large marker) | 5 / 5 | 5 / 5 | 5 / 5 | 15 / 15 |
| Asymmetric (banana) | 5 / 5 | 5 / 5 | 5 / 5 | 15 / 15 |
| Total | 15 / 15 | 15 / 15 | 15 / 15 | **45 / 45** |

- [x] Complete grasp and asset validation for all three objects.
- [x] Create a 45-row JSON/YAML run manifest: object/task/seed/trajectory/start pose/
  parent/split/output path, with five explicit variants per object-task pair.
- [x] Target 6–10 seconds at 30 Hz: 180–300 frames per sequence, 8,100–13,500 total.
- [x] Vary reachable starts, translations and rotations; differing path lengths vary
  speed under fixed phase timing. Keep fixed camera/exposure and measured visibility variation.
- [x] Freeze split/group assignments before capture. Never split neighboring
  frames or shared B/C parents between train and validation.
- [x] Measure one representative run: wall time, bytes/frame, peak GPU memory,
  initialization overhead. Estimate full storage and runtime from measurements.
- [x] Recheck disk space and set run time/storage limits with documented headroom.
- [x] Generate a small batch first, validate every sequence, then continue the
  remaining manifest rows. Refuse overwrites; resume only incomplete work safely.
- [x] Every accepted row passes task-specific and export validation. Failed runs
  do not count toward 45; retain them and record explicit replacement settings.
- [x] Publish final local index, acceptance/rejection reasons, 45 accepted counts,
  reader, coordinate/schema docs, review videos and measured resource summary.

Completion means **45 accepted sequences**, not 45 simulation attempts. No claim
of model improvement follows from collecting this dataset.

## Immediate execution order

1. Native articulation measured-state and gripper-opening probe.
2. Target/table collision and settling check.
3. One physical grasp/lift/release video with actual object motion diagnostics.
4. Synchronized exporter and one validated A/B/C set.
5. Remaining two assets and 45-row pilot manifest; format/resource gates.
6. Generate, validate and summarize 45 accepted sequences.

## Progress log

| Date | Action | Result / next action |
|---|---|---|
| 2026-11-13 | Inspected hardware, repo and runtime | Headless rendering works; historical launcher paths obsolete. |
| 2026-11-13 | Resolved NVIDIA table, warehouse and OMY | Static scene rendered; source references preserved. |
| 2026-11-13 | Added real-scale textured gelatin box | Visual candidate only; grasp dimensions still need checking. |
| 2026-11-13 | User simplified background | Preview 007 uses only floor and wall. |
| 2026-11-13 | Tried Isaac Lab articulation | Warp ProxyArray error; no sequence accepted. |
| 2026-11-13 | Native PhysX joint-drive preview | Motion GIF and verified 120-frame MP4; no grasp. |
| 2026-11-13 | User reviewed motion and confirmed 45-sequence pilot | Prioritize physical grasp, then validated A/B/C and full pilot. |

### Latest execution update — 2026-11-13

The first native measured-state probe failed to attach its physics view. Explicit
stage ID and startup updates resolved that failure in probe 002. The resulting
90-frame arm/gripper probe records joint names, measured positions and velocities
and an animated review. This is still not a grasp: fingers were commanded in
free space, not around the object. Next: quantify finger clearance and validate
target contact/settling, then approach and physically lift the target.

Artifacts: `outputs/omy_gripper_probe_002/diagnostics.json`, `motion.gif`.
Accepted pilot count remains **0/45**.

### Physics and first grasp attempt — 2026-11-13

- `outputs/omy_physics_inventory_001/physics_inventory.json`: identified the
  visual-only target (no body/collider), authored table collider and finger meshes.
- Added target rigid body (initial mass 0.10 kg, provisional) and convex-hull
  collision, plus floor/wall static collision, in the diagnostic composition.
- `outputs/omy_target_settle_001`: 90-frame settle check; target position stable
  to recorded precision over final 30 frames. Full contact/material audit pending.
- `outputs/omy_grasp_probe_001`: physical drive/IK approach, descent, close, lift
  attempted. **Rejected**: maximum target height increase 0.583 mm, below 50 mm.
  Arm had not reached descent pose when closing began. No successful grasp.
- Longer diagnostic attempt 002 started; success must be checked from actual
  object lift and hold, not assumed. Current controller phases are time-based;
  replace them with measured convergence gates before accepted dataset capture.

Accepted pilot count remains **0/45**.

### Second physical grasp result — 2026-11-13

`outputs/omy_grasp_probe_002/validation.json`: **rejected**. Longer descent
produced target contact but displaced the box approximately 148.9 mm sideways.
Maximum transient height increase was 12.65 mm; final height returned to the
starting level. This is not a stable lift. `attempt.mp4` is encoded and decode
checked. No attachment or object teleportation was used.

Next corrective gate: inspect finger contact geometry and approach alignment;
use measured position/orientation convergence before closing, reduce approach
speed near contact, and verify a collision-free grasp pose before another lift.
Do not multiply failed trials into the pilot. Accepted count remains **0/45**.

### First observed physical lift — 2026-11-13

Grasp probe 003 used an upright, true-scale target and measured-convergence
transitions. Final object height increased 0.18960 m. Over the last 60 frames,
relative object-to-link6 translation drift was 1.12 micrometres and rotation
drift 0.000724 degrees according to synchronized USD transforms. No fixed-joint
attachment or object teleportation was used. This is a promising grasp result,
not accepted dataset data: contact geometry, frame/sync audits and full export
remain. See `outputs/omy_grasp_probe_003/validation.json`.

Place/release/retreat attempt started at `outputs/omy_grasp_place_001`.
45 planned entries are now in `configs/omy_tracking/pilot_manifest.json`.
NVIDIA soup-can and power-drill USD endpoints returned HTTP 200; they remain
unvalidated grasp candidates. Accepted pilot count stays **0/45**.

### Export and release iteration — 2026-11-13

- `outputs/omy_grasp_place_001`: grasp/lift/lower/open/retreat completed; object
  settled after release, but release was too high. Diagnostic only.
- `outputs/omy_observation_probe_001`: 30 RGB/depth/mask frames and state records.
  Basic checks: 640x480; uint16 mm depth; nonempty target mask (594 pixels on
  audit frame); timestamp differences 1/30 s. Overlay validation still pending.
- `scripts/read_omy_observation_probe.py` selects only explicit observation fields
  and caller-provided previous estimated pose. It refuses index 0 because this
  diagnostic format has no pre-image state. This limitation must be fixed before
  the accepted handoff; the reader is not full model integration.
- Place attempt 002 now lowers according to target bottom height and waits near
  tabletop support before release. It exports original images/state for review.

### Acceptance configuration and current batch state — 2026-11-13

`configs/omy_tracking/acceptance.json` now lists proposed numerical gates and
mandatory validation categories. Missing checks fail acceptance. The 45-row
manifest remains planning-only; successful debug lift does not increment it.
Place/release attempt 002 is recording 1,200 diagnostic frames with original
RGB, depth, masks and measured joints. It is longer than pilot target duration
and must not be counted as a 6–10-second accepted episode without valid
segmentation/preroll and parent-group handling.

### Diagnostic acceptance audit — 2026-11-13

`outputs/omy_grasp_place_002/diagnostic_validation.json` passes basic cadence,
frame ordering, finite measured joints, rigid transforms, image completeness,
depth encoding and visible initial mask across 1,200 frames. Size including
review video is approximately 253 MB. This does not pass pilot acceptance:
geometry/texture equivalence, overlays, contact/release validation, amodal
visibility and complete manifest remain missing. Native physics capture is
working; the earlier Lab ProxyArray failure remains bypassed, not repaired.

Release attempt 003 extends through retreat and records original observations.
Candidate-asset inspection timed out during startup under concurrent load;
no geometry conclusions were drawn from that attempt. Repeat it sequentially.
A format-review request is pending with the user; no answer has been assumed.

### Completed release/retreat and geometry check — 2026-11-13

- `outputs/omy_grasp_place_003`: 1,500 diagnostic frames, including release and
  retreat. Original-RGB `review.mp4` encoded and decoded successfully. Basic
  observation validator passes; no pilot acceptance claimed.
- `outputs/omy_occlusion_probe_001`: 600-frame noncontact candidate, zero maximum
  object-origin height increase, visible mask range 438–595 pixels. Full pose
  stationarity/contact and rendered-amodal checks still required.
- `outputs/omy_target_model_001`: 8,417 vertices, 16,380 faces, exported OBJ/MTL,
  UVs and original 11.3 MB NVIDIA texture, with SHA-256 hashes. Pixel/render
  equivalence is not yet validated.
- Target projection containment passes on 50 sampled grasp/place frames with
  one-pixel tolerance. Saved overlays and report are under
  `outputs/omy_grasp_place_003/object_projection_audit/`. This is a convex-hull
  containment audit, not a full silhouette/depth or robot-FK validation.
- Pilot accepted count remains **0/45**; pending format review has no reply yet.

### FK and candidate inspection — 2026-11-13

Authored-joint-frame FK from measured joints passes all 1,500 frames of
`omy_grasp_place_003`: max wrist translation discrepancy 6.64e-7 m and rotation
0.000109 degrees. `fk_audit.json` records the result. This is wrist FK agreement,
not a complete per-link image audit.

Sequential candidate inspection succeeded: soup can bounds approximately
67.7 × 101.9 × 67.7 mm (long axis Y); drill 184.4 × 186.8 × 57.2 mm. Candidates
are at native scale, with metre metadata. Drill needs a local handle grasp;
do not assume its complete bounding width fits the gripper.

### Render replay and contact diagnostics — 2026-11-13

Frozen robot geometry reconstructed from measured-joint FK agrees with saved
RGB-D at seven sampled poses: robot depth p95 errors 0.474–0.478 mm, consistent
with uint16-mm quantization. Evidence: `omy_grasp_place_003/fk_render_audit`.
This is not yet an all-frame silhouette IoU audit.

Textured OBJ round-trip render at the same pose/camera/light gives mask IoU 1.0,
depth p95 difference 4.77e-7 m, and RGB MAE 2.13/255 on target pixels. Images
were inspected. Shader implementations differ (OmniPBR vs UsdPreviewSurface).
Evidence: `outputs/omy_model_render_audit_001`.

Can attempts 001–005 did not produce a stable lift. Native contact reports
localized premature contact to proximal finger links l1/r1, not pads l2/r2.
Attempt 006 tests the authored tool-tip frame without the earlier 45 mm inset.
Collision contact/rest offsets are now explicitly 1 mm / 0 in diagnostic code;
final object trials must all be repeated under one frozen physics configuration.
No failed can attempt counts toward the pilot. Accepted total remains **0/45**.

### Cylinder calibration and robot export — 2026-11-13

Can attempt 006 also failed to lift stably. Contact audit 001 records real normal
forces on proximal finger links (up to about 274 N in the failed descent), while
pad-link contacts remained zero. This is a rejected calibration attempt, not a
successful grasp. A narrower NVIDIA YCB large-marker candidate endpoint returns
HTTP 200; geometry inspection is underway before selecting it for the cylinder
slot. The soup-can choice is not locked.

`outputs/omy_robot_geometry_001/manifest.json` now lists 11 canonical body-local
visual OBJ meshes and hashes. Collision meshes were excluded. Source revision
is pinned; exported-mesh round-trip verification remains pending.

New diagnostic arguments expose target mass, collider approximation, grasp
height, tool inset and moving-pad-centre experiments. These parameter changes
must be frozen and recorded in production run manifests before acceptance.

### Narrow-cylinder diagnosis — 2026-11-13

Marker attempt 004 completed the control phases but produced zero lift. Offline
FK of the actual finger mesh shows the earlier 0.8 rad closure leaves a 34.1 mm
gap; the marker diameter is only 19 mm. Attempt 005 uses 1.10 rad (within the
authored 1.101 rad limit), a moving pad-centre target and 1.027 m pad height.
This changes a diagnosed grasp parameter, not the target scale or attachment.
The actual NVIDIA YCB directory inventory is saved in
`outputs/omy_runtime_probe/nvidia_ycb_catalog.json`.

### Marker lift demonstrated; asymmetric calibration — 2026-11-13

`omy_marker_grasp_005` lifts the 30 g native-scale marker 117.4 mm with both
pad-link contacts, no proximal contacts, and final-second relative drift below
0.001 mm / 0.001 degrees. Pilot cylinder candidate changed from soup can to
marker; no accepted sequence yet. Drill attempts 001–003 fail stable lift.
Mesh inspection locates the handle at local approximately (+0.037,+0.025) m;
correcting the grasp still resulted in slip/ejection. These attempts remain
rejected. A native NVIDIA banana is being inspected as an alternative asymmetric
rigid target. Contact callback now logs every substep event; sampled force
matrices are retained separately. New carry control and faster clip timings
remain unvalidated until the next complete trial.

### Complete carry behavior and stricter release — 2026-11-13

Marker carry/place 002 passes B behavior: actual-mesh table clearance 114.8 mm,
relative hold drift 0.0034 mm / 0.0048 degrees, carry 66.4 mm / 20.05 degrees,
bilateral pad contacts. All 11 links pass encoder-FK comparison across 882
frames (maximum translation discrepancy below 1 micrometre). C fails the
5 mm release-gap gate (5.30 mm), despite final settling and independent retreat.
Banana carry/place 001 passes B behavior: clearance 118.1 mm, carry 58.0 mm /
20.03 degrees, stable hold and bilateral contacts. C release gap 7.76 mm fails.
The new controller uses transformed mesh vertices, rather than a transformed
bounding box, for placement height and requires real table contact before
release. This correction is pending a complete rerun.

The cylinder is the native NVIDIA large marker; the asymmetric candidate is
now the native NVIDIA banana, modelled as rigid at an explicitly assumed 120 g.
No exact textured symmetry is asserted. All object masses and contact materials
are simulation assumptions, not measurements of real specimens. Explicit
physics material values, computed inertia/COM, and 32/4 solver iterations are
now recorded. Pilot acceptance remains 0/45.

### First packaged manipulation samples — 2026-11-13

Box carry/place 002 passes B and C physical behavior, including real table
contact before release. Marker carry/place 003 repeats B/C successfully with
861 original RGB-D frames. Packaging produced
`outputs/omy_handoff_001/cylinder_B_00` (300 frames / 10 s) and
`outputs/omy_handoff_001/cylinder_C_00` (235 frames / 7.83 s). Both pass the
existing `validate_isaac_export.py` contract validator. Reader checks pass for
frames 0 and 1 while access to privileged frame/contact files is explicitly
blocked; the identity caller pose is only a loader test, not a tracking result.

Measured marker capture: 81.9 s wall time, 253.9 MB parent data, peak sampled
whole-device GPU memory 3,429 MiB (includes desktop/other GPU usage), child
peak RSS approximately 7.76 GiB. This is an offline capture, not a real-time
performance claim. The 45-clip RGB-D payload is expected around 3–4 GB;
retained parents/audits/models/rejected trials require additional storage.
Current disk free: about 216 GiB. Shared immutable link meshes avoid 45 copies.

Marker noncontact 001 has zero object drift and zero robot contact, but lacks
clear start/end views. A revised raised-start/occlude/raised-end path is pending.
Every-frame exported-OBJ/FK depth/segmentation replay is running for the B/C
sample interval. Sample acceptance and partner format confirmation remain open.

### Visibility design and acceptance hardening — 2026-11-13

The original-view marker A clip passes full per-frame exported-geometry replay:
100% → 15.7% → 100% visible fraction, zero object drift/contact. Marker textured
OBJ round-trip: mask IoU 1.0, depth p95 4.77e-7 m, RGB MAE 3.03/255.
B/C capture 003 also passes every-frame mesh/FK replay, but its manipulation
occlusion is mild. Negative wrist tilt 004 mainly foreshortens the marker; it
does not materially occlude it. Large positive tilt 005 fails stable carry.

Task validator v2 now checks clearance and object-to-gripper pose throughout
carry and unsupported placement, preventing a dropped object or table contact
during carry from passing merely because phase names and net motion look right.
Previous reports are preserved as `.previous_*.json`. Baseline marker 003 and
box 002 still pass B/C; marker 005 correctly fails both.

A camera-design probe on frozen measured poses identified the higher oblique
view `(0.6, -0.6, 2.5)` looking at `(0.1, -0.08, 1.2)` as a useful candidate:
more target pixels and real gripper occlusion. High-view trial 001 passes
physical B/C; approach/retreat and a clear held-object preroll are being tuned
for the visibility gates. Original scene 007 remains unchanged.

The surface-feature helper uses persistent canonical point samples and measured
encoder FK. Independent verification of 2,816 points passes below 0.4 micrometres.
An updated asynchronous format-review question is pending, with loadable
A/B/C packages in `omy_handoff_001`; no response has been assumed.

### Higher-view handoff candidates — 2026-11-13

`omy_handoff_002` now contains A (240 frames / 8 s), B (300 / 10 s), and C
(260 / 8.67 s), all with original-RGB MP4s. Source parents are
`omy_marker_highview_A_002` and `omy_marker_highview_003`. All-frame exported
OBJ/FK replay passes: A silhouette IoU 1.0; B/C minimum 0.9957. A has zero
object drift/contact and visible fraction 1.0 → 0.268 → 1.0. B minimum visible
fraction is 0.380. C includes full occlusion and a fully clear ending.

Initialization policy is explicit: A/B require clear initial frames; C begins
with an already held object and requires a continuous 30-frame preroll with at
least 40% visibility. The actual C preroll stays above 50%. The 80% clear-view
portion remains required elsewhere in every clip. This separates partially
visible in-hand initialization from the clear/occluded variation gate; it does
not claim that FoundationPose initialization succeeds. The local checkout
currently lacks FoundationPose weights and Docker, so initialization has not
been run. Partner review remains pending before bulk generation.

Validator v3 checks every noncontact frame (no ignored initial interval), real
table-support impulses before release, and all unsupported placement frames.
The latest manipulation parent passes these checks. Full sample acceptance
reports are being assembled with hashed textured-model round-trip evidence.

### Technical handoff acceptance passed — 2026-11-13

All A/B/C packages in `outputs/omy_handoff_002` pass
`scripts/validate_omy_sample.py`; reports are in each `validation/acceptance.json`.
Original-RGB and geometry-overlay MP4s are present. Overlay clips decode to
exactly 240 / 300 / 260 frames using bundled FFmpeg; this OpenCV build cannot
decode H.264, so it is not used for video verification.

Box high-view 001 passes full B/C physical behavior under the updated setup.
Banana high-view 001 is running with 160 mm lift clearance for its longer shape.
This is asset qualification, not the 45-sequence bulk run. No partner review
response or waiver has been received. Accepted pilot count remains 0/45.


### 2026-11-13 — retry runner and remaining asset qualification

- Added `scripts/run_omy_pilot.py`: 45 slots, unique preserved attempts,
  physical/visibility/geometry/schema checks, MP4 verification, parent-safe splits,
  resumable accepted index, and generated `PILOT_RUN_STATUS.md`. Not yet exercised
  on a production cohort; partner review remains pending.
- Corrected copy-tree path handling and added acceptance-gate hash consistency
  and a 20 GiB free-space stop. No thresholds were relaxed for these changes.
- `outputs/omy_box_highview_001` and `outputs/omy_banana_highview_001` both pass
  v3 physical B/C checks. Banana carry-relative drift is 0.090 mm / 0.048 degrees;
  table support precedes release. Both remain qualification captures.
- Updated `HANDOFF.md` to the fully validated handoff 002 videos and documented
  the partial-view C initialization condition and untested FoundationPose stage.
- Next: complete model/visibility qualification, freeze runnable settings, then
  execute the retry runner after the explicit format-review decision.


### 2026-11-13 — complete box qualification

- `outputs/omy_box_highview_001/exported_geometry_audit/report.json` passes all
  557 frames, with target silhouette IoU 1.0. All 11 links independently pass FK.
- `outputs/omy_handoff_002/box_B_00` and `box_C_00` pass every technical check,
  including clear/occluded portions. Original-RGB and geometry-overlay MP4s
  were encoded and decoded successfully. B is 300 frames; C is 257 frames.
- The first box package check correctly failed on a missing FK report. Kept
  `validation/acceptance.before_fk_check.json`, ran the missing independent
  check, and revalidated. No acceptance threshold changed.
- Box/banana textured OBJ audits pass, with mask IoU 1.0, depth p95 below
  0.4 micrometres, RGB MAE 7.10/0.96 out of 255. Source/reimported images reviewed.
- Capture configuration now includes the higher oblique camera, native object
  settings, deterministic seeds, and -45-degree baseline carry yaw. Variants
  are planned perturbations and must independently pass all gates.


### 2026-11-13 — qualified handoff and pilot launch checkpoint

- **Seven technical passes, zero cohort acceptances**: marker A/B/C, box B/C,
  banana B/C under `outputs/omy_handoff_002`. All have RGB and overlay MP4s.
- Banana replay passes 575 frames; minimum target silhouette IoU 0.99869.
  Its B/C packages pass every check (300/275 frames).
- `configs/omy_tracking/pilot_capture.json` is ready for review-gated execution.
  Qualification covers baseline manipulation of all three objects and marker A;
  remaining trajectories/object combinations are subject to per-sequence gates.
- Verified all 45 manifest slots are unique and agree with the capture seed map.
  Runner syntax/help and metadata-isolation tests pass. An empty review record
  was explicitly rejected without creating an accepted index or starting capture.
- `scripts/run_omy_pilot.py` has not yet had a complete production invocation.
  Preserve that limitation; do not count prepared slots as completed sequences.
- Required external next step: actual partner loading confirmation or explicit
  user waiver of the brief's pre-bulk review requirement. The pending question
  is not answered by its default option. Once resolved, run, inspect failures,
  adjust bounded controls as needed, and resume until all 45 slots pass.


### Pilot execution authorized

User replied “proceed” to the explicit pre-bulk review choice. Recorded in
`configs/omy_tracking/review_decision_20261113.json`; partner loading is not
claimed. Proceeding with all technical gates and preserved retries.


### Pilot retries and rendering isolation

- `box_manipulation_00_attempt_001` failed silhouette agreement at one heavily
  occluded frame (710; IoU 0.75). Its physical motion passed; it was not accepted.
- `asymmetric_manipulation_01_attempt_001` passed physics but had no clear view
  in B. A folded arm posture occluded the object before grasp.
- Retried with grasp yaw 0 degrees while preserving target yaw 86 degrees, seed
  4101 and the trajectory. `outputs/omy_banana_retry_002` and both packaged
  samples under `outputs/omy_retry_samples_001` pass every technical check.
  They await selection into the cohort when the main index writer stops.
- The first isolated retry launch lacked the already-authorized EULA environment
  setting and exited before capture; its log is preserved as `banana_retry_001.log`.
- A brief overlap of capture/replay jobs stayed below 5.8 GiB sampled whole-GPU
  usage, but `asymmetric_manipulation_02_attempt_001` failed alignment at five
  frames. Causality is not proven; subsequent GPU work will be sequential and
  the affected pair will be rerun or independently revalidated without relaxing gates.


### Postflight joint-limit defect and withdrawal

- The initial gates reached 45 selections, but the additional measured-state
  audit found passive `rh_l2` excursions beyond the authored -15-degree lower
  limit in all five marker and all five banana C clips (up to 0.503 rad excess).
  These ten clips were withdrawn. The other 35 clips remain selected.
- Preserved `index.before_joint_limit_audit_001.json`, original packages and all
  reports. `index.json` records each withdrawal and is authoritative.
- Added `check_omy_joint_limits.py`, checking finite measured positions/velocities
  and authored limits with a 0.001-rad numerical allowance. It is now enforced
  in new package validation, promotion, and independently on the final cohort.
- A gradual opening alone (`omy_release_fix_probe_001`) still failed. Measured
  wrist Z fell from 1.013 m to 0.981 m while the controller tried to maintain
  the changing fingertip center. The high box grasp avoided this table interaction.
- Correction under test: freeze the grasp control offset during release/retreat,
  open smoothly over 30 frames, and retain a 0.02-rad open-angle margin.
  Robot geometry, authored limits, native contacts, and acceptance tolerances
  remain intact. No object teleportation or attachment is introduced.
- Replacement C clips will use distinct physical parent groups in the same
  preassigned split. Valid B clips are retained; a replacement C still must
  have a successful physical grasp/carry in its own parent capture.


### Contact-gated release correction qualified

`omy_release_fix_probe_002` reduced the wrist descent but still exceeded a
passive-joint limit by 0.188 rad. Opening close to the tabletop also requires
vertical clearance. Probe 003 freezes the control reference, opens smoothly,
and raises the gripper 40 mm only after two frames with no robot/target contact
and continuing table support. Its entire 846-frame capture has zero authored
joint-limit excess. The ten C replacements are now undergoing full validation.
The original acceptance hashes remain intact; `postflight_acceptance.json`
records the additional mandatory state/limit check applied to every final clip.


### Final pilot delivery — 45/45 accepted

- Final clean export: `outputs/omy_pilot/dataset`; authoritative index:
  `outputs/omy_pilot/index.json`. Earlier selections and withdrawn C files remain
  outside the clean export, with the complete withdrawal/replacement history.
- `cohort_audit_final_001.json` independently passes all 45 sequences, current
  joint limits/finite states, texture/evidence hashes, parent/split consistency,
  image counts, and all 90 RGB/overlay MP4 frame counts.
- The portable reader and canonical-surface helper load the exported folder
  with privileged files blocked (`portable_reader_audit_001.json`). This checks
  loading/features, not FoundationPose initialization or tracking accuracy.
- Two-second holds from all 25 selected manipulation parents pass: maximum arm
  command/measured discrepancy 0.01848 rad; measured base translation drift zero.
- Nine representative A/B/C clips are concatenated in `pilot_demo.mp4` (80.4 s).
  `PILOT_RESULTS.md` gives all 45 video links, frame/storage/resource totals and
  retained rejection reasons; `accepted_checksums.sha256` supports copying.
- No 720-sequence generation was launched. Partner loading review and tracking
  evaluation remain separate, explicitly unverified steps.


### 2026-11-14 — GitHub handover and visual results

Added `PIPELINE_HANDOVER.md`, original-frame grasp/release GIFs, a measured
occlusion figure, compact cohort/reader/hold audits, and dataset checksums for
GitHub publication. The full dataset remains at the documented local path and
is excluded by the existing outputs ignore rule. Capture acceptance is unchanged.
