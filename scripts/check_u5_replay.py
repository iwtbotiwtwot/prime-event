"""Compare reproduced journal science with the frozen 100M qualification prefix."""
import argparse,json,sys
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('workdir',type=Path);a=p.parse_args();ref=json.loads((Path(__file__).resolve().parents[1]/'evidence/u5/REFERENCE.json').read_text());cp=json.loads((a.workdir/'data/CHECKPOINT.json').read_text());assert cp['config']['seed']==9369001
checks=0
for j in range(len(cp['records'])):
 name=f'chunk_{j:05d}.npz'
 if name not in ref:raise ValueError('Reference ends at 100M; do not extrapolate checks')
 with np.load(a.workdir/'data'/name,allow_pickle=False) as z:m=json.loads(z['metadata'].tobytes())
 for key in ['bank_sha256','emission_sha256','period_sha256','status','base_rng','extra_rng','fp','fn']:
  assert m[key]==ref[name][key],(name,key);checks+=1
print(json.dumps({'status':'PASS','checks':checks,'unique_decisions':len(cp['records'])*5000000}))
