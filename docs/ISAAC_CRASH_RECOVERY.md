# Isaac renderer crash recovery

Last verified: 2026-09-11 (Asia/Seoul)

## Diagnosis

The failure is below the EA-FoundationPose and ROBOTIS Lab application layers.
Two independent launches crashed with the same native backtrace:

- a minimal `AppLauncher` program that only opens the bottle USD
- Isaac Lab's unchanged `run_usd_camera.py --headless --enable_cameras`

Both crash dumps show driver 595.91.07 and terminate in
`librtx.scenedb.plugin.so` while the RTX Hydra engine is being created. They
have ample free system memory and crash before project scene code executes.

Historical logs on this same host establish the most useful control. Isaac Sim
5.1 reached `app ready` and `Isaac Sim Full App is loaded` four times in March
2026 with driver 580.126.09. A public Isaac Lab report independently records the
same SceneDB crash after moving from driver 595.71.05 to 595.84:

<https://github.com/isaac-sim/IsaacLab/issues/6785>

NVIDIA lists 580.65.06 as the tested Linux driver for Isaac Sim 5.1:

<https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html>

The renderer regression and the Python environment conflicts are separate.
`pip check` currently reports nine conflicts in the shared `env_isaaclab`,
including wrong `numpy`, `packaging`, `sympy`, and `torchaudio` versions. One
log also shows the resulting SciPy/NumPy ufunc error while loading the ROS 2
bridge. Repairing that shared environment in place risks breaking other local
robotics projects.

## Recommended recovery path

1. Move the host from driver 595.91.07 back to the Ubuntu 580 production branch.
   The current Ubuntu repository offers `nvidia-driver-580`; this host previously
   worked with 580.126.09. A reboot is required after changing the kernel driver.
   On this Ubuntu host, the intended package-manager sequence is:

   ```bash
   apt-cache policy nvidia-driver-580
   sudo apt update
   sudo apt install nvidia-driver-580
   sudo reboot
   ```

2. Verify the loaded kernel and user-space driver agree:

   ```bash
   nvidia-smi
   dkms status
   modinfo nvidia | rg '^version:'
   ```

3. Avoid the conflicted shared Conda environment. Build/start the existing
   ROBOTIS Lab Docker image, which pins Isaac Sim 5.1 and Isaac Lab 2.3.x:

   ```bash
   cd /home/mjcha/robotis_lab
   ./docker/container.sh start
   ```

4. Run an unchanged renderer gate in that clean environment before running any
   EA code. Success means the process reaches `app ready`, creates a camera
   render product, emits at least one RGB/depth frame, and exits with status 0.
5. Mount or copy only the EA capture entry point into the running container and
   write the export to the host project. Do not copy weights or datasets into
   Git.

The RTX 3070 has 8 GB VRAM, below NVIDIA's published 16 GB minimum for Isaac
Sim 5.1. This short one-environment, 848 x 480 capture may still work—as the old
local startup logs suggest—but it remains an unsupported configuration. Keep
the scene to one environment and one active camera, use headless mode, and close
FoundationPose containers before launching Isaac to maximize available VRAM.

## Acceptance gates

Run these in order and stop at the first failure:

1. `nvidia-smi` works after reboot and reports a 580-series driver.
2. A CUDA container sees the GPU.
3. The unchanged Isaac Lab camera tutorial exits normally.
4. The OMY capture writes ten synchronized RGB, depth, and mask images.
5. `scripts/validate_isaac_export.py` passes the capture.
6. `scripts/run_isaac_foundationpose.sh` completes and its overlays align.

## Longer-term alternative

Isaac Lab 3.0 beta 2 patch 1 supports Isaac Sim 6.0.1. Isaac Sim 6.0.1 was
tested with Linux driver 595.58.03, but the same RTX 4080/16 GB minimum applies.
Moving to this stack should be done in a separate Python 3.12 environment and
requires migrating ROBOTIS Lab 2.x APIs; it is not the quickest path to the
pending ten-frame control capture.

- <https://github.com/isaac-sim/IsaacLab/releases/tag/v3.0.0-beta2.patch1>
- <https://docs.isaacsim.omniverse.nvidia.com/6.0.1/installation/requirements.html>
