# OMY 45-sequence pilot results

[Visual summary and pipeline handover](PIPELINE_HANDOVER.md). The per-sequence
video paths below are local workstation paths; the full RGB-D payload is not
stored in Git. Published GIFs and audit evidence are linked from the handover.

**45 / 45 accepted.** The independent cohort audit passes all 45 entries and
decodes both review videos for every entry: 90 MP4 files with exact frame counts.

- Frames: **11,999**, at 30 Hz; total clip duration 399.97 s.
- Splits: 36 train / 9 validation.
- Each object has five A, five B and five C sequences. B/C parents stay in one split.
- Accepted payload: 37,654 files; 7.543 GB logical bytes,
  3.597 GB after deduplicating hardlinked files.
- Rejected attempts retained: 5.
- Historical C clips withdrawn after the joint-limit audit: 10; all have validated replacements in this final cohort.
- Indexed batch/repair capture measurements (40 captures): median
  79.8 s; summed capture wall time 49.0 min.
  These exclude separately logged probes/retries, prior handoff preparation, and geometry replay time. Peak sampled whole-GPU
  usage: 5875 MiB, including desktop/other processes.

Evidence: `outputs/omy_pilot/cohort_audit_final_001.json` and `outputs/omy_pilot/index.json`.
Checksum list: `outputs/omy_pilot/accepted_checksums.sha256`. From `outputs/omy_pilot`, run
`sha256sum -c accepted_checksums.sha256` after copying the dataset.

Pilot selection is recorded in each manifest and `validation/pilot_acceptance.json`.
All selected clips also pass the independent finite-state and authored-joint-limit
check in `postflight_acceptance.json`. The corrected low-grasp releases freeze
the control reference and lift only after the object is supported and contact
with the robot has cleared.

The immutable technical report predates cohort selection; its original
`accepted_pilot_sequence: false` is superseded by that separate selection proof.

The user authorized proceeding while partner format review is pending.
FoundationPose initialization and tracking accuracy have **not** been evaluated.
Task C starts with an already held, partially visible object; see HANDOFF.md.
The 720-sequence main dataset was not generated.

## Sequences

| Sequence | Frames | Seconds | Split | Visible fraction | Videos |
|---|---:|---:|---|---:|---|
| asymmetric_A_00 | 240 | 8.00 | train | 0.325–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_A_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_A_00/validation/geometry_overlay.mp4) |
| asymmetric_A_01 | 240 | 8.00 | train | 0.385–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_A_01/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_A_01/validation/geometry_overlay.mp4) |
| asymmetric_A_02 | 240 | 8.00 | train | 0.266–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_A_02/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_A_02/validation/geometry_overlay.mp4) |
| asymmetric_A_03 | 240 | 8.00 | train | 0.353–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_A_03/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_A_03/validation/geometry_overlay.mp4) |
| asymmetric_A_04 | 240 | 8.00 | validation | 0.258–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_A_04/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_A_04/validation/geometry_overlay.mp4) |
| asymmetric_B_00 | 300 | 10.00 | train | 0.465–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_B_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_B_00/validation/geometry_overlay.mp4) |
| asymmetric_B_01 | 300 | 10.00 | train | 0.475–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_B_01/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_B_01/validation/geometry_overlay.mp4) |
| asymmetric_B_02 | 300 | 10.00 | train | 0.494–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_B_02/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_B_02/validation/geometry_overlay.mp4) |
| asymmetric_B_03 | 300 | 10.00 | train | 0.507–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_B_03/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_B_03/validation/geometry_overlay.mp4) |
| asymmetric_B_04 | 300 | 10.00 | validation | 0.552–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_B_04/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_B_04/validation/geometry_overlay.mp4) |
| asymmetric_C_00 | 275 | 9.17 | train | 0.107–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_C_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_C_00/validation/geometry_overlay.mp4) |
| asymmetric_C_01 | 275 | 9.17 | train | 0.124–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_C_01/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_C_01/validation/geometry_overlay.mp4) |
| asymmetric_C_02 | 274 | 9.13 | train | 0.106–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_C_02/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_C_02/validation/geometry_overlay.mp4) |
| asymmetric_C_03 | 272 | 9.07 | train | 0.102–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_C_03/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_C_03/validation/geometry_overlay.mp4) |
| asymmetric_C_04 | 267 | 8.90 | validation | 0.267–1.000 | [RGB](../../outputs/omy_pilot/dataset/asymmetric_C_04/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/asymmetric_C_04/validation/geometry_overlay.mp4) |
| box_A_00 | 240 | 8.00 | train | 0.196–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_A_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_A_00/validation/geometry_overlay.mp4) |
| box_A_01 | 240 | 8.00 | train | 0.195–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_A_01/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_A_01/validation/geometry_overlay.mp4) |
| box_A_02 | 240 | 8.00 | train | 0.184–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_A_02/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_A_02/validation/geometry_overlay.mp4) |
| box_A_03 | 240 | 8.00 | train | 0.202–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_A_03/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_A_03/validation/geometry_overlay.mp4) |
| box_A_04 | 240 | 8.00 | validation | 0.173–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_A_04/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_A_04/validation/geometry_overlay.mp4) |
| box_B_00 | 300 | 10.00 | train | 0.400–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_B_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_B_00/validation/geometry_overlay.mp4) |
| box_B_01 | 300 | 10.00 | train | 0.396–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_B_01/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_B_01/validation/geometry_overlay.mp4) |
| box_B_02 | 300 | 10.00 | train | 0.374–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_B_02/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_B_02/validation/geometry_overlay.mp4) |
| box_B_03 | 300 | 10.00 | train | 0.417–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_B_03/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_B_03/validation/geometry_overlay.mp4) |
| box_B_04 | 300 | 10.00 | validation | 0.359–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_B_04/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_B_04/validation/geometry_overlay.mp4) |
| box_C_00 | 257 | 8.57 | train | 0.000–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_C_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_C_00/validation/geometry_overlay.mp4) |
| box_C_01 | 256 | 8.53 | train | 0.000–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_C_01/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_C_01/validation/geometry_overlay.mp4) |
| box_C_02 | 249 | 8.30 | train | 0.256–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_C_02/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_C_02/validation/geometry_overlay.mp4) |
| box_C_03 | 245 | 8.17 | train | 0.137–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_C_03/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_C_03/validation/geometry_overlay.mp4) |
| box_C_04 | 243 | 8.10 | validation | 0.253–1.000 | [RGB](../../outputs/omy_pilot/dataset/box_C_04/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/box_C_04/validation/geometry_overlay.mp4) |
| cylinder_A_00 | 240 | 8.00 | train | 0.265–1.000 | [RGB](../../outputs/omy_pilot/dataset/cylinder_A_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_A_00/validation/geometry_overlay.mp4) |
| cylinder_A_01 | 240 | 8.00 | train | 0.296–1.000 | [RGB](../../outputs/omy_pilot/dataset/cylinder_A_01/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_A_01/validation/geometry_overlay.mp4) |
| cylinder_A_02 | 240 | 8.00 | train | 0.181–1.000 | [RGB](../../outputs/omy_pilot/dataset/cylinder_A_02/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_A_02/validation/geometry_overlay.mp4) |
| cylinder_A_03 | 240 | 8.00 | train | 0.274–1.000 | [RGB](../../outputs/omy_pilot/dataset/cylinder_A_03/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_A_03/validation/geometry_overlay.mp4) |
| cylinder_A_04 | 240 | 8.00 | validation | 0.161–1.000 | [RGB](../../outputs/omy_pilot/dataset/cylinder_A_04/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_A_04/validation/geometry_overlay.mp4) |
| cylinder_B_00 | 300 | 10.00 | train | 0.380–1.000 | [RGB](../../outputs/omy_pilot/dataset/cylinder_B_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_B_00/validation/geometry_overlay.mp4) |
| cylinder_B_01 | 300 | 10.00 | train | 0.375–1.000 | [RGB](../../outputs/omy_pilot/dataset/cylinder_B_01/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_B_01/validation/geometry_overlay.mp4) |
| cylinder_B_02 | 300 | 10.00 | train | 0.358–1.000 | [RGB](../../outputs/omy_pilot/dataset/cylinder_B_02/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_B_02/validation/geometry_overlay.mp4) |
| cylinder_B_03 | 300 | 10.00 | train | 0.399–1.000 | [RGB](../../outputs/omy_pilot/dataset/cylinder_B_03/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_B_03/validation/geometry_overlay.mp4) |
| cylinder_B_04 | 300 | 10.00 | validation | 0.337–1.000 | [RGB](../../outputs/omy_pilot/dataset/cylinder_B_04/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_B_04/validation/geometry_overlay.mp4) |
| cylinder_C_00 | 260 | 8.67 | train | 0.000–1.002 | [RGB](../../outputs/omy_pilot/dataset/cylinder_C_00/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_C_00/validation/geometry_overlay.mp4) |
| cylinder_C_01 | 260 | 8.67 | train | 0.000–1.000 | [RGB](../../outputs/omy_pilot/dataset/cylinder_C_01/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_C_01/validation/geometry_overlay.mp4) |
| cylinder_C_02 | 259 | 8.63 | train | 0.000–1.000 | [RGB](../../outputs/omy_pilot/dataset/cylinder_C_02/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_C_02/validation/geometry_overlay.mp4) |
| cylinder_C_03 | 255 | 8.50 | train | 0.000–1.000 | [RGB](../../outputs/omy_pilot/dataset/cylinder_C_03/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_C_03/validation/geometry_overlay.mp4) |
| cylinder_C_04 | 252 | 8.40 | validation | 0.000–1.000 | [RGB](../../outputs/omy_pilot/dataset/cylinder_C_04/review.mp4) / [overlay](../../outputs/omy_pilot/dataset/cylinder_C_04/validation/geometry_overlay.mp4) |

## Retained rejected attempts

- `box_manipulation_00_attempt_001`: validate_omy_sample.py failed; see outputs/omy_pilot/logs/box_manipulation_00_attempt_001/validate_C.log
- `asymmetric_manipulation_01_attempt_001`: validate_omy_sample.py failed; see outputs/omy_pilot/logs/asymmetric_manipulation_01_attempt_001/validate_B.log
- `asymmetric_manipulation_02_attempt_001`: validate_omy_sample.py failed; see outputs/omy_pilot/logs/asymmetric_manipulation_02_attempt_001/validate_B.log
- `release_fix_probe_001`: Smoothing alone did not prevent moving-fingertip control from lowering the wrist during release; max joint-limit excess 0.469 rad.
- `release_fix_probe_002`: Frozen control reference reduced but did not eliminate tabletop interaction; max passive-joint excess 0.188 rad. Superseded by contact-gated clearance lift.

## Validated handoff/replacement samples selected

- `box_B_00` from `outputs/omy_handoff_002/box_B_00`. Original handoff and failed alternatives preserved.
- `box_C_00` from `outputs/omy_handoff_002/box_C_00`. Original handoff and failed alternatives preserved.
- `asymmetric_B_01` from `outputs/omy_retry_samples_001/asymmetric_B_01`. Original handoff and failed alternatives preserved.
- `cylinder_C_00` from `outputs/omy_pilot/repairs/release_fix_001/candidates/cylinder_C_00_attempt_001/cylinder_C_00`. Original handoff and failed alternatives preserved.
- `cylinder_C_01` from `outputs/omy_pilot/repairs/release_fix_001/candidates/cylinder_C_01_attempt_001/cylinder_C_01`. Original handoff and failed alternatives preserved.
- `cylinder_C_02` from `outputs/omy_pilot/repairs/release_fix_001/candidates/cylinder_C_02_attempt_001/cylinder_C_02`. Original handoff and failed alternatives preserved.
- `cylinder_C_03` from `outputs/omy_pilot/repairs/release_fix_001/candidates/cylinder_C_03_attempt_001/cylinder_C_03`. Original handoff and failed alternatives preserved.
- `cylinder_C_04` from `outputs/omy_pilot/repairs/release_fix_001/candidates/cylinder_C_04_attempt_001/cylinder_C_04`. Original handoff and failed alternatives preserved.
- `asymmetric_C_00` from `outputs/omy_pilot/repairs/release_fix_001/candidates/asymmetric_C_00_attempt_001/asymmetric_C_00`. Original handoff and failed alternatives preserved.
- `asymmetric_C_01` from `outputs/omy_pilot/repairs/release_fix_001/candidates/asymmetric_C_01_attempt_001/asymmetric_C_01`. Original handoff and failed alternatives preserved.
- `asymmetric_C_02` from `outputs/omy_pilot/repairs/release_fix_001/candidates/asymmetric_C_02_attempt_001/asymmetric_C_02`. Original handoff and failed alternatives preserved.
- `asymmetric_C_03` from `outputs/omy_pilot/repairs/release_fix_001/candidates/asymmetric_C_03_attempt_001/asymmetric_C_03`. Original handoff and failed alternatives preserved.
- `asymmetric_C_04` from `outputs/omy_pilot/repairs/release_fix_001/candidates/asymmetric_C_04_attempt_001/asymmetric_C_04`. Original handoff and failed alternatives preserved.

## Additional final verification

- Portable reader and robot surface features load from the clean export with
  privileged label files blocked (`portable_reader_audit_001.json`).
- Two-second holds from all 25 selected manipulation parents pass: maximum
  arm command/measured error 0.01848 rad; measured base translation drift zero
  (`two_second_hold_audit_001.json`).
- All 37,654 checksum entries verified successfully
  (`checksum_verification_001.json`).
- [Living plan and full history](PLAN_AND_PROGRESS.md).
