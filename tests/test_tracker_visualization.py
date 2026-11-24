import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pytest
import torch
import trimesh
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
from robot_conditioned_pose.visualization import (project_segments,box_edges,mesh_edges,render_frame,
    validate_intrinsics,PREDICTED,GROUND_TRUTH,ROBOT)
from robot_conditioned_pose.omy_sequence import OmySequence
from visualize_robot_tracker import load_predictions,check_provenance,main
from test_omy_training_integration import fixture


def make_scene(tmp_path):
    dataset=tmp_path/'dataset';dataset.mkdir()
    sequence=dataset/'box_B_04';sequence.mkdir()
    rows=fixture(sequence)
    k=np.array([[250,0,160],[0,250,120],[0,0,1.]])
    mesh=trimesh.creation.box(extents=[.2,.14,.12]);mesh.export(sequence/'mesh/object.obj')
    link=trimesh.creation.box(extents=[.08,.3,.08]);link.export(sequence/'robot/link.obj')
    manifest=json.loads((sequence/'manifest.json').read_text());manifest['camera']['K']=k.tolist()
    offset=np.eye(4);offset[0,3]=.07
    manifest['mesh']['T_object_mesh']=offset.tolist()
    (sequence/'manifest.json').write_text(json.dumps(manifest))
    predictions=[]
    for i,row in enumerate(rows):
        base=np.eye(4);base[:3,3]=[-.12,0,.9]
        row['T_world_camera']=np.eye(4).tolist();row['T_world_robot_base']=base.tolist()
        rgb=np.full((240,320,3),[50,61,70],dtype=np.uint8)
        rgb[95:145,130:190]=[170,180,190]
        Image.fromarray(rgb).save(sequence/'rgb'/f'{i:06d}.png')
        gt=np.eye(4);gt[:3,3]=[-.07,.02,1.]
        pred=gt@offset;pred[0,3]+=.04*i
        predictions.append(dict(frame_id=row['frame_id'],frame_index=i,T_camera_mesh=pred.tolist()))
    (sequence/'robot_observations.jsonl').write_text('\n'.join(map(json.dumps,rows)))
    truth=[dict(r,T_world_object_gt=gt.tolist(),T_world_robot_links={'link':(np.eye(4)*999).tolist()}) for r in rows]
    (sequence/'frames.jsonl').write_text('\n'.join(map(json.dumps,truth)))
    run=tmp_path/'run';run.mkdir();poses=run/'poses.jsonl';poses.write_text('\n'.join(map(json.dumps,predictions)))
    return sequence,poses,k


def test_projection_uses_opencv_axes_and_camera_transform():
    k=np.array([[100,0,50],[0,100,40],[0,0,1.]])
    pose=np.eye(4);pose[2,3]=1
    segments=np.array([[[0,0,0],[.1,.1,0]]])
    pixels,ids=project_segments(segments,pose,k,(100,80))
    np.testing.assert_allclose(pixels,[[[50,40],[60,50]]]);assert ids.tolist()==[0]


def test_projection_clips_behind_camera_and_offscreen():
    k=np.array([[100,0,50],[0,100,40],[0,0,1.]])
    lines=np.array([[[0,0,-2],[0,0,-1]], [[-10,0,1],[10,0,1]],
                    [[0,0,-1],[0,.1,1]], [[-10,10,1],[-9,10,1]]])
    pixels,ids=project_segments(lines,np.eye(4),k,(100,80))
    assert ids.tolist()==[1,2]
    assert np.isfinite(pixels).all() and np.all(pixels>=0)
    assert np.all(pixels[...,0]<=99) and np.all(pixels[...,1]<=79)
    np.testing.assert_allclose(pixels[0],[[0,40],[99,40]])


def test_boxes_sparse_edges_and_intrinsics():
    mesh=trimesh.creation.box(extents=[.2,.1,.3])
    assert box_edges(mesh).shape==(12,2,3)
    assert mesh_edges(mesh,5).shape==(5,2,3)
    np.testing.assert_array_equal(mesh_edges(mesh,5),mesh_edges(mesh,5))
    with pytest.raises(ValueError,match='intrinsics'): validate_intrinsics(np.ones((3,4)))


def test_gt_raw_mesh_offset_and_fk_does_not_use_simulator_links(tmp_path):
    sequence,poses,k=make_scene(tmp_path)
    reader=OmySequence(sequence)
    np.testing.assert_allclose(reader.target(0).numpy()[:3,3],[0,.02,1],atol=1e-7)
    # Poisoned simulator link truth is irrelevant to robot projection.
    links=reader.robot_link_poses(1)
    np.testing.assert_allclose(links['link'][:3,3],[-.12,0,.9])
    assert np.allclose(links['link'][:3,:3].T@links['link'][:3,:3],np.eye(3))
    assert not np.array_equal(links['link'],reader.robot_link_poses(0)['link'])


def test_prediction_alignment_and_partial_prefix(tmp_path):
    sequence,path,k=make_scene(tmp_path);reader=OmySequence(sequence)
    rows=load_predictions(path,reader.frames);path.write_text(json.dumps(rows[0]))
    with pytest.raises(ValueError,match='count'): load_predictions(path,reader.frames)
    assert len(load_predictions(path,reader.frames,True))==1
    path.write_text('\n'.join(map(json.dumps,rows[::-1])))
    with pytest.raises(ValueError,match='alignment'): load_predictions(path,reader.frames)
    rows[0]['T_camera_mesh'][0][0]=2
    path.write_text('\n'.join(map(json.dumps,rows)))
    with pytest.raises(ValueError,match='rigid'): load_predictions(path,reader.frames)


def test_provenance_rejects_wrong_observations_and_respects_no_gt(tmp_path):
    sequence,path,k=make_scene(tmp_path);reader=OmySequence(sequence)
    assert check_provenance(path,reader)['status']=='unverified'
    run={'sequence':sequence.name,'inputs':{'robot_observations.jsonl':'bad'}}
    (path.parent/'run.json').write_text(json.dumps(run))
    with pytest.raises(ValueError,match='hash mismatch'): check_provenance(path,reader)
    run['inputs']={'frames.jsonl':'bad'}
    (path.parent/'run.json').write_text(json.dumps(run))
    (sequence/'frames.jsonl').unlink()
    assert 'GT unchecked' in check_provenance(path,reader,True)['status']


def test_grid_has_three_layers_and_no_mutation(tmp_path):
    sequence,path,k=make_scene(tmp_path);reader=OmySequence(sequence)
    rgb=Image.open(sequence/'rgb/000001.png').convert('RGB');original=np.array(rgb)
    row=load_predictions(path,reader.frames)[1]
    obj=reader.mesh;link=trimesh.load(sequence/'robot/link.obj',process=False)
    canvas,stats=render_frame(rgb,k,np.array(row['T_camera_mesh']),reader.target(1).numpy(),reader.robot_link_poses(1),
        mesh_edges(obj,512),box_edges(obj),{'link':mesh_edges(link,128)},.07,'Frame 000001',effector_link='link')
    assert canvas.size==(640,590) and stats['predicted_box_visible_edges']==12
    pixels=np.array(canvas)
    # Check the combined image region, not legend colors.
    combined=pixels[240+110+25:,320:]
    for color in (PREDICTED,GROUND_TRUTH,ROBOT): assert np.any(np.all(combined==color,axis=2))
    np.testing.assert_array_equal(rgb,original)


def test_png_cli_frame_mapping_input_unchanged_and_no_gt(tmp_path):
    sequence,path,k=make_scene(tmp_path)
    before=path.read_bytes()
    out=tmp_path/'visualization'
    result=main([str(sequence),'--poses',str(path),'--output',str(out),'--effector-link','link','--png-only',
                 '--start','1','--stride','2'])
    assert result['frames']==1 and result['fps']==15
    mapping=json.loads((out/'frames.jsonl').read_text());assert mapping['frame_index']==1
    assert (out/'frames/000001.png').is_file() and (out/'preview.png').is_file()
    assert path.read_bytes()==before
    with pytest.raises(FileExistsError):
        main([str(sequence),'--poses',str(path),'--output',str(out),'--effector-link','link','--png-only'])
    (sequence/'frames.jsonl').unlink()
    result=main([str(sequence),'--poses',str(path),'--output',str(tmp_path/'no-gt'),'--effector-link','link',
                 '--png-only','--no-gt','--layout','overlay'])
    assert result['no_gt'] and result['gt_sha256'] is None


def test_mp4_cli_round_trip(tmp_path):
    pytest.importorskip('imageio_ffmpeg')
    import imageio.v2 as imageio
    sequence,path,k=make_scene(tmp_path)
    out=tmp_path/'video'
    result=main([str(sequence),'--poses',str(path),'--output',str(out),'--effector-link','link'])
    with imageio.get_reader(out/'overlay.mp4',format='FFMPEG') as video:
        assert video.count_frames()==2
        assert video.get_meta_data()['fps']==pytest.approx(30)
        assert video.get_data(0).shape==(590,640,3)
    assert result['provenance']['status']=='unverified'
