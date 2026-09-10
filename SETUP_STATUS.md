# EA-FoundationPose setup status

Last updated: 2026-09-10 (Asia/Seoul)

## Paused checkpoint

- Project workspace: `/home/mjcha/effector-aware-foundationpose`
- Existing FoundationPose checkout: `third_party/FoundationPose`
- Pinned upstream commit: `a1b694b83e633c2cb6115b9063d940a687759392`
- Physical GPU: NVIDIA GeForce RTX 3070 (not the RTX 3060 initially assumed)
- Ubuntu 22.04.5, kernel 6.8.0-111-generic
- NVIDIA driver/DKMS 595.91.07 is installed and the kernel module is loaded
- Docker 29.4.0 and NVIDIA Container Toolkit 1.19.0 are installed
- System CUDA compiler (`nvcc`) is absent
- About 281 GiB disk space and 31 GiB RAM were available
- No FoundationPose weights/demo data downloaded
- No EA-FoundationPose method code implemented
- Pulled only the CUDA 12.4.1 base image used for the GPU smoke test
- No FoundationPose image, large data download, simulation, or training job started

## Repository progress

- Initialized the project as a local Git repository on branch `main`
- Registered `third_party/FoundationPose` as a submodule at the pinned commit
- Added the minimal README, directory scaffold, and artifact exclusions
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

## Host gate passed

The following checks completed successfully:

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

The next repository action is to create a private GitHub repository and push
`main`. The GitHub CLI is not installed and no GitHub token is exposed. Existing
local remotes and commits strongly indicate that the owner is `chlgkals07`.

Next, create the private GitHub remote, pull the official FoundationPose image,
obtain only the two model-based weight sets (`2023-10-28-18-33-37` refiner and
`2024-01-11-20-02-45` scorer) plus demo data, build the native extension, and
run `python run_demo.py` unchanged.

## License warning

FoundationPose uses the NVIDIA Source Code License, including a non-commercial
research/evaluation limitation and redistribution conditions. Do not commit or
redistribute its downloaded pretrained weights or demo data.
