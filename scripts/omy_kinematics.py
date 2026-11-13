"""Canonical OMY rigid-link FK from the pinned USD joint inventory."""
import ast
import numpy as np
from scipy.spatial.transform import Rotation


def joint_frame(attributes, side):
    transform = np.eye(4)
    transform[:3, 3] = ast.literal_eval(attributes['physics:localPos'+str(side)])
    w, x, y, z = ast.literal_eval(attributes['physics:localRot'+str(side)])
    transform[:3, :3] = Rotation.from_quat([x, y, z, w]).as_matrix()
    return transform


def forward_kinematics(inventory, joint_names, positions, world_base):
    if len(joint_names) != len(positions) or len(set(joint_names)) != len(joint_names):
        raise ValueError('Joint names and positions must have matching unique order')
    angles = dict(zip(joint_names, positions))
    world = {'/World/Robot/OMY/world': np.asarray(world_base)}
    pending = [j for j in inventory['joints'] if j['path'].rsplit('/', 1)[-1] in angles]
    while pending:
        remaining = []
        for joint in pending:
            parent = joint['relationships']['physics:body0'][0]
            if parent not in world:
                remaining.append(joint)
                continue
            child = joint['relationships']['physics:body1'][0]
            attributes = joint['attributes']
            angle = angles[joint['path'].rsplit('/', 1)[-1]]
            rotation = np.eye(4)
            rotation[:3, :3] = Rotation.from_euler(attributes['physics:axis'].lower(), angle).as_matrix()
            world[child] = world[parent] @ joint_frame(attributes, 0) @ rotation @ np.linalg.inv(joint_frame(attributes, 1))
        if len(remaining) == len(pending):
            raise ValueError('Disconnected or cyclic joint graph')
        pending = remaining
    return {path.rsplit('/', 1)[-1]: transform for path, transform in world.items()}
