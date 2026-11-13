"""Resume the 45-slot OMY pilot, retaining every attempt and accepting only checked clips.

Requires an explicit partner-review/waiver record and validated A/B/C handoff.
Never generates the 720-sequence main dataset. All subprocess arguments are lists.
"""
import argparse,hashlib,json,math,os,shutil,subprocess,sys,time
from pathlib import Path
from check_omy_joint_limits import audit_sample

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--config',type=Path,default=Path('configs/omy_tracking/pilot_capture.json'))
p.add_argument('--review-record',type=Path,required=True)
p.add_argument('--handoff',type=Path,default=Path('outputs/omy_handoff_002'))
p.add_argument('--attempts-per-group',type=int,default=3)
p.add_argument('--max-new-groups',type=int,default=30)
p.add_argument('--adopt-handoff',action='store_true',help='Promote matching validated handoff samples into still-empty slots')
p.add_argument('--adopt-samples',type=Path,help='Additional fully validated samples to select for empty slots')
p.add_argument('--adopt-single-clips',action='store_true',help='Select independently captured clips with their own parent-group identity')
a=p.parse_args();cfg=json.loads(a.config.read_text());review=json.loads(a.review_record.read_text())
if subprocess.check_output(['git','branch','--show-current'],text=True).strip()!='feature/omy-tracking-dataset':p.error('Wrong working branch')
if cfg['status']!='ready_for_review_gated_pilot':p.error('Capture configuration is not qualified/frozen')
if len(cfg['objects'])!=3 or len(cfg['variants'])!=5 or len({v['id'] for v in cfg['variants']})!=5:p.error('Expected three objects and five distinct variants')
for settings in cfg['objects'].values():
 if not (Path(settings['model'])/'object.obj').is_file() or not (Path(settings['model_audit'])/'report.json').is_file():p.error('Required object model or model audit is missing')
if review.get('decision') not in ('confirmed','waived_by_user') or not review.get('user_statement'):p.error('Missing explicit review confirmation or user waiver')
gates_sha=hashlib.sha256(Path('configs/omy_tracking/acceptance.json').read_bytes()).hexdigest()
for task in 'ABC':
 qualified=[]
 for sample in a.handoff.glob(f'*_{task}_*'):
  path=sample/'validation/acceptance.json'
  if not path.is_file():continue
  report=json.loads(path.read_text())
  if report['technical_pass'] and report.get('gates_sha256')==gates_sha and audit_sample(sample)['passed']:qualified.append(sample)
 if not qualified:p.error('No handoff '+task+' passes current technical and joint-limit checks')
root=Path(cfg['output_root']);root.mkdir(parents=True,exist_ok=True)
for folder in ['parents','attempts','accepted','logs','provenance']:(root/folder).mkdir(exist_ok=True)
run_id=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+f'_{time.time_ns()%1_000_000_000:09d}'
shutil.copy2(a.config,root/'provenance'/f'config_{run_id}.json');shutil.copy2(a.review_record,root/'provenance'/f'review_{run_id}.json')
index_path=root/'index.json'
index=json.loads(index_path.read_text()) if index_path.exists() else {'required':45,'accepted':{},'rejected_attempts':[],'runs':[]}
for entry in index['accepted'].values():
 prior=json.loads((Path(entry['path'])/'validation/acceptance.json').read_text())
 if prior.get('gates_sha256')!=gates_sha:p.error('Existing cohort uses different acceptance gates; review before resuming')
index['runs'].append({'id':run_id,'review_record':str(a.review_record),'config_sha256':hashlib.sha256(a.config.read_bytes()).hexdigest()})
python=cfg['python'];script=Path('scripts/render_omy_motion_check.py');frozen_sha=hashlib.sha256(script.read_bytes()).hexdigest()
asset_root='https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.2/Isaac/Props/YCB/Axis_Aligned/'

def atomic_json(path,data):
 temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)

def update_status():
 atomic_json(index_path,index)
 lines=['# OMY pilot execution status','',f'Accepted: **{len(index["accepted"])} / 45**.','',
        'Only entries with complete technical validation and a recorded format-review decision are counted.','',
        '| Object | A | B | C |','|---|---:|---:|---:|']
 for obj in cfg['objects']:
  counts=[sum(key.startswith(obj+'_'+task+'_') for key in index['accepted']) for task in 'ABC']
  lines.append('| '+obj+' | '+' | '.join(map(str,counts))+' |')
 lines+=['','## Recent rejected attempts','']
 for row in index['rejected_attempts'][-12:]:lines.append(f'- `{row["attempt"]}`: {row["reason"]}')
 (Path('docs/omy_tracking')/'PILOT_RUN_STATUS.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps({'accepted':len(index['accepted']),'required':45,'rejected_attempts':len(index['rejected_attempts'])}),flush=True)

def run(arguments,log,required=None):
 with log.open('w') as stream:
  result=subprocess.run(arguments,stdout=stream,stderr=subprocess.STDOUT,env={**os.environ,'OMNI_KIT_ACCEPT_EULA':'YES'},timeout=330)
 if result.returncode or (required and not required.is_file()):raise RuntimeError(f'{Path(arguments[1]).name if len(arguments)>1 else arguments[0]} failed; see {log}')

def copy_artifact(source,destination):
 source,destination=Path(source),Path(destination)
 if source.suffix in ('.json','.jsonl','.py','.usda','.txt'):return shutil.copy2(source,destination)
 try:os.link(source,destination)
 except OSError:shutil.copy2(source,destination)
 return destination

def promote(sample,episode_id,parent_group):
 if episode_id in index['accepted']:return
 report_path=sample/'validation/acceptance.json';report=json.loads(report_path.read_text())
 state_audit=audit_sample(sample)
 if not report['technical_pass'] or not state_audit['passed']:raise RuntimeError('Cannot promote failed sample')
 destination=root/'accepted'/episode_id
 if destination.exists():
  destination=root/'accepted_revisions'/run_id/episode_id
  destination.parent.mkdir(parents=True,exist_ok=True)
 shutil.copytree(sample,destination,copy_function=copy_artifact)
 manifest=json.loads((destination/'manifest.json').read_text());manifest['sequence_id']=episode_id
 manifest['omy_tracking'].update(status='accepted_pilot_sequence',accepted=True)
 atomic_json(destination/'manifest.json',manifest)
 proof={'accepted':True,'technical_report_sha256':hashlib.sha256(report_path.read_bytes()).hexdigest(),
        'review_decision':review['decision'],'review_record_sha256':hashlib.sha256(a.review_record.read_bytes()).hexdigest(),
        'run_id':run_id,'parent_group':parent_group,'initializer_result':'not_measured_by_capture_pipeline'}
 atomic_json(destination/'validation/joint_limits.json',state_audit)
 proof['joint_limits_report_sha256']=hashlib.sha256((destination/'validation/joint_limits.json').read_bytes()).hexdigest()
 atomic_json(destination/'validation/pilot_acceptance.json',proof)
 index['accepted'][episode_id]={'path':str(destination),'parent_group':parent_group,'split':manifest['omy_tracking']['split'],'frames':manifest['frame_count'],'proof':proof}

if a.adopt_handoff or a.adopt_samples:
 candidate_root=a.adopt_samples or a.handoff
 for obj,settings in cfg['objects'].items():
  for baseline in cfg['variants']:
   for tasks in ([('A',),('B',),('C',)] if a.adopt_single_clips else [('A',),('B','C')]):
    candidates=[candidate_root/f'{obj}_{task}_{baseline["id"]:02d}' for task in tasks]
    if any(sample.name in index['accepted'] for sample in candidates) or not all((sample/'validation/acceptance.json').is_file() for sample in candidates):continue
    metadata=[]
    for sample in candidates:
     report=json.loads((sample/'validation/acceptance.json').read_text());manifest=json.loads((sample/'manifest.json').read_text());meta=manifest['omy_tracking'];generation=meta['generation_arguments']
     if not report['technical_pass'] or report['gates_sha256']!=gates_sha:raise RuntimeError('Handoff no longer passes current gates')
     if meta['object']!=obj or meta['seed']!=baseline['seed'] or meta['split']!=baseline['split']:raise RuntimeError('Handoff slot metadata differs')
     if generation['camera_eye']!=cfg['camera']['eye'] or generation['camera_look']!=cfg['camera']['look']:raise RuntimeError('Handoff camera differs')
     if [generation['target_x'],generation['target_y']]!=baseline['target_xy_m']:raise RuntimeError('Handoff target position differs')
     if hashlib.sha256((sample/'mesh/object.obj').read_bytes()).hexdigest()!=hashlib.sha256((Path(settings['model'])/'object.obj').read_bytes()).hexdigest():raise RuntimeError('Handoff model differs')
     if manifest['source']['parent_diagnostics_sha256']!=hashlib.sha256((Path(manifest['source']['diagnostic_parent'])/'diagnostics.json').read_bytes()).hexdigest():raise RuntimeError('Handoff parent changed')
     metadata.append(meta)
    if len({meta['parent_group'] for meta in metadata})!=1:raise RuntimeError('Handoff B/C groups differ')
    for sample,meta in zip(candidates,metadata):
     promote(sample,sample.name,meta['parent_group']);index['accepted'][sample.name]['promoted_from_handoff']=str(sample);update_status()

new_groups=0
for obj,settings in cfg['objects'].items():
 for variant in cfg['variants']:
  for kind,tasks in [('A',['A']),('BC',['B','C'])]:
   ids=[f'{obj}_{task}_{variant["id"]:02d}' for task in tasks]
   if all(key in index['accepted'] for key in ids):continue
   if new_groups>=a.max_new_groups:update_status();raise SystemExit(0)
   if hashlib.sha256(script.read_bytes()).hexdigest()!=frozen_sha:raise RuntimeError('Capture source changed during this invocation; restart after reviewing changes')
   if shutil.disk_usage(root).free < 20*1024**3:raise RuntimeError('Less than 20 GiB free; preserve results and stop for storage review')
   new_groups+=1;group=f'{obj}_{"noncontact" if kind=="A" else "manipulation"}_{variant["id"]:02d}'
   accepted=False
   for retry in range(a.attempts_per_group):
    number=1
    while (root/'attempts'/f'{group}_attempt_{number:03d}').exists():number+=1
    attempt_id=f'{group}_attempt_{number:03d}';attempt=root/'attempts'/attempt_id;attempt.mkdir()
    parent=root/'parents'/attempt_id;logroot=root/'logs'/attempt_id;logroot.mkdir()
    seed=variant['seed'];x,y=variant['target_xy_m'];yaw=variant['yaw_delta_deg'];theta=math.radians(yaw)
    controls=settings.get('variant_overrides',{}).get(str(variant['id']),{})
    grasp_yaw=controls.get('grasp_yaw_deg',yaw)
    ox,oy=settings['grasp_offset_xy_m'];offset=[math.cos(theta)*ox-math.sin(theta)*oy,math.sin(theta)*ox+math.cos(theta)*oy]
    height_adjust=[0,.002,-.002][retry%3]
    arguments=[python,str(script),'--scene',cfg['scene'],'--output',str(parent),'--frames','540' if kind=='A' else '1200',
      '--export-observations','--upright-target','--upright-axis',settings['upright_axis'],'--upright-angle',str(settings['upright_angle_deg']),
      '--target-yaw',str(settings['target_yaw_deg']+yaw),'--target-x',str(x),'--target-y',str(y),'--grasp-yaw',str(grasp_yaw),
      '--target-usd',asset_root+settings['asset'],'--target-mass',str(settings['mass_kg']),'--collision-approximation',settings['collision'],
      '--seed',str(seed),'--camera-eye',*map(str,cfg['camera']['eye']),'--camera-look',*map(str,cfg['camera']['look'])]
    if kind=='A':
     eye=cfg['camera']['eye'];z=settings['rest_root_z_m'];arguments+=['--occlusion-probe','--occlusion-centre-x',str(x+.1*(eye[0]-x)),
       '--occlusion-y',str(y+.1*(eye[1]-y)),'--occlusion-z',str(z+.1*(eye[2]-z)+height_adjust*3),
       '--occlusion-amplitude','-0.09','--occlusion-clearance-rise','0.08']
    else:
     arguments+=['--grasp-probe','--carry-probe','--place-probe','--pilot-timing','--stop-after-retreat','--moving-pad-centre',
       '--grasp-height',str(settings['grasp_height_m']+height_adjust),'--grasp-offset-x',str(offset[0]),'--grasp-offset-y',str(offset[1]),
       '--gripper-close',str(settings['gripper_close_rad']),'--carry-x',str(variant['carry_xy_m'][0]),'--carry-y',str(variant['carry_xy_m'][1]),
       '--carry-yaw',str(variant['carry_yaw_deg']),'--carry-pitch','-25','--carry-hold-frames','30','--place-return-pitch',
       '--release-lift-distance','0.04','--release-lift-frames','15','--freeze-release-tcp','--release-ramp-frames','30','--release-open-angle','0.02','--lift-distance',str(settings['lift_distance_m']),'--approach-clearance','0.08','--approach-offset-x','-0.08','--retreat-y','0.12']
    atomic_json(attempt/'attempt.json',{'parent_group':group,'seed':seed,'variant':variant,'retry':retry,'arguments':arguments})
    try:
     run([sys.executable,'scripts/run_omy_capture_measured.py','--output',str(parent),'--log',str(logroot/'capture.log'),'--','timeout','240',*arguments],logroot/'capture_wrapper.log',parent/'diagnostics.json')
     run([python,'scripts/check_omy_task_behavior.py',str(parent),settings['model']],logroot/'behavior.log',parent/'task_behavior.json')
     behavior=json.loads((parent/'task_behavior.json').read_text())
     if not all(behavior.get(task,{}).get('behavior_pass') for task in tasks):raise RuntimeError('Physical task validation failed')
     run([python,'scripts/audit_omy_all_link_fk.py',str(parent)],logroot/'fk.log',parent/'all_link_fk_audit.json')
     frames=json.loads((parent/'diagnostics.json').read_text())['frames'];carry=[r['frame'] for r in frames if r['phase']=='carry']
     if kind=='A':intervals={'A':(300,540)}
     else:
      b_stop=carry[0]+75;intervals={'B':(b_stop-300,b_stop),'C':(carry[-1]-29,len(frames))}
     begin=min(v[0] for v in intervals.values());end=max(v[1] for v in intervals.values());audit=parent/'exported_geometry_audit'
     run([python,'scripts/audit_omy_exported_geometry.py',str(parent),'--model',settings['model'],'--start',str(begin),'--stop',str(end),'--output',str(audit)],logroot/'geometry.log',audit/'report.json')
     samples=[]
     for task,(start,stop) in intervals.items():
      sample=attempt/f'{obj}_{task}_{variant["id"]:02d}'
      run([python,'scripts/package_omy_sample.py',str(parent),str(sample),'--model',settings['model'],'--start',str(start),'--stop',str(stop),
           '--task',task,'--object',obj,'--seed',str(seed),'--parent-group',group,'--split',variant['split']],logroot/f'package_{task}.log',sample/'manifest.json')
      run([python,'scripts/validate_omy_sample.py',str(sample),'--model-audit',settings['model_audit'],'--geometry-audit',str(audit)],logroot/f'validate_{task}.log',sample/'validation/acceptance.json')
      run([python,'scripts/encode_omy_review.py',str(sample)],logroot/f'video_{task}.log',sample/'review.mp4')
      run([python,'scripts/package_omy_overlay_video.py',str(audit/'geometry_overlay.mp4'),str(sample/'validation/geometry_overlay.mp4'),
           '--start-frame',str(start-begin),'--frames',str(stop-start)],logroot/f'overlay_{task}.log',sample/'validation/geometry_overlay.json')
      samples.append((sample,f'{obj}_{task}_{variant["id"]:02d}'))
     for sample,episode_id in samples:
      promote(sample,episode_id,group);update_status()
     accepted=True;update_status();break
    except (RuntimeError,subprocess.SubprocessError,OSError,ValueError) as error:
     rejection={'attempt':attempt_id,'reason':str(error),'path':str(attempt)}
     atomic_json(attempt/'rejection.json',rejection);index['rejected_attempts'].append(rejection);update_status()
   if not accepted:print('Group remains unaccepted: '+group,flush=True)
update_status()
raise SystemExit(0 if len(index['accepted'])==45 else 2)
