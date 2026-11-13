"""Concatenate nine accepted baseline RGB videos without altering their source files."""
import argparse,json,subprocess,tempfile
from pathlib import Path
import imageio_ffmpeg
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--root',type=Path,default=Path('outputs/omy_pilot'))
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();metadata=a.output.with_suffix('.json')
if a.output.exists() or metadata.exists():p.error('Choose a new demo output')
index=json.loads((a.root/'index.json').read_text());segments=[];frames=0
with tempfile.TemporaryDirectory() as temporary:
 listing=Path(temporary)/'clips.txt';lines=[]
 for obj in ['box','cylinder','asymmetric']:
  for task in 'ABC':
   name=f'{obj}_{task}_00';entry=index['accepted'][name]
   video=(Path(entry['path'])/'review.mp4').resolve()
   lines.append("file '"+str(video).replace("'","'\\''")+"'")
   segments.append({'sequence':name,'start_frame':frames,'end_frame':frames+entry['frames'],'start_s':frames/30,'duration_s':entry['frames']/30})
   frames+=entry['frames']
 listing.write_text('\n'.join(lines)+'\n')
 subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-n','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(a.output)],check=True)
reader=imageio_ffmpeg.read_frames(str(a.output));info=next(reader);decoded=sum(1 for _ in reader)
assert decoded==frames and info['size']==(640,480) and abs(info['fps']-30)<1e-6
metadata.write_text(json.dumps({'frames':frames,'fps':30,'duration_s':frames/30,'decoded_frame_count':decoded,'segments':segments,'note':'Original RGB videos concatenated in box, marker, banana order; each object shows A, B, C. No labels or overlays added to the images.'},indent=2)+'\n')
print(json.dumps({'video':str(a.output),'frames':frames,'duration_s':frames/30}))
