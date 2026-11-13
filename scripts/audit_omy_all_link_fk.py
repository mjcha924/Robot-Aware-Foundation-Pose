"""Compare all measured OMY link poses to encoder FK, including gripper links."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from omy_kinematics import forward_kinematics
p=argparse.ArgumentParser(description=__doc__);p.add_argument('sequence',type=Path)
p.add_argument('--inventory',type=Path,default=Path('outputs/omy_physics_inventory_001/physics_inventory.json'))
a=p.parse_args();d=json.loads((a.sequence/'diagnostics.json').read_text());inventory=json.loads(a.inventory.read_text())
errors={};failures=[]
for row in d['frames']:
 predicted=forward_kinematics(inventory,d['joint_names'],row['measured_joint_positions'][0],row['T_world_robot_base'])
 actual=row.get('T_world_robot_links')
 if actual is None:raise ValueError('Capture lacks independent simulator link poses')
 if set(actual)!=set(predicted):raise ValueError('Link sets differ')
 for name,t in predicted.items():
  reference=np.asarray(actual[name]);translation=float(np.linalg.norm(t[:3,3]-reference[:3,3]));rotation=float(np.rad2deg(Rotation.from_matrix(t[:3,:3]@reference[:3,:3].T).magnitude()))
  value=errors.setdefault(name,{'max_translation_m':0.,'max_rotation_deg':0.})
  value['max_translation_m']=max(value['max_translation_m'],translation);value['max_rotation_deg']=max(value['max_rotation_deg'],rotation)
  if translation>.001 or rotation>.1:failures.append({'frame':row['frame'],'link':name,'translation_m':translation,'rotation_deg':rotation})
report={'passed':not failures,'frame_count':len(d['frames']),'per_link':errors,'failure_count':len(failures),'first_failures':failures[:20]}
(a.sequence/'all_link_fk_audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
raise SystemExit(0 if report['passed'] else 1)
