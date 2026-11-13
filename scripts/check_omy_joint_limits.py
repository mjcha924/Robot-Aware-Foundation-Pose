"""Check finite measured states against authored OMY joint limits (degrees -> radians)."""
import json,math
from pathlib import Path

TOLERANCE_RAD=json.loads((Path(__file__).resolve().parents[1]/'configs/omy_tracking/postflight_acceptance.json').read_text())['joint_limit_numerical_tolerance_rad']  # 0.057 degrees; not mechanical overtravel.

def evaluate(names,rows,inventory):
 limits={Path(j['path']).name:(math.radians(float(j['attributes']['physics:lowerLimit'])),math.radians(float(j['attributes']['physics:upperLimit']))) for j in inventory['joints'] if 'physics:lowerLimit' in j['attributes']}
 missing=sorted(set(names)-set(limits));finite=True;bad=[];maximum=0.;ranges={}
 for row in rows:
  q=row['joint_positions'];dq=row['joint_velocities']
  if len(q)!=len(names) or len(dq)!=len(names):finite=False;continue
  if not all(math.isfinite(float(x)) for x in q+dq+[row['timestamp_s']]):finite=False;continue
  for name,value in zip(names,q):
   if name not in limits:continue
   lower,upper=limits[name];excess=max(lower-value,value-upper,0);maximum=max(maximum,excess)
   record=ranges.setdefault(name,{'minimum_rad':value,'maximum_rad':value,'lower_limit_rad':lower,'upper_limit_rad':upper,'maximum_excess_rad':0.})
   record['minimum_rad']=min(record['minimum_rad'],value);record['maximum_rad']=max(record['maximum_rad'],value);record['maximum_excess_rad']=max(record['maximum_excess_rad'],excess)
   if excess>TOLERANCE_RAD:bad.append({'frame':row.get('frame_id',row.get('frame','previous')),'joint':name,'excess_rad':excess})
 return {'passed':finite and not missing and not bad,'tolerance_rad':TOLERANCE_RAD,'finite_states':finite,'missing_limits':missing,'maximum_excess_rad':maximum,'violation_count':len(bad),'first_violations':bad[:20],'per_joint':ranges,'row_count':len(rows)}

def audit_sample(root):
 root=Path(root);meta=json.loads((root/'manifest.json').read_text())['omy_tracking']
 inventory=json.loads((root/meta['joint_inventory']).read_text())
 rows=[json.loads(line) for line in (root/'robot_observations.jsonl').read_text().splitlines()]
 previous=json.loads((root/'previous_robot_state.json').read_text());rows.insert(0,previous)
 return evaluate(meta['joint_names'],rows,inventory)

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--diagnostic',action='store_true');p.add_argument('--output',type=Path,required=True)
 a=p.parse_args()
 if a.output.exists():p.error('Choose a fresh report path')
 if a.diagnostic:
  data=json.loads((a.root/'diagnostics.json').read_text());inventory=json.loads(Path('outputs/omy_physics_inventory_001/physics_inventory.json').read_text())
  rows=[{'frame_id':r['frame'],'joint_positions':r['measured_joint_positions'][0],'joint_velocities':r['measured_joint_velocities'][0],'timestamp_s':r['timeline_s']} for r in data['frames']]
  report=evaluate(data['joint_names'],rows,inventory)
 else:report=audit_sample(a.root)
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(0 if report['passed'] else 1)
