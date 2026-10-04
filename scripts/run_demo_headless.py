#!/usr/bin/env python3
"""Run FoundationPose's unmodified run_demo.py without a display (run inside the container).

run_demo.py calls cv2.imshow when --debug >= 1, which crashes without DISPLAY. This stubs the
window calls and then executes the upstream script as-is. Usage (cwd = third_party/FoundationPose):
    python /proj/scripts/run_demo_headless.py --test_scene_dir ... --mesh_file ... --debug 2 --debug_dir ...
"""
import os
import runpy
import sys

import cv2

sys.path.insert(0, os.getcwd())  # upstream modules (estimater, ...) live in the cwd
cv2.imshow = lambda *args, **kwargs: None
cv2.waitKey = lambda *args, **kwargs: -1
sys.argv = ["run_demo.py", *sys.argv[1:]]
runpy.run_path("run_demo.py", run_name="__main__")
