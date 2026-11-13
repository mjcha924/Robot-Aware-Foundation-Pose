"""Fail-closed technical acceptance for a packaged OMY handoff/pilot sample.

This does not authorize bulk generation or substitute for partner format review.
"""
import argparse,hashlib,json,subprocess,sys,shutil
from pathlib import Path
import numpy as np
from PIL import Image
from read_omy_tracking_sample import read_tracking_input
from check_omy_task_behavior import drift
from check_omy_joint_limits import audit_sample

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('sample',type=Path);p.add_argument('--model-audit',type=Path,required=True)
p.add_argument('--geometry-audit',type=Path,required=True)
p.add_argument('--gates',type=Path,default=Path('configs/omy_tracking/acceptance.json'))
a=p.parse_args();root=a.sample;manifest=json.loads((root/'manifest.json').read_text());meta=manifest['omy_tracking']
parent=Path(manifest['source']['diagnostic_parent']);start,stop=meta['parent_interval'];gates=json.loads(a.gates.read_text())
checks={};details={}
def load(path):
 return json.loads(path.read_text()) if path.is_file() else None
schema=subprocess.run([sys.executable,str(Path(__file__).with_name('validate_isaac_export.py')),str(root)],capture_output=True,text=True)
checks['schema_and_completeness']=schema.returncode==0;details['schema_output']=schema.stdout+schema.stderr
rows=[json.loads(s) for s in (root/'frames.jsonl').read_text().splitlines()]
obs=[json.loads(s) for s in (root/'robot_observations.jsonl').read_text().splitlines()]
previous=load(root/'previous_robot_state.json');timestamps=np.array([previous['timestamp_s']]+[r['timestamp_s'] for r in rows])
checks['capture_sync']=bool(len(rows)==len(obs)==stop-start and np.allclose(np.diff(timestamps),1/30,atol=1e-6,rtol=0))
checks['clip_duration']=gates['minimum_clip_duration_s']<=len(rows)/30<=gates['maximum_clip_duration_s']
checks['original_rgb_depth_masks']=True
for row in rows:
 stem=row['frame_id']+'.png';rgb=np.asarray(Image.open(root/'rgb'/stem));depth=np.asarray(Image.open(root/'depth'/stem));mask=np.asarray(Image.open(root/'masks'/stem))
 checks['original_rgb_depth_masks'] &= rgb.shape==(480,640,3) and rgb.dtype==np.uint8 and depth.shape==(480,640) and depth.dtype==np.uint16 and mask.shape==(480,640) and mask.dtype==np.uint8 and bool(np.isin(mask,[0,255]).all())
 checks['capture_sync'] &= bool(np.allclose(row['T_world_camera'],rows[0]['T_world_camera'],atol=1e-9))
geometry=load(a.geometry_audit/'report.json');selected=[]
if geometry:
 selected=[r for r in geometry['frames'] if start<=r['frame']<stop]
 complete=[r['frame'] for r in selected]==list(range(start,stop))
 checks['camera_and_object_overlay']=complete and all(r['target_mask_iou']>=.90 and (r['target_object_depth_p95_m'] is None or r['target_object_depth_p95_m']<=.003) for r in selected) and any(r['target_object_depth_samples']>0 for r in selected)
 checks['robot_fk_overlay']=complete and all(r['robot_audit_depth_samples']>100 and r['robot_audit_depth_p95_m'] is not None and r['robot_audit_depth_p95_m']<=.003 for r in selected)
 fractions=[r['visible_fraction'] for r in selected]
 valid=complete and all(v is not None and 0<=v<=1.02 for v in fractions)
 clear=sum(v>=gates['minimum_clear_visible_fraction'] for v in fractions if v is not None)
 occluded=sum(v<=gates['maximum_occluded_visible_fraction'] for v in fractions if v is not None)
 checks['amodal_visibility']=valid and clear>=gates['minimum_frames_per_visibility_portion'] and occluded>=gates['minimum_frames_per_visibility_portion'] and not any(r['touches_image_boundary'] for r in selected)
 if meta['task']=='A':checks['amodal_visibility'] &= all(v>=.8 for v in fractions[:15]+fractions[-15:])
 else:
  initial_count=gates['minimum_initial_visible_frames_by_task'][meta['task']]
  initial_fraction=gates['minimum_initial_visible_fraction_by_task'][meta['task']]
  checks['amodal_visibility'] &= len(fractions)>=initial_count and all(v is not None and v>=initial_fraction for v in fractions[:initial_count])
 details['visibility']={'range':[min(fractions),max(fractions)] if valid else None,'clear_frames':clear,'occluded_frames':occluded}
 details['geometry']={'frame_count':len(selected),'minimum_target_iou':min((r['target_mask_iou'] for r in selected),default=None)}
else:
 checks.update(camera_and_object_overlay=False,robot_fk_overlay=False,amodal_visibility=False)
fk=load(parent/'all_link_fk_audit.json');checks['robot_fk_overlay'] &= bool(fk and fk['passed'])
behavior=load(parent/'task_behavior.json');task=meta['task']
checks['task_behavior']=bool(behavior and behavior.get(task,{}).get('behavior_pass') and behavior['no_deep_table_penetration'])
phases=[r['task_phase'] for r in rows]
checks['task_behavior'] &= (all(x=='noncontact_sweep' for x in phases) if task=='A' else all(x in phases for x in (['close','lift','carry'] if task=='B' else ['carry','place','release','retreat'])))
if task=='C':checks['task_behavior'] &= bool(behavior and behavior.get('B',{}).get('behavior_pass'))
if task=='B':
 target=np.array([r['T_world_object_gt'] for r in rows]);effector=np.array([r['T_world_effector'] for r in rows]);relative=np.linalg.inv(effector)@target
 held=[i for i,phase in enumerate(phases) if phase=='lift'][-30:];carried=[i for i,phase in enumerate(phases) if phase=='carry']
 if len(held)!=30 or not carried:checks['task_behavior']=False
 else:
  movement=drift(target[[held[-1],carried[-1]]]);slip=drift(relative[[held[-1]]+carried])
  checks['task_behavior'] &= movement['translation_m']>=gates['minimum_carry_translation_m'] and movement['rotation_deg']>=gates['minimum_carry_rotation_deg'] and slip['translation_m']<=.01 and slip['rotation_deg']<=10
  details['clip_carry_motion']=movement;details['clip_carry_relative_drift']=slip
provenance=load(parent/'capture_provenance.json');snapshot=parent/'generator_snapshot.py'
checks['physical_grasp_provenance']=bool(provenance and not provenance['attachment_used'] and not provenance['physics_state_directly_set_during_episode'] and snapshot.is_file() and hashlib.sha256(snapshot.read_bytes()).hexdigest()==provenance['generator_sha256'])
model=load(a.model_audit/'report.json')
checks['textured_object_model_equivalence']=bool(model and model['mask_iou']>=.99 and model['depth_p95_m']<=.001 and model['rgb_mae_8bit']<=15)
# Source model hash is required in new audit reports; no anonymous metrics accepted.
checks['textured_object_model_equivalence'] &= bool(model and model.get('object_obj_sha256')==hashlib.sha256((root/'mesh'/'object.obj').read_bytes()).hexdigest())
opened=[];original_open=Path.open
try:
 def guard(self,*args,**kwargs):
  opened.append(str(self))
  if self.name=='frames.jsonl' or 'validation' in self.parts:raise AssertionError('Reader accessed privileged labels')
  return original_open(self,*args,**kwargs)
 Path.open=guard
 for index in [0,1,len(rows)-1]:
  value=read_tracking_input(root,index,np.eye(4))
  if any(any(word in key for word in ['contact','phase','object_gt','ground_truth']) for key in value):raise AssertionError('Reader leaked labels')
 checks['inference_truth_boundary']=True
except Exception as exc:
 checks['inference_truth_boundary']=False;details['reader_error']=str(exc)
finally:Path.open=original_open
details['reader_note']='Identity caller pose tests loading only; no initialization/tracking accuracy claimed.'
groups={}
for path in root.parent.glob('*/manifest.json'):
 other=json.loads(path.read_text()).get('omy_tracking',{})
 if 'parent_group' in other:groups.setdefault(other['parent_group'],set()).add(other['split'])
checks['episode_parent_split_integrity']=all(len(splits)==1 for splits in groups.values())
physics=meta.get('physics')
checks['physics_configuration']=bool(physics and physics.get('computed_body_inertia_kg_m2') and physics.get('computed_body_com_xyz_quat_xyzw'))
if checks['physics_configuration']:
 inertia=np.asarray(physics['computed_body_inertia_kg_m2']).reshape(3,3,order='F')
 checks['physics_configuration'] &= bool(np.isfinite(inertia).all() and np.linalg.eigvalsh(inertia).min()>0 and np.isclose(float(np.asarray(physics['computed_mass_kg']).flat[0]),physics['target_mass_kg']))
checks['seed_provenance']=meta['seed']==meta['generation_arguments']['seed']
joint_limits=audit_sample(root);checks['finite_states_and_joint_limits']=joint_limits['passed'];details['joint_limits']=joint_limits
for key in gates['required_checks']:checks.setdefault(key,False)
report={'technical_pass':all(checks.values()),'accepted_pilot_sequence':False,'bulk_generation_authorized_by_this_report':False,
        'checks':{k:bool(v) for k,v in checks.items()},'details':details,'frame_count':len(rows),'duration_s':len(rows)/30,
        'gates_sha256':hashlib.sha256(a.gates.read_bytes()).hexdigest(),
        'note':'Technical sample validation is separate from partner format review and cohort selection.'}
validation=root/'validation'
for name,data in [('geometry_replay.json',{'frames':selected}),('all_link_fk.json',fk),('task_behavior.json',behavior),('textured_model_equivalence.json',model),('capture_provenance.json',provenance)]:
 (validation/name).write_text(json.dumps(data,indent=2)+'\n')
(validation/'acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
raise SystemExit(0 if report['technical_pass'] else 1)
