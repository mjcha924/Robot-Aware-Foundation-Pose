# OMY workstation inspection — 2026-11-13

Work branch: feature/omy-tracking-dataset at 2474ef6. Fetched origin and
merged origin/main: already up to date. Remote baseline is 2474ef6;
remote main is bcae895. No remote update was available at inspection time.
The untracked user brief and existing results were preserved.

Host: RTX 5080, 16303 MiB VRAM, driver 595.99.02; 62 GiB RAM,
222 GiB available workspace disk. Docker command is absent. Historical
3070/580-driver instructions do not describe this host.

Local robotics checkout: /home/a09/robotics/isaaclab-so101.
Isaac Sim 6.2.0.0 package metadata exists in /home/a09/.cache/uv/archive-v0.
This demonstrates cached packages, not a working simulator installation.
No ROBOTIS/cyclo checkout was found in the initial bounded home search.
Simulator launch, installed Isaac Lab version, OMY revision, articulation,
gripper opening and asset dependencies remain unverified.
Existing capture launchers point to /home/mjcha and require robotis_lab.
The capture implementation preserves live camera refresh and optical-axis
depth; reuse these when adapting the task registration to the actual checkout.
Its hard-coded historical robot revision must become measured provenance.

## First scene plan (provisional until USD inspection)

Official NVIDIA environment catalog:
https://docs.isaacsim.omniverse.nvidia.com/6.2.0/assets/usd_assets_environments.html

Documented asset references, relative to the resolved NVIDIA asset root:

- /Isaac/Environments/Simple_Warehouse/warehouse.usd: preferred compact
  industrial shell, with one shelf. Keep the shelf behind the manipulation area.
- /Isaac/Environments/Simple_Room/simple_room.usd: documented furnished
  room with a table; inspect its table geometry as a workstation candidate.

These are catalog-confirmed paths, not locally resolved assets. Local paths,
content hashes, dependency availability and applicable asset terms are pending.
Do not label either candidate SimReady without inspecting its provenance.
A suitable industrial workbench and graspable targets have not yet been
verified; do not substitute fabricated filenames or resize warehouse props.

Compose source references under /World/Scenery in a new layer. Use metres,
Z up. Plan tabletop height 0.75–0.85 m, subject to actual authored dimensions.
Mount the fixed OMY base on the table with the target initially 0.25 m ahead;
final offset requires measured reach and gripper clearance. Keep a clear
0.4 m square manipulation region. Place one shelf behind the bench and at
most two background boxes outside the reach region. Preserve authored materials.

Place one fixed oblique external camera facing the target and arm; initial
camera offset from target (0.9, -1.1, 0.8) m, then adjust framing after loading.
Use 640x480 at 30 Hz, RTX real-time, fixed exposure and area illumination.
Use a separate overview camera only for review. Save both views before capture.
Select an opaque box first after checking its real size against measured
finger opening; cylinder and asymmetric targets follow the same inspection.

## Executable milestone gates

1. Locate the interpreter owning the cached simulator and inspect package
   metadata; locate or obtain a pinned compatible ROBOTIS checkout.
2. Resolve the two catalog references with that runtime, inspect dependencies,
   units, bounding boxes and table prims. Record URLs, hashes, local paths and
   terms in a JSON manifest. Choose the actual bench and target only then.
3. Compose a new workstation layer, preserve original USDs, inspect target
   mass/colliders/friction and gripper geometry, and render overview/sensor views.
4. Run a short task-A capture using existing synchronization and export code;
   validate depth alignment, robot FK, object stationarity and transforms.

This checkpoint is inspection and scene planning only. No simulator launch,
render, physical grasp, asset download or validated sequence is claimed.

## Runtime confirmed

After explicit user acceptance of the NVIDIA license, headless startup passed
on 2026-11-13 using:
`/home/a09/robotics/isaaclab-so101/examples/isaaclab/.venv/bin/python`.
Installed metadata: Python 3.12.3, Isaac Sim 6.2.0.0, Isaac Lab 3.0.0,
PyTorch 2.11.0. Torch and Kit both detected the RTX 5080.
With `OMNI_KIT_ACCEPT_EULA=YES`, SimulationApp(headless=True) initialized,
completed one app update, printed OMY_RUNTIME_STARTUP_OK and closed with
exit code 0. Kit reported startup complete at 13.124 seconds.
Log: outputs/omy_runtime_probe/startup_accepted.log (generated, outside Git).
This validates basic startup only; scene rendering, physics and OMY package
compatibility still need their own checks. No installation or driver changes
were needed. Reuse this interpreter for inspection without changing its packages;
choose an isolated OMY environment once ROBOTIS version requirements are known.

## Source assets resolved

Cloned upstream cyclo_lab into /home/a09/robotics/cyclo_lab at
 a44392325d2ccb250ba77ece3237b55ba1f206e1, without installing its packages.
Checkout size is 339 MiB. The real OMY USD is present (not an LFS pointer).
Upstream README targets Isaac Sim 5.1 and Isaac Lab 2.3; do not install its
requirements into the existing 6.2/3.0 environment blindly.

The installed storage extension defines the asset root as
https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.2.
PackingTable/packing_table.usd is referenced by an upstream ROBOTIS task.
HTTP checks returned 200 for it, Simple Room, and Simple Warehouse.
The packing-table root layer is 13,964,280 bytes; dependencies add to this.
USD inspection successfully opened both the packing table and OMY.
Their metadata says centimetres but their authored bounds are metre-sized;
ROBOTIS explicitly references the packing table at scale 1 in its task.
The preview follows that convention and records composed bounds for review.
The table assembly spans approximately 2.474 x 0.782 x 1.083 stage units.
These are assembly bounds, not a measured tabletop height.

Added configs/omy_tracking/assets.json and scripts/preview_omy_workstation.py.
The preview composes original references, removes crate clutter through local
activation overrides, places OMY on the bench mesh upper bound, and captures
an overview plus 640x480 sensor view. It is a static composition check, not a
validated physics scene. It refuses to overwrite an existing output directory.

## Preview rendered and configuration import passed

outputs/omy_workstation_preview_004 contains overview.png, sensor.png,
workstation.usda and table_bounds.json. Both images were visually inspected;
the revised sensor view includes the full robot. Bench mesh top is
0.9940513388652052 m in the composed metre stage. The layout is still missing
its target and environment shell; it is not the completed realistic scene.
The first run exposed an incorrect viewport utility import; switching to
get_active_viewport and setting camera_path fixed it. All prior run directories
are retained. Python syntax and manifest JSON checks pass.

The actual cyclo_lab OMY_CFG import passed under installed Isaac Lab 3.0,
without installing or modifying packages. This reduces the immediate need for
a second simulator installation but does not establish physics compatibility.
User now prefers headless runs with screenshot/video deliverables.

Reproduce the configured preview with a fresh output directory:

```bash
python3 scripts/run_omy_workstation_preview.py --output outputs/omy_workstation_review_next
```

The launcher defaults to headless; --gui keeps a visible window open. The
machine-specific interpreter and source paths are in
configs/omy_tracking/preview.json. It checks expected artifacts because Kit
shutdown can mask a Python failure with a zero process exit code.

## Warehouse preview passed

Headless outputs/omy_workstation_preview_005 completed in approximately
90 seconds of Kit elapsed time on first resource load. Its overview.png and
sensor.png were visually inspected: authored warehouse floor, brick walls,
shelving and boxes render behind the packing table, and the entire OMY is
inside the sensor frame. Source assets are referenced without destructive edits.
This is a static scene milestone, not task data: no target is selected yet,
no physical motion has been validated, and no dataset performance is claimed.
Next gate: inspect small NVIDIA target assets and actual finger clearance,
then validate fixed-base articulation and camera/control timing for task A.

## Simplified background and dynamics blocker

User requested an affordable floor/wall background instead of the warehouse.
preview.json now disables the warehouse and configures matte floor and painted
wall materials. Preview 007 rendered successfully and was visually inspected;
original table, OMY and full-size target references remain. Prior previews remain.

The sequence prerequisite dynamics probe failed before any trajectory:
outputs/omy_articulation_check_002/error.txt records sim.reset() failing in
get_joint_acc_from_joint_vel: Warp expects an array but receives ProxyArray.
This is in the installed Isaac Lab 3 / PhysX / Warp integration. The earlier
successful OMY_CFG import did not validate articulation dynamics. No validated
sequence has been generated. Resolve runtime compatibility before task A/B/C.

## First physical motion preview

Native Isaac Sim PhysX angular joint drives run without the failing Isaac Lab
ProxyArray path. scripts/render_omy_motion_check.py produced 120 frames,
outputs/omy_motion_check_002/motion.gif, three stills and diagnostics.json.
The midpoint image visibly shows arm bending. Commands perform a small smooth
out-and-back motion using authored joints, without teleporting links.
This is a motion debug preview only, not validated task A, grasp or dataset
export: depth/masks, FK audit, contact checks and synchronization remain.
The installed OpenCV MP4 encoder was unavailable, so the preview is an animated
GIF. Prior unsuccessful output directories are preserved.
