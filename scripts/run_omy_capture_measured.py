"""Run one capture and record wall time, sampled GPU use, and artifact completeness."""
import argparse,json,os,resource,subprocess,threading,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True);p.add_argument('--log',type=Path,required=True)
p.add_argument('command',nargs=argparse.REMAINDER)
a=p.parse_args();command=a.command[1:] if a.command[:1]==['--'] else a.command
if not command:p.error('Expected capture command after --')
if a.output.exists() or a.log.exists():p.error('Use fresh output and log paths')
a.log.parent.mkdir(parents=True,exist_ok=True)
samples=[];stop=threading.Event()
def monitor():
 while not stop.is_set():
  try:
   result=subprocess.run(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,check=True)
   memory,utilization=map(float,result.stdout.strip().splitlines()[0].split(','))
   samples.append({'wall_offset_s':time.monotonic()-started,'whole_gpu_memory_MiB':memory,'gpu_utilization_percent':utilization})
  except (OSError,ValueError,subprocess.SubprocessError):pass
  stop.wait(.5)
started=time.monotonic();thread=threading.Thread(target=monitor,daemon=True);thread.start()
with a.log.open('w') as log:
 process=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=os.environ.copy())
stop.set();thread.join(timeout=6)
complete=(a.output/'diagnostics.json').is_file() and not (a.output/'error.txt').exists()
report={'command':command,'exit_code':process.returncode,'required_artifacts_present':complete,
 'wall_seconds':time.monotonic()-started,'peak_child_RSS_KiB':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
 'peak_sampled_whole_gpu_MiB':max((s['whole_gpu_memory_MiB'] for s in samples),default=None),
 'gpu_measurement_note':'Whole-device usage sampled every ~0.5 s; includes other desktop/process usage, not an exact process allocation maximum.',
 'disk_bytes':sum(f.stat().st_size for f in a.output.rglob('*') if f.is_file()) if a.output.exists() else 0,'samples':samples}
a.log.with_suffix('.resources.json').write_text(json.dumps(report,indent=2))
print({k:v for k,v in report.items() if k not in ('command','samples')})
raise SystemExit(0 if process.returncode==0 and complete else 1)
