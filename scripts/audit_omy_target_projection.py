"""Audit projected target vertices against masks; not a rendered amodal audit."""
import argparse,json
from pathlib import Path
import numpy as np
import cv2
from PIL import Image
p=argparse.ArgumentParser(description=__doc__);p.add_argument('sequence',type=Path);p.add_argument('geometry',type=Path);p.add_argument('--stride',type=int,default=30)
a=p.parse_args();frames=[json.loads(s) for s in (a.sequence/'frames.jsonl').read_text().splitlines()];meshes=json.loads(a.geometry.read_text())['meshes'];vertices=np.concatenate([m['points'] for m in meshes]);K=np.array(json.loads((a.sequence/'camera.json').read_text())['K']);out=a.sequence/'object_projection_audit';out.mkdir(exist_ok=False);report=[]
for row in frames[::a.stride]:
 t=np.linalg.inv(row['T_world_camera'])@np.array(row['target_usd_world']);xyz=(t@np.c_[vertices,np.ones(len(vertices))].T).T[:,:3]
 if np.any(xyz[:,2]<=0):raise RuntimeError('Target crosses camera plane')
 uv=xyz@K.T;uv=uv[:,:2]/uv[:,2:];hull=cv2.convexHull(np.round(uv).astype(np.int32));mask=np.zeros((480,640),np.uint8);cv2.fillConvexPoly(mask,hull,255)
 stem=f'{row["frame"]:06d}.png';visible=np.array(Image.open(a.sequence/'masks'/stem))>0;expanded=cv2.dilate(mask,np.ones((3,3),np.uint8))>0
 outside=int(np.count_nonzero(visible&~expanded));report.append({'frame':row['frame'],'visible_pixels':int(visible.sum()),'visible_outside_projected_hull_with_1px_tolerance':outside,'truncated':bool(np.any(uv<0) or np.any(uv[:,0]>=640) or np.any(uv[:,1]>=480))})
 image=cv2.imread(str(a.sequence/'rgb'/stem));cv2.polylines(image,[hull],True,(0,255,0),1);cv2.imwrite(str(out/stem),image)
(out/'report.json').write_text(json.dumps({'method':'convex_hull_of_projected_visual_vertices','limitation':'Containment check only; does not validate robot geometry, pixel-perfect silhouette, depth, or rendered amodal visibility.','samples':report,'passed_containment':all(r['visible_outside_projected_hull_with_1px_tolerance']==0 for r in report)},indent=2))
print(out)
