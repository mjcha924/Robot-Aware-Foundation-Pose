"""Replay measured-joint FK as frozen geometry and compare rendered depth."""
import argparse,json,ast,traceback
from pathlib import Path
from isaacsim import SimulationApp
p=argparse.ArgumentParser(description=__doc__);p.add_argument('sequence',type=Path);p.add_argument('inventory',type=Path)
a=p.parse_args();out=a.sequence/'fk_render_audit';out.mkdir(exist_ok=False)
app=SimulationApp({'headless':True})
try:
 import omni.usd
 import omni.replicator.core as rep
 import numpy as np
 from scipy.spatial.transform import Rotation
 from PIL import Image
 from pxr import UsdGeom,UsdPhysics,Gf
 omni.usd.get_context().open_stage(str((a.sequence/'capture_scene.usda').resolve()));stage=omni.usd.get_context().get_stage()
 for prim in stage.Traverse():
  if prim.HasAPI(UsdPhysics.RigidBodyAPI):UsdPhysics.RigidBodyAPI(prim).CreateRigidBodyEnabledAttr(False)
  if prim.IsA(UsdPhysics.Joint):UsdPhysics.Joint(prim).CreateJointEnabledAttr(False)
 frames=[json.loads(s) for s in (a.sequence/'frames.jsonl').read_text().splitlines()];names=json.loads((a.sequence/'diagnostics.json').read_text())['joint_names'];joints=json.loads(a.inventory.read_text())['joints']
 rep.modify.semantics([('class','robot')],input_prims=['/World/Robot'],mode='replace')
 product=rep.create.render_product('/World/sensor',(640,480));depth=rep.AnnotatorRegistry.get_annotator('distance_to_image_plane');depth.attach(product);rgb=rep.AnnotatorRegistry.get_annotator('rgb');rgb.attach(product);seg=rep.AnnotatorRegistry.get_annotator('semantic_segmentation',init_params={'colorize':False});seg.attach(product)
 def local(attrs,i):
  t=np.eye(4);t[:3,3]=ast.literal_eval(attrs['physics:localPos'+str(i)]);q=ast.literal_eval(attrs['physics:localRot'+str(i)]);t[:3,:3]=Rotation.from_quat([q[1],q[2],q[3],q[0]]).as_matrix();return t
 def place(path,matrix):
  prim=stage.GetPrimAtPath(path);parent=np.array(UsdGeom.XformCache().GetLocalToWorldTransform(prim.GetParent())).T
  UsdGeom.Xformable(prim).MakeMatrixXform().Set(Gf.Matrix4d((np.linalg.inv(parent)@matrix).T.tolist()))
 results=[]
 for index in [0,250,450,650,900,1200,len(frames)-1]:
  if index>=len(frames):continue
  row=frames[index];world={'/World/Robot/OMY/world':np.array(row['T_world_robot_base'])};q=row['measured_joint_positions'][0]
  for j in joints:
   name=j['path'].split('/')[-1]
   if name not in names:continue
   attrs=j['attributes'];r=np.eye(4);r[:3,:3]=Rotation.from_euler(attrs['physics:axis'].lower(),q[names.index(name)]).as_matrix();parent=j['relationships']['physics:body0'][0];child=j['relationships']['physics:body1'][0];world[child]=world[parent]@local(attrs,0)@r@np.linalg.inv(local(attrs,1))
  for path,matrix in world.items():place(path,matrix)
  place('/World/Target',np.array(row['target_usd_world']))
  rep.orchestrator.step(delta_time=0.0,rt_subframes=4,pause_timeline=True)
  d=depth.get_data().reshape(480,640);label=seg.get_data();ids=[int(k) for k,v in label['info']['idToLabels'].items() if v.get('class')=='robot'];mask=np.isin(label['data'].reshape(480,640),ids)
  original=np.array(Image.open(a.sequence/'depth'/f'{index:06d}.png'))*.001;valid=mask&np.isfinite(d)&(original>0);errors=np.abs(d[valid]-original[valid]);results.append({'frame':index,'robot_pixels':int(valid.sum()),'depth_error_p95_m':float(np.percentile(errors,95)) if errors.size else None,'median_m':float(np.median(errors)) if errors.size else None})
  Image.fromarray(rgb.get_data()[:,:,:3]).save(out/f'{index:06d}.png')
 (out/'report.json').write_text(json.dumps({'method':'frozen_measured_joint_FK_replay','samples':results,'accepted':False,'note':'Inspect numerical results and image evidence before defining pass.'},indent=2));print(results,flush=True)
except Exception:traceback.print_exc();(out/'error.txt').write_text(traceback.format_exc())
finally:app.close()
