"""Compare source USD and exported textured OBJ at the same frozen pose."""
import argparse,json,traceback
from pathlib import Path
from isaacsim import SimulationApp
p=argparse.ArgumentParser(description=__doc__);p.add_argument('scene',type=Path);p.add_argument('model',type=Path);p.add_argument('output',type=Path)
a=p.parse_args();a.output.mkdir(exist_ok=False)
app=SimulationApp({'headless':True})
try:
 import omni.usd
 import omni.replicator.core as rep
 import numpy as np
 import hashlib
 from PIL import Image
 from pxr import UsdGeom,UsdShade,UsdPhysics,Sdf,Gf
 omni.usd.get_context().open_stage(str(a.scene.resolve()));stage=omni.usd.get_context().get_stage()
 metadata=json.loads((a.model/'manifest.json').read_text())
 if metadata.get('target_source'):
  refs=stage.GetPrimAtPath('/World/Target/Asset').GetReferences();refs.ClearReferences();refs.AddReference(metadata['target_source'])
 for prim in stage.Traverse():
  if prim.HasAPI(UsdPhysics.RigidBodyAPI):UsdPhysics.RigidBodyAPI(prim).CreateRigidBodyEnabledAttr(False)
  if prim.IsA(UsdPhysics.Joint):UsdPhysics.Joint(prim).CreateJointEnabledAttr(False)
 rep.modify.semantics([('class','target_object')],input_prims=['/World/Target'],mode='replace')
 product=rep.create.render_product('/World/sensor',(640,480));rgb=rep.AnnotatorRegistry.get_annotator('rgb');rgb.attach(product);depth=rep.AnnotatorRegistry.get_annotator('distance_to_image_plane');depth.attach(product);seg=rep.AnnotatorRegistry.get_annotator('semantic_segmentation',init_params={'colorize':False});seg.attach(product)
 def capture(name):
  rep.orchestrator.step(delta_time=0,rt_subframes=8,pause_timeline=True);im=rgb.get_data()[:,:,:3].copy();d=depth.get_data().reshape(480,640).copy();s=seg.get_data();ids=[int(k) for k,v in s['info']['idToLabels'].items() if v.get('class')=='target_object'];mask=np.isin(s['data'].reshape(480,640),ids);Image.fromarray(im).save(a.output/(name+'.png'));return im,d,mask
 before=capture('source_usd')
 vertices=[];uv=[];faces=[];uvfaces=[]
 for line in (a.model/'object.obj').read_text().splitlines():
  parts=line.split()
  if not parts:continue
  if parts[0]=='v':vertices.append(tuple(map(float,parts[1:4])))
  if parts[0]=='vt':uv.append(tuple(map(float,parts[1:3])))
  if parts[0]=='f':
   faces.append([int(x.split('/')[0])-1 for x in parts[1:]]);uvfaces.extend(int(x.split('/')[1])-1 for x in parts[1:])
 stage.GetPrimAtPath('/World/Target/Asset').SetActive(False)
 mesh=UsdGeom.Mesh.Define(stage,'/World/Target/ExportedModel');mesh.CreatePointsAttr(vertices);mesh.CreateFaceVertexCountsAttr([len(f) for f in faces]);mesh.CreateFaceVertexIndicesAttr([i for f in faces for i in f]);mesh.CreateSubdivisionSchemeAttr('none')
 st=UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('st',Sdf.ValueTypeNames.TexCoord2fArray,UsdGeom.Tokens.faceVarying);st.Set([uv[i] for i in uvfaces])
 mat=UsdShade.Material.Define(stage,'/World/Target/ExportedMaterial');shader=UsdShade.Shader.Define(stage,str(mat.GetPath())+'/Surface');shader.CreateIdAttr('UsdPreviewSurface')
 texture=UsdShade.Shader.Define(stage,str(mat.GetPath())+'/Texture');texture.CreateIdAttr('UsdUVTexture');texture.CreateInput('file',Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath(str((a.model/'texture.png').resolve())));texture.CreateInput('sourceColorSpace',Sdf.ValueTypeNames.Token).Set('sRGB')
 reader=UsdShade.Shader.Define(stage,str(mat.GetPath())+'/UV');reader.CreateIdAttr('UsdPrimvarReader_float2');reader.CreateInput('varname',Sdf.ValueTypeNames.Token).Set('st');texture.CreateInput('st',Sdf.ValueTypeNames.Float2).ConnectToSource(reader.ConnectableAPI(),'result');shader.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).ConnectToSource(texture.ConnectableAPI(),'rgb');mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface');UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(mat)
 after=capture('exported_obj');common=before[2]&after[2];union=before[2]|after[2]
 report={'mask_iou':float(common.sum()/union.sum()),'depth_p95_m':float(np.percentile(np.abs(before[1][common]-after[1][common]),95)),'rgb_mae_8bit':float(np.abs(before[0][common].astype(float)-after[0][common]).mean()),'object_obj_sha256':hashlib.sha256((a.model/'object.obj').read_bytes()).hexdigest(),'texture_sha256':hashlib.sha256((a.model/'texture.png').read_bytes()).hexdigest(),'scene_sha256':hashlib.sha256(a.scene.read_bytes()).hexdigest(),'note':'Same pose/camera/light; material implementations differ (OmniPBR vs UsdPreviewSurface). Review images before acceptance.'};(a.output/'report.json').write_text(json.dumps(report,indent=2));print(report,flush=True)
except Exception:traceback.print_exc();(a.output/'error.txt').write_text(traceback.format_exc())
finally:app.close()
