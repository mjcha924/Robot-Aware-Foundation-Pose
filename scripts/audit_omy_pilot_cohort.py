"""Independently check the completed 45-slot index, evidence, splits and videos."""
import argparse, hashlib, json
from pathlib import Path
import imageio_ffmpeg
from check_omy_joint_limits import audit_sample

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--root', type=Path, default=Path('outputs/omy_pilot'))
p.add_argument('--config', type=Path, default=Path('configs/omy_tracking/pilot_capture.json'))
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
if a.output.exists(): p.error('Preserve existing audit; choose a new output')
config = json.loads(a.config.read_text())
index = json.loads((a.root / 'index.json').read_text())
gates_hash = hashlib.sha256(Path('configs/omy_tracking/acceptance.json').read_bytes()).hexdigest()
expected = {f'{obj}_{task}_{v["id"]:02d}' for obj in config['objects'] for task in 'ABC' for v in config['variants']}
failures, records, parents, parent_sources = [], [], {}, {}
if set(index['accepted']) != expected:
    failures.append({'missing': sorted(expected-set(index['accepted'])), 'unexpected': sorted(set(index['accepted'])-expected)})
for episode, entry in sorted(index['accepted'].items()):
    root = Path(entry['path'])
    try:
        manifest = json.loads((root/'manifest.json').read_text())
        technical_path = root/'validation/acceptance.json'
        technical = json.loads(technical_path.read_text())
        proof = json.loads((root/'validation/pilot_acceptance.json').read_text())
        meta = manifest['omy_tracking']
        assert manifest['sequence_id'] == episode and meta['accepted']
        assert technical['technical_pass'] and all(technical['checks'].values())
        state_audit=audit_sample(root)
        assert state_audit['passed'],state_audit
        assert technical['gates_sha256'] == gates_hash
        assert proof['accepted'] and proof == entry['proof']
        assert proof['technical_report_sha256'] == hashlib.sha256(technical_path.read_bytes()).hexdigest()
        assert 180 <= manifest['frame_count'] <= 300
        assert entry['frames'] == manifest['frame_count'] == technical['frame_count']
        group = entry['parent_group']
        assert meta['parent_group'] == group == proof['parent_group']
        model_proof=json.loads((root/'validation/textured_model_equivalence.json').read_text())
        assert model_proof['texture_sha256']==hashlib.sha256((root/'mesh/texture.png').read_bytes()).hexdigest()
        assert parents.setdefault(group, entry['split']) == entry['split']
        assert meta['split'] == entry['split']
        assert parent_sources.setdefault(group, manifest['source']['diagnostic_parent']) == manifest['source']['diagnostic_parent']
        assert manifest['source']['parent_diagnostics_sha256'] == hashlib.sha256((Path(manifest['source']['diagnostic_parent'])/'diagnostics.json').read_bytes()).hexdigest()
        obj, task, variant_id = episode.rsplit('_',2)
        variant = next(v for v in config['variants'] if v['id']==int(variant_id))
        assert meta['object']==obj and meta['task']==task and meta['seed']==variant['seed']
        assert meta['split']==variant['split']
        assert hashlib.sha256((root/'mesh/object.obj').read_bytes()).hexdigest()==hashlib.sha256((Path(config['objects'][obj]['model'])/'object.obj').read_bytes()).hexdigest()
        for folder in ['rgb', 'depth', 'masks']:
            assert len(list((root/folder).glob('*.png'))) == manifest['frame_count']
        video_counts = {}
        for video in ['review.mp4', 'validation/geometry_overlay.mp4']:
            reader = imageio_ffmpeg.read_frames(str(root/video), pix_fmt='rgb24')
            info = next(reader)
            assert info['size'] == (640,480) and abs(info['fps']-30)<1e-6
            count = sum(1 for _ in reader)
            assert count == manifest['frame_count'], (video,count,manifest['frame_count'])
            video_counts[video] = count
        records.append({'episode':episode, 'passed':True, 'video_frames':video_counts, 'joint_limit_maximum_excess_rad':state_audit['maximum_excess_rad'], 'joint_limit_rows':state_audit['row_count'], 'parent_group':group, 'split':entry['split']})
    except Exception as exc:
        failures.append({'episode':episode,'error':repr(exc)})
        records.append({'episode':episode,'passed':False})
report = {'passed':not failures and len(records)==45, 'accepted_count':len(index['accepted']), 'required':45,
          'gates_sha256':gates_hash, 'postflight_gates_sha256':hashlib.sha256(Path('configs/omy_tracking/postflight_acceptance.json').read_bytes()).hexdigest(), 'failures':failures, 'sequences':records,
          'note':'Capture/geometry acceptance only; FoundationPose initialization and learned tracking accuracy are not measured.'}
a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':report['passed'],'accepted_count':len(index['accepted']),'failures':failures}),flush=True)
raise SystemExit(0 if report['passed'] else 1)
