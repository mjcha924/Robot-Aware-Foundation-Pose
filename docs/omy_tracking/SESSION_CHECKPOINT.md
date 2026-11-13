# OMY pilot session checkpoint — 2026-11-14

## Resume instruction

Paste this into the next Codex session:

> Read docs/omy_tracking/SESSION_CHECKPOINT.md and docs/omy_tracking/PIPELINE_HANDOVER.md.
> Inspect the current Git status and remote before editing. Continue on
> feature/omy-tracking-dataset, preserve all files and results, and do not regenerate
> the completed pilot. First report the remaining dataset-publication and
> FoundationPose integration work.

## Workspace and source control

- Workspace: /home/a09/mj-projects/omy-tracking-dataset
- Repository: https://github.com/mjcha924/Robot-Aware-Foundation-Pose
- Required working branch: feature/omy-tracking-dataset.
- Published pilot commit before this checkpoint: beee022d8985ce7129779ee501db37780c094461.
- The local feature branch was synchronized with that published commit.
- Original local publication commits 1b96807 and 67dad8b are preserved under
  archive/omy-pilot-local-67dad8b. The published pilot has the same repository tree.
- OMY_Dataset_Codex_Prompt.md remains an untracked local user brief. Preserve it.
- Do not reset, clean, force-push, overwrite outputs, or work on main.
- GitHub app account verified as mjcha924. Publishing through the app succeeded.
  Terminal HTTPS push failed because no terminal credentials were configured.
  App access and terminal Git authentication are separate; recheck after login.
  Never request private keys or write credentials to files or logs.

## What the 45 sequences mean

The original brief, section 9, specifies 3 objects × 3 tasks × 5 variants = 45
task clips. These are not 45 complete pick-and-place cycles.

| Object | A: noncontact occlusion | B: physical grasp/lift/carry | C: place/release/retreat |
| --- | ---: | ---: | ---: |
| Gelatin box | 5 | 5 | 5 |
| Large marker | 5 | 5 | 5 |
| Banana | 5 | 5 | 5 |

The variants change starting position/orientation and manipulation trajectories.
The workstation and camera are shared, so clips can look similar. B/C may share
a physical parent, as explicitly allowed in the brief; correlated parents must
remain in one split. Repaired C clips use distinct parent captures where needed.

- Accepted: 45/45; 11,999 frames at 30 Hz, approximately 8–10 seconds per clip.
- Split: 36 train / 9 validation.
- Payload: 37,654 checksum entries; 7.543 GB logical / 3.597 GB with hardlinks.
- All 90 RGB/geometry-overlay review videos passed the final decode/count audit.
- Portable reader and canonical robot surface helpers passed with privileged
  label-file access blocked. This is not a FoundationPose accuracy result.
- Two-second holds passed across all 25 selected manipulation parent captures.

## Authoritative local data — preserve it

All paths below are relative to the workspace:

- Clean delivered data: outputs/omy_pilot/dataset/
- Accepted index and replacement history: outputs/omy_pilot/index.json
- Dataset checksums: outputs/omy_pilot/accepted_checksums.sha256
- Final cohort audit: outputs/omy_pilot/cohort_audit_final_001.json
- Reader audit: outputs/omy_pilot/portable_reader_audit_001.json
- Hold audit: outputs/omy_pilot/two_second_hold_audit_001.json
- Checksum verification: outputs/omy_pilot/checksum_verification_001.json
- Representative MP4: outputs/omy_pilot/pilot_demo.mp4
- MP4 segment provenance: outputs/omy_pilot/pilot_demo.json

Use dataset/, not older accepted/, diagnostic, retry, or handoff folders.
Historical failures and withdrawn clips are deliberately retained outside the
clean export. No regeneration is needed to resume.

## Visual summary and its scope

Published visuals are in [the handover](PIPELINE_HANDOVER.md#visual-results):

- [Grasp GIF](media/grasp_three_objects.gif): three B clips, one per object.
- [Release GIF](media/release_three_objects.gif): three C clips, one per object.
- [Occlusion figure](media/occlusion_example.png): three frames from banana A.
- [Visual provenance](media/visual_sources.json): exact clip IDs and crop details.

The local 80.4-second MP4 contains nine clips: variant 00 of A/B/C for each object.
Neither the GIFs nor that MP4 show all 45 sequences.
[PILOT_RESULTS.md](PILOT_RESULTS.md#sequences) lists every accepted clip; its
per-sequence video links point to local outputs and are not GitHub downloads.

## Publication status and the user's latest questions

Code, configurations, manifests, compact audits/checksums, handover, and GIFs
are published on the feature branch. The full dataset and pilot MP4 are not.

The original brief explicitly says to keep datasets and outputs outside Git.
The user subsequently asked whether the full dataset should also be available
on GitHub and whether 7.5 GB is too large for the repository. We recommended
versioned GitHub Release attachments, each smaller than 2 GiB, with checksums
and extraction instructions, instead of ordinary Git commits.

No release, release archive, dataset upload, or download script has been created.
Do not imply that cloning the repository downloads the dataset. The currently
available GitHub app tools have no release-asset upload operation; terminal
authentication or another supported upload route must be established to publish
release assets. The latest user action is to save this checkpoint before signing
out of Codex, not to start a long upload or another generation run.

## Important implementation choices

- Real NVIDIA table and YCB objects, actual OMY articulation and gripper, simple
  floor/wall as requested; no warehouse background.
- Physical finger contacts; no hidden attachment or object teleportation.
- Ten original marker/banana C clips failed a later passive-joint limit audit
  and were withdrawn. All ten have validated replacements in the final 45.
- Preserve the release correction in render_omy_motion_check.py:
  --freeze-release-tcp --release-ramp-frames 30 --release-open-angle 0.02
  --release-lift-distance 0.04 --release-lift-frames 15.
  Clearance begins only after two contact-free frames with continuing support.
- Preserve configs/omy_tracking/postflight_acceptance.json: finite states and
  authored joint limits, with only the documented 0.001-rad numerical allowance.
- Run capture and geometry replay sequentially.
- Keep GT object poses, contact/task/grasp labels out of inference inputs.
  Tracking must propagate previous estimated poses and reuse canonical robot
  surface samples across time.

## Environment

- RTX 5080, 16 GB; Isaac Sim 6.2, Python 3.12.
- Simulator Python:
  /home/a09/robotics/isaaclab-so101/examples/isaaclab/.venv/bin/python
- cyclo_lab revision: a44392325d2ccb250ba77ece3237b55ba1f206e1.
- Native PhysX capture works; the earlier Isaac Lab Warp reset issue was bypassed,
  not fixed. See [inspection](inspection.md) and [handover](PIPELINE_HANDOVER.md).
- Use imageio_ffmpeg for review-video decoding; this environment's OpenCV H264
  decoding was unsuccessful.
- Do not modify system drivers or assume another machine has the same assets.

## Remaining work, in order

- [ ] Establish a supported dataset-publication route; package the clean dataset,
      retaining hardlinks where possible, then verify archives and publish
      checksums/download instructions. Publish the representative MP4 too.
- [ ] Have the partner load a sample and confirm intended model inputs.
      This confirmation remains pending; proceeding with pilot generation was
      explicitly authorized and recorded in review_decision_20261113.json.
- [ ] Run actual FoundationPose initialization, especially the partially visible
      held-object preroll of task C. Capture validation does not establish this.
- [ ] Integrate estimated-pose feedback and inference-available robot features.
      Do not implement the partner's trainable refiner without a new request.
- [ ] Evaluate tracking with matched masks, initialization, and split protocols.
      FoundationPose initialization and tracking accuracy are currently untested.
- [ ] Agree on scope and measured cost before expansion. No 720-sequence run
      has been launched or authorized.

Keep [PLAN_AND_PROGRESS.md](PLAN_AND_PROGRESS.md) updated as work continues.
