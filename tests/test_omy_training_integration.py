import json
import sys
from pathlib import Path
import numpy as np
import pytest
import torch
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from robot_conditioned_pose.omy_sequence import OmySequence
from robot_conditioned_pose.data import check_splits
from run_omy_training import verify_checksums


def fixture(root):
    for name in ['mesh','robot','rgb','depth']: (root/name).mkdir()
    obj='v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n'
    (root/'mesh/object.obj').write_text(obj)
    (root/'robot/link.obj').write_text(obj)
    identity=np.eye(4).tolist()
    attributes={'physics:localPos0':'(0, 0, 0)', 'physics:localPos1':'(0, 0, 0)',
        'physics:localRot0':'(1, 0, 0, 0)', 'physics:localRot1':'(1, 0, 0, 0)', 'physics:axis':'Z'}
    inventory={'joints':[{'path':'/j', 'attributes':attributes, 'relationships':{
        'physics:body0':['/World/Robot/OMY/world'], 'physics:body1':['/World/Robot/OMY/link']}}]}
    (root/'robot/joint_inventory.json').write_text(json.dumps(inventory))
    manifest={'frame_count':2,'frames_file':'frames.jsonl','camera':{'K':identity[:3]},
        'mesh':{'path':'mesh/object.obj','T_object_mesh':identity},
        'robot_geometry':{'links':[{'name':'link','path':'robot/link.obj'}]},
        'omy_tracking':{'robot_observations_file':'robot_observations.jsonl',
        'previous_robot_state_file':'previous_robot_state.json','joint_names':['j'],
        'joint_inventory':'robot/joint_inventory.json'}}
    (root/'manifest.json').write_text(json.dumps(manifest))
    rows=[]
    for i in range(2):
        rows.append({'frame_id':f'{i:06d}', 'timestamp_s':(i+1)/30, 'joint_positions':[i*.1],
                     'joint_velocities':[3.], 'T_world_camera':identity,'T_world_robot_base':identity})
        Image.fromarray(np.zeros((4,4,3),np.uint8)).save(root/'rgb'/f'{i:06d}.png')
        Image.fromarray(np.full((4,4),1000,np.uint16)).save(root/'depth'/f'{i:06d}.png')
    (root/'robot_observations.jsonl').write_text('\n'.join(map(json.dumps,rows)))
    prev=dict(rows[0], timestamp_s=0, joint_positions=[-.1])
    (root/'previous_robot_state.json').write_text(json.dumps(prev))
    return rows


def test_no_gt_access_and_surface_velocity(tmp_path):
    fixture(tmp_path)
    # No privileged file exists: constructor, RGB-D and robot input must work.
    reader=OmySequence(tmp_path)
    p=reader.points(1,torch.eye(4),1.)
    assert p.shape==(768,11)
    assert torch.isfinite(p).all() and torch.count_nonzero(p[:512,6:9])>0
    assert torch.all(p[:512,10]==1) and torch.all(p[512:,10]==0)
    f=reader.points(0,torch.eye(4),1.)
    assert torch.count_nonzero(f[:512,6:9])>0  # actual preroll, not fabricated zero
    assert np.all(reader.observation(0)[1]==1.)
    other=OmySequence(tmp_path)
    torch.testing.assert_close(p,other.points(1,torch.eye(4),1.))
    with pytest.raises(FileNotFoundError):reader.target(0)


def test_target_alignment_rejected(tmp_path):
    rows=fixture(tmp_path)
    for r in rows:r['T_world_object_gt']=np.eye(4).tolist()
    rows.reverse()
    (tmp_path/'frames.jsonl').write_text('\n'.join(map(json.dumps,rows)))
    with pytest.raises(ValueError,match='alignment'):OmySequence(tmp_path).target(0)


def test_parent_leak_rejected():
    from types import SimpleNamespace
    a=SimpleNamespace(manifest={'parent_groups':['same']})
    with pytest.raises(ValueError,match='physical parent'):check_splits(a,a)


def test_checksum_failure_and_escape(tmp_path):
    dataset=tmp_path/'dataset';dataset.mkdir();(dataset/'f').write_text('x')
    sums=tmp_path/'checksums'
    sums.write_text('0'*64+'  dataset/f\n')
    with pytest.raises(ValueError,match='mismatch'):verify_checksums(sums,dataset)
    sums.write_text('0'*64+'  ../escape\n')
    with pytest.raises(ValueError,match='outside'):verify_checksums(sums,dataset)
