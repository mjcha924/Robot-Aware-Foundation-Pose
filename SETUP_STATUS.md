# EA-FoundationPose setup status

Last updated: 2026-09-10 (Asia/Seoul)

## Current checkpoint

- Project workspace: `/home/mjcha/effector-aware-foundationpose`
- Existing FoundationPose checkout: `third_party/FoundationPose`
- Pinned upstream commit: `a1b694b83e633c2cb6115b9063d940a687759392`
- Physical GPU: NVIDIA GeForce RTX 3070 (not the RTX 3060 initially assumed)
- Ubuntu 22.04.5, kernel 6.8.0-111-generic
- NVIDIA driver/DKMS 595.91.07 is installed and the kernel module is loaded
- Docker 29.4.0 and NVIDIA Container Toolkit 1.19.0 are installed
- System CUDA compiler (`nvcc`) is absent
- About 281 GiB disk space and 31 GiB RAM were available
- Both required FoundationPose checkpoint sets are downloaded and verified
- The 737-frame `mustard0` RGB-D demo and textured mesh are installed locally
- No EA-FoundationPose method code implemented
- The official FoundationPose image is pulled and tagged `foundationpose:latest`
- The pinned checkout's native `mycpp` extension is built
- The unchanged pretrained model-based demo passed on all 737 frames
- No simulation or training job has been started

## Repository progress

- Initialized the project as a local Git repository on branch `main`
- Registered `third_party/FoundationPose` as a submodule at the pinned commit
- Added the minimal README, directory scaffold, and artifact exclusions
- Defined the versioned Isaac export contract and added a dependency-free
  validator with passing unit tests
- Downloaded weights, demo data, simulator exports, and generated outputs are
  excluded from Git
- Recovered the established local GitHub identity from existing repository
  history and used it only for this repository
- Created the initial local commit
- A GitHub remote has not been created or pushed

The Codex sandbox does not expose `/dev/nvidia*`, the Docker socket, or the
user's supplementary groups. The host gate was therefore rerun with host access
and passed on 2026-09-10.

## Decisions so far

1. First milestone is an unchanged pretrained, model-based FoundationPose demo.
2. The official Docker route is the smallest reliable starting path because
   upstream recommends it and local Conda would require installing CUDA plus
   compiling PyTorch3D and NVDiffRast.
3. Keep FoundationPose isolated as a pinned Git submodule in our own project.
4. Create a private GitHub repository for collaboration with the user's friend.
5. Do not begin Isaac Sim integration or candidate pruning until the baseline
   demo passes and later URDF/camera overlay alignment is trustworthy.

## Baseline passed

The host and container checks completed successfully:

```bash
cd /home/mjcha/effector-aware-foundationpose
nvidia-smi
id
docker info
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

The native and containerized checks both detected an NVIDIA GeForce RTX 3070
with driver 595.91.07. Docker Engine 29.4.0 is running, the user is in the
`docker` group, the NVIDIA runtime/CDI devices are registered, and the CUDA
12.4.1 container successfully ran `nvidia-smi`.

The unchanged `python run_demo.py` baseline then completed all 737 frames using
the default 252 pose candidates, five registration refinements, and two tracking
refinements. A second visualization-enabled run saved 737 overlays and poses
under `outputs/foundationpose_baseline/`; representative first, middle, and last
frames were visually aligned. See `docs/BASELINE.md` for provenance, hashes,
environment versions, and numerical validation.

## Next actions

1. Create a private GitHub repository and push `main`. The GitHub CLI is not
   installed and no GitHub token is exposed. Existing local history strongly
   indicates the owner is `chlgkals07`.
2. Export one short static-object sequence using the contract in
   `docs/ISAAC_EXPORT_CONTRACT.md` and run `scripts/validate_isaac_export.py`.
3. Validate its camera/URDF overlay
   before implementing end-effector-aware candidate pruning.
4. Preserve the upstream baseline as the control; place all new method code in
   this repository rather than modifying the FoundationPose submodule.

## License warning

FoundationPose uses the NVIDIA Source Code License, including a non-commercial
research/evaluation limitation and redistribution conditions. Do not commit or
redistribute its downloaded pretrained weights or demo data.
