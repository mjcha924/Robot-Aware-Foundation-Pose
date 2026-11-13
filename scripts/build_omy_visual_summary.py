"""Build labelled review GIFs/figures from accepted RGB frames; no synthetic imagery."""
import argparse,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,default=Path('outputs/omy_pilot/dataset'));p.add_argument('--output',type=Path,default=Path('docs/omy_tracking/media'));a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
objects=[('box','Gelatin box'),('cylinder','Large marker'),('asymmetric','Banana')]
metadata={'source':'accepted RGB frames','crop_xyxy':[190,150,480,440],'display':'work-area crops, sampled at 10 fps; shorter release clips hold their last frame','artifacts':{}}
def tile(root,frame,label):
 im=Image.open(root/'rgb'/f'{frame:06d}.png').convert('RGB').crop((190,150,480,440)).resize((320,320))
 canvas=Image.new('RGB',(320,352),(23,29,38));canvas.paste(im,(0,32));ImageDraw.Draw(canvas).text((8,7),label,font=font,fill='white');return canvas
for task,name in [('B','grasp_three_objects.gif'),('C','release_three_objects.gif')]:
 target=a.output/name
 if target.exists():raise FileExistsError(target)
 sources=[a.dataset/f'{obj}_{task}_00' for obj,_ in objects];rows=[[json.loads(line) for line in (root/'frames.jsonl').read_text().splitlines()] for root in sources];images=[]
 for i in range(0,max(map(len,rows)),3):
  canvas=Image.new('RGB',(960,352))
  for col,((obj,label),root,data) in enumerate(zip(objects,sources,rows)):
   frame=min(i,len(data)-1);canvas.paste(tile(root,frame,label+' | '+data[frame]['task_phase']),(col*320,0))
  images.append(canvas)
 palette_source=Image.new('RGB',(960,1376))
 for j,k in enumerate([0,len(images)//2,len(images)-1]):palette_source.paste(images[k],(0,j*352))
 # Give target texture colours representation alongside the large grey background.
 for col,root in enumerate(sources):
  pixels=[]
  for k in [0,len(rows[col])//2,len(rows[col])-1]:
   rgb=np.asarray(Image.open(root/'rgb'/f'{k:06d}.png').convert('RGB'));mask=np.asarray(Image.open(root/'masks'/f'{k:06d}.png'))>0
   pixels.extend(rgb[mask].tolist())
  swatch=np.resize(np.asarray(pixels,dtype=np.uint8),(320,320,3))
  palette_source.paste(Image.fromarray(swatch),(col*320,1056))
 palette=palette_source.quantize(colors=256)
 images=[frame.quantize(palette=palette,dither=Image.Dither.NONE) for frame in images]
 images[0].save(target,save_all=True,append_images=images[1:],duration=100,loop=0,optimize=True)
 with Image.open(target) as check:assert check.n_frames==len(images)
 metadata['artifacts'][name]={'sequences':[r.name for r in sources],'frames':len(images),'duration_s':len(images)/10}
root=a.dataset/'asymmetric_A_00';audit=json.loads((root/'validation/geometry_replay.json').read_text())['frames'];indices=[0,min(range(len(audit)),key=lambda i:audit[i]['visible_fraction']),len(audit)-1]
canvas=Image.new('RGB',(960,352))
for col,(frame,label) in enumerate(zip(indices,['Clear','Occluded','Clear again'])):
 canvas.paste(tile(root,frame,f'{label} | {100*audit[frame]["visible_fraction"]:.0f}% visible'),(col*320,0))
canvas.save(a.output/'occlusion_example.png');metadata['artifacts']['occlusion_example.png']={'sequence':root.name,'frames':indices,'visible_fractions':[audit[i]['visible_fraction'] for i in indices]}
(a.output/'visual_sources.json').write_text(json.dumps(metadata,indent=2)+'\n');print(json.dumps({p.name:p.stat().st_size for p in a.output.iterdir()}))
