"""Extract a frame-aligned geometry-overlay review clip; preserve source video."""
import argparse,json,subprocess
from pathlib import Path
import imageio_ffmpeg
p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path)
p.add_argument('--start-frame',type=int,required=True);p.add_argument('--frames',type=int,required=True)
p.add_argument('--verify-existing',action='store_true')
a=p.parse_args()
if a.output.exists() and not a.verify_existing:p.error('Use a fresh output path')
if not a.verify_existing:
 subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-loglevel','error','-ss',str(a.start_frame/30),'-i',str(a.source),'-frames:v',str(a.frames),'-an','-r','30','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',str(a.output)],check=True)
video=imageio_ffmpeg.read_frames(str(a.output),pix_fmt='rgb24');metadata=next(video)
if tuple(metadata['size'])!=(640,480) or abs(metadata['fps']-30)>.001:raise RuntimeError('Unexpected video resolution or cadence')
count=sum(1 for frame in video)
if count!=a.frames:raise RuntimeError(f'Decoded {count}, expected {a.frames}')
a.output.with_suffix('.json').write_text(json.dumps({'source':str(a.source),'source_start_frame':a.start_frame,'decoded_frames':count,'fps':30,'review_only':True},indent=2))
print(str(a.output))
