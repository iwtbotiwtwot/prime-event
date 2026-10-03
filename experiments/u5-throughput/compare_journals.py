"""Authenticate and compare two journals, including every event and RNG state."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('left',type=Path);p.add_argument('right',type=Path)
p.add_argument('--chunks',type=int)
a=p.parse_args()
left=json.loads((a.left/'data/CHECKPOINT.json').read_text())
right=json.loads((a.right/'data/CHECKPOINT.json').read_text())
assert left['config']['seed']==right['config']['seed']
count=a.chunks if a.chunks is not None else len(left['records'])
assert 0<count<=min(len(left['records']),len(right['records']))
if a.chunks is None:assert len(left['records'])==len(right['records'])
checks=0
for j in range(count):
    metadata=[]
    for root,cp in [(a.left,left),(a.right,right)]:
        rec=cp['records'][j];path=root/'data'/f'chunk_{j:05d}.npz'
        assert hashlib.sha256(path.read_bytes()).hexdigest()==rec['sha256']
        with np.load(path,allow_pickle=False) as z:
            m=json.loads(z['metadata'].tobytes())
            events=np.cumsum(z['period_gaps'],dtype=np.uint64)+np.uint64(m['first'])
        assert len(events)==rec['count']==m['period_count']
        assert hashlib.sha256(events.tobytes()).hexdigest()==m['period_sha256']
        assert m['previous_sha256']==(cp['records'][j-1]['sha256'] if j else None)
        metadata.append(m)
    for key in ['first','next_n','source','bank_sha256','emission_sha256','period_sha256',
                'period_count','status','base_rng','extra_rng','errors','fp','fn']:
        assert metadata[0][key]==metadata[1][key],(j,key)
        checks+=1
print(json.dumps(dict(status='PASS',seed=left['config']['seed'],chunks=count,
                      decisions=count*5000000,metadata_comparisons=checks)))
