"""Canonical surface points, normals and motion from inference-available robot state."""
import hashlib,json
import numpy as np
from omy_kinematics import forward_kinematics


def canonical_surface_points(geometry, points_per_link=1024, seed=0):
    """Call once and reuse the returned points for every frame in a sequence."""
    if points_per_link<=0:raise ValueError('points_per_link must be positive')
    canonical={}
    for name,path in sorted(geometry.items()):
        vertices=[];triangles=[]
        for line in path.read_text().splitlines():
            parts=line.split()
            if not parts:continue
            if parts[0]=='v':vertices.append([float(x) for x in parts[1:4]])
            elif parts[0]=='f':
                face=[int(x.split('/')[0])-1 for x in parts[1:]]
                triangles.extend([face[0],face[i],face[i+1]] for i in range(1,len(face)-1))
        v=np.asarray(vertices);faces=np.asarray(triangles);mesh=v[faces]
        cross=np.cross(mesh[:,1]-mesh[:,0],mesh[:,2]-mesh[:,0]);twice_area=np.linalg.norm(cross,axis=1)
        if twice_area.sum()<=0:raise ValueError('Degenerate geometry: '+name)
        link_seed=int.from_bytes(hashlib.sha256(f'{seed}:{name}'.encode()).digest()[:8],'little')
        rng=np.random.default_rng(link_seed);indices=rng.choice(len(faces),points_per_link,p=twice_area/twice_area.sum())
        u=np.sqrt(rng.random(points_per_link));v_bary=rng.random(points_per_link)
        bary=np.stack([1-u,u*(1-v_bary),u*v_bary],axis=1)
        points=(mesh[indices]*bary[:,:,None]).sum(axis=1)
        normals=cross[indices]/twice_area[indices,None]
        canonical[name]={'points_link_m':points,'normals_link':normals,'triangle_indices':indices,'barycentric':bary}
    return canonical


def robot_surface_pair(sample,canonical):
    """Transform identical canonical samples in both frames; never read pose labels."""
    inventory=json.loads(sample['robot_joint_inventory'].read_text())
    current=forward_kinematics(inventory,sample['joint_names'],sample['joint_positions'],sample['T_world_robot_base'])
    previous=forward_kinematics(inventory,sample['joint_names'],sample['previous_joint_positions'],sample['T_world_robot_base'])
    camera_world=np.linalg.inv(sample['T_world_camera']);positions=[];prior=[];normals=[];link_ids=[]
    for index,(name,surface) in enumerate(sorted(canonical.items())):
        t=camera_world@current[name];old=camera_world@previous[name];points=surface['points_link_m']
        positions.append(points@t[:3,:3].T+t[:3,3]);prior.append(points@old[:3,:3].T+old[:3,3])
        normals.append(surface['normals_link']@t[:3,:3].T);link_ids.extend([index]*len(points))
    positions=np.concatenate(positions);prior=np.concatenate(prior)
    return {'positions_camera_m':positions,'previous_positions_camera_m':prior,
            'normals_camera':np.concatenate(normals),'motion_camera_m':positions-prior,
            'link_ids':np.asarray(link_ids,dtype=np.int32),'link_names':tuple(sorted(canonical))}
