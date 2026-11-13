"""Export the scene target visual mesh and inspect its authored material inputs."""
import argparse,json,traceback
from pathlib import Path
from isaacsim import SimulationApp
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scene',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--target-usd')
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
app=SimulationApp({'headless':True})
try:
 import omni.usd
 from pxr import Usd,UsdGeom,UsdShade
 omni.usd.get_context().open_stage(str(a.scene.resolve()));stage=omni.usd.get_context().get_stage()
 if a.target_usd:
  refs=stage.GetPrimAtPath('/World/Target/Asset').GetReferences();refs.ClearReferences();refs.AddReference(a.target_usd)
 root=stage.GetPrimAtPath('/World/Target');cache=UsdGeom.XformCache();inv=cache.GetLocalToWorldTransform(root).GetInverse()
 records=[];materials=[]
 for prim in Usd.PrimRange(root):
  if prim.IsA(UsdGeom.Mesh):
   m=UsdGeom.Mesh(prim);mat=cache.GetLocalToWorldTransform(prim)*inv
   record={'path':str(prim.GetPath()),'points':[list(mat.Transform(v)) for v in m.GetPointsAttr().Get()],'counts':list(m.GetFaceVertexCountsAttr().Get()),'indices':list(m.GetFaceVertexIndicesAttr().Get()),'uv':{}}
   for var in UsdGeom.PrimvarsAPI(prim).GetPrimvars():
    if str(var.GetTypeName()).startswith('texCoord2'):
     record['uv'][var.GetPrimvarName()]={'interpolation':str(var.GetInterpolation()),'values':[list(v) for v in var.ComputeFlattened()]}
   records.append(record)
  if prim.IsA(UsdShade.Shader):
   materials.append({'path':str(prim.GetPath()),'inputs':{v.GetBaseName():str(v.Get()) for v in UsdShade.Shader(prim).GetInputs()}})
 (a.output/'visual_geometry.json').write_text(json.dumps({'frame':'target_root','units':'metres_in_composed_stage','meshes':records,'materials':materials},indent=2))
 import urllib.request,hashlib
 textures=[]
 for prim in Usd.PrimRange(root):
  if prim.IsA(UsdShade.Shader):
   value=UsdShade.Shader(prim).GetInput('diffuse_texture')
   if value:
    asset=value.Get()
    if asset:textures.append(asset.resolvedPath or asset.path)
 if len(set(textures))!=1:raise ValueError('Expected one resolved diffuse texture')
 source=textures[0]
 texture=urllib.request.urlopen(source,timeout=90).read() if source.startswith(('http://','https://')) else Path(source).read_bytes()
 suffix=Path(source).suffix
 (a.output/('texture'+suffix)).write_bytes(texture)
 (a.output/'object.mtl').write_text('newmtl target\nKd 1 1 1\nmap_Kd texture'+suffix+'\n')
 lines=['mtllib object.mtl','usemtl target'];vertex_offset=0;uv_offset=0
 for mesh in records:
  uv=next(iter(mesh['uv'].values()),None)
  if uv is None or uv['interpolation'] not in ('vertex','faceVarying'):raise ValueError('Unsupported UV layout')
  lines.extend('v '+' '.join(map(str,v)) for v in mesh['points'])
  lines.extend('vt '+' '.join(map(str,v)) for v in uv['values'])
  cursor=0
  for count in mesh['counts']:
   face=mesh['indices'][cursor:cursor+count]
   lines.append('f '+' '.join(f'{vertex_offset+v+1}/{uv_offset+(v if uv["interpolation"]=="vertex" else cursor+k)+1}' for k,v in enumerate(face)))
   cursor+=count
  vertex_offset+=len(mesh['points']);uv_offset+=len(uv['values'])
 (a.output/'object.obj').write_text('\n'.join(lines)+'\n')
 manifest={'frame':'target_root','units':'metres','scale':1,'T_object_mesh':[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],'target_source':a.target_usd,'texture_source':source,'files':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in a.output.iterdir() if f.is_file()},'status':'exported_roundtrip_validation_pending'}
 (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2))
 print(json.dumps(materials),flush=True)
except Exception:traceback.print_exc();(a.output/'error.txt').write_text(traceback.format_exc())
finally:app.close()
