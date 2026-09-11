#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="${FOUNDATIONPOSE_IMAGE:-foundationpose:latest}"
display="${DISPLAY:-:0}"
xauthority="${XAUTHORITY:-/run/user/$(id -u)/gdm/Xauthority}"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <sequence-dir> [run_isaac_sequence.py options...]" >&2
  exit 2
fi

sequence="$(realpath "$1")"
shift
case "$sequence" in
  "$project_root"/*) ;;
  *) echo "Sequence must be inside $project_root so Docker can access it." >&2; exit 2 ;;
esac
container_sequence="/workspace/${sequence#"$project_root"/}"

for required_path in \
  "$project_root/third_party/FoundationPose/mycpp/build" \
  "$project_root/third_party/FoundationPose/weights/2023-10-28-18-33-37/model_best.pth" \
  "$project_root/third_party/FoundationPose/weights/2024-01-11-20-02-45/model_best.pth"
do
  if [[ ! -e "$required_path" ]]; then
    echo "Missing FoundationPose prerequisite: $required_path" >&2
    exit 1
  fi
done

if [[ ! -S /tmp/.X11-unix/X0 || ! -r "$xauthority" ]]; then
  echo "FoundationPose rasterization requires the active X11 display and authority file." >&2
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
  python /workspace/scripts/run_isaac_sequence.py "$container_sequence" "$@"
