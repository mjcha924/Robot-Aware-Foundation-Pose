"""Materialize only the current 45 selections into a clean, portable dataset folder."""
import argparse,hashlib,json,os,shutil
from pathlib import Path
from check_omy_joint_limits import audit_sample
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path('outputs/omy_pilot'));a=p.parse_args()
index_path=a.root/'index.json';index=json.loads(index_path.read_text());assert len(index['accepted'])==45
output=a.root/'dataset';staging=a.root/'dataset.building'
if output.exists() or staging.exists():p.error('Preserve existing export; choose a new root/version')
staging.mkdir();manifest={'sequence_count':45,'capture_hz':30,'sequences':{},'units':{'length':'metres','joints':'radians','depth_png':'uint16 millimetres; zero invalid'},'camera_axes':'OpenCV: +X right, +Y down, +Z forward','transform_convention':'T_A_B maps B into A using column vectors','tracking_accuracy_evaluated':False}
def copy_file(source,destination):
 source=Path(source)
 if source.suffix in ('.json','.jsonl','.py','.usda','.txt','.md'):return shutil.copy2(source,destination)
 try:os.link(source,destination)
 except OSError:shutil.copy2(source,destination)
 return destination
for episode,entry in sorted(index['accepted'].items()):
 source=Path(entry['path']);state=audit_sample(source);assert state['passed'],(episode,state)
 target=staging/episode;shutil.copytree(source,target,copy_function=copy_file)
 (target/'validation/joint_limits_postflight.json').write_text(json.dumps(state,indent=2)+'\n')
 manifest['sequences'][episode]={'path':episode,'frames':entry['frames'],'split':entry['split'],'parent_group':entry['parent_group'],'selection_proof':str(Path(episode)/'validation/pilot_acceptance.json')}
 entry['source_selection_path']=entry['path'];entry['path']=str(output/episode)
reader=staging/'reader';reader.mkdir()
for name in ['read_omy_tracking_sample.py','omy_robot_surface.py','omy_kinematics.py']:shutil.copy2(Path('scripts')/name,reader/name)
(reader/'requirements.txt').write_text('numpy\nPillow\nscipy\n')
policies=staging/'validation_policies';policies.mkdir()
for name in ['acceptance.json','postflight_acceptance.json']:shutil.copy2(Path('configs/omy_tracking')/name,policies/name)
(staging/'dataset_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(staging/'README.md').write_text('''# OMY 45-sequence pilot

This directory contains only current selections. There are five examples per
object/task pair: gelatin box, large marker, banana × A noncontact occlusion,
B physical grasp/carry, C place/release. Frame rate is 30 Hz at 640×480.

Each sequence includes RGB, uint16-mm optical-axis depth (zero invalid), masks,
textured object CAD, canonical robot meshes and joint inventory, measured robot
states, calibration, privileged labels, validation evidence, and two MP4s.
`dataset_manifest.json` lists the 36 train / 9 validation clips and parent groups.
Replacement C clips can have a different physical parent from B; their variant
split is preserved. Clips derived from one parent never cross splits.

## Reader

Install dependencies listed in `reader/requirements.txt`, then add `reader/` to
your Python path and import `read_omy_tracking_sample.read_tracking_input`.
Pass a sequence directory, frame index, and the previous **estimated** object
pose as a 4×4 `T_camera_object` matrix. Initialize frame 0 externally using the
object model and your declared segmentation/initialization protocol.

The reader accesses only current RGB-D, measured robot observations, calibration,
and geometry. It never reads `frames.jsonl` or `validation/` ground truth.
`oracle_mask=True` is an explicitly separate oracle-segmentation comparison.
The same canonical surface points should be reused across consecutive frames.

Transforms use column vectors: T_A_B maps B to A. Camera axes are OpenCV
(+X right, +Y down, +Z forward); poses are metres, joints radians, time seconds.
The reader converts PNG depth from millimetres to metres. The preceding measured
robot state is included for the first frame of each clip.

Pilot selection is established by `validation/pilot_acceptance.json`; the earlier
immutable technical report may still say `accepted_pilot_sequence: false`.
Every final clip also passes the independent postflight joint-limit check.
Earlier withdrawn releases are preserved outside this clean dataset directory.

The user authorized capture while partner loading review remained pending.
FoundationPose initialization and tracking accuracy have not been evaluated.
C starts with an already held, partially visible object. Contact, phase, success,
and object-GT labels are for training/evaluation/validation, not inference inputs.
''')
staging.rename(output)
snapshot=a.root/'index.before_final_export_001.json'
if snapshot.exists():raise RuntimeError('Index snapshot already exists')
shutil.copy2(index_path,snapshot);index['final_dataset']=str(output);index['status']='complete_pending_final_audit'
temporary=index_path.with_suffix('.json.tmp');temporary.write_text(json.dumps(index,indent=2)+'\n');temporary.replace(index_path)
print(json.dumps({'dataset':str(output),'sequences':45,'next':'Run independent cohort audit before declaring completion.'}))
