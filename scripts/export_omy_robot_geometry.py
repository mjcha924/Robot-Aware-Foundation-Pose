"""Export canonical body-local OMY visual meshes for robot geometry inputs."""
import argparse,json,hashlib,traceback
from pathlib import Path
from isaacsim import SimulationApp
p=argparse.ArgumentParser(description=__doc__);p.add_argument('scene',type=Path);p.add_argument('output',type=Path)
a=p.parse_args();a.output.mkdir(exist_ok=False)
app=SimulationApp({'headless':True})
try:
 import omni.usd
 from pxr import Usd,UsdGeom,UsdPhysics
 omni.usd.get_context().open_stage(str(a.scene.resolve()));stage=omni.usd.get_context().get_stage();cache=UsdGeom.XformCache();links=[]
 bodies=[p for p in stage.Traverse() if str(p.GetPath()).startswith('/World/Robot/') and p.HasAPI(UsdPhysics.RigidBodyAPI)]
 for body in bodies:
  inverse=cache.GetLocalToWorldTransform(body).GetInverse();vertices=[];faces=[]
  for prim in Usd.PrimRange(body):
   if not prim.IsA(UsdGeom.Mesh) or '/collisions/' in str(prim.GetPath()):continue
   owner=prim.GetParent()
   while owner and not owner.HasAPI(UsdPhysics.RigidBodyAPI):owner=owner.GetParent()
   if owner!=body:continue
   if UsdGeom.Imageable(prim).ComputeVisibility()=='invisible':continue
   mesh=UsdGeom.Mesh(prim);transform=cache.GetLocalToWorldTransform(prim)*inverse;offset=len(vertices);vertices.extend(tuple(transform.Transform(v)) for v in mesh.GetPointsAttr().Get());indices=mesh.GetFaceVertexIndicesAttr().Get();cursor=0
   for count in mesh.GetFaceVertexCountsAttr().Get():
    face=[int(v)+offset+1 for v in indices[cursor:cursor+count]];cursor+=count
    faces.extend((face[0],face[j],face[j+1]) for j in range(1,count-1))
  if not vertices:raise RuntimeError('No visual geometry for '+str(body.GetPath()))
  path=a.output/(body.GetName()+'.obj')
  with path.open('w') as f:
   for v in vertices:f.write('v '+' '.join(map(str,v))+'\n')
   for face in faces:f.write('f '+' '.join(map(str,face))+'\n')
  links.append({'name':body.GetName(),'prim_path':str(body.GetPath()),'path':path.name,'vertices':len(vertices),'triangles':len(faces),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
 (a.output/'manifest.json').write_text(json.dumps({'units':'metres','frame':'rigid_body_link_origin','source_revision':'a44392325d2ccb250ba77ece3237b55ba1f206e1','links':links,'status':'exported_verification_pending'},indent=2));print('EXPORTED',len(links),flush=True)
except Exception:traceback.print_exc();(a.output/'error.txt').write_text(traceback.format_exc())
finally:app.close()
