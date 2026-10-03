"""Bounded two-buffer preparation and single-writer durable checkpoint pipeline.

Only actual event history enters preparation. A period p cannot return in a
window ending below 2p. The early durability fence and the step>=4 inequality
below enforce this bound for pending writes; no prime oracle is involved.
"""
from concurrent.futures import ThreadPoolExecutor
from collections import deque
import copy
import fcntl
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import time
import numpy as np
from random_buffers import RandomBuffers
from journal import Writer, load
from native_history import bind

def run(r,acc,root,until,workers,seconds,cache_mib=4096,milestone_steps=0):
    root.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter();initial=[]
    cp_path=root/'CHECKPOINT.json'
    publish=getattr(r,'milestone_commit',None)
    def publish_bootstrap(obj):
        cumulative_fp=cumulative_fn=0
        for j,record in enumerate(obj['records']):
            meta,_=r.unpack(Path(record['path']).read_bytes())
            cumulative_fp+=meta['fp'];cumulative_fn+=meta['fn']
            if (j+1)%milestone_steps==0:
                publish(dict(config=obj['config'],records=list(obj['records'][:j+1]),status=meta['status'],
                    base_rng=meta['base_rng'],extra_rng=meta['extra_rng'],next_n=meta['next_n'],
                    fp=cumulative_fp,fn=cumulative_fn))
    if not cp_path.exists() or len(json.loads(cp_path.read_text())['records'])<2:
        bootstrap=r.run(root,min(2,until),'indexed',cache_mib)
        initial=bootstrap['rows']
        if publish and milestone_steps:publish_bootstrap(load(root))
        if bootstrap['stop_reason']!='target' or until<=2:return bootstrap
    lock=(root/'WRITER.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    cp=load(root);config=cp['config']
    assert config['accelerator']==json.loads(os.environ['PRIME_ACCELERATOR'])
    assert config['seed']==int(os.environ['PRIME_SEED'])
    assert config['cache_mib']==cache_mib
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
    if publish and milestone_steps:
        if not initial and len(records)%milestone_steps==0:publish(cp)
    if acc.history_gpu is None:
        history=bind(r.History,r.P,acc.history_threads,workers)(records,cache_mib*1024**2,acc)
    else:
        from gpu_roles import gpu_history_class
        history=gpu_history_class(r.History,r.P,acc.history_threads,workers,
            device=acc.history_gpu,device_cache_bytes=acc.gpu_cache_mib*1024**2)(records,cache_mib*1024**2,acc)
        acc.role_cleanups.append(history.release_device)
    restore_start=time.perf_counter()
    # Use otherwise idle RAM to avoid serial decompression misses after restart.
    # A bounded queue limits in-flight decode buffers; authenticate every file.
    eligible=max(0,min(len(records),((first+r.W-1)//2-2)//r.W+1))
    budget=int(history.limit*0.95)
    if acc.history_gpu is not None:
        # GPU hits no longer need decoded host copies. Warm the actual upload
        # working set and near-future requests, without filling an old prefix.
        needed=set(history.required_ids(first)) if len(records)<until else set()
        used=sum(records[j]['count']*4 for j in needed)
        for offset in range(1,min(64,until-len(records),len(records))):
            for j in history.required_ids(first+offset*r.W):
                size=records[j]['count']*4
                if j not in needed and used+size<=budget:needed.add(j);used+=size
        restore_ids=[];used=0
        for j in sorted(needed):
            size=records[j]['count']*4
            if used+size<=budget:restore_ids.append(j);used+=size
        restore_mode='gpu_upload_working_set'
    elif sum(rec['count']*4 for rec in records[:eligible])<=budget:
        restore_ids=list(range(eligible));restore_mode='eligible_prefix'
    else:
        # Reserve active and near-future masks, then fill remaining space with
        # older eligible history. Crossing the cache budget never disables
        # preloading or turns a useful large cache into a tiny lookahead cache.
        # All ids refer to immutable committed history; no truth data enters it.
        needed=set(history.required_ids(first)) if len(records)<until else set()
        used=sum(records[j]['count']*4 for j in needed)
        for offset in range(1,min(64,until-len(records),len(records))):
            for j in history.required_ids(first+offset*r.W):
                size=records[j]['count']*4
                if j not in needed and used+size<=budget:needed.add(j);used+=size
        for j in range(eligible):
            size=records[j]['count']*4
            if j in needed:continue
            if used+size>budget:break
            needed.add(j);used+=size
        restore_ids=[];used=0
        for j in sorted(needed):
            size=records[j]['count']*4
            if used+size<=budget:restore_ids.append(j);used+=size
        restore_mode='bounded_prefix_and_lookahead'
    if restore_ids:
        def decode(j):
            rec=records[j];raw=Path(rec['path']).read_bytes()
            if r.sha(raw)!=rec['sha256']:raise ValueError('History digest mismatch')
            meta,events=r.unpack(raw)
            if len(events)!=rec['count'] or meta['first']!=rec['first']:raise ValueError('History record mismatch')
            return j,history.compact(j,events),len(raw)
        def restore_progress(done):
            r.atomic(root/'PROGRESS.json',dict(status='RESTORING',seed=config['seed'],
                decisions=first-2,through=first-1,fp=fp,fn=fn,restored_chunks=done,
                total_chunks=len(restore_ids),restore_mode=restore_mode,
                updated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
        restore_progress(0)
        with ThreadPoolExecutor(max_workers=workers) as loader:
            jobs=deque();next_job=0
            done=0
            while next_job<len(restore_ids) or jobs:
                while next_job<len(restore_ids) and len(jobs)<2*workers:
                    jobs.append(loader.submit(decode,restore_ids[next_job]));next_job+=1
                j,events,nbytes=jobs.popleft().result()
                history.cache[j]=events;history.bytes+=events.nbytes;history.read_bytes+=nbytes;history.misses+=1
                done+=1
                if done%1000==0:restore_progress(done)
        history.peak=history.bytes
    restore_seconds=time.perf_counter()-restore_start
    durable=Writer(root,{**cp,'records':list(records)},getattr(r,'report_commit',None),
        milestone_steps,publish)
    buffers=[RandomBuffers(workers),RandomBuffers(workers)]
    proposal_buffers=[np.empty(r.W,np.uint32),np.empty(r.W,np.uint32)]
    pending=[]
    for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,lambda signum,frame:pending.append(signum))
    side=ThreadPoolExecutor(max_workers=2)
    def timed(fn,*args):
        start=time.perf_counter();value=fn(*args);return value,time.perf_counter()-start
    def prepare(first,slot):
        # Freshly emitted periods cannot return in this next window. Keep the
        # LRU for eligible history; authenticated files retain the fresh events.
        bank_future=side.submit(timed,history.banks,first)
        truth_future=side.submit(timed,acc.truth,first)
        t=time.perf_counter();u,v=buffers[slot].draw(base,extra,r.W);rt=time.perf_counter()-t
        br,er=copy.deepcopy(base.bit_generator.state),copy.deepcopy(extra.bit_generator.state)
        banks,bt=bank_future.result();bank_details=dict(history.last_stats)
        out=proposal_buffers[slot];t=time.perf_counter()
        if acc.backend=='gpu':
            acc.pin(u);acc.pin(v);acc.pin(out)
            acc.check(acc.gpu.gpu_propose(first,r.W,u.ctypes.data,v.ctypes.data,banks.ctypes.data,out.ctypes.data))
        else:acc.lib.propose(first,r.W,*[x.ctypes.data for x in [acc.row,acc.low,acc.high,acc.lut,u,v,banks,out]],acc.threads)
        pt=time.perf_counter()-t;truth,st=truth_future.result()
        return banks,u,v,out,truth,br,er,dict(banks=bt,rng=rt,proposal=pt,sieve=st,bank_details=bank_details)
    def commit(step,meta,events,snapshot,record,previous_hash,bank_hash,emission_hash):
        t=time.perf_counter();meta.update(period_sha256=r.digest(events),bank_sha256=r.digest(bank_hash),
            emission_sha256=r.digest(emission_hash),previous_sha256=previous_hash)
        blob=r.pack(meta,events);record['sha256']=r.sha(blob);compression=time.perf_counter()-t
        t=time.perf_counter();durable.add(record,blob,snapshot)
        return dict(compression=compression,durable_write=time.perf_counter()-t)
    # Complete timing records remain on disk; retain only a fixed diagnostic
    # tail in RAM and in the session summary, including at orderly shutdown.
    for row in initial:
        with (root/'TIMINGS.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    rows=deque(initial,maxlen=1024);reason='target';future_write=None
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
            snapshot=dict(status=status.tolist(),base_rng=br,extra_rng=er,next_n=first,fp=fp,fn=fn)
            previous_hash=records[-2]['sha256'] if step else None
            future_write=writer.submit(commit,step,meta,events,snapshot,record,previous_hash,banks,np.packbits(emit,bitorder='little'))
            timing.update(step=step,first=first-r.W,seconds=time.perf_counter()-tick,fp=fpi,fn=fni)
            rows.append(timing);slot=1-slot
        if future_write is not None:
            rows[-1].update(future_write.result())
            with (root/'TIMINGS.jsonl').open('a') as f:f.write(json.dumps(rows[-1])+'\n')
    durable.snapshot()
    for b in buffers:b.close()
    side.shutdown()
    history.close()
    elapsed=time.perf_counter()-started;decisions=(len(records)-start_step)*r.W
    result=dict(status='PASS',stop_reason=reason,mode='pipeline',start_step=start_step,end_step=len(records),
        new_decisions=decisions,seconds=elapsed,per_second=decisions/elapsed,through=first-1,fp=fp,fn=fn,
        events=int(status[1]),orphan_quarantined=orphan_count,rows=list(rows),cache=history.counters(),
        timing_rows_total=len(records)-start_step,timing_rows_retained=len(rows),
        timing_rows_scope='all' if len(records)-start_step<=len(rows) else 'tail',
        timings_path=str(root/'TIMINGS.jsonl'),
        history_restore_seconds=restore_seconds,
        history_restore_mode=restore_mode,history_restored_chunks=len(restore_ids),
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    r.atomic(root/f'RUN_{start_step:05d}_{len(records):05d}.json',result)
    r.atomic(root/'PROGRESS.json',dict(status='STOPPED',reason=reason,through=first-1,fp=fp,fn=fn,
        per_second=result['per_second'],updated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)
    return result
