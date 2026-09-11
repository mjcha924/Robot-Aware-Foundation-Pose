# Resume EA-FoundationPose after reboot

Handoff saved: 2026-09-11 (Asia/Seoul)

> **Completed:** This reboot handoff was successfully resumed. Driver
> 580.178.04, Docker GPU access, Isaac capture, export validation, and the
> ten-frame FoundationPose control all passed. Continue from
> `docs/ISAAC_CONTROL.md` and `SETUP_STATUS.md`.

## Resume prompt

Start the next Codex session with:

> Resume EA-FoundationPose from `docs/RESUME_AFTER_REBOOT.md`. Continue the
> renderer gate, OMY capture, validation, and GitHub push without asking for
> approval.

## Repository checkpoint

- Workspace: `/home/mjcha/effector-aware-foundationpose`
- Branch: `main`
- Last implementation commit before this handoff: `20dc072`
- FoundationPose submodule: `a1b694b83e633c2cb6115b9063d940a687759392`
- Remote: `https://github.com/mjcha924/Effector-Aware-Foundation-Pose.git`
- Worktree was clean before adding this handoff.
- The project history was subsequently integrated with the remote placeholder
  commit and pushed to GitHub at merge commit `774c34f`.

## Reboot boundary

At handoff time, the loaded NVIDIA driver was still 595.91.07 and crashed Isaac
Sim 5.1 in `librtx.scenedb.plugin.so`. The host was subsequently changed to
580.178.04 and rebooted successfully; the checks and captures below all passed.

The user must run this in a local terminal before rebooting:

```bash
sudo apt update
sudo apt install nvidia-driver-580
sudo reboot
```

Ubuntu currently resolves `nvidia-driver-580` to 580.178.04. The transaction
replaces the 20 installed 595-series driver packages with their 580-series
counterparts. Do not run `apt autoremove` as part of this recovery.

## First checks after reboot

Run from the project root:

```bash
cd /home/mjcha/effector-aware-foundationpose
nvidia-smi
dkms status
modinfo nvidia | rg '^version:'
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

Required result: every driver check reports the 580 series and the CUDA
container sees the RTX 3070. If the kernel still reports 595, stop before Isaac
and inspect the installed packages and running kernel.

## Renderer and capture gates

The isolated ROBOTIS image `robotis/robotis-lab:latest` is already present. Its
critical NumPy, packaging, Torch, and TorchAudio versions match the Isaac 5.1
stack. Do not use the conflicted shared `env_isaaclab` for this capture.

1. Run the unchanged Isaac Lab camera tutorial inside the isolated image, or use
   the project launcher as the first practical renderer gate.
2. Capture ten frames:

   ```bash
   ./scripts/run_omy_isaac_capture_docker.sh --overwrite
   ```

3. Validate the export:

   ```bash
   python3 scripts/validate_isaac_export.py \
     data/isaac_exports/omy_bottle_short
   ```

4. Run FoundationPose:

   ```bash
   ./scripts/run_isaac_foundationpose.sh \
     data/isaac_exports/omy_bottle_short \
     --output /workspace/outputs/omy_bottle_short \
     --save-vis \
     --overwrite
   ```

5. Inspect RGB, depth, mask, camera/object, and end-effector/object alignment.
   Freeze a passing run as the Isaac control before implementing candidate
   pruning.

The RTX 3070 has 8 GB VRAM, below NVIDIA's supported minimum. Keep one simulator
environment and one 848 x 480 camera active, use headless mode, and stop other
GPU workloads during capture.

## GitHub continuation

GitHub authentication was established privately on the host. Never place a
token in this document or in a remote URL. Future updates can use:

```bash
cd /home/mjcha/effector-aware-foundationpose
git status --short
git push -u origin main
```

Weights, datasets, simulator captures, and outputs are ignored and must remain
out of Git.

## Verification already completed

- Unchanged FoundationPose baseline passed all 737 YCBInEOAT frames.
- A three-frame contract-to-FoundationPose GPU smoke test passed.
- Six unit tests pass.
- Python compilation, Bash syntax, JSON parsing, export validation, and Git
  whitespace checks pass.
- The existing `/home/mjcha/robotis_lab` worktree contains unrelated user edits
  and must not be reset or overwritten.

See `docs/PROJECT_SUMMARY.md`, `docs/ISAAC_CRASH_RECOVERY.md`, and
`docs/ISAAC_INTEGRATION.md` for the full technical record.
