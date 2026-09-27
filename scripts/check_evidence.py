import json
from pathlib import Path
p=Path(__file__).resolve().parents[1];rows=json.loads((p/'evidence/trajectories.json').read_text());checks=0
for exp,n,fp,fn,exact in [('baseline-matched',64,271,13,1),('balanced-matched',64,17,3,47),('balanced-fresh',16,2,1,13)]:
 for profile in ['uniform','rough']:
  a=[r for r in rows if r['experiment']==exp and r['profile']==profile];assert len(a)==n
  expected_fp=272 if exp=='baseline-matched' and profile=='rough' else fp
  assert sum(r['fp'] for r in a)==expected_fp and sum(r['fn'] for r in a)==fn
  assert sum(r['fp']+r['fn']==0 for r in a)==exact
  for r in a:
   assert r['through']==10**9 and r['tp']+r['fn']==50847534
   assert len(r['errors'])==r['fp']+r['fn'] and r['terminal_status'][1]==r['tp']+r['fp'];checks+=1
print(json.dumps({'status':'PASS','published_trajectories_checked':checks}))
