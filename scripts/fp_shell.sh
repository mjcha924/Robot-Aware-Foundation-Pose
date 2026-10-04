#!/usr/bin/env bash
# Enter the FoundationPose container (created on first use, reused afterwards).
# Inside, the working directory is third_party/FoundationPose, so:  python run_demo.py
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME=fp

# Fall back to the local desktop session if this shell has no DISPLAY.
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-/run/user/$(id -u)/gdm/Xauthority}"
xhost +si:localuser:root >/dev/null 2>&1 || echo "warning: xhost failed; GUI windows may not open"

if ! docker container inspect "$NAME" >/dev/null 2>&1; then
  docker run -d --name "$NAME" --gpus all --env NVIDIA_DISABLE_REQUIRE=1 --ipc=host \
    -v /tmp/.X11-unix:/tmp/.X11-unix -v "$ROOT":/proj -w /proj/third_party/FoundationPose \
    foundationpose:latest sleep infinity >/dev/null
fi
docker start "$NAME" >/dev/null

# Build the native extension once (idempotent).
docker exec "$NAME" bash -c '[ -f /proj/third_party/FoundationPose/mycpp/build/mycpp*.so ] || bash build_all.sh >/dev/null 2>&1 || true'

exec docker exec -it -e DISPLAY="$DISPLAY" -w /proj/third_party/FoundationPose "$NAME" bash
