"""Render object-only masks/depth at saved poses without advancing physics.

Visibility is total visibility (all scene occluders), not robot-specific visibility.
"""
import argparse,json,traceback
from pathlib import Path
from isaacsim import SimulationApp
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('sequence',type=Path)
p.add_argument('--stride',type=int,default=1)
a=p.parse_args();out=a.sequence/'visibility_audit';out.mkdir(exist_ok=False)
app=SimulationApp({'headless':True})
try:
 import omni.usd
 import omni.replicator.core as rep
 import numpy as np
 import cv2
 from PIL import Image
 from pxr import UsdGeom,UsdPhysics,Gf
 omni.usd.get_context().open_stage(str((a.sequence/'capture_scene.usda').resolve()))
 stage=omni.usd.get_context().get_stage()
 for prim in stage.Traverse():
  if prim.HasAPI(UsdPhysics.RigidBodyAPI):UsdPhysics.RigidBodyAPI(prim).CreateRigidBodyEnabledAttr(False)
  if prim.IsA(UsdPhysics.Joint):UsdPhysics.Joint(prim).CreateJointEnabledAttr(False)
 for path in ['/World/Robot','/World/PackingTable','/World/Background']:
  prim=stage.GetPrimAtPath(path)
  if prim:UsdGeom.Imageable(prim).MakeInvisible()
 rep.modify.semantics([('class','target_object')],input_prims=['/World/Target'],mode='replace')
 product=rep.create.render_product('/World/sensor',(640,480))
 seg=rep.AnnotatorRegistry.get_annotator('semantic_segmentation',init_params={'colorize':False});seg.attach(product)
 depth=rep.AnnotatorRegistry.get_annotator('distance_to_image_plane');depth.attach(product)
 frames=[json.loads(s) for s in (a.sequence/'frames.jsonl').read_text().splitlines()]
 (out/'amodal_masks').mkdir();(out/'overlays').mkdir();results=[]
 for row in frames[::a.stride]:
  index=row['frame'];stem=f'{index:06d}.png'
  t=np.array(row['target_usd_world']);prim=stage.GetPrimAtPath('/World/Target')
  parent=np.array(UsdGeom.XformCache().GetLocalToWorldTransform(prim.GetParent())).T
  UsdGeom.Xformable(prim).MakeMatrixXform().Set(Gf.Matrix4d((np.linalg.inv(parent)@t).T.tolist()))
  rep.orchestrator.step(delta_time=0,rt_subframes=1,pause_timeline=True)
  data=seg.get_data();ids=[int(k) for k,v in data['info']['idToLabels'].items() if v.get('class')=='target_object']
  amodal=np.isin(data['data'].reshape(480,640),ids)
  visible=np.asarray(Image.open(a.sequence/'masks'/stem))>0
  original_depth=np.asarray(Image.open(a.sequence/'depth'/stem))*.001
  rendered_depth=depth.get_data().reshape(480,640)
  inside=cv2.erode((visible&amodal).astype(np.uint8),np.ones((3,3),np.uint8))>0
  valid=inside&(original_depth>0)&np.isfinite(rendered_depth)
  errors=np.abs(original_depth[valid]-rendered_depth[valid])
  denominator=int(amodal.sum());area=int(visible.sum())
  results.append({'frame':index,'visible_pixels':area,'amodal_pixels':denominator,
                  'visible_fraction':area/denominator if denominator else None,
                  'outside_amodal_pixels':int((visible&~amodal).sum()),
                  'touches_image_boundary':bool(amodal[0].any() or amodal[-1].any() or amodal[:,0].any() or amodal[:,-1].any()),
                  'depth_alignment_samples':int(valid.sum()),
                  'depth_error_p95_m':float(np.percentile(errors,95)) if errors.size else None})
  Image.fromarray(amodal.astype(np.uint8)*255).save(out/'amodal_masks'/stem,compress_level=1)
  if index%30==0 or index==len(frames)-1:
   image=np.array(Image.open(a.sequence/'rgb'/stem))[:,:,:3].copy()
   contours,_=cv2.findContours(amodal.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
   cv2.drawContours(image,contours,-1,(0,255,0),1)
   Image.fromarray(image).save(out/'overlays'/stem)
 report={'protocol':'frozen_object_only_same_pose_camera_no_physics_step','occlusion_type':'total_scene',
         'stride':a.stride,'frames':results,'accepted_pilot_sequence':False}
 (out/'report.json').write_text(json.dumps(report,indent=2))
 fractions=[x['visible_fraction'] for x in results if x['visible_fraction'] is not None]
 print({'frames':len(results),'fraction_min':min(fractions),'fraction_max':max(fractions),'max_depth_p95_m':max((x['depth_error_p95_m'] or 0) for x in results)},flush=True)
except Exception:
 traceback.print_exc();(out/'error.txt').write_text(traceback.format_exc())
finally:app.close()
