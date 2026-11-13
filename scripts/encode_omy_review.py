"""Encode original diagnostic RGB frames as H.264 MP4 without overwriting."""
import argparse
from pathlib import Path
import subprocess
import imageio_ffmpeg
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('sequence',type=Path)
a=p.parse_args();encoder=imageio_ffmpeg.get_ffmpeg_exe()
output=a.sequence/'review.mp4'
subprocess.run([encoder,'-v','error','-n','-framerate','30','-i',str(a.sequence/'rgb/%06d.png'),'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],check=True)
subprocess.run([encoder,'-v','error','-i',str(output),'-f','null','-'],check=True)
print(output)
