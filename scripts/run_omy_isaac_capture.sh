#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
robotis_lab_root="${ROBOTIS_LAB_ROOT:-/home/mjcha/robotis_lab}"
isaac_python="${ISAAC_PYTHON:-/home/mjcha/miniconda3/envs/env_isaaclab/bin/python}"

if [[ ! -x "$isaac_python" ]]; then
  echo "Isaac Python is not executable: $isaac_python" >&2
  exit 1
fi
if [[ ! -d "$robotis_lab_root/source/robotis_lab/robotis_lab" ]]; then
  echo "ROBOTIS Lab package is missing: $robotis_lab_root/source/robotis_lab/robotis_lab" >&2
  exit 1
fi

PYTHONPATH="$robotis_lab_root/source/robotis_lab${PYTHONPATH:+:$PYTHONPATH}" \
  "$isaac_python" "$project_root/scripts/capture_omy_isaac.py" \
  --robotis-lab-root "$robotis_lab_root" \
  --headless \
  --enable_cameras \
  "$@"
