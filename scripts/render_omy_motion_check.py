"""PhysX joint-drive motion preview, explicitly not a validated dataset export."""
import argparse
import json
import traceback
from pathlib import Path
from isaacsim import SimulationApp
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--scene',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--frames',type=int,default=120)
p.add_argument('--probe-gripper',action='store_true')
p.add_argument('--settle-target',action='store_true')
p.add_argument('--grasp-probe',action='store_true')
p.add_argument('--upright-target',action='store_true')
p.add_argument('--upright-axis',choices=['X','Y'],default='Y')
p.add_argument('--upright-angle',type=float,default=90)
p.add_argument('--target-usd')
p.add_argument('--target-x',type=float,default=0.22)
p.add_argument('--target-y',type=float,default=-0.16)
p.add_argument('--target-yaw',type=float,default=0)
p.add_argument('--grasp-height',type=float,default=1.05)
p.add_argument('--grasp-offset-x',type=float,default=0)
p.add_argument('--grasp-offset-y',type=float,default=0)
p.add_argument('--grasp-yaw',type=float,default=0)
p.add_argument('--carry-probe',action='store_true')
p.add_argument('--carry-x',type=float,default=0.05)
p.add_argument('--carry-y',type=float,default=0.025)
p.add_argument('--carry-yaw',type=float,default=20)
p.add_argument('--carry-pitch',type=float,default=0)
p.add_argument('--carry-hold-frames',type=int,default=0)
p.add_argument('--place-return-pitch',action='store_true')
p.add_argument('--lift-distance',type=float,default=0.12)
p.add_argument('--moving-pad-centre',action='store_true')
p.add_argument('--tool-inset',type=float,default=0.045)
p.add_argument('--target-mass',type=float,default=0.10)
p.add_argument('--gripper-close',type=float,default=0.8,help='Drive closure in radians, within the authored 1.101 rad limit')
p.add_argument('--release-ramp-frames',type=int,default=0,help='Smooth gripper release over this many 30-Hz frames; zero preserves the diagnostic step command')
p.add_argument('--release-open-angle',type=float,default=0,help='Open target angle in radians during release/retreat')
p.add_argument('--freeze-release-tcp',action='store_true',help='Freeze the closed-grasp control offset while opening and retreating; do not lower the wrist to chase moving fingertips')
p.add_argument('--release-lift-distance',type=float,default=0,help='Raise the open gripper only after target/robot contact clears and table support remains')
p.add_argument('--release-lift-frames',type=int,default=15)
p.add_argument('--collision-approximation',choices=['convexHull','convexDecomposition'],default='convexHull')
p.add_argument('--place-probe',action='store_true')
p.add_argument('--export-observations',action='store_true')
p.add_argument('--occlusion-probe',action='store_true')
p.add_argument('--occlusion-preroll',type=int,default=300)
p.add_argument('--occlusion-cycle-frames',type=int,default=240)
p.add_argument('--occlusion-centre-x',type=float,default=0.323)
p.add_argument('--occlusion-y',type=float,default=-0.334)
p.add_argument('--occlusion-z',type=float,default=1.135)
p.add_argument('--occlusion-amplitude',type=float,default=0.09)
p.add_argument('--occlusion-clearance-rise',type=float,default=0.12)
p.add_argument('--occlusion-gripper-close',type=float,default=0.8)
p.add_argument('--no-gif',action='store_true')
p.add_argument('--pilot-timing',action='store_true',help='Shorter trajectories for 6–10 second task clips; still requires measured validation')
p.add_argument('--stop-after-retreat',action='store_true')
p.add_argument('--solver-position-iterations',type=int,default=32)
p.add_argument('--seed',type=int,default=4100)
p.add_argument('--camera-eye',type=float,nargs=3)
p.add_argument('--camera-look',type=float,nargs=3)
p.add_argument('--approach-clearance',type=float)
p.add_argument('--approach-offset-x',type=float,default=0)
p.add_argument('--approach-offset-y',type=float,default=0)
p.add_argument('--retreat-x',type=float,default=0)
p.add_argument('--retreat-y',type=float,default=0)
a=p.parse_args()
if not 0 <= a.gripper_close <= 1.10:
    p.error('--gripper-close must lie in [0, 1.10] radians')
if bool(a.camera_eye) != bool(a.camera_look):p.error('Supply both camera eye and look positions')
a.output.mkdir(parents=True,exist_ok=False)
import shutil,hashlib,time
shutil.copy2(__file__,a.output/'generator_snapshot.py')
generator_sha256=hashlib.sha256((a.output/'generator_snapshot.py').read_bytes()).hexdigest()
capture_wall_start=time.monotonic()
app=SimulationApp({'headless':True,'renderer':'RaytracedLighting'})
try:
    import carb
    carb.settings.get_settings().set_bool('/rtx/post/histogram/enabled',False)
    import omni.usd
    import omni.replicator.core as rep
    import omni.timeline
    import numpy as np
    np.random.seed(a.seed)
    rep.set_global_seed(a.seed)
    import cv2
    from pxr import UsdPhysics, PhysxSchema, UsdGeom, Usd, Gf, UsdShade
    omni.usd.get_context().open_stage(str(a.scene.resolve()))
    stage=omni.usd.get_context().get_stage()
    if a.camera_eye:
        camera=UsdGeom.Xformable(stage.GetPrimAtPath('/World/sensor'))
        camera.MakeMatrixXform().Set(Gf.Matrix4d().SetLookAt(Gf.Vec3d(*a.camera_eye),Gf.Vec3d(*a.camera_look),Gf.Vec3d(0,0,1)).GetInverse())
    if a.target_usd:
        reference=stage.GetPrimAtPath('/World/Target/Asset').GetReferences()
        reference.ClearReferences();reference.AddReference(a.target_usd)
    physics=UsdPhysics.Scene.Define(stage,'/World/Physics')
    physics.CreateGravityDirectionAttr(Gf.Vec3f(0,0,-1))
    physics.CreateGravityMagnitudeAttr(9.81)
    PhysxSchema.PhysxSceneAPI.Apply(physics.GetPrim()).CreateTimeStepsPerSecondAttr(120)
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            api=PhysxSchema.PhysxArticulationAPI.Apply(prim)
            api.CreateSolverPositionIterationCountAttr(a.solver_position_iterations)
            api.CreateSolverVelocityIterationCountAttr(4)
    material_settings={'target':{'static_friction':0.6,'dynamic_friction':0.5,'restitution':0.0},
                       'finger':{'static_friction':0.9,'dynamic_friction':0.8,'restitution':0.0},
                       'table':{'static_friction':0.5,'dynamic_friction':0.4,'restitution':0.0}}
    physics_materials={}
    for name,values in material_settings.items():
        material=UsdShade.Material.Define(stage,'/World/PhysicsMaterials/'+name)
        api=UsdPhysics.MaterialAPI.Apply(material.GetPrim())
        api.CreateStaticFrictionAttr(values['static_friction']);api.CreateDynamicFrictionAttr(values['dynamic_friction']);api.CreateRestitutionAttr(values['restitution'])
        physics_materials[name]=material
    if a.settle_target or a.grasp_probe or a.occlusion_probe:
        target=stage.GetPrimAtPath('/World/Target')
        xf=UsdGeom.Xformable(target)
        for op in xf.GetOrderedXformOps():
            if op.GetOpType()==UsdGeom.XformOp.TypeTranslate:
                value=op.Get();value[0]=a.target_x;value[1]=a.target_y;op.Set(value)
        xf.AddRotateZOp().Set(a.target_yaw)
        if a.upright_target:
            xf=UsdGeom.Xformable(target)
            (xf.AddRotateXOp() if a.upright_axis=='X' else xf.AddRotateYOp()).Set(a.upright_angle)
            bounds=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render']).ComputeWorldBound(target).ComputeAlignedRange()
            for op in xf.GetOrderedXformOps():
                if op.GetOpType()==UsdGeom.XformOp.TypeTranslate:
                    value=op.Get();value[2]+=0.9951-bounds.GetMin()[2];op.Set(value)
        UsdPhysics.RigidBodyAPI.Apply(target).CreateRigidBodyEnabledAttr(True)
        UsdPhysics.MassAPI.Apply(target).CreateMassAttr(a.target_mass)
        for prim in Usd.PrimRange(target):
            if prim.IsA(UsdGeom.Mesh):
                UsdPhysics.CollisionAPI.Apply(prim).CreateCollisionEnabledAttr(True)
                UsdPhysics.MeshCollisionAPI.Apply(prim).CreateApproximationAttr(a.collision_approximation)
        for path in ['/World/Background/Floor','/World/Background/Wall']:
            UsdPhysics.CollisionAPI.Apply(stage.GetPrimAtPath(path))
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            collision=PhysxSchema.PhysxCollisionAPI.Apply(prim)
            collision.CreateContactOffsetAttr(0.001)
            collision.CreateRestOffsetAttr(0.0)
            path=str(prim.GetPath())
            kind='target' if path.startswith('/World/Target') else 'finger' if '/gripper/' in path else 'table' if path.startswith('/World/PackingTable') else None
            if kind:UsdShade.MaterialBindingAPI.Apply(prim).Bind(physics_materials[kind],materialPurpose='physics')
    contact_bodies=[]
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.RigidBodyAPI) and str(prim.GetPath()).startswith('/World/Robot/'):
            PhysxSchema.PhysxContactReportAPI.Apply(prim).CreateThresholdAttr(0.0)
            contact_bodies.append(str(prim.GetPath()))
    # Accumulate every physics-substep event, not only the final 120-Hz
    # contact-force sample visible at each 30-Hz image.
    from omni.physx import get_physx_simulation_interface
    from pxr import PhysicsSchemaTools
    contact_events=[]
    def on_contact(headers, data):
        for header in headers:
            actors=[str(PhysicsSchemaTools.intToSdfPath(v)) for v in (header.actor0,header.actor1)]
            if '/World/Target' not in actors:continue
            points=data[header.contact_data_offset:header.contact_data_offset+header.num_contact_data]
            contact_events.append({'actors':actors,'type':str(header.type),'point_count':header.num_contact_data,
                                   'impulse_norm_sum_Ns':float(sum(np.linalg.norm(v.impulse) for v in points)),
                                   'minimum_separation_m':float(min((v.separation for v in points),default=0))})
    if a.settle_target or a.grasp_probe or a.occlusion_probe:
        PhysxSchema.PhysxContactReportAPI.Apply(stage.GetPrimAtPath('/World/Target')).CreateThresholdAttr(0.0)
    contact_subscription=get_physx_simulation_interface().subscribe_contact_report_events(on_contact)
    joints={p.GetName():p for p in stage.Traverse() if p.IsA(UsdPhysics.RevoluteJoint)}
    names=['joint1','joint2','joint3','joint4','joint5','joint6']
    for name in names:
        drive=UsdPhysics.DriveAPI.Apply(joints[name],'angular')
        drive.CreateStiffnessAttr(120)
        drive.CreateDampingAttr(12)
        drive.CreateMaxForceAttr(61.4 if name in names[:2] else 31.7)
    lighting=[]
    light_cache=UsdGeom.XformCache()
    for prim in stage.Traverse():
        if str(prim.GetTypeName()).endswith('Light'):
            lighting.append({'path':str(prim.GetPath()),'type':str(prim.GetTypeName()),
                             'inputs':{attr.GetName():str(attr.Get()) for attr in prim.GetAttributes() if attr.GetName().startswith('inputs:') and attr.Get() is not None},
                             'T_world_light':np.array(light_cache.GetLocalToWorldTransform(prim)).T.tolist()})
    render_settings={'auto_exposure':False,'renderer':'RaytracedLighting','resolution':[640,480],
                     'lighting':lighting,'replicator_subframes':1}
    product=rep.create.render_product('/World/sensor',(640,480))
    rgb=rep.AnnotatorRegistry.get_annotator('rgb'); rgb.attach(product)
    if a.export_observations:
        rep.modify.semantics([('class','target_object')],input_prims=['/World/Target'],mode='replace')
        depth=rep.AnnotatorRegistry.get_annotator('distance_to_image_plane');depth.attach(product)
        segmentation=rep.AnnotatorRegistry.get_annotator('semantic_segmentation',init_params={'colorize':False});segmentation.attach(product)
        for name in ['rgb','depth','masks']:(a.output/name).mkdir()
        camera=UsdGeom.Camera(stage.GetPrimAtPath('/World/sensor'))
        focal=camera.GetFocalLengthAttr().Get();aperture=camera.GetHorizontalApertureAttr().Get()
        fx=640*focal/aperture
        stage.GetRootLayer().Export(str((a.output/'capture_scene.usda').resolve()))
        (a.output/'camera.json').write_text(json.dumps({'K':[[fx,0,320],[0,fx,240],[0,0,1]],'resolution':[640,480],'depth':'optical_axis_uint16_mm_zero_invalid','status':'diagnostic_calibration_pending_overlay_validation'},indent=2))
    pad_centres={}
    target_points=[]
    xc=UsdGeom.XformCache()
    target_root=stage.GetPrimAtPath('/World/Target')
    target_inverse=xc.GetLocalToWorldTransform(target_root).GetInverse()
    for prim in Usd.PrimRange(target_root):
        if prim.IsA(UsdGeom.Mesh):
            transform=xc.GetLocalToWorldTransform(prim)*target_inverse
            target_points.extend(list(transform.Transform(v)) for v in UsdGeom.Mesh(prim).GetPointsAttr().Get())
    target_points=np.asarray(target_points)
    if a.moving_pad_centre:
        xc=UsdGeom.XformCache()
        for side in ['l','r']:
            body_path=f'/World/Robot/OMY/gripper/rh_p12_rn_{side}2'
            mesh_path=body_path+f'/visuals/{side}2/mesh'
            mesh=UsdGeom.Mesh(stage.GetPrimAtPath(mesh_path))
            transform=xc.GetLocalToWorldTransform(mesh.GetPrim())*xc.GetLocalToWorldTransform(stage.GetPrimAtPath(body_path)).GetInverse()
            points=np.array([list(transform.Transform(v)) for v in mesh.GetPointsAttr().Get()])
            pad_centres[f'rh_p12_rn_{side}2']=(points.min(0)+points.max(0))/2
    timeline=omni.timeline.get_timeline_interface()
    timeline.play()
    for _ in range(8):
        app.update()
    from PIL import Image
    images=[]
    records=[]
    articulation=None
    physics_metadata={'gravity_m_s2':9.81,'physics_hz':120,'contact_offset_m':0.001,'rest_offset_m':0.0,
                      'materials':material_settings,'target_mass_kg':a.target_mass,
                      'target_collider':a.collision_approximation,'mass_source':'explicit_simulation_assumption_not_measured_real_object'}
    physics_metadata['solver_position_iterations']=a.solver_position_iterations
    physics_metadata['solver_velocity_iterations']=4
    physics_metadata['inertia_layout']='9 column-major entries, at COM, expressed in rigid-body frame'
    physics_metadata['com_frame']='principal_axes_frame_relative_to_rigid_body_root; xyz + quaternion xyzw'
    offset=None
    phase='approach'
    phase_start=0
    converged=0
    place_z=None
    support_frames=0
    release_clear_frames=0
    release_lift_start=None
    descend_frames=60 if a.pilot_timing else 120
    close_frames=75 if a.pilot_timing else 90
    close_ramp=60
    lift_frames=75 if a.pilot_timing else 210
    carry_frames=(75 if a.pilot_timing else 180)+a.carry_hold_frames
    release_frames=45 if a.pilot_timing else 90
    for i in range(a.frames):
        # Small reversible joint sweep from authored straight posture.
        s=np.sin(np.pi*i/(a.frames-1))**2
        commands=[0,0,0,0,0,0] if a.settle_target else [25*s,-25*s,35*s,-10*s,0,0]
        if (a.grasp_probe or a.occlusion_probe) and articulation is not None:
            from scipy.spatial.transform import Rotation
            q=articulation.get_dof_positions().cpu().numpy()[0]
            bodies=list(articulation.shared_metatype.link_names)
            idx=bodies.index('link6')
            pose=articulation.get_link_transforms().cpu().numpy()[0,idx]
            rotation=Rotation.from_quat(pose[3:]).as_matrix()
            if offset is None:
                xc=UsdGeom.XformCache()
                root=xc.GetLocalToWorldTransform(stage.GetPrimAtPath('/World/Robot/OMY/link6'))
                tip=xc.GetLocalToWorldTransform(stage.GetPrimAtPath('/World/Robot/OMY/link6/end_effector_flange_link/end_effector_link'))
                offset=np.array((tip*root.GetInverse()).ExtractTranslation())
                offset[1]+=a.tool_inset  # contact-pad centre, 45 mm behind authored tool tip
            if a.moving_pad_centre and not (a.freeze_release_tcp and phase in ('release','retreat')):
                poses=articulation.get_link_transforms().cpu().numpy()[0]
                contacts=[]
                for body,centre in pad_centres.items():
                    bp=poses[bodies.index(body)]
                    contacts.append(bp[:3]+Rotation.from_quat(bp[3:]).as_matrix()@centre)
                offset=rotation.T@(np.mean(contacts,axis=0)-pose[:3])
            grasp_z=a.grasp_height if a.upright_target else 1.025
            approach_z=grasp_z+a.approach_clearance if a.approach_clearance is not None else 1.20
            if phase=='descend':
                z=approach_z+(grasp_z-approach_z)*min((i-phase_start)/descend_frames,1)
            else:
                z=approach_z if phase=='approach' else 1.20 if phase=='retreat' else grasp_z if phase in ('close','release') else grasp_z+a.lift_distance
            if phase=='release' and place_z is not None:z=place_z
            if phase=='release' and a.release_lift_distance>0:
                touching_robot=any(e['point_count']>0 and any(actor.startswith('/World/Robot/') for actor in e['actors']) for e in contact_events)
                supported=any(e['point_count']>0 and any(actor.startswith('/World/PackingTable/') for actor in e['actors']) for e in contact_events)
                release_clear_frames=release_clear_frames+1 if supported and not touching_robot else 0
                if release_lift_start is None and release_clear_frames>=2:release_lift_start=i
                if release_lift_start is not None:
                    progress=min((i-release_lift_start)/max(a.release_lift_frames,1),1)
                    z+=a.release_lift_distance*progress*progress*(3-2*progress)

            if phase=='lift' and a.pilot_timing:
                progress=min((i-phase_start)/45,1)
                z=grasp_z+a.lift_distance*progress*progress*(3-2*progress)
            if phase=='place':
                target_transform=np.array(UsdGeom.XformCache().GetLocalToWorldTransform(target_root)).T
                bottom=(target_points@target_transform[:3,:3].T+target_transform[:3,3])[:,2].min()
                if place_z is None:place_z=grasp_z+a.lift_distance
                place_z-=min(max(bottom-0.99455,0)*0.15,0.002 if a.pilot_timing else 0.001)
                z=place_z
                table_contact=any(e['point_count']>0 and any(actor.startswith('/World/PackingTable/') for actor in e['actors']) for e in contact_events)
                support_frames=support_frames+1 if abs(bottom-0.99405)<0.003 and table_contact else 0
            desired=np.array([a.target_x+a.grasp_offset_x,a.target_y+a.grasp_offset_y,z])
            if phase in ('approach','descend'):
                weight=1 if phase=='approach' else 1-min((i-phase_start)/descend_frames,1)
                desired[:2]+=weight*np.array([a.approach_offset_x,a.approach_offset_y])
            carry_progress=0
            if phase=='carry':
                progress=min((i-phase_start)/(45 if a.pilot_timing else 120),1)
                carry_progress=progress*progress*(3-2*progress)
            elif a.carry_probe and phase in ('place','release','retreat'):
                carry_progress=1
            desired[:2]+=carry_progress*np.array([a.carry_x,a.carry_y])
            if phase=='retreat':
                progress=min((i-phase_start)/45,1)
                desired[:2]+=progress*progress*(3-2*progress)*np.array([a.retreat_x,a.retreat_y])
            if a.occlusion_probe:
                phase='noncontact_preroll' if i<a.occlusion_preroll else 'noncontact_sweep'
                progress=max(0,i-a.occlusion_preroll)/a.occlusion_cycle_frames
                ramp=np.clip((progress-.125)/.25,0,1) if progress<.5 else 1-np.clip((progress-.625)/.25,0,1)
                coverage=ramp*ramp*(3-2*ramp)
                desired=np.array([a.occlusion_centre_x+a.occlusion_amplitude*(1-coverage),a.occlusion_y,a.occlusion_z+a.occlusion_clearance_rise*(1-coverage)])
            pitch_progress=carry_progress
            if a.place_return_pitch:
                if phase=='place':
                    progress=min((i-phase_start)/45,1)
                    pitch_progress=1-progress*progress*(3-2*progress)
                elif phase in ('release','retreat'):pitch_progress=0
            rdes=(Rotation.from_euler('z',a.grasp_yaw+carry_progress*a.carry_yaw,degrees=True)*Rotation.from_euler('x',90+pitch_progress*a.carry_pitch,degrees=True)).as_matrix()
            rotated=rotation@offset
            error=np.r_[desired-(pose[:3]+rotated),Rotation.from_matrix(rdes@rotation.T).as_rotvec()]
            converged=converged+1 if np.linalg.norm(error[:3])<0.005 and np.linalg.norm(error[3:])<0.06 else 0
            if phase=='approach' and converged>=15:
                phase='descend';phase_start=i;converged=0
            elif phase=='descend' and i-phase_start>=descend_frames and converged>=15:
                phase='close';phase_start=i;converged=0
            elif phase=='close' and i-phase_start>=close_frames:
                phase='lift';phase_start=i;converged=0
            if a.carry_probe and phase=='lift' and i-phase_start>=lift_frames:
                phase='carry';phase_start=i
            elif a.place_probe and ((phase=='lift' and not a.carry_probe and i-phase_start>=lift_frames) or (phase=='carry' and i-phase_start>=carry_frames)):
                phase='place';phase_start=i
            elif phase=='place' and support_frames>=(10 if a.pilot_timing else 30) and (not a.place_return_pitch or i-phase_start>=60):
                phase='release';phase_start=i
            elif phase=='release' and i-phase_start>=release_frames:
                phase='retreat';phase_start=i
            jac=articulation.get_jacobians().cpu().numpy()[0,idx-1,:,:6].copy()
            skew=np.array([[0,-rotated[2],rotated[1]],[rotated[2],0,-rotated[0]],[-rotated[1],rotated[0],0]])
            jac[:3]-=skew@jac[3:]
            delta=jac.T@np.linalg.solve(jac@jac.T+0.01*np.eye(6),error)
            command=np.clip(q[:6]+np.clip(delta,-0.025,0.025),articulation.get_dof_limits().cpu().numpy()[0,:6,0],articulation.get_dof_limits().cpu().numpy()[0,:6,1])
            commands=np.rad2deg(command).tolist()
        for name, value in zip(names,commands):
            UsdPhysics.DriveAPI(joints[name],'angular').GetTargetPositionAttr().Set(float(value))
        if a.probe_gripper or a.grasp_probe or a.occlusion_probe:
            finger_drive=UsdPhysics.DriveAPI.Apply(joints['rh_r1_joint'],'angular')
            finger_drive.CreateStiffnessAttr(100)
            finger_drive.CreateDampingAttr(4)
            finger_drive.CreateMaxForceAttr(30)
            closure=a.occlusion_gripper_close*min(i/60,1) if a.occlusion_probe else a.gripper_close*((min((i-phase_start)/close_ramp,1) if phase=='close' else int(phase in ('lift','carry','place'))) if a.grasp_probe else s)
            if a.grasp_probe and phase in ('release','retreat'):
                progress=1 if phase=='retreat' or a.release_ramp_frames<=0 else min((i-phase_start)/a.release_ramp_frames,1)
                weight=progress*progress*(3-2*progress)
                closure=a.gripper_close+(a.release_open_angle-a.gripper_close)*weight
            finger_drive.CreateTargetPositionAttr(float(closure*180/np.pi))
        contact_events.clear()
        rep.orchestrator.step(delta_time=1/30,rt_subframes=1,pause_timeline=False)
        if articulation is None:
            import omni.physics.tensors as tensors
            simulation_view=tensors.create_simulation_view('torch', stage_id=omni.usd.get_context().get_stage_id())
            simulation_view.set_subspace_roots('/')
            articulation=simulation_view.create_articulation_view('/World/Robot/OMY')
            contact_view=simulation_view.create_rigid_contact_view(contact_bodies,filter_patterns=[['/World/Target'] for _ in contact_bodies],max_contact_data_count=256)
            if a.settle_target or a.grasp_probe or a.occlusion_probe:
                target_view=simulation_view.create_rigid_body_view('/World/Target')
                physics_metadata['computed_mass_kg']=target_view.get_masses().cpu().tolist()
                physics_metadata['computed_body_com_xyz_quat_xyzw']=target_view.get_coms().cpu().tolist()
                physics_metadata['computed_body_inertia_kg_m2']=target_view.get_inertias().cpu().tolist()
            physics_metadata['effective_dof_limits_rad']=articulation.get_dof_limits().cpu().tolist()
            if articulation.count != 1:
                raise RuntimeError('Expected exactly one OMY articulation')
        pixels=rgb.get_data()
        if pixels.size==0: raise RuntimeError('Empty image')
        if a.export_observations:
            stem=f'{i:06d}.png'
            Image.fromarray(pixels[:,:,:3]).save(a.output/'rgb'/stem,compress_level=1)
            d=depth.get_data().reshape(480,640)
            valid=np.isfinite(d)&(d>0)&(d<65.535)
            mm=np.zeros(d.shape,dtype=np.uint16);mm[valid]=np.rint(d[valid]*1000).astype(np.uint16)
            Image.fromarray(mm).save(a.output/'depth'/stem,compress_level=1)
            seg=segmentation.get_data();ids=[int(k) for k,v in seg['info']['idToLabels'].items() if v.get('class')=='target_object']
            mask=np.isin(seg['data'].reshape(480,640),ids).astype(np.uint8)*255
            Image.fromarray(mask).save(a.output/'masks'/stem,compress_level=1)
        elif not a.no_gif:
            images.append(Image.fromarray(pixels[:,:,:3].copy()))
        cache=UsdGeom.XformCache(Usd.TimeCode.Default())
        link=stage.GetPrimAtPath('/World/Robot/OMY/link6')
        records.append({'frame':i,'phase':phase,'release_lift_start':release_lift_start,'timeline_s':timeline.get_current_time(),'command_degrees':commands,'measured_joint_positions':articulation.get_dof_positions().cpu().tolist(),'measured_joint_velocities':articulation.get_dof_velocities().cpu().tolist(),'link6_usd_world':np.array(cache.GetLocalToWorldTransform(link)).T.tolist()})
        records[-1]['validation_contact_normal_forces_N']=contact_view.get_normal_contact_force_matrix(1/120).cpu().tolist()
        records[-1]['validation_contact_events']=list(contact_events)
        records[-1]['T_world_robot_base']=np.array(cache.GetLocalToWorldTransform(stage.GetPrimAtPath('/World/Robot/OMY/world'))).T.tolist()
        records[-1]['T_world_camera']=(np.array(cache.GetLocalToWorldTransform(stage.GetPrimAtPath('/World/sensor'))).T@np.diag([1,-1,-1,1])).tolist()
        records[-1]['T_world_effector']=np.array(cache.GetLocalToWorldTransform(stage.GetPrimAtPath('/World/Robot/OMY/link6/end_effector_flange_link/end_effector_link'))).T.tolist()
        records[-1]['T_world_robot_links']={path.rsplit('/',1)[-1]:np.array(cache.GetLocalToWorldTransform(stage.GetPrimAtPath(path))).T.tolist() for path in contact_bodies}
        records[-1]['target_usd_world']=np.array(cache.GetLocalToWorldTransform(stage.GetPrimAtPath('/World/Target'))).T.tolist()
        if i in (0,a.frames//2,a.frames-1): cv2.imwrite(str(a.output/f'frame_{i:04d}.png'),cv2.cvtColor(pixels[:,:,:3],cv2.COLOR_RGB2BGR))
        if a.stop_after_retreat and phase=='retreat' and i-phase_start>=90:
            cv2.imwrite(str(a.output/f'frame_{i:04d}.png'),cv2.cvtColor(pixels[:,:,:3],cv2.COLOR_RGB2BGR))
            break
    if images:
        images[0].save(a.output/'motion.gif',save_all=True,append_images=images[1:],duration=33,loop=0)
    if a.export_observations:
        with (a.output/'frames.jsonl').open('w') as stream:
            for row in records:
                stream.write(json.dumps(row)+'\n')
    (a.output/'capture_provenance.json').write_text(json.dumps({'generator_sha256':generator_sha256,'wall_seconds_including_startup':time.monotonic()-capture_wall_start,'frames':len(records),'physics_state_directly_set_during_episode':False,'attachment_used':False,'controller_timing_frames':{'descend':descend_frames,'close':close_frames,'close_ramp':close_ramp,'lift':lift_frames,'carry':carry_frames,'release':release_frames,'retreat':91}},indent=2))
    timeline.stop()
    (a.output/'diagnostics.json').write_text(json.dumps({'arguments':{k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},'physics_metadata':physics_metadata,'render_settings':render_settings,'protocol':'joint_drive_motion_debug_only','validated_task_a':False,'gripper_probe':a.probe_gripper,'target_settling_probe':a.settle_target,'upright_target':a.upright_target,'target_override':a.target_usd,'upright_axis':a.upright_axis,'occlusion_probe':a.occlusion_probe,'contact_body_order':contact_bodies,'joint_names':list(articulation.shared_metatype.dof_names),'frames':records},indent=2))
    print('MOTION_PREVIEW_COMPLETE',flush=True)
except Exception:
    traceback.print_exc()
    (a.output/'error.txt').write_text(traceback.format_exc())
finally:
    app.close()
