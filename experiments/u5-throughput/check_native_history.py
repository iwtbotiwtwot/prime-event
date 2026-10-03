"""Compare native bank masks with the frozen index on arbitrary event histories."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np

p=argparse.ArgumentParser();p.add_argument('source',type=Path);a=p.parse_args()
sys.path.insert(0,str(a.source.resolve()))
import pilot_runner as r
from native_history import bind

rng=np.random.default_rng(81723);cases=0
class MemoryHistory(r.History):
    def get(self,j):return events[j]
k=r.Kernels();native=bind(MemoryHistory,a.source.resolve(),8)
for n in [10_000_002,25_000_002,100_000_002,450_000_002]:
    records=[];events=[];rank=0
    for j in range((n-2)//r.W):
        # Non-prime events and irregular ranks explicitly test raw feedback.
        arr=np.unique(np.concatenate((rng.integers(2+j*r.W,2+(j+1)*r.W,2000,dtype=np.uint64),
            np.array([2+j*r.W,1+(j+1)*r.W],np.uint64))))
        records.append(dict(rank=rank));rank+=len(arr);events.append(arr)
    old=MemoryHistory(records,0,k).banks(n);new=native(records,0,k).banks(n)
    if not np.array_equal(old,new):raise AssertionError((n,np.flatnonzero(old!=new)[:10]))
    cases+=1
print(json.dumps(dict(status='PASS',arbitrary_history_windows=cases,mask_bytes_compared=cases*r.W)))
