"""Compare FK from measured arm joints and authored joint frames to saved link6."""
import argparse,ast,json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
p=argparse.ArgumentParser(description=__doc__);p.add_argument('sequence',type=Path);p.add_argument('inventory',type=Path)
a=p.parse_args();frames=[json.loads(s) for s in (a.sequence/'frames.jsonl').read_text().splitlines()];joints={j['path'].split('/')[-1]:j for j in json.loads(a.inventory.read_text())['joints']};names=json.loads((a.sequence/'diagnostics.json').read_text())['joint_names']
def local(attrs,index):
 t=np.eye(4);t[:3,3]=ast.literal_eval(attrs['physics:localPos'+str(index)]);q=ast.literal_eval(attrs['physics:localRot'+str(index)]);t[:3,:3]=Rotation.from_quat([q[1],q[2],q[3],q[0]]).as_matrix();return t
errors=[]
for row in frames:
 t=np.array(row['T_world_robot_base']);q=row['measured_joint_positions'][0]
 for name in ['joint1','joint2','joint3','joint4','joint5','joint6']:
  attr=joints[name]['attributes'];angle=q[names.index(name)];r=np.eye(4);r[:3,:3]=Rotation.from_euler(attr['physics:axis'].lower(),angle).as_matrix();t=t@local(attr,0)@r@np.linalg.inv(local(attr,1))
 actual=np.array(row['link6_usd_world']);errors.append({'frame':row['frame'],'translation_m':float(np.linalg.norm(t[:3,3]-actual[:3,3])),'rotation_deg':float(np.rad2deg(Rotation.from_matrix(t[:3,:3]@actual[:3,:3].T).magnitude()))})
report={'method':'measured_joint_FK_using_authored_USD_joint_frames','max_translation_m':max(r['translation_m'] for r in errors),'max_rotation_deg':max(r['rotation_deg'] for r in errors),'frames':len(errors),'samples':errors[::30]};report['passed']=report['max_translation_m']<0.001 and report['max_rotation_deg']<0.1
(a.sequence/'fk_audit.json').write_text(json.dumps(report,indent=2));print({k:v for k,v in report.items() if k!='samples'})
raise SystemExit(0 if report['passed'] else 1)
