#!/usr/bin/env python3
"""CPU, offline RGB overlays of saved predictions, object GT and measured robot FK."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_predictions(path, frames, allow_partial=False):
    import numpy as np
    import torch
    from robot_conditioned_pose.motion_prior import validate_pose
    rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows or len(rows)>len(frames) or (not allow_partial and len(rows)!=len(frames)):
        raise ValueError('prediction count mismatch; --allow-partial accepts only an aligned prefix')
    for i,(row,frame) in enumerate(zip(rows,frames)):
        if row.get('frame_id')!=frame['frame_id'] or row.get('frame_index',i)!=i:
            raise ValueError(f'prediction frame alignment mismatch at index {i}')
        pose=np.asarray(row['T_camera_mesh'],dtype=np.float64)
        validate_pose(torch.as_tensor(pose))
    return rows


def check_provenance(poses, reader, no_gt=False):
    """Use evaluator run metadata when present; imported pose files remain usable."""
    path=poses.parent/'run.json'
    if not path.exists(): return {'status':'unverified', 'reason':'No run.json alongside poses file'}
    run=json.loads(path.read_text())
    if run.get('sequence')!=reader.path.name: raise ValueError('run.json sequence mismatch')
    for relative,digest in run.get('inputs',{}).items():
        if no_gt and relative==reader.manifest['frames_file']: continue
        source=(reader.path/relative).resolve()
        if reader.path.resolve() not in source.parents: raise ValueError('run input path outside sequence')
        if file_hash(source)!=digest: raise ValueError('run input hash mismatch: '+relative)
    from robot_conditioned_pose.contracts import geometry_record
    if run.get('mesh_sha256') and run['mesh_sha256']!=geometry_record(reader.mesh,1.)['mesh_sha256']:
        raise ValueError('run mesh geometry mismatch')
    return dict(status='matched recorded inputs (GT unchecked)' if no_gt else 'matched recorded inputs',initialization=run.get('initialization'),
                method=run.get('method'),model_mode=run.get('model_mode'),run_sha256=file_hash(path))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('sequence',type=Path)
    p.add_argument('--poses',required=True,type=Path,help='poses.jsonl from evaluate_robot_tracker.py')
    p.add_argument('--output',required=True,type=Path,help='New visualization directory outside the raw dataset')
    p.add_argument('--layout',choices=['grid','overlay'],default='grid')
    p.add_argument('--panel-width',type=int,default=640,help='Max width per panel; no upscaling')
    p.add_argument('--start',type=int,default=0,help='Inclusive source frame index')
    p.add_argument('--stop',type=int,help='Exclusive source frame index')
    p.add_argument('--stride',type=int,default=1)
    p.add_argument('--no-gt',action='store_true',help='Explicitly omit object truth for observation-only data')
    p.add_argument('--allow-partial',action='store_true',help='Accept an aligned prediction prefix after an interrupted run')
    p.add_argument('--png-only',action='store_true',help='Write each selected frame without FFmpeg/MP4')
    p.add_argument('--save-frames',action='store_true',help='Also save every selected frame as PNG')
    p.add_argument('--object-edges',type=int,default=512)
    p.add_argument('--robot-edges-per-link',type=int,default=128)
    p.add_argument('--effector-link',default='link6',help='Link for E:XYZ axes; all geometry links are still drawn')
    a=p.parse_args(argv)
    if min(a.stride,a.object_edges,a.robot_edges_per_link)<1 or a.panel_width<320 or a.start<0:
        p.error('positive stride/edge limits, panel-width >=320 and start >=0 required')
    a.sequence=a.sequence.resolve();a.poses=a.poses.resolve();a.output=a.output.resolve()
    # Output must not enter the raw dataset or overwrite the prediction run.
    if a.output==a.sequence.parent or a.sequence.parent in a.output.parents:
        p.error('output must be outside the raw dataset parent directory')
    if a.output==a.poses.parent: p.error('output must be a new visualization directory')
    import numpy as np
    import trimesh
    from PIL import Image
    from robot_conditioned_pose.omy_sequence import OmySequence
    from robot_conditioned_pose.visualization import validate_intrinsics,mesh_edges,box_edges,render_frame
    reader=OmySequence(a.sequence)
    k=validate_intrinsics(reader.K)
    rows=load_predictions(a.poses,reader.frames,a.allow_partial)
    provenance=check_provenance(a.poses,reader,a.no_gt)
    run_label=' | '.join(str(provenance[key]) for key in ('method','model_mode','initialization') if provenance.get(key))
    if not run_label: run_label='Imported poses | initialization unverified'
    stop=len(rows) if a.stop is None else a.stop
    if not a.start<stop<=len(rows): p.error('require 0 <= start < stop <= prediction count')
    indices=list(range(a.start,stop,a.stride))
    timestamps=np.asarray([f['timestamp_s'] for f in reader.frames],dtype=float)
    if len(timestamps)<2 or not np.isfinite(timestamps).all() or not np.allclose(np.diff(timestamps),1/30,atol=1e-6):
        raise ValueError('expected continuous 30 Hz OMY observations')
    fps=30/a.stride
    obj_edges=mesh_edges(reader.mesh,a.object_edges);obj_box=box_edges(reader.mesh)
    axis_length=float(np.max(reader.mesh.extents))*.35
    if axis_length<=0: raise ValueError('degenerate object mesh')
    robot={link['name']:mesh_edges(trimesh.load(a.sequence/link['path'],force='mesh',process=False),a.robot_edges_per_link)
           for link in reader.manifest['robot_geometry']['links']}
    # Validate label alignment and robot link mapping before creating any outputs.
    if not a.no_gt: reader.target(indices[0])
    links=reader.robot_link_poses(indices[0])
    if set(robot)-set(links): raise ValueError('robot geometry/FK link mismatch')
    if a.effector_link not in links: raise ValueError('unknown effector link: '+a.effector_link)
    if not a.png_only:
        try:
            import imageio_ffmpeg
            imageio_ffmpeg.get_ffmpeg_version()
        except (ImportError,RuntimeError,OSError) as exc:
            raise RuntimeError('MP4 needs FFmpeg: pip install -r requirements-visualization.txt; or use --png-only') from exc
    a.output.mkdir(parents=True,exist_ok=False)
    save_frames=a.save_frames or a.png_only
    if save_frames: (a.output/'frames').mkdir()
    writer=None
    if not a.png_only:
        import imageio.v2 as imageio
        writer=imageio.get_writer(str(a.output/'overlay.mp4'),format='FFMPEG',mode='I',fps=fps,
            codec='libx264',pixelformat='yuv420p',macro_block_size=1,ffmpeg_log_level='error',
            output_params=['-movflags','+faststart'])
    dimensions=None
    try:
        with (a.output/'frames.jsonl').open('w') as mapping:
            for output_index,i in enumerate(indices):
                frame=reader.frames[i]
                with Image.open(a.sequence/'rgb'/(frame['frame_id']+'.png')) as original:
                    rgb=original.convert('RGB')
                if dimensions is None: dimensions=rgb.size
                if rgb.size!=dimensions: raise ValueError('RGB dimensions changed within sequence')
                width=min(rgb.width,a.panel_width);height=max(1,round(rgb.height*width/rgb.width))
                sx,sy=width/rgb.width,height/rgb.height
                scaled_k=np.array([[sx,0,(sx-1)/2],[0,sy,(sy-1)/2],[0,0,1]])@k
                rgb=rgb.resize((width,height),Image.Resampling.LANCZOS)
                estimate=np.asarray(rows[i]['T_camera_mesh'])
                target=None if a.no_gt else reader.target(i).numpy()
                label=f"Frame {frame['frame_id']} | t={timestamps[i]-timestamps[0]:.3f}s"
                if i==0: label+=' | INITIAL POSE'
                canvas,stats=render_frame(rgb,scaled_k,estimate,target,reader.robot_link_poses(i),
                    obj_edges,obj_box,robot,axis_length,label,a.layout,a.effector_link,run_label)
                if output_index==0: canvas.save(a.output/'preview.png')
                if save_frames: canvas.save(a.output/'frames'/f'{i:06d}.png')
                if writer is not None: writer.append_data(np.asarray(canvas))
                record=dict(output_index=output_index,frame_index=i,frame_id=frame['frame_id'],
                    timestamp_s=float(timestamps[i]),video_time_s=output_index/fps,**stats)
                mapping.write(json.dumps(record)+'\n')
    finally:
        if writer is not None: writer.close()
    ext=reader.manifest['omy_tracking']
    from robot_conditioned_pose.contracts import geometry_record
    metadata=dict(sequence=a.sequence.name,poses_sha256=file_hash(a.poses),provenance=provenance,
        mesh_geometry_sha256=geometry_record(reader.mesh,1.)['mesh_sha256'],
        manifest_sha256=file_hash(a.sequence/'manifest.json'),
        observations_sha256=file_hash(a.sequence/ext['robot_observations_file']),
        joint_inventory_sha256=file_hash(a.sequence/ext['joint_inventory']),
        gt_sha256=None if a.no_gt else file_hash(a.sequence/reader.manifest['frames_file']),
        robot_geometry_sha256={link['name']:file_hash(a.sequence/link['path']) for link in reader.manifest['robot_geometry']['links']},
        frames=len(indices),prediction_frames=len(rows),sequence_frames=len(reader.frames),
        partial=len(rows)!=len(reader.frames),start=a.start,stop=stop,stride=a.stride,fps=fps,
        layout=a.layout,output_size=list(canvas.size),no_gt=a.no_gt,
        effector_link=a.effector_link,object_edges=a.object_edges,robot_edges_per_link=a.robot_edges_per_link,
        overlay_note='X-ray wireframes. No depth test. Behind-camera segments are clipped; hidden surfaces remain visible.',
        pose_convention='T_camera_raw_mesh; robot links from measured joints + FK, not simulator link GT')
    (a.output/'visualization.json').write_text(json.dumps(metadata,indent=2))
    print(json.dumps(dict(output=str(a.output),frames=len(indices),fps=fps,provenance=provenance['status']),indent=2))
    return metadata


if __name__=='__main__': main()
