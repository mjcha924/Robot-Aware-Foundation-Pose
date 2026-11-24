"""Regression checks for portable geometry and leakage-free matched rollouts."""
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
import torch
import trimesh
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'scripts'))
from robot_conditioned_pose.contracts import (GEOMETRY_VERSION, check_checkpoint,
    mesh_diameter, evaluation_surface, portable_provenance)
from robot_conditioned_pose.motion_prior import propagate_pose, validate_pose
from robot_conditioned_pose.omy_sequence import OmySequence
from robot_conditioned_pose.data import FeatureDataset, check_splits
from evaluate_robot_tracker import rollout, score_predictions
from test_omy_training_integration import fixture


def pose(x=0., y=0., z=0., angle=0.):
    t = torch.eye(4)
    c, s = np.cos(angle), np.sin(angle)
    t[:3,:3] = torch.tensor([[c,-s,0],[s,c,0],[0,0,1]], dtype=t.dtype)
    t[:3,3] = torch.tensor([x,y,z])
    return t


def test_portable_checkpoint_keeps_semantics_and_weight_identity(tmp_path):
    weight = tmp_path/'weights.pt'; weight.write_bytes(b'content')
    cfg = dict(ckpt_dir=str(weight), crop_ratio=1.2)
    saved = dict(cfg=dict(cfg, ckpt_dir='/other/machine/weights.pt'), provenance=dict(
        weight_sha256=hashlib.sha256(b'content').hexdigest(), geometry_version=GEOMETRY_VERSION))
    check_checkpoint(saved, cfg)
    with pytest.raises(ValueError, match='config'): check_checkpoint(saved, dict(cfg, crop_ratio=1.3))
    weight.write_bytes(b'different')
    with pytest.raises(ValueError, match='weight content'): check_checkpoint(saved, cfg)
    weight.write_bytes(b'content'); saved['provenance'].pop('geometry_version')
    with pytest.raises(ValueError, match='rebuild'): check_checkpoint(saved, cfg)


def test_split_and_resume_identity_ignore_weight_location_only():
    a = dict(cfg=dict(ckpt_dir='/a', crop_ratio=1.2), weight_sha256='same', upstream_commit='same',
             geometry_version=GEOMETRY_VERSION, sequence_ids=['train'])
    b = dict(a, cfg=dict(a['cfg'], ckpt_dir='/b'), sequence_ids=['val'])
    check_splits(SimpleNamespace(manifest=a), SimpleNamespace(manifest=b))
    assert portable_provenance(a) == portable_provenance(dict(a, cfg=b['cfg']))
    b['weight_sha256'] = 'different'
    with pytest.raises(ValueError, match='weight_sha256'):
        check_splits(SimpleNamespace(manifest=a), SimpleNamespace(manifest=b))


def test_old_cache_rejected(tmp_path):
    (tmp_path/'manifest.json').write_text(json.dumps(dict(samples=['0.pt'])))
    with pytest.raises(ValueError, match='rebuild'): FeatureDataset(tmp_path)


@pytest.mark.parametrize('points', [np.array([[0,0,0],[1,0,0],[0,1,0]]),
    np.array([[0,0,0],[0,0,2],[0,0,1]]), np.array([[0,0,0],[1,2,3],[0,2,0],[1,0,0]])])
def test_exact_diameter_independent_of_rng_and_vertex_order(points):
    expected = np.linalg.norm(points[:,None]-points[None], axis=-1).max()
    state = np.random.get_state()
    for seed in (0,9,103):
        np.random.seed(seed)
        before = np.random.get_state()
        actual = mesh_diameter(SimpleNamespace(vertices=points[::-1]))
        assert actual == pytest.approx(expected)
        assert np.array_equal(before[1], np.random.get_state()[1])
    np.random.set_state(state)


def test_dense_surface_independent_from_global_rng():
    mesh = trimesh.creation.box(extents=[.1,.2,.3])
    a = evaluation_surface(mesh)
    np.random.seed(912)
    np.random.randn(100)
    b = evaluation_surface(mesh)
    np.testing.assert_array_equal(a,b)
    assert a.shape == (4096,3)
    assert not np.array_equal(a[:256], evaluation_surface(mesh,256,seed=0))


def test_rigid_motion_camera_change_and_constant_tool_offset():
    e0, e1 = pose(.2,.3,angle=.5), pose(-.1,.2,angle=1.2)
    c0, c1 = pose(z=-1,angle=.2), pose(.1,z=-.8,angle=-.3)
    attached = pose(.2,.1,z=.1,angle=.7)  # lever arm: rotation must also move object origin
    prior = torch.linalg.inv(c0) @ e0 @ attached
    expected = torch.linalg.inv(c1) @ e1 @ attached
    actual = propagate_pose(prior,c0,c1,e0,e1)
    torch.testing.assert_close(actual,expected)
    offset = pose(.3, -.2, angle=.4)
    torch.testing.assert_close(propagate_pose(prior,c0,c1,e0@offset,e1@offset),expected)
    static = propagate_pose(prior,c0,c1)
    torch.testing.assert_close(c1@static,c0@prior)
    with pytest.raises(ValueError,match='both'): propagate_pose(prior,c0,c1,e0,None)


def test_cached_inputs_no_repeated_io_or_fk_and_no_gt(tmp_path, monkeypatch):
    fixture(tmp_path)
    import robot_conditioned_pose.omy_sequence as module
    actual = module.forward_kinematics
    calls = []
    def counted(*args):
        calls.append(1); return actual(*args)
    monkeypatch.setattr(module,'forward_kinematics',counted)
    reader = OmySequence(tmp_path)
    # Construction consumed all JSON inputs. Repeated points must not read any file.
    def forbidden(*args, **kwargs): raise AssertionError('unexpected file I/O')
    monkeypatch.setattr(Path, 'read_text', forbidden)
    first = reader.points(1,torch.eye(4),1.)
    assert len(calls)==2
    second = reader.points(1,pose(x=.1),1.)
    assert len(calls)==2
    assert not torch.equal(first[:,:3],second[:,:3])
    reader.effector_pose(1,'link')
    assert len(calls)==2
    from PIL import Image
    original_open = Image.open
    image_calls = []
    def counted_open(*args,**kwargs):
        image_calls.append(1); return original_open(*args,**kwargs)
    monkeypatch.setattr(Image,'open',counted_open)
    reader.observation(1); reader.observation(1)
    assert len(image_calls)==2


def test_base_movement_included_in_previous_surface(tmp_path):
    rows=fixture(tmp_path)
    rows[1]['joint_positions']=[0.]
    rows[1]['T_world_robot_base'][0][3]=.1
    # fixture identities share references in memory, so replace explicitly.
    rows[0]['T_world_robot_base']=np.eye(4).tolist()
    rows[0]['T_world_camera']=np.eye(4).tolist()
    rows[1]['T_world_camera']=np.eye(4).tolist()
    (tmp_path/'robot_observations.jsonl').write_text('\n'.join(map(json.dumps,rows)))
    reader=OmySequence(tmp_path)
    points=reader.points(1,torch.eye(4),1.)
    torch.testing.assert_close(points[:512,6],torch.full((512,),3.))
    torch.testing.assert_close(points[:512,7:9],torch.zeros(512,2))


@pytest.mark.parametrize('method', ['hold','kinematic','visual','kinematic-refine','learned'])
def test_rollout_same_initial_no_truth_and_single_prior_per_frame(tmp_path, method):
    rows=fixture(tmp_path)
    reader=OmySequence(tmp_path)  # GT file deliberately absent
    initial=pose(x=.4,z=1.)
    seen=[]
    def refine(i, estimate):
        seen.append((i, estimate.clone())); return estimate
    use_visual=method in ('visual','kinematic-refine','learned')
    result=list(rollout(reader,initial,method,refine if use_visual else None,'link'))
    torch.testing.assert_close(torch.tensor(result[0]['T_camera_mesh']),initial)
    expected = reader.effector_pose(1,'link') @ torch.linalg.inv(reader.effector_pose(0,'link')) @ initial if 'kinematic' in method else initial
    torch.testing.assert_close(torch.tensor(result[1]['T_camera_mesh']),expected)
    assert len(seen)==int(use_visual) and (not seen or seen[0][0]==1)
    with pytest.raises(ValueError,match='Unknown effector'): reader.effector_pose(0,'wrong')


def test_scoring_excludes_initializer_and_uses_dense_points():
    target=pose()
    reader=SimpleNamespace(mesh=trimesh.creation.box(), symmetries=target[None], target=lambda i:target)
    rows=[dict(frame_id=str(i),T_camera_mesh=pose(x=x).tolist(),tracking_seconds=.02) for i,x in enumerate([1.,.02,.04])]
    frames,metrics=score_predictions(reader,rows,1.)
    assert metrics['initial_error_m']==pytest.approx(1.)
    assert metrics['mean_error_m']==pytest.approx(.03)
    assert metrics['tracked_frames']==2 and metrics['failure_fraction_10pct_diameter']==0
    assert len(frames)==3


def test_cpu_evaluator_writes_complete_rollout_without_upstream(tmp_path,monkeypatch):
    import evaluate_robot_tracker as evaluator
    import validate_isaac_export
    sequence=tmp_path/'sequence'; sequence.mkdir()
    rows=fixture(sequence)
    for r in rows:r['T_world_object_gt']=pose(z=1.).tolist()
    (sequence/'frames.jsonl').write_text('\n'.join(map(json.dumps,rows)))
    initial=tmp_path/'initial.npy'; np.save(initial,pose(z=1.).numpy())
    output=tmp_path/'results'
    # Minimal fixture is intentionally not the full packaged export schema.
    # Full schema validator is covered separately by test_validate_isaac_export.
    monkeypatch.setattr(validate_isaac_export,'validate_sequence',lambda _:[])
    monkeypatch.setattr(sys,'argv',['evaluate',str(sequence),'--initial-pose',str(initial),
        '--initialization','external','--method','kinematic','--effector-link','link','--output',str(output)])
    evaluator.main()
    summary=json.loads((output/'summary.json').read_text())
    assert summary['tracked_frames']==1 and summary['method']=='kinematic'
    assert summary['evaluation_points']==4096 and summary['pretrained_sha256'] is None
    assert len((output/'poses.jsonl').read_text().splitlines())==2
    assert (output/'frame_metrics.jsonl').is_file()


def test_comparison_macro_groups_and_mismatched_init(tmp_path):
    from run_omy_comparison import aggregate
    identity=dict(protocol_version=2,initial_pose_sha256='pose',initialization='external',inputs={},
        mesh_sha256='mesh',geometry_version=GEOMETRY_VERSION,diameter_m=1.,evaluation_points=4096,
        evaluation_seed=2026,first_frame_policy='unchanged',tracked_frames=2,source_commit='source',
        method='visual',model_mode='visual',checkpoint_sha256=None,pretrained_sha256='weight',
        config={},iterations=2,effector_link=None)
    for label in ('hold','kinematic'):
        for sequence,error in [('box_A_04',.1),('box_B_04',.3)]:
            folder=tmp_path/label/sequence;folder.mkdir(parents=True)
            data=dict(identity,mean_error_m=error,final_error_m=error,
                failure_fraction_10pct_diameter=.5,mean_tracking_seconds=.01)
            (folder/'summary.json').write_text(json.dumps(data))
    result=aggregate(tmp_path,['hold','kinematic'],['box_A_04','box_B_04'])
    assert result['methods']['hold']['all']['mean_error_m']==pytest.approx(.2)
    assert result['methods']['kinematic']['A']['sequence_count']==1
    path=tmp_path/'kinematic'/'box_B_04'/'summary.json'
    data=json.loads(path.read_text());data['initial_pose_sha256']='different';path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='incomparable'): aggregate(tmp_path,['hold','kinematic'],['box_A_04','box_B_04'])
    data['initial_pose_sha256']='pose';data['iterations']=3;path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='settings within label'): aggregate(tmp_path,['hold','kinematic'],['box_A_04','box_B_04'])


@pytest.mark.parametrize('invalid', [torch.zeros(4,4), torch.eye(3), torch.full((4,4),float('nan'))])
def test_invalid_initial_pose_rejected(invalid):
    with pytest.raises(ValueError,match='rigid'): validate_pose(invalid)
