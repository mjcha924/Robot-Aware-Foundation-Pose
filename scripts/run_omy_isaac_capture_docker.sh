#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
robotis_lab_root="${ROBOTIS_LAB_ROOT:-/home/mjcha/robotis_lab}"
robotis_image="${ROBOTIS_LAB_IMAGE:-robotis/robotis-lab:latest}"

if [[ ! -d "$robotis_lab_root/source/robotis_lab/robotis_lab" ]]; then
  echo "ROBOTIS Lab package is missing: $robotis_lab_root/source/robotis_lab/robotis_lab" >&2
  exit 1
fi
if ! docker image inspect "$robotis_image" >/dev/null 2>&1; then
  echo "ROBOTIS Lab image is missing: $robotis_image" >&2
  echo "Build it with: cd $robotis_lab_root && ./docker/container.sh build" >&2
  exit 1
fi

docker run --rm \
  --gpus all \
  --network host \
  --shm-size 16g \
  --env ACCEPT_EULA=Y \
  --env PRIVACY_CONSENT=Y \
  --env PYTHONPATH=/workspace/robotis_lab/source/robotis_lab \
  --volume "$project_root:/workspace/ea-foundationpose" \
  --volume "$robotis_lab_root/source:/workspace/robotis_lab/source:ro" \
  "$robotis_image" \
  /isaac-sim/python.sh \
  /workspace/ea-foundationpose/scripts/capture_omy_isaac.py \
  --robotis-lab-root /workspace/robotis_lab \
  --output /workspace/ea-foundationpose/data/isaac_exports/omy_bottle_short \
  --headless \
  --enable_cameras \
  "$@"
