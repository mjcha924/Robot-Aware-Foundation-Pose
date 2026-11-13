"""Replace withdrawn release clips with fully checked, smoothly opened episodes.

Retains valid A/B clips. Each replacement C has a distinct physical parent group
and keeps the original variant's split. Never overwrites historical selections.
"""
import argparse,json,os,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--review-record',type=Path,required=True)
p.add_argument('--probe',type=Path,default=Path('outputs/omy_release_fix_probe_001'))
p.add_argument('--max-clips',type=int,default=10)
a=p.parse_args();root=Path('outputs/omy_pilot');work=root/'repairs/release_fix_001'
config=json.loads(Path('configs/omy_tracking/pilot_capture.json').read_text());python=config['python']
index=json.loads((root/'index.json').read_text());jobs=sorted(index['revoked_after_postflight'],key=lambda x:(0 if x['sequence'].startswith('cylinder') else 1,x['sequence']))
for folder in ['parents','candidates','logs']:(work/folder).mkdir(parents=True,exist_ok=True)
def run(command,log,required=None):
 with log.open('x') as stream:result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,env={**os.environ,'OMNI_KIT_ACCEPT_EULA':'YES'},timeout=360)
 if result.returncode or (required and not required.is_file()):raise RuntimeError(f'Command failed: {command[1]}; see {log}')
completed=0
for job in jobs:
 episode=job['sequence'];current=json.loads((root/'index.json').read_text())
 if episode in current['accepted']:continue
 if completed>=a.max_clips:break
 old=Path(job['previous_entry']['path']);manifest=json.loads((old/'manifest.json').read_text());meta=manifest['omy_tracking'];obj=meta['object'];model=config['objects'][obj]['model']
 completed+=1
 for retry in range(3):
  number=1
  while (work/'candidates'/f'{episode}_attempt_{number:03d}').exists():number+=1
  attempt=f'{episode}_attempt_{number:03d}';candidate_root=work/'candidates'/attempt;candidate_root.mkdir();logroot=work/'logs'/attempt;logroot.mkdir()
  parent=work/'parents'/attempt
  reuse_probe=episode=='cylinder_C_00' and number==1 and (a.probe/'diagnostics.json').is_file()
  if reuse_probe:parent=a.probe
  arguments=meta['generation_arguments'].copy();arguments.update(output=str(parent),release_ramp_frames=[30,36,40][retry],release_open_angle=[.02,.04,.06][retry],freeze_release_tcp=True,release_lift_distance=.04,release_lift_frames=15,no_gif=True)
  command=[python,'-u','scripts/render_omy_motion_check.py']
  for name,value in arguments.items():
   if value is None or value is False:continue
   command.append('--'+name.replace('_','-'))
   if value is True:continue
   command.extend(map(str,value if isinstance(value,list) else [value]))
  (candidate_root/'attempt.json').write_text(json.dumps({'source_withdrawn':str(old),'parent':str(parent),'arguments':arguments,'reused_probe':reuse_probe},indent=2)+'\n')
  try:
   if not reuse_probe:run([sys.executable,'scripts/run_omy_capture_measured.py','--output',str(parent),'--log',str(logroot/'capture.log'),'--','timeout','240',*command],logroot/'capture_wrapper.log',parent/'diagnostics.json')
   if not (parent/'task_behavior.json').is_file():run([python,'scripts/check_omy_task_behavior.py',str(parent),model],logroot/'behavior.log',parent/'task_behavior.json')
   behavior=json.loads((parent/'task_behavior.json').read_text())
   if not behavior['B']['behavior_pass'] or not behavior['C']['behavior_pass']:raise RuntimeError('Physical grasp/place/release check failed')
   if not (parent/'joint_limits.json').is_file():run([python,'scripts/check_omy_joint_limits.py',str(parent),'--diagnostic','--output',str(parent/'joint_limits.json')],logroot/'joint_limits.log',parent/'joint_limits.json')
   if not json.loads((parent/'joint_limits.json').read_text())['passed']:raise RuntimeError('Joint-limit audit failed')
   if not (parent/'all_link_fk_audit.json').is_file():run([python,'scripts/audit_omy_all_link_fk.py',str(parent)],logroot/'fk.log',parent/'all_link_fk_audit.json')
   frames=json.loads((parent/'diagnostics.json').read_text())['frames'];start=[r['frame'] for r in frames if r['phase']=='carry'][-1]-29;stop=len(frames)
   if not 180<=stop-start<=300:raise RuntimeError('Replacement clip outside 6–10 seconds')
   audit=parent/'release_geometry_audit'
   run([python,'scripts/audit_omy_exported_geometry.py',str(parent),'--model',model,'--start',str(start),'--stop',str(stop),'--output',str(audit)],logroot/'geometry.log',audit/'report.json')
   sample=candidate_root/episode;group=f'{obj}_releasefix_{episode.rsplit("_",1)[1]}_attempt_{number:03d}'
   run([python,'scripts/package_omy_sample.py',str(parent),str(sample),'--model',model,'--start',str(start),'--stop',str(stop),'--task','C','--object',obj,'--seed',str(meta['seed']),'--parent-group',group,'--split',meta['split']],logroot/'package.log',sample/'manifest.json')
   run([python,'scripts/validate_omy_sample.py',str(sample),'--model-audit',config['objects'][obj]['model_audit'],'--geometry-audit',str(audit)],logroot/'validate.log',sample/'validation/acceptance.json')
   run([python,'scripts/encode_omy_review.py',str(sample)],logroot/'video.log',sample/'review.mp4')
   run([python,'scripts/package_omy_overlay_video.py',str(audit/'geometry_overlay.mp4'),str(sample/'validation/geometry_overlay.mp4'),'--start-frame','0','--frames',str(stop-start)],logroot/'overlay.log',sample/'validation/geometry_overlay.json')
   run([sys.executable,'scripts/run_omy_pilot.py','--review-record',str(a.review_record),'--adopt-samples',str(candidate_root),'--adopt-single-clips','--max-new-groups','0'],logroot/'selection.log')
   subprocess.run([sys.executable,'scripts/update_omy_pilot_progress.py'],check=True)
   print('REPLACEMENT_ACCEPTED '+episode,flush=True);break
  except (RuntimeError,subprocess.SubprocessError,OSError,ValueError) as error:
   rejection={'attempt':'releasefix_'+attempt,'reason':str(error),'path':str(candidate_root)}
   (candidate_root/'rejection.json').write_text(json.dumps(rejection,indent=2)+'\n')
   current=json.loads((root/'index.json').read_text());current['rejected_attempts'].append(rejection)
   temp=root/'index.json.tmp';temp.write_text(json.dumps(current,indent=2)+'\n');temp.replace(root/'index.json')
   subprocess.run([sys.executable,'scripts/update_omy_pilot_progress.py'],check=True);print('REPLACEMENT_REJECTED '+episode+': '+str(error),flush=True)

final_count=len(json.loads((root/'index.json').read_text())['accepted'])
print(json.dumps({'accepted':final_count,'required':45}),flush=True)
raise SystemExit(0 if final_count==45 else 2)
