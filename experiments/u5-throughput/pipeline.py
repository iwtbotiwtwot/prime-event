"""Bounded two-buffer preparation and single-writer durable checkpoint pipeline.

Only actual event history enters preparation. A period p cannot return in a
window ending below 2p. The early durability fence and the step>=4 inequality
below enforce this bound for pending writes; no prime oracle is involved.
"""
from concurrent.futures import ThreadPoolExecutor
import copy
import fcntl
import json
import os
import queue
from pathlib import Path
import resource
import shutil
import signal
import time
import numpy as np
from random_buffers import RandomBuffers

def run(r,acc,root,until,workers,seconds):
    root.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter();initial=[]
    cp_path=root/'CHECKPOINT.json'
    if not cp_path.exists() or len(json.loads(cp_path.read_text())['records'])<2:
        bootstrap=r.run(root,min(2,until),'indexed',4096)
        initial=bootstrap['rows']
        if bootstrap['stop_reason']!='target' or until<=2:return bootstrap
    lock=(root/'WRITER.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    cp=json.loads(cp_path.read_text());config=cp['config']
    assert config['accelerator']==json.loads(os.environ['PRIME_ACCELERATOR'])
    assert config['seed']==int(os.environ['PRIME_SEED'])
    assert config['cdf_sha256']==r.sha((r.P/'u5_cdf.npy').read_bytes())
    assert config['initial_sha256']==r.sha((r.P/'u5_initial.npy').read_bytes())
    records=cp['records'];status=np.array(cp['status'],np.uint64)
    start_step=len(records)-len(initial);first=cp['next_n'];fp,fn=cp['fp'],cp['fn']
    assert first==2+len(records)*r.W
    rank=0
    for j,rec in enumerate(records):assert rec['rank']==rank and rec['first']==2+j*r.W;rank+=rec['count']
    assert rank==int(status[1])
    raw=Path(records[-1]['path']).read_bytes();assert r.sha(raw)==records[-1]['sha256']
    meta,_=r.unpack(raw)
    for key in ['status','base_rng','extra_rng']:assert meta[key]==cp[key]
    orphan_count=0
    for path in root.glob('chunk_*.npz'):
        if int(path.stem.split('_')[1])>=len(records):
            q=root/'quarantine';q.mkdir(exist_ok=True);assert not (q/path.name).exists()
            os.replace(path,q/path.name);orphan_count+=1
    base=np.random.default_rng();extra=np.random.default_rng()
    base.bit_generator.state=cp['base_rng'];extra.bit_generator.state=cp['extra_rng']
    history=r.History(records,4096*1024**2,acc)
    recent_events=queue.SimpleQueue()
    buffers=[RandomBuffers(workers),RandomBuffers(workers)]
    proposal_buffers=[np.empty(r.W,np.uint32),np.empty(r.W,np.uint32)]
    pending=[]
    for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,lambda signum,frame:pending.append(signum))
    side=ThreadPoolExecutor(max_workers=2)
    def timed(fn,*args):
        start=time.perf_counter();value=fn(*args);return value,time.perf_counter()-start
    def prepare(first,slot):
        # Transfer immutable, compact actual-event arrays to the preparer's LRU.
        # A single preparer owns the cache; the decision thread only queues data.
        while not recent_events.empty():
            j,events=recent_events.get_nowait()
            while history.cache and history.bytes+events.nbytes>history.limit:
                _,old=history.cache.popitem(last=False);history.bytes-=old.nbytes;history.evictions+=1
            if events.nbytes<=history.limit:
                history.cache[j]=events;history.bytes+=events.nbytes;history.peak=max(history.peak,history.bytes)
        bank_future=side.submit(timed,history.banks,first)
        truth_future=side.submit(timed,acc.truth,first)
        t=time.perf_counter();u,v=buffers[slot].draw(base,extra,r.W);rt=time.perf_counter()-t
        br,er=copy.deepcopy(base.bit_generator.state),copy.deepcopy(extra.bit_generator.state)
        banks,bt=bank_future.result()
        out=proposal_buffers[slot];t=time.perf_counter()
        if acc.backend=='gpu':acc.check(acc.gpu.gpu_propose(first,r.W,u.ctypes.data,v.ctypes.data,banks.ctypes.data,out.ctypes.data))
        else:acc.lib.propose(first,r.W,*[x.ctypes.data for x in [acc.row,acc.low,acc.high,acc.lut,u,v,banks,out]],acc.threads)
        pt=time.perf_counter()-t;truth,st=truth_future.result()
        return banks,u,v,out,truth,br,er,dict(banks=bt,rng=rt,proposal=pt,sieve=st)
    def commit(step,meta,events,snapshot,record,bank_hash,emission_hash):
        t=time.perf_counter();meta.update(period_sha256=r.digest(events),bank_sha256=r.digest(bank_hash),
            emission_sha256=r.digest(emission_hash),previous_sha256=snapshot['records'][-2]['sha256'] if step else None)
        blob=r.pack(meta,events);record['sha256']=r.sha(blob);compression=time.perf_counter()-t
        t=time.perf_counter();r.atomic(Path(record['path']),blob);r.atomic(cp_path,snapshot)
        return dict(compression=compression,durable_write=time.perf_counter()-t)
    rows=list(initial);reason='target';future_write=None
    with ThreadPoolExecutor(max_workers=1) as prep,ThreadPoolExecutor(max_workers=1) as writer:
        slot=0;future=prep.submit(prepare,first,slot) if len(records)<until else None
        while len(records)<until:
            if pending or (root/'STOP').exists():reason='requested';break
            if time.perf_counter()-started>=seconds:reason='session_time_budget';break
            if shutil.disk_usage(root).free<20*1024**3:reason='storage_reserve';break
            tick=time.perf_counter();step=len(records)
            banks,u,v,out,truth,br,er,timing=future.result()
            # In the short prefix, next-window preparation can need the pending
            # writer's chunk. For step>=4, 2*(2+(step-1)*W) exceeds the next
            # window's end, so that chunk provably cannot contribute a return.
            if future_write is not None and step<4:
                rows[-1].update(future_write.result())
                with (root/'TIMINGS.jsonl').open('a') as f:f.write(json.dumps(rows[-1])+'\n')
                future_write=None
            # A future window may only use committed older records. The last
            # two windows cannot contribute any period to its bank masks.
            assert first>=2+2*r.W
            if step+1<until:future=prep.submit(prepare,first+r.W,1-slot)
            emit=np.empty(r.W,np.uint8);prefix=np.empty(0,np.uint8);t=time.perf_counter()
            code=acc.lib.consume(first,r.W,*[x.ctypes.data for x in [acc.cdf,u,v,banks,emit,prefix]],0,status.ctypes.data,out.ctypes.data,acc.counters.ctypes.data)
            assert code==0;timing['consume']=time.perf_counter()-t;t=time.perf_counter()
            event_storage=np.empty(r.W,np.uint64);error_storage=np.empty(r.W,np.uint64);totals=np.empty(4,np.uint64)
            acc.lib.grade(first,r.W,*[x.ctypes.data for x in [emit,truth,event_storage,error_storage,totals]])
            events=event_storage[:int(totals[0])];wrong=error_storage[:int(totals[1])]
            errors=[dict(n=int(first+i),kind='FN' if truth[i] else 'FP') for i in wrong]
            fpi,fni=int(totals[2]),int(totals[3]);fp+=fpi;fn+=fni
            timing['grade']=time.perf_counter()-t
            if future_write is not None:
                rows[-1].update(future_write.result())
                with (root/'TIMINGS.jsonl').open('a') as f:f.write(json.dumps(rows[-1])+'\n')
            meta=dict(first=first,next_n=first+r.W,source=config['cdf_sha256'],status=status.tolist(),
                base_rng=br,extra_rng=er,period_count=len(events),errors=errors,fp=fpi,fn=fni)
            record=dict(first=first,count=len(events),rank=int(status[1])-len(events),path=str(root/f'chunk_{step:05d}.npz'))
            records.append(record);first+=r.W
            recent_events.put((step,events.copy()))
            snapshot=dict(config=config,records=list(records),status=status.tolist(),base_rng=br,extra_rng=er,next_n=first,fp=fp,fn=fn)
            future_write=writer.submit(commit,step,meta,events,snapshot,record,banks,np.packbits(emit,bitorder='little'))
            timing.update(step=step,first=first-r.W,seconds=time.perf_counter()-tick,fp=fpi,fn=fni)
            rows.append(timing);slot=1-slot
        if future_write is not None:
            rows[-1].update(future_write.result())
            with (root/'TIMINGS.jsonl').open('a') as f:f.write(json.dumps(rows[-1])+'\n')
    for b in buffers:b.close()
    side.shutdown()
    elapsed=time.perf_counter()-started;decisions=(len(records)-start_step)*r.W
    result=dict(status='PASS',stop_reason=reason,mode='pipeline',start_step=start_step,end_step=len(records),
        new_decisions=decisions,seconds=elapsed,per_second=decisions/elapsed,through=first-1,fp=fp,fn=fn,
        events=int(status[1]),orphan_quarantined=orphan_count,rows=rows,cache=history.counters(),
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    r.atomic(root/f'RUN_{start_step:05d}_{len(records):05d}.json',result)
    r.atomic(root/'PROGRESS.json',dict(status='STOPPED',reason=reason,through=first-1,fp=fp,fn=fn,
        per_second=result['per_second'],updated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)
    return result
