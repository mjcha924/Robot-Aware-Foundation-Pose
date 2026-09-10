#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="$project_root/third_party/FoundationPose"
image="${FOUNDATIONPOSE_IMAGE:-foundationpose:latest}"
display="${DISPLAY:-:0}"
xauthority="${XAUTHORITY:-/run/user/$(id -u)/gdm/Xauthority}"

required_paths=(
  "$source_dir/mycpp/build"
  "$source_dir/weights/2023-10-28-18-33-37/model_best.pth"
  "$source_dir/weights/2024-01-11-20-02-45/model_best.pth"
  "$source_dir/demo_data/mustard0/mesh/textured_simple.obj"
)

for required_path in "${required_paths[@]}"; do
  if [[ ! -e "$required_path" ]]; then
    echo "Missing baseline prerequisite: $required_path" >&2
    exit 1
  fi
done

if [[ ! -S /tmp/.X11-unix/X0 || ! -r "$xauthority" ]]; then
  echo "The upstream demo requires the active X11 display and authority file." >&2
  exit 1
fi

docker run --rm \
  --gpus all \
  --ipc=host \
  --network=host \
  --user "$(id -u):$(id -g)" \
  -e DISPLAY="$display" \
  -e XAUTHORITY=/tmp/.Xauthority \
  -e QT_X11_NO_MITSHM=1 \
  -e HOME=/tmp/foundationpose-home \
  -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
  -v "$xauthority":/tmp/.Xauthority:ro \
  -v "$project_root":/workspace \
  -w /workspace/third_party/FoundationPose \
  "$image" \
  python run_demo.py "$@"
