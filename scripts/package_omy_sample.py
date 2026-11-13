"""Package an explicitly selected diagnostic interval as an unaccepted handoff sample."""
import argparse,json,hashlib,shutil,os
from pathlib import Path
import numpy as np

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('source',type=Path);p.add_argument('output',type=Path)
p.add_argument('--model',type=Path,required=True)
p.add_argument('--robot-model',type=Path,default=Path('outputs/omy_robot_geometry_001'))
p.add_argument('--inventory',type=Path,default=Path('outputs/omy_physics_inventory_001/physics_inventory.json'))
p.add_argument('--start',type=int,required=True);p.add_argument('--stop',type=int,required=True)
p.add_argument('--task',choices=['A','B','C'],required=True);p.add_argument('--object',required=True)
p.add_argument('--seed',type=int,required=True);p.add_argument('--parent-group',required=True)
p.add_argument('--split',choices=['train','validation'],required=True)
a=p.parse_args()
all_rows=[json.loads(x) for x in (a.source/'frames.jsonl').read_text().splitlines()]
if not 1<=a.start<a.stop<=len(all_rows):p.error('Interval must retain an actual preceding robot state')
rows=all_rows[a.start:a.stop];diagnostics=json.loads((a.source/'diagnostics.json').read_text())
if any('T_world_robot_links' not in r for r in rows):p.error('This capture lacks recorded per-link validation poses')
a.output.mkdir(parents=True,exist_ok=False)
for folder in ['rgb','depth','masks','mesh','robot','validation']:(a.output/folder).mkdir()
# Immutable artifacts can share inodes, but all references remain inside the package.
def preserve_copy(source,destination):
 try:os.link(source,destination)
 except OSError:shutil.copy2(source,destination)
for name in ['capture_scene.usda','capture_provenance.json','generator_snapshot.py']:
 if (a.source/name).is_file():preserve_copy(a.source/name,a.output/'validation'/name)
for source in a.model.iterdir():
 if source.is_file() and source.suffix in ('.obj','.mtl','.png','.jpg','.json'):
  preserve_copy(source,a.output/'mesh'/source.name)
robot=json.loads((a.robot_model/'manifest.json').read_text())
links=[]
for link in robot['links']:
 preserve_copy(a.robot_model/link['path'],a.output/'robot'/link['path'])
 links.append({'name':link['name'],'path':'robot/'+link['path'],'sha256':link['sha256'],
               'vertex_count':link['vertices'],'triangle_count':link['triangles']})
shutil.copy2(a.inventory,a.output/'robot'/'joint_inventory.json')
camera=json.loads((a.source/'camera.json').read_text());np.savetxt(a.output/'cam_K.txt',camera['K'])
def observation(row,frame_id):
 return {'frame_id':frame_id,'timestamp_s':row['timeline_s'],
         'joint_positions':row['measured_joint_positions'][0],
         'joint_velocities':row['measured_joint_velocities'][0],
         'T_world_camera':row['T_world_camera'],'T_world_robot_base':row['T_world_robot_base']}
previous=observation(all_rows[a.start-1],None)
(a.output/'previous_robot_state.json').write_text(json.dumps(previous,indent=2))
with (a.output/'frames.jsonl').open('w') as ground_truth,(a.output/'robot_observations.jsonl').open('w') as observations,(a.output/'validation'/'contacts.jsonl').open('w') as contacts:
 for index,row in enumerate(rows):
  stem=f'{index:06d}';original=f'{row["frame"]:06d}.png'
  for folder in ['rgb','depth','masks']:preserve_copy(a.source/folder/original,a.output/folder/(stem+'.png'))
  record=observation(row,stem)
  observations.write(json.dumps(record)+'\n')
  record.update({'parent_frame_id':row['frame'],'T_world_effector':row['T_world_effector'],
                 'T_world_object_gt':row['target_usd_world'],'T_world_robot_links':row['T_world_robot_links'],
                 'task_phase':row['phase'],'diagnostic_status':'unaccepted_sample'})
  ground_truth.write(json.dumps(record)+'\n')
  contacts.write(json.dumps({'frame_id':stem,'events':row.get('validation_contact_events'),
                             'normal_forces_N':row.get('validation_contact_normal_forces_N')})+'\n')
manifest={'schema_version':'1.0','sequence_id':a.output.name,'frame_count':len(rows),'frames_file':'frames.jsonl',
 'units':{'length':'meter','depth_encoding':'uint16_mm','depth_scale_to_m':.001},
 'image':{'width':640,'height':480,'rgb_format':'png_rgb8','depth_format':'png_uint16','mask_format':'png_uint8_binary'},
 'camera':{'model':'pinhole','convention':'opencv_x_right_y_down_z_forward','K':camera['K'],'fixed_within_episode':True},
 'mesh':{'path':'mesh/object.obj','units':'meter','T_object_mesh':np.eye(4).tolist()},
 'segmentation':{'object_id':1,'initial_mask_only':False,'protocol':'oracle_visible_mask_for_equal_method_comparison'},
 'robot_geometry':{'version':1,'units':'meter','pose_convention':'T_world_link_origin','pose_source':'measured_simulator_link_transforms_validation_only','links':links},
 'omy_tracking':{'version':1,'status':'sample_validation_pending','accepted':False,'task':a.task,'object':a.object,
   'seed':a.seed,'split':a.split,'parent_group':a.parent_group,'parent_interval':[a.start,a.stop],
   'capture_hz':30,'physics_hz':120,'joint_names':diagnostics['joint_names'],'joint_units':'radians',
   'robot_observations_file':'robot_observations.jsonl','previous_robot_state_file':'previous_robot_state.json',
   'joint_inventory':'robot/joint_inventory.json','physical_grasp':a.task in ('B','C'),'attachment_used':False,
   'generation_arguments':diagnostics['arguments'],'render_settings':diagnostics['render_settings'],
   'scene_metadata':{'path':'validation/capture_scene.usda','sha256':hashlib.sha256((a.source/'capture_scene.usda').read_bytes()).hexdigest(),'lighting_source':'USD light definitions /World/Fill and /World/Key'},
   'physics':diagnostics.get('physics_metadata'),'contact_body_order':diagnostics['contact_body_order'],
   'robot_source_revision':robot['source_revision'],'object_symmetry':'no_exact_textured_symmetry_declared',
   'truth_boundary':'Reader whitelists robot observations; caller supplies previous estimated object pose.'},
 'source':{'diagnostic_parent':str(a.source.resolve()),'parent_diagnostics_sha256':hashlib.sha256((a.source/'diagnostics.json').read_bytes()).hexdigest()}}
(a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'sample':str(a.output),'frames':len(rows),'duration_s':len(rows)/30,'accepted':False}))
