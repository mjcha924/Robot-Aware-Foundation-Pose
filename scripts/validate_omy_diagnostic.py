"""Audit diagnostic captures; never promote them to accepted pilot data."""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('root',type=Path)
a=p.parse_args()
d=json.loads((a.root/'diagnostics.json').read_text());frames=d['frames']
checks={};timestamps=np.array([r['timeline_s'] for r in frames])
checks['cadence_30hz']=bool(len(frames)>1 and np.allclose(np.diff(timestamps),1/30,atol=1e-6,rtol=0))
checks['frame_order']=all(r['frame']==i for i,r in enumerate(frames))
checks['finite_measured_joints']=all(np.isfinite(r['measured_joint_positions']).all() and np.isfinite(r['measured_joint_velocities']).all() for r in frames)
transforms=[np.asarray(r[k]) for r in frames for k in ['link6_usd_world','target_usd_world']]
checks['rigid_transforms']=all(t.shape==(4,4) and np.isfinite(t).all() and np.allclose(t[3],[0,0,0,1],atol=1e-5) and np.allclose(t[:3,:3].T@t[:3,:3],np.eye(3),atol=1e-4) and abs(np.linalg.det(t[:3,:3])-1)<1e-4 for t in transforms)
mask_counts=[];complete=True;depth_valid=True
for row in frames:
 stem=f'{row["frame"]:06d}.png'
 for folder in ['rgb','depth','masks']:
  path=a.root/folder/stem
  if not path.is_file():complete=False;continue
  with Image.open(path) as im:
   arr=np.asarray(im)
   if im.size!=(640,480):complete=False
   if folder=='depth' and (arr.dtype!=np.uint16 or arr.ndim!=2):depth_valid=False
   if folder=='masks':mask_counts.append(int(np.count_nonzero(arr)))
checks['image_completeness']=complete
checks['depth_encoding']=complete and depth_valid
checks['visible_initial_target']=bool(mask_counts and mask_counts[0]>0)
z=[r['target_usd_world'][2][3] for r in frames]
phases={phase:sum(r['phase']==phase for r in frames) for phase in sorted({r['phase'] for r in frames})}
report={'diagnostic_checks':checks,'frames':len(frames),'phase_counts':phases,'max_object_origin_lift_m':max(z)-z[0],'mask_pixel_range':[min(mask_counts),max(mask_counts)] if mask_counts else None,'accepted_pilot_sequence':False,'missing_acceptance_evidence':['textured_model_equivalence','object_and_robot_projection_audits','contact_and_release_validation','amodal_visibility','complete_versioned_manifest','split_and_parent_provenance','partner_format_validation'],'disk_bytes':sum(f.stat().st_size for f in a.root.rglob('*') if f.is_file())}
(a.root/'diagnostic_validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
raise SystemExit(0 if all(checks.values()) else 1)
