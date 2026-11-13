"""Synchronize the living plan and planned-slot manifest from the accepted index."""
import json,re
from pathlib import Path
root=Path('outputs/omy_pilot')
index=json.loads((root/'index.json').read_text())
accepted=index['accepted'];count=len(accepted)
p=Path('configs/omy_tracking/pilot_manifest.json');data=json.loads(p.read_text())
data.update(accepted=count,status='complete' if count==45 else 'running',note='Accepted entries come from outputs/omy_pilot/index.json. Partner pre-bulk review was explicitly deferred by the user; all technical gates remain required.')
for row in data['runs']:
 entry=accepted.get(row['episode_id']);row['accepted']=entry is not None
 row['status']='accepted' if entry else 'pending';row['output']=entry['path'] if entry else None
 row['blocking_gates']=[] if entry else ['per_sequence_technical_acceptance']
p.write_text(json.dumps(data,indent=2)+'\n')
p=Path('docs/omy_tracking/PLAN_AND_PROGRESS.md');text=p.read_text()
text=re.sub(r'\| Accepted pilot sequences \|.*',f'| Accepted pilot sequences | **{count} / 45** | From the accepted index; {len(index["rejected_attempts"])} rejected attempts retained. See PILOT_RUN_STATUS.md. |',text)
labels={'box':'Box (gelatin box)','cylinder':'Cylinder (large marker)','asymmetric':'Asymmetric (banana)'}
for obj,label in labels.items():
 counts=[sum(key.startswith(obj+'_'+task+'_') for key in accepted) for task in 'ABC']
 row='| '+label+' | '+' | '.join(f'{n} / 5' for n in counts)+f' | {sum(counts)} / 15 |'
 text=re.sub(r'\| '+re.escape(label)+r' \|.*',lambda match:row,text)
counts=[sum('_'+task+'_' in key for key in accepted) for task in 'ABC']
row='| Total | '+' | '.join(f'{n} / 15' for n in counts)+f' | **{count} / 45** |'
text=re.sub(r'\| Total \|.*',lambda match:row,text)
p.write_text(text)
print(json.dumps({'accepted':count,'rejected_attempts':len(index['rejected_attempts'])}))

status=['# OMY pilot execution status','',f'Accepted: **{count} / 45**.','',f'Historical clips withdrawn after the joint-limit audit: {len(index.get("revoked_after_postflight",[]))}. Their files are preserved; the index is authoritative.','','| Object | A | B | C |','|---|---:|---:|---:|']
for obj in labels:
 numbers=[sum(key.startswith(obj+'_'+task+'_') for key in accepted) for task in 'ABC']
 status.append('| '+obj+' | '+' | '.join(map(str,numbers))+' |')
status+=['','See [PLAN_AND_PROGRESS.md](PLAN_AND_PROGRESS.md) for the audit and retry history.']
Path('docs/omy_tracking/PILOT_RUN_STATUS.md').write_text('\n'.join(status)+'\n')
