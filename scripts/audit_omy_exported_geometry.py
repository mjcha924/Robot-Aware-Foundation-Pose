"""Replay exported OBJ geometry from measured joints and audit every selected frame.

Outputs a review video with target (green) and robot (cyan) model contours on
original RGB. Ground truth is used only in this validation tool.
"""
import argparse,json,traceback
from pathlib import Path
from isaacsim import SimulationApp
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('sequence',type=Path);p.add_argument('--model',type=Path,required=True)
p.add_argument('--robot-model',type=Path,default=Path('outputs/omy_robot_geometry_001'))
p.add_argument('--inventory',type=Path,default=Path('outputs/omy_physics_inventory_001/physics_inventory.json'))
p.add_argument('--start',type=int,default=0);p.add_argument('--stop',type=int)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
app=SimulationApp({'headless':True})
try:
 import omni.usd
 import omni.replicator.core as rep
 import numpy as np
 import cv2,imageio_ffmpeg
 from PIL import Image
 from pxr import UsdGeom,UsdPhysics,Gf
 from omy_kinematics import forward_kinematics
 omni.usd.get_context().open_stage(str((a.sequence/'capture_scene.usda').resolve()));stage=omni.usd.get_context().get_stage()
 for prim in stage.Traverse():
  if prim.HasAPI(UsdPhysics.RigidBodyAPI):UsdPhysics.RigidBodyAPI(prim).CreateRigidBodyEnabledAttr(False)
  if prim.IsA(UsdPhysics.Joint):UsdPhysics.Joint(prim).CreateJointEnabledAttr(False)
 UsdGeom.Imageable(stage.GetPrimAtPath('/World/Robot')).MakeInvisible()
 stage.GetPrimAtPath('/World/Target/Asset').SetActive(False)
 def mesh_from_obj(source,path):
  vertices=[];faces=[]
  for line in source.read_text().splitlines():
   parts=line.split()
   if not parts:continue
   if parts[0]=='v':vertices.append(tuple(map(float,parts[1:4])))
   elif parts[0]=='f':faces.append([int(v.split('/')[0])-1 for v in parts[1:]])
  mesh=UsdGeom.Mesh.Define(stage,path);mesh.CreatePointsAttr(vertices);mesh.CreateFaceVertexCountsAttr([len(f) for f in faces]);mesh.CreateFaceVertexIndicesAttr([v for f in faces for v in f]);mesh.CreateSubdivisionSchemeAttr('none')
  return mesh
 mesh_from_obj(a.model/'object.obj','/World/Target/ExportedAuditMesh')
 robot=json.loads((a.robot_model/'manifest.json').read_text())
 UsdGeom.Xform.Define(stage,'/World/ExportedRobot')
 for link in robot['links']:mesh_from_obj(a.robot_model/link['path'],'/World/ExportedRobot/'+link['name'])
 rep.modify.semantics([('class','robot_audit')],input_prims=['/World/ExportedRobot'],mode='replace')
 rep.modify.semantics([('class','target_object')],input_prims=['/World/Target'],mode='replace')
 product=rep.create.render_product('/World/sensor',(640,480));depth=rep.AnnotatorRegistry.get_annotator('distance_to_image_plane');depth.attach(product);seg=rep.AnnotatorRegistry.get_annotator('semantic_segmentation',init_params={'colorize':False});seg.attach(product)
 d=json.loads((a.sequence/'diagnostics.json').read_text());inventory=json.loads(a.inventory.read_text());frames=d['frames'][a.start:a.stop]
 def place(path,t):
  prim=stage.GetPrimAtPath(path);parent=np.array(UsdGeom.XformCache().GetLocalToWorldTransform(prim.GetParent())).T
  UsdGeom.Xformable(prim).MakeMatrixXform().Set(Gf.Matrix4d((np.linalg.inv(parent)@t).T.tolist()))
 writer=imageio_ffmpeg.write_frames(str(a.output/'geometry_overlay.mp4'),(640,480),fps=30,codec='libx264',pix_fmt_in='rgb24',pix_fmt_out='yuv420p',quality=8,macro_block_size=1);writer.send(None)
 results=[]
 (a.output/'amodal_masks').mkdir()
 for row in frames:
  index=row['frame'];stem=f'{index:06d}.png'
  poses=forward_kinematics(inventory,d['joint_names'],row['measured_joint_positions'][0],row['T_world_robot_base'])
  for name,t in poses.items():place('/World/ExportedRobot/'+name,t)
  place('/World/Target',np.array(row['target_usd_world']))
  rep.orchestrator.step(delta_time=0,rt_subframes=1,pause_timeline=True)
  data=seg.get_data();labels=data['data'].reshape(480,640)
  masks={name:np.isin(labels,[int(k) for k,v in data['info']['idToLabels'].items() if v.get('class')==name]) for name in ['robot_audit','target_object']}
  original_depth=np.array(Image.open(a.sequence/'depth'/stem))*.001;rendered_depth=depth.get_data().reshape(480,640)
  target_mask=np.array(Image.open(a.sequence/'masks'/stem))>0;intersection=target_mask&masks['target_object'];union=target_mask|masks['target_object']
  metrics={'frame':index,'target_mask_iou':float(intersection.sum()/union.sum()) if union.any() else 1.,'target_pixels':int(target_mask.sum())}
  image=np.array(Image.open(a.sequence/'rgb'/stem))[:,:,:3].copy()
  for name,color in [('target_object',(0,255,0)),('robot_audit',(0,255,255))]:
   mask=masks[name];inside=cv2.erode(mask.astype(np.uint8),np.ones((3,3),np.uint8))>0
   valid=inside&np.isfinite(rendered_depth)&(original_depth>0);error=np.abs(rendered_depth[valid]-original_depth[valid])
   metrics[name+'_depth_p95_m']=float(np.percentile(error,95)) if error.size else None
   metrics[name+'_depth_samples']=int(valid.sum())
   contours,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);cv2.drawContours(image,contours,-1,color,1)
  occluders=[stage.GetPrimAtPath(path) for path in ['/World/ExportedRobot','/World/PackingTable','/World/Background']]
  for prim in occluders:
   if prim:UsdGeom.Imageable(prim).MakeInvisible()
  rep.orchestrator.step(delta_time=0,rt_subframes=1,pause_timeline=True)
  isolated=seg.get_data();target_ids=[int(k) for k,v in isolated['info']['idToLabels'].items() if v.get('class')=='target_object']
  amodal=np.isin(isolated['data'].reshape(480,640),target_ids)
  for prim in occluders:
   if prim:UsdGeom.Imageable(prim).MakeVisible()
  area=int(amodal.sum())
  metrics['amodal_pixels']=area
  metrics['visible_fraction']=float(target_mask.sum()/area) if area else None
  metrics['touches_image_boundary']=bool(amodal[0].any() or amodal[-1].any() or amodal[:,0].any() or amodal[:,-1].any())
  Image.fromarray(amodal.astype(np.uint8)*255).save(a.output/'amodal_masks'/stem,compress_level=1)
  contours,_=cv2.findContours(amodal.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
  cv2.drawContours(image,contours,-1,(0,255,0),1)
  writer.send(np.ascontiguousarray(image))
  if index%30==0:Image.fromarray(image).save(a.output/(stem))
  results.append(metrics)
 writer.close()
 passes=all(r['target_mask_iou']>=.90 and all(r[n+'_depth_p95_m'] is None or r[n+'_depth_p95_m']<=.003 for n in ['target_object','robot_audit']) and r['robot_audit_depth_samples']>100 and r['amodal_pixels']>0 and not r['touches_image_boundary'] for r in results) and any(r['target_object_depth_samples']>0 for r in results)
 report={'passed':passes,'protocol':'exported_OBJ_encoder_FK_and_object_GT_same_camera_replay','frame_count':len(results),'frames':results,
         'limits':{'target_mask_iou_min':.90,'interior_depth_p95_max_m':.003},'accepted_pilot_sequence':False}
 (a.output/'report.json').write_text(json.dumps(report,indent=2));print({'passed':passes,'frames':len(results),'minimum_target_iou':min(r['target_mask_iou'] for r in results)},flush=True)
except Exception:
 traceback.print_exc();(a.output/'error.txt').write_text(traceback.format_exc())
finally:app.close()
