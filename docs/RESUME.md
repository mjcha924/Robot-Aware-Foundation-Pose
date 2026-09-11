# Current Codex resume handoff

Saved: 2026-09-11 (Asia/Seoul)

## Resume this exact session

After reopening a terminal, run:

```bash
resume
```

The host wrapper at `~/.local/bin/resume` resumes Codex session
`01a08a95-f15d-7793-85d3-250b7c3a457a`, selects this repository as the working
directory, and retains the user's no-approval preference.

Equivalent fallback command:

```bash
codex resume \
  --ask-for-approval never \
  --cd /home/mjcha/effector-aware-foundationpose \
  01a08a95-f15d-7793-85d3-250b7c3a457a
```

If exact-session resume is unavailable, start a new Codex session in
`/home/mjcha/effector-aware-foundationpose` and enter:

> Resume EA-FoundationPose from `docs/RESUME.md` and `SETUP_STATUS.md`.

Codex documents `codex resume` as the command for reopening a saved chat:
<https://learn.chatgpt.com/docs/codex/cli>.

## Current verified checkpoint

- Branch `main` and `origin/main` were synchronized at `7ced941` immediately
  before this handoff update.
- The pinned FoundationPose submodule remains unchanged at
  `a1b694b83e633c2cb6115b9063d940a687759392`.
- The unchanged pretrained FoundationPose baseline passed all 737 official
  YCBInEOAT mustard-bottle frames.
- NVIDIA driver 580.178.04 fixed the Isaac Sim 5.1 SceneDB crash on the RTX
  3070. Native and Docker GPU checks passed.
- Isaac Sim captured and validated ten project-generated OMY/green-tea-bottle
  frames at 848 x 480.
- FoundationPose processed all ten Isaac frames with 8.117 mm mean translation
  error and 1.196 degree mean rotation error against simulator truth.
- The dependency-free evaluator reproduces those results in camera and
  end-effector coordinates. All 12 offline tests pass.
- A representative Isaac overlay and side-by-side MP4 are committed under
  `docs/assets/` and displayed from the GitHub README.
- GitHub remote:
  `https://github.com/mjcha924/Effector-Aware-Foundation-Pose.git`.

## Deliberately unfinished work

- The pretrained FoundationPose estimator is still the experimental control;
  end-effector-aware candidate pruning has not been implemented.
- `scripts/capture_omy_isaac.py` contains an opt-in
  `--motion effector-sweep` draft. It compiles, but its first 48-frame Isaac run
  was stopped during startup at the user's request. No dynamic result was
  produced or claimed.
- A richer experiment scene with the table plus OMY gripper or LEAP hand was
  discussed and intentionally deferred.

## Recommended next session

1. Confirm the desired robot embodiment: existing OMY gripper or LEAP hand.
2. Finish and validate a longer dynamic/occlusion capture using only one
   environment and one camera to stay within the RTX 3070's 8 GB VRAM.
3. Run the unchanged FoundationPose control and `evaluate_pose_results.py` on
   that sequence.
4. Define and implement the first end-effector-aware candidate-pruning rule,
   preserving the pinned upstream submodule as the control.

Generated datasets, weights, and full inference outputs remain ignored. Do not
commit them; only intentionally selected documentation media belongs in Git.
