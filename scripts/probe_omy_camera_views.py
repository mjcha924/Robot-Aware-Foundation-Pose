"""Compare fixed camera candidates on frozen measured poses; not a dataset capture."""
import argparse,json,traceback
from pathlib import Path
from isaacsim import SimulationApp
p=argparse.ArgumentParser(description=__doc__);p.add_argument('sequence',type=Path);p.add_argument('output',type=Path)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
app=SimulationApp({'headless':True})
try:
 import omni.usd
 import omni.replicator.core as rep
 import numpy as np
 from PIL import Image
 from pxr import UsdGeom,UsdPhysics,Gf
 omni.usd.get_context().open_stage(str((a.sequence/'capture_scene.usda').resolve()));stage=omni.usd.get_context().get_stage()
 for prim in stage.Traverse():
  if prim.HasAPI(UsdPhysics.RigidBodyAPI):UsdPhysics.RigidBodyAPI(prim).CreateRigidBodyEnabledAttr(False)
  if prim.IsA(UsdPhysics.Joint):UsdPhysics.Joint(prim).CreateJointEnabledAttr(False)
 frames=json.loads((a.sequence/'diagnostics.json').read_text())['frames']
 candidates={'current':None,'high_oblique':{'eye':[.6,-.6,2.5],'look':[.1,-.08,1.2]},'overhead':{'eye':[.45,-.45,2.6],'look':[.1,-.08,1.2]}}
 product=rep.create.render_product('/World/sensor',(640,480));rgb=rep.AnnotatorRegistry.get_annotator('rgb');rgb.attach(product);seg=rep.AnnotatorRegistry.get_annotator('semantic_segmentation',init_params={'colorize':False});seg.attach(product)
 rep.modify.semantics([('class','target_object')],input_prims=['/World/Target'],mode='replace')
 def place(path,t):
  prim=stage.GetPrimAtPath(path);parent=np.array(UsdGeom.XformCache().GetLocalToWorldTransform(prim.GetParent())).T
  UsdGeom.Xformable(prim).MakeMatrixXform().Set(Gf.Matrix4d((np.linalg.inv(parent)@t).T.tolist()))
 def mask():
  data=seg.get_data();ids=[int(k) for k,v in data['info']['idToLabels'].items() if v.get('class')=='target_object'];return np.isin(data['data'].reshape(480,640),ids)
 results=[];bodies=json.loads((a.sequence/'diagnostics.json').read_text())['contact_body_order']
 for name,config in candidates.items():
  if config:
   camera=UsdGeom.Xformable(stage.GetPrimAtPath('/World/sensor'));camera.MakeMatrixXform().Set(Gf.Matrix4d().SetLookAt(Gf.Vec3d(*config['eye']),Gf.Vec3d(*config['look']),Gf.Vec3d(0,0,1)).GetInverse())
  for index in [356,540,650,710,850]:
   row=frames[index]
   for path in bodies:place(path,np.array(row['T_world_robot_links'][path.rsplit('/',1)[-1]]))
   place('/World/Target',np.array(row['target_usd_world']))
   rep.orchestrator.step(delta_time=0,rt_subframes=4,pause_timeline=True)
   visible=mask();Image.fromarray(rgb.get_data()[:,:,:3]).save(a.output/f'{name}_{index:06d}.png')
   for path in ['/World/Robot','/World/PackingTable','/World/Background']:UsdGeom.Imageable(stage.GetPrimAtPath(path)).MakeInvisible()
   rep.orchestrator.step(delta_time=0,rt_subframes=1,pause_timeline=True);amodal=mask()
   for path in ['/World/Robot','/World/PackingTable','/World/Background']:UsdGeom.Imageable(stage.GetPrimAtPath(path)).MakeVisible()
   results.append({'camera':name,'config':config,'parent_frame':index,'visible_pixels':int(visible.sum()),'amodal_pixels':int(amodal.sum()),'visible_fraction':float(visible.sum()/amodal.sum())})
 (a.output/'report.json').write_text(json.dumps({'protocol':'camera_design_probe_only','results':results},indent=2));print(results,flush=True)
except Exception:
 traceback.print_exc();(a.output/'error.txt').write_text(traceback.format_exc())
finally:app.close()
