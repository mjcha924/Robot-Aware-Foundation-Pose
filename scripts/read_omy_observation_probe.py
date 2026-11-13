"""Read diagnostic RGB-D observations without passing validation labels to a model.

This example uses the recorded preceding robot state. Previous object pose must
come from the caller's estimator; simulator GT is never selected here.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image


def read_pair(root, index, previous_estimated_pose):
    root = Path(root)
    if index < 1:
        raise ValueError('This diagnostic capture lacks pre-image state; use index >= 1')
    frames = [json.loads(line) for line in (root/'frames.jsonl').read_text().splitlines()]
    current, previous = frames[index], frames[index-1]
    pose = np.asarray(previous_estimated_pose, dtype=np.float64)
    if pose.shape != (4,4) or not np.isfinite(pose).all():
        raise ValueError('Expected a finite caller-supplied 4x4 estimated pose')
    stem = f'{current["frame"]:06d}.png'
    return {
        'rgb': np.asarray(Image.open(root/'rgb'/stem)),
        'depth_m': np.asarray(Image.open(root/'depth'/stem), dtype=np.float32)*0.001,
        'previous_estimated_pose': pose,
        'joint_positions': np.asarray(current['measured_joint_positions'][0]),
        'previous_joint_positions': np.asarray(previous['measured_joint_positions'][0]),
        'joint_velocities': np.asarray(current['measured_joint_velocities'][0]),
        'timestamp_s': current['timeline_s'],
        'previous_timestamp_s': previous['timeline_s'],
    }


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('--index',type=int,default=1)
    parser.add_argument('--previous-estimated-pose',type=Path,required=True)
    args=parser.parse_args()
    sample=read_pair(args.root,args.index,np.loadtxt(args.previous_estimated_pose))
    print({k:tuple(v.shape) if isinstance(v,np.ndarray) else v for k,v in sample.items()})
