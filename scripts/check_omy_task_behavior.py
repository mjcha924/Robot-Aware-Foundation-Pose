"""Measure task behavior from privileged diagnostics and the matching object mesh."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation


def drift(transforms):
    transforms=np.asarray(transforms)
    if len(transforms)==0:return None
    return {'translation_m':float(np.linalg.norm(transforms[:,:3,3]-transforms[0,:3,3],axis=1).max()),
            'rotation_deg':float(np.rad2deg(Rotation.from_matrix(transforms[:,:3,:3]@transforms[0,:3,:3].T).magnitude()).max())}


def check(root,model):
    d=json.loads((root/'diagnostics.json').read_text());rows=d['frames']
    vertices=np.array([[float(v) for v in line.split()[1:4]] for line in (model/'object.obj').read_text().splitlines() if line.startswith('v ')])
    target=np.array([r['target_usd_world'] for r in rows]);effector=np.array([r['T_world_effector'] for r in rows])
    relative=np.linalg.inv(effector)@target
    bottom=np.array([(vertices@t[:3,:3].T+t[:3,3])[:,2].min() for t in target])
    table=.9940513388652052
    phases={phase:[i for i,r in enumerate(rows) if r['phase']==phase] for phase in {r['phase'] for r in rows}}
    report={'validator_version':3,'accepted_pilot_sequence':False,'table_height_m':table,'minimum_object_bottom_m':float(bottom.min()),
            'maximum_object_clearance_m':float(bottom.max()-table),'phase_frames':{p:len(v) for p,v in phases.items()}}
    events=[r.get('validation_contact_events') for r in rows]
    robot_contacts=None if any(e is None for e in events) else [sum(1 for e in es if e['point_count']>0 and any(actor.startswith('/World/Robot') for actor in e['actors'])) for es in events]
    report['contact_substep_records_available']=robot_contacts is not None
    if 'noncontact_sweep' in phases:
        indices=phases['noncontact_sweep'];settled=indices
        motion=drift(target[settled]);report['A']={'object_drift_after_settle':motion,'robot_contact_events':None if robot_contacts is None else sum(robot_contacts[i] for i in settled)}
        report['A']['behavior_pass']=bool(motion and motion['translation_m']<=.002 and motion['rotation_deg']<=2 and robot_contacts is not None and sum(robot_contacts[i] for i in settled)==0)
    if 'lift' in phases:
        hold=phases['lift'][-30:];motion=drift(relative[hold])
        bilateral=False
        if robot_contacts is not None and len(hold)==30:
            bodies={actor for i in hold for e in events[i] if e['point_count']>0 for actor in e['actors']}
            bilateral=any(x.endswith('rh_p12_rn_l2') for x in bodies) and any(x.endswith('rh_p12_rn_r2') for x in bodies)
        report['B']={'hold_frames':hold,'relative_hold_drift':motion,'hold_minimum_clearance_m':float(bottom[hold].min()-table),
                     'hold_bilateral_pad_contact':bilateral}
        carried=phases.get('carry',[])
        if carried:
            pair=np.array([target[hold[-1]],target[carried[-1]]]);report['B']['carry_motion']=drift(pair)
            report['B']['carry_relative_drift']=drift(relative[[hold[-1]]+carried])
            report['B']['carry_minimum_clearance_m']=float(bottom[carried].min()-table)
        report['B']['behavior_pass']=bool(len(hold)==30 and motion['translation_m']<=.01 and motion['rotation_deg']<=10
                                         and bottom[hold].min()-table>=.05 and bilateral and carried
                                         and report['B']['carry_motion']['translation_m']>=.03
                                         and report['B']['carry_motion']['rotation_deg']>=10
                                         and report['B']['carry_minimum_clearance_m']>=.04
                                         and report['B']['carry_relative_drift']['translation_m']<=.01
                                         and report['B']['carry_relative_drift']['rotation_deg']<=10)
    if 'release' in phases and 'retreat' in phases:
        release=phases['release'];retreat=phases['retreat'];last=retreat[-30:];motion=drift(target[last]);tool_motion=float(np.linalg.norm(effector[retreat[-1],:3,3]-effector[release[0],:3,3]))
        report['C']={'release_support_gap_m':float(bottom[release[0]]-table),'final_support_gap_m':float(bottom[last].mean()-table),
                     'final_object_drift':motion,'effector_retreat_m':tool_motion,
                     'final_robot_contact_events':None if robot_contacts is None else sum(robot_contacts[i] for i in last)}
        report['C']['behavior_pass']=bool(len(last)==30 and abs(bottom[release[0]]-table)<=.005
                                         and np.max(np.abs(bottom[last]-table))<=.005 and motion['translation_m']<=.002
                                         and motion['rotation_deg']<=2 and tool_motion>=.05
                                         and robot_contacts is not None and sum(robot_contacts[i] for i in last)==0
                                         and report.get('B',{}).get('behavior_pass',False))
        support_contact=any(e['point_count']>0 and e['impulse_norm_sum_Ns']>1e-8 and any(actor.startswith('/World/PackingTable/') for actor in e['actors']) for i in range(max(0,release[0]-10),release[0]+1) for e in (events[i] or []))
        report['C']['table_support_impulse_before_release']=support_contact
        report['C']['behavior_pass'] &= support_contact
        unsupported=[i for i in phases.get('place',[]) if bottom[i]-table>.005]
        if unsupported:
            placement_drift=drift(relative[[phases['carry'][-1]]+unsupported])
            report['C']['unsupported_placement_relative_drift']=placement_drift
            report['C']['behavior_pass'] &= placement_drift['translation_m']<=.01 and placement_drift['rotation_deg']<=10
    report['no_deep_table_penetration']=bool(bottom.min()>=table-.005)
    path=root/'task_behavior.json'
    if path.exists() and json.loads(path.read_text())!=report:
        version=1
        while (root/f'task_behavior.previous_{version:03d}.json').exists():version+=1
        path.rename(root/f'task_behavior.previous_{version:03d}.json')
    path.write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('model',type=Path)
    a=p.parse_args();print(json.dumps(check(a.root,a.model),indent=2))
