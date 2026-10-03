"""Adversarial interval, bank-change and full-state checks, independent of throughput."""
import argparse
import ctypes as C
from pathlib import Path
import sys
import numpy as np

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('source',type=Path)
p.add_argument('--backend',choices=['cpu','gpu'],default='cpu')
a=p.parse_args();sys.path.insert(0,str(a.source.resolve()))
import runner
from accelerated import Accelerator
k=runner.Kernels();acc=Accelerator(a.source.resolve(),k,a.backend,8)
rng=np.random.default_rng(42901)

def proposals(first,base,extra,banks):
    out=np.empty(len(base),np.uint32)
    if a.backend=='gpu':
        acc.check(acc.gpu.gpu_propose(first,len(base),base.ctypes.data,extra.ctypes.data,banks.ctypes.data,out.ctypes.data))
    else:
        acc.lib.propose(first,len(base),*[x.ctypes.data for x in [acc.row,acc.low,acc.high,acc.lut,base,extra,banks,out]],8)
    return out

# Probe exact CDF endpoints and their adjacent float64s. Certainty must hold for
# EVERY possible incoming state, even when that state is rare in live trajectories.
n=35000;first=5000002;banks=rng.integers(0,4,n,dtype=np.uint8)
tables=(((np.arange(n,dtype=np.uint64)+first-2)%35)*4+banks).astype(int)
cdf=acc.cdf.reshape(140,128,128)
incoming=rng.integers(0,128,n);boundary=rng.integers(0,128,n)
u=cdf[tables,incoming,boundary].copy()
u[::3]=np.nextafter(u[::3],-np.inf);u[1::3]=np.nextafter(u[1::3],np.inf)
u=np.clip(u,0,np.nextafter(1.,0.));v=np.column_stack((u,u))
word=proposals(first,u,v,banks);s=(word&255).astype(int)
certified=s<128;checked=0
for t in range(140):
    take=np.flatnonzero((tables==t)&certified)
    for incoming in range(128):
        expected=np.searchsorted(cdf[t,incoming],u[take],side='right')
        assert np.array_equal(s[take],expected),(t,incoming)
        checked+=len(take)

# Force the speculative consumer through initial-window feedback changes as well
# as ordinary windows; compare every one of the three states, not just emissions.
for first in [2,35002,5000002]:
    n=35000;base=rng.random(n);extra=rng.random((n,2))
    banks=np.zeros(n,np.uint8) if first==2 else rng.integers(0,4,n,dtype=np.uint8)
    b1,b2=banks.copy(),banks.copy();e1,e2=np.zeros(n,np.uint8),np.zeros(n,np.uint8)
    p1,p2=np.empty(n*3,np.uint8),np.empty(n*3,np.uint8)
    s1=np.array([rng.integers(0,128),13,1469598103934665603],np.uint64);s2=s1.copy()
    out=proposals(first,base,extra,banks)
    assert k.advance(first,n,*[x.ctypes.data for x in [acc.cdf,base,extra,b1,e1,p1]],n,s1.ctypes.data)==0
    assert acc.lib.consume(first,n,*[x.ctypes.data for x in [acc.cdf,base,extra,b2,e2,p2]],n,s2.ctypes.data,out.ctypes.data,acc.counters.ctypes.data)==0
    for x,y in [(b1,b2),(e1,e2),(p1,p2),(s1,s2)]:assert np.array_equal(x,y)
    # The optimized scorer remains separate from actual-event feedback.
    reference=np.array([all(x%d for d in range(2,int(x**.5)+1)) for x in range(first,first+1000)])
    assert np.array_equal(acc.truth(first,1000),reference)
print({'status':'PASS','backend':a.backend,'boundary_certifications':checked,
       'sequential_decisions':105000,'fallback_readings':int(acc.counters[0]),
       'changed_banks':int(acc.counters[1])})

# Mark arbitrary actual histories, including composites and nonzero rank parity.
for first,count,rank in [(2,1001,0),(550001,1700033,1),(800000002,500000,9)]:
    periods=np.unique(rng.integers(2,first+count,50000,dtype=np.uint64))
    b1=rng.integers(0,4,count,dtype=np.uint8);b2=b1.copy()
    assert k.mark(first,count,periods.ctypes.data,len(periods),rank,b1.ctypes.data)==0
    assert acc.mark(first,count,periods.ctypes.data,len(periods),rank,b2.ctypes.data)==0
    assert np.array_equal(b1,b2)
    truth=rng.integers(0,2,count,dtype=np.uint8);emit=rng.integers(0,2,count,dtype=np.uint8)
    events=np.empty(count,np.uint64);errors=np.empty(count,np.uint64);totals=np.empty(4,np.uint64)
    acc.lib.grade(first,count,*[x.ctypes.data for x in [emit,truth,events,errors,totals]])
    assert np.array_equal(events[:int(totals[0])],np.flatnonzero(emit)+first)
    assert np.array_equal(errors[:int(totals[1])],np.flatnonzero(emit!=truth))
    assert totals[2]==np.count_nonzero(emit & (1-truth))
    assert totals[3]==np.count_nonzero((1-emit) & truth)
print({'status':'PASS','parallel_history_and_grade_cases':3})
