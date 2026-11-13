"""Inspect actual authored colliders, joint limits, frames and finger bounds."""
import argparse,json,traceback
from pathlib import Path
from isaacsim import SimulationApp
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--scene',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
app=SimulationApp({'headless':True})
try:
 import omni.usd
 from pxr import Usd,UsdGeom,UsdPhysics,PhysxSchema
 omni.usd.get_context().open_stage(str(a.scene.resolve()));stage=omni.usd.get_context().get_stage()
 cache=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render','proxy'])
 report={'joints':[],'bodies':[],'colliders':[],'finger_meshes':[],'frames':[]}
 for prim in stage.Traverse():
  path=str(prim.GetPath())
  if prim.IsA(UsdPhysics.Joint):
   report['joints'].append({'path':path,'attributes':{x.GetName():str(x.Get()) for x in prim.GetAttributes() if x.GetName().startswith(('physics:','physxMimic'))},'relationships':{x.GetName():[str(v) for v in x.GetTargets()] for x in prim.GetRelationships()}})
  if prim.HasAPI(UsdPhysics.RigidBodyAPI):report['bodies'].append({'path':path,'attributes':{x.GetName():str(x.Get()) for x in prim.GetAttributes() if x.GetName().startswith(('physics:','physxRigidBody:'))}})
  if prim.HasAPI(UsdPhysics.CollisionAPI):report['colliders'].append({'path':path,'enabled':UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get()})
  if 'rh_' in path and prim.IsA(UsdGeom.Mesh):
   box=cache.ComputeWorldBound(prim).ComputeAlignedRange();report['finger_meshes'].append({'path':path,'min':list(box.GetMin()),'max':list(box.GetMax())})
  if 'effector' in path or 'Target' in path:
   report['frames'].append({'path':path,'transform':str(UsdGeom.XformCache().GetLocalToWorldTransform(prim))})
 (a.output/'physics_inventory.json').write_text(json.dumps(report,indent=2))
 print('INVENTORY_COMPLETE',len(report['colliders']),len(report['bodies']),flush=True)
except Exception:
 traceback.print_exc();(a.output/'error.txt').write_text(traceback.format_exc())
finally:app.close()
