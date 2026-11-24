"""CPU diagnostic wireframes. OpenCV camera axes, raw mesh coordinates, metres.

Lines are intentionally X-ray overlays: no depth test or occlusion inference.
Projection clips segments to the near plane and image frustum before division.
"""
import itertools
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PREDICTED = (55, 230, 245)
GROUND_TRUTH = (255, 99, 190)
ROBOT = (255, 192, 65)
BACKGROUND = (17, 31, 42)


def validate_intrinsics(k):
    k = np.asarray(k, dtype=np.float64)
    if (k.shape != (3, 3) or not np.isfinite(k).all() or k[0,0] <= 0 or k[1,1] <= 0
        or not np.allclose(k[2], [0,0,1])):
        raise ValueError('expected finite OpenCV 3x3 intrinsics with positive focal lengths')
    return k


def project_segments(segments, pose, k, size, near=.001):
    """Transform and clip 3D segments, returning bounded pixel segments and IDs."""
    width, height = size
    points = np.asarray(segments, dtype=np.float64) @ np.asarray(pose)[:3,:3].T + np.asarray(pose)[:3,3]
    if not np.isfinite(points).all(): raise ValueError('non-finite wireframe geometry')
    if len(points) == 0: return np.empty((0,2,2)), np.empty(0,dtype=int)
    start, end = points[:,0], points[:,1]
    lo, hi = np.zeros(len(points)), np.ones(len(points))
    valid = np.ones(len(points), dtype=bool)
    planes = [(np.array([0,0,1]), -near), (k[0],0), ((width-1)*k[2]-k[0],0),
              (k[1],0), ((height-1)*k[2]-k[1],0)]
    for normal, offset in planes:
        a, b = start@normal+offset, end@normal+offset
        outside_a, outside_b = a<0, b<0
        valid &= ~(outside_a & outside_b)
        crossing = outside_a != outside_b
        fraction = np.divide(a, a-b, out=np.zeros_like(a), where=crossing)
        lo = np.where(crossing & outside_a, np.maximum(lo,fraction),lo)
        hi = np.where(crossing & outside_b, np.minimum(hi,fraction),hi)
    ids = np.flatnonzero(valid & (lo<=hi))
    direction = end-start
    clipped = np.stack((start[ids]+lo[ids,None]*direction[ids], start[ids]+hi[ids,None]*direction[ids]),axis=1)
    homogeneous = clipped @ k.T
    pixels = homogeneous[...,:2]/homogeneous[...,2:3]
    return np.clip(pixels, [0,0], [width-1,height-1]), ids


def mesh_edges(mesh, limit):
    """Deterministic sparse edges, bounded to keep CPU diagnostics practical."""
    edges = np.asarray(mesh.edges_unique)
    if limit < 1: raise ValueError('edge limit must be positive')
    if len(edges)>limit: edges=edges[np.linspace(0,len(edges)-1,limit,dtype=int)]
    segments = np.asarray(mesh.vertices)[edges]
    if not np.isfinite(segments).all(): raise ValueError('non-finite mesh')
    return segments


def box_edges(mesh):
    bounds = np.asarray(mesh.bounds)
    bits = np.array(list(itertools.product((0,1),repeat=3)))
    corners = np.where(bits,bounds[1],bounds[0])
    edges = [(i,j) for i in range(8) for j in range(i+1,8) if np.sum(bits[i]!=bits[j])==1]
    return corners[np.asarray(edges)]


@lru_cache(maxsize=8)
def font(size=16):
    try: return ImageFont.truetype('DejaVuSans.ttf', size)
    except OSError:
        try: return ImageFont.load_default(size=size)
        except TypeError: return ImageFont.load_default()


def draw_segments(image, segments, pose, k, color, width=1, dashed=False):
    pixels, ids = project_segments(segments,pose,k,image.size)
    draw = ImageDraw.Draw(image)
    for a,b in pixels:
        if not dashed:
            draw.line([tuple(a),tuple(b)],fill=color,width=width)
        else:
            length=float(np.linalg.norm(b-a))
            for start in np.arange(0,length,10):
                p=a+(b-a)*start/max(length,1e-12)
                q=a+(b-a)*min(start+6,length)/max(length,1e-12)
                draw.line([tuple(p),tuple(q)],fill=color,width=width)
    return len(ids)


def draw_axes(image, pose, k, length, color, label):
    segments = np.stack((np.zeros((3,3)),np.eye(3)*length),axis=1)
    draw_segments(image,segments,pose,k,color,width=2)
    draw = ImageDraw.Draw(image)
    ends = np.eye(3)*length @ pose[:3,:3].T + pose[:3,3]
    occupied=[]
    for index,(axis,point) in enumerate(zip('XYZ',ends)):
        if point[2] < .001: continue
        pixel=k@point; u,v=pixel[:2]/pixel[2]
        # Put GT labels on the opposite side of predicted labels. Fan out Z,
        # whose projection can coincide with the origin when viewed head-on.
        x=u+(-32 if label=='G:' else 8); y=v+(index-1)*13
        for _ in range(3):
            if not any(abs(x-ox)<30 and abs(y-oy)<14 for ox,oy in occupied): break
            y+=14
        if 0<=x<image.width-30 and 0<=y<image.height-14:
            draw.text((x,y),label+axis,fill=color,font=font(12),stroke_width=1,stroke_fill=BACKGROUND)
            occupied.append((x,y))


def object_overlay(rgb, pose, k, edges, box, color, label, axis_length, dashed=False):
    image=rgb.copy()
    draw_segments(image,edges,pose,k,tuple(int(c*.7) for c in color))
    visible=draw_segments(image,box,pose,k,color,width=2,dashed=dashed)
    draw_axes(image,pose,k,axis_length,color,label)
    return image, visible


def label_panel(image, title):
    draw=ImageDraw.Draw(image)
    draw.rectangle((0,0,image.width,25),fill=BACKGROUND)
    draw.text((9,4),title,font=font(14),fill=(235,241,245))
    return image


def render_frame(rgb, k, estimate, target, link_poses, object_edges, object_box,
                 robot_edges, axis_length, frame_label, layout='grid', effector_link='link6', run_label=''):
    """RGB / pose / measured FK / all grid, or one combined overlay."""
    rgb=rgb.convert('RGB')
    poses,pred_visible=object_overlay(rgb,estimate,k,object_edges,object_box,PREDICTED,'P:',axis_length)
    gt_visible=None
    if target is not None:
        poses,gt_visible=object_overlay(poses,target,k,object_edges,object_box,GROUND_TRUTH,'G:',axis_length,True)
    robot,combined=rgb.copy(),poses.copy()
    fk_visible=0
    for name,edges in robot_edges.items():
        if name not in link_poses: raise ValueError('FK has no geometry link: '+name)
        fk_visible+=draw_segments(robot,edges,link_poses[name],k,ROBOT)
        draw_segments(combined,edges,link_poses[name],k,ROBOT)
    if effector_link in link_poses:
        for image in (robot,combined): draw_axes(image,link_poses[effector_link],k,axis_length,ROBOT,'E:')
    if layout=='grid':
        width,height=rgb.size
        canvas=Image.new('RGB',(width*2,height*2+110),BACKGROUND)
        for tile,offset,title in ((rgb,(0,110),'RGB'),(poses,(width,110),'Predicted + GT'),
            (robot,(0,height+110),'Measured robot FK'),(combined,(width,height+110),'Combined (X-ray)')):
            canvas.paste(label_panel(tile,title),offset)
    elif layout=='overlay':
        canvas=Image.new('RGB',(rgb.width,rgb.height+110),BACKGROUND);canvas.paste(combined,(0,110))
    else: raise ValueError('unknown layout')
    draw=ImageDraw.Draw(canvas)
    draw.text((10,5),frame_label,font=font(14),fill='white')
    draw.text((10,26),'P: predicted pose / solid box',font=font(14),fill=PREDICTED)
    draw.text((10,46),'G: GT pose / dashed box' if target is not None else 'G: GT unavailable (--no-gt)',font=font(14),fill=GROUND_TRUTH)
    draw.text((10,66),'E: measured FK | X-ray lines; no depth test',font=font(14),fill=ROBOT)
    draw.text((10,88),run_label or 'Offline diagnostic | saved predictions',font=font(12),fill=(210,219,225))
    # yuv420p requires even dimensions. Pad; never rescale the camera geometry.
    if canvas.width%2 or canvas.height%2:
        padded=Image.new('RGB',(canvas.width+canvas.width%2,canvas.height+canvas.height%2),BACKGROUND)
        padded.paste(canvas,(0,0));canvas=padded
    return canvas,dict(predicted_box_visible_edges=pred_visible,gt_box_visible_edges=gt_visible,
                       robot_visible_edges=fk_visible)
