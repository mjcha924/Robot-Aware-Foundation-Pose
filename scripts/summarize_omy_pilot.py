"""Write a reviewable completed-cohort report and portable file checksums."""
import argparse,hashlib,json,statistics
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--root',type=Path,default=Path('outputs/omy_pilot'))
p.add_argument('--audit',type=Path,required=True)
p.add_argument('--report',type=Path,required=True)
p.add_argument('--checksums',type=Path,required=True)
a=p.parse_args()
if a.report.exists() or a.checksums.exists():p.error('Choose fresh report/checksum paths')
index=json.loads((a.root/'index.json').read_text());audit=json.loads(a.audit.read_text())
assert len(index['accepted'])==45 and audit['passed']
rows=[];total_frames=0;splits={};files=0;logical_bytes=0;unique={}
with a.checksums.open('x') as output:
 for episode,entry in sorted(index['accepted'].items()):
  root=Path(entry['path']);meta=json.loads((root/'manifest.json').read_text())['omy_tracking']
  report=json.loads((root/'validation/acceptance.json').read_text())
  total_frames+=entry['frames'];splits[entry['split']]=splits.get(entry['split'],0)+1
  visibility=report['details']['visibility']['range']
  rows.append(f'| {episode} | {entry["frames"]} | {entry["frames"]/30:.2f} | {entry["split"]} | {visibility[0]:.3f}–{visibility[1]:.3f} | [RGB](../../{root}/review.mp4) / [overlay](../../{root}/validation/geometry_overlay.mp4) |')
  for file in sorted(root.rglob('*')):
   if not file.is_file():continue
   stat=file.stat();logical_bytes+=stat.st_size;unique[(stat.st_dev,stat.st_ino)]=stat.st_size;files+=1
   with file.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
   output.write(digest+'  '+str(file.relative_to(a.root))+'\n')
 # Include the portable reader, policies and dataset-level manifest as well.
 dataset=a.root/'dataset'
 extras=[dataset/'README.md',dataset/'dataset_manifest.json',*(dataset/'reader').rglob('*'),*(dataset/'validation_policies').rglob('*')]
 for file in sorted(extras):
  if not file.is_file():continue
  stat=file.stat();logical_bytes+=stat.st_size;unique[(stat.st_dev,stat.st_ino)]=stat.st_size;files+=1
  with file.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
  output.write(digest+'  '+str(file.relative_to(a.root))+'\n')
resources=[json.loads(path.read_text()) for path in [*(a.root/'logs').glob('*/capture.resources.json'),*(a.root/'repairs').rglob('capture.resources.json')]]
wall=[r['wall_seconds'] for r in resources];gpu=[r['peak_sampled_whole_gpu_MiB'] for r in resources if r['peak_sampled_whole_gpu_MiB'] is not None]
text=f'''# OMY 45-sequence pilot results

**45 / 45 accepted.** The independent cohort audit passes all 45 entries and
decodes both review videos for every entry: 90 MP4 files with exact frame counts.

- Frames: **{total_frames:,}**, at 30 Hz; total clip duration {total_frames/30:.2f} s.
- Splits: {splits.get('train',0)} train / {splits.get('validation',0)} validation.
- Each object has five A, five B and five C sequences. B/C parents stay in one split.
- Accepted payload: {files:,} files; {logical_bytes/1e9:.3f} GB logical bytes,
  {sum(unique.values())/1e9:.3f} GB after deduplicating hardlinked files.
- Rejected attempts retained: {len(index['rejected_attempts'])}.
- Historical C clips withdrawn after the joint-limit audit: {len(index.get('revoked_after_postflight',[]))}; all have validated replacements in this final cohort.
- Indexed batch/repair capture measurements ({len(resources)} captures): median
  {statistics.median(wall):.1f} s; summed capture wall time {sum(wall)/60:.1f} min.
  These exclude separately logged probes/retries, prior handoff preparation, and geometry replay time. Peak sampled whole-GPU
  usage: {max(gpu):.0f} MiB, including desktop/other processes.

Evidence: `{a.audit}` and `{a.root}/index.json`.
Checksum list: `{a.checksums}`. From `{a.root}`, run
`sha256sum -c {a.checksums.name}` after copying the dataset.

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
'''+ '\n'.join(rows)+'\n\n## Retained rejected attempts\n\n'
for rejection in index['rejected_attempts']:text+=f'- `{rejection["attempt"]}`: {rejection["reason"]}\n'
adopted=[(key,entry['promoted_from_handoff']) for key,entry in index['accepted'].items() if 'promoted_from_handoff' in entry]
if adopted:
 text+='\n## Validated handoff/replacement samples selected\n\n'
 for key,path in adopted:text+=f'- `{key}` from `{path}`. Original handoff and failed alternatives preserved.\n'
a.report.write_text(text)
print(json.dumps({'report':str(a.report),'frames':total_frames,'sequences':45,'files':files,'checksums':str(a.checksums)}))
