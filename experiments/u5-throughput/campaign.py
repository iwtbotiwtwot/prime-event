"""Continue one raw trajectory, retain exact milestones, and mirror its journals.

Only clean target/time-budget exits renew. STOP, storage stops and failures end
the campaign. All report counts come from committed checkpoints.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from journal import load
from runtime_config import add_gpu_arguments,validate_gpu_arguments,gpu_options

HERE=Path(__file__).resolve().parent
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
def atomic(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('w') as f:json.dump(obj,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
def mirror(root,dest,checkpoint,milestone):
    """Copy only immutable committed chunks; authenticate each new copy."""
    (dest/'data').mkdir(parents=True,exist_ok=True)
    for record in checkpoint['records']:
        source=Path(record['path']);target=dest/'data'/source.name
        if target.exists() and target.stat().st_size==source.stat().st_size:continue
        if shutil.disk_usage(dest).free<20*1024**3+source.stat().st_size:
            raise RuntimeError('Container backup reached the 20 GiB free-space reserve')
        temporary=target.with_suffix('.partial');shutil.copyfile(source,temporary)
        with temporary.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==record['sha256']
        os.replace(temporary,target)
    atomic(dest/'data/CHECKPOINT.json',checkpoint)
    atomic(dest/'MIRROR.json',dict(status='VERIFIED_COPY',decisions=checkpoint['next_n']-2,
        updated_utc=utc(),source_root=str(root),restore_note='Checkpoint retains original absolute paths; restore there before resuming.'))
    atomic(root/'BACKUP.json',dict(status='COMPLETE',milestone=milestone,updated_utc=utc(),destination=str(dest)))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--mirror',type=Path,required=True)
    p.add_argument('--seed',type=int,default=9370001)
    p.add_argument('--milestone',type=int,default=100_000_000_000)
    p.add_argument('--max-milestones',type=int,default=0,help='0 continues until stopped')
    p.add_argument('--cache-mib',type=int,default=65536)
    p.add_argument('--threads',type=int,default=8)
    p.add_argument('--workers',type=int,default=8)
    p.add_argument('--history-threads',type=int,default=12)
    p.add_argument('--session-seconds',type=int,default=86300)
    add_gpu_arguments(p)
    a=p.parse_args();root=a.root.resolve();root.mkdir(parents=True,exist_ok=True)
    validate_gpu_arguments(p,a)
    if a.milestone<5_000_000 or a.milestone%5_000_000:p.error('milestone must be a positive multiple of 5M')
    if min(a.cache_mib,a.threads,a.workers,a.history_threads,a.session_seconds)<1 or a.max_milestones<0:
        p.error('positive resource limits and nonnegative milestone limit required')
    lock=(root/'CAMPAIGN.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    (root/'data').mkdir(exist_ok=True)
    for sig in [signal.SIGINT,signal.SIGTERM]:signal.signal(sig,lambda *_:(root/'data/STOP').touch())
    identity=dict(seed=a.seed,milestone=a.milestone,cache_mib=a.cache_mib,backend='gpu',
        threads=a.threads,workers=a.workers,history_threads=a.history_threads,**gpu_options(a))
    statepath=root/'CAMPAIGN.json'
    state=json.loads(statepath.read_text()) if statepath.exists() else dict(config=identity,started_utc=utc(),started_unix=time.time(),reports=[])
    for key in ('seed','milestone','cache_mib','backend'):assert state['config'][key]==identity[key]
    if state['config']!=identity:state['previous_scheduling_config']=state['config']
    state['config']=identity
    state.update(status='RUNNING',pid=os.getpid());state.pop('reason',None);atomic(statepath,state)
    atomic(root/'REPORTS.json',state['reports'])
    pool=ThreadPoolExecutor(max_workers=1);backup=None;child=None
    def collect():
        nonlocal backup
        while not a.max_milestones or len(state['reports'])<a.max_milestones:
            target=(len(state['reports'])+1)*a.milestone
            marker=root/'data'/f'MILESTONE_{target:015d}.json'
            if not marker.exists():break
            witness=json.loads(marker.read_text());assert witness['decisions']==target and witness['seed']==a.seed
            raw=Path(witness['checkpoint_path']).read_bytes()
            assert hashlib.sha256(raw).hexdigest()==witness['checkpoint_sha256']
            cp=json.loads(raw);assert cp['next_n']-2==target
            assert cp['fp']==witness['fp'] and cp['fn']==witness['fn']
            now=witness['unix'];prior=state['reports'][-1] if state['reports'] else dict(unix=state['started_unix'],decisions=0,fp=0,fn=0)
            assert now>prior['unix']
            report=dict(milestone=len(state['reports'])+1,observed_utc=witness['observed_utc'],unix=now,seed=a.seed,
                decisions=target,through=witness['through'],fp=cp['fp'],fn=cp['fn'],errors=cp['fp']+cp['fn'],
                interval_fp=cp['fp']-prior['fp'],interval_fn=cp['fn']-prior['fn'],
                interval_seconds=now-prior['unix'],interval_per_second=(target-prior['decisions'])/(now-prior['unix']),
                cumulative_seconds=now-state['started_unix'],cumulative_per_second=target/(now-state['started_unix']),
                checkpoint_sha256=witness['checkpoint_sha256'],checkpoint_path=witness['checkpoint_path'],
                worker_pid=witness['worker_pid'],feedback='raw; no repair or correction')
            state['reports'].append(report);atomic(root/'milestones'/f'{target:015d}.json',report)
            atomic(statepath,state);atomic(root/'REPORTS.json',state['reports'])
            a.mirror.mkdir(parents=True,exist_ok=True);atomic(a.mirror/'REPORTS.json',state['reports']);atomic(a.mirror/'CAMPAIGN.json',state)
            print(json.dumps(report),flush=True)
            if (root/'ARCHIVE_POLICY.json').exists():
                atomic(root/'BACKUP.json',dict(status='ARCHIVE_ROTATION',threshold_bytes=100*1024**3,
                    working_history_retained=True,updated_utc=utc()))
            else:
                if backup is not None:backup.result()
                atomic(root/'BACKUP.json',dict(status='COPYING',milestone=target,updated_utc=utc()))
                backup=pool.submit(mirror,root,a.mirror,cp,target)
    try:
        while not a.max_milestones or len(state['reports'])<a.max_milestones:
            if (root/'data/STOP').exists():state['status']='STOPPED';state['reason']='requested';break
            if backup is not None and backup.done():backup.result();backup=None
            collect()
            if a.max_milestones and len(state['reports'])>=a.max_milestones:break
            cp=load(root/'data') if (root/'data/CHECKPOINT.json').exists() else None
            current=cp['next_n']-2 if cp else 0
            # A finite session limit allows periodic orderly renewal, while
            # milestone publication itself keeps the worker and cache alive.
            target=a.max_milestones*a.milestone if a.max_milestones else (current//a.milestone+10000)*a.milestone
            assert current<target
            command=[sys.executable,str(HERE/'pilot.py'),'--workdir',str(root),'--backend','gpu',
                '--pipeline','--threads',str(a.threads),'--workers',str(a.workers),
                '--history-threads',str(a.history_threads),'--seed',str(a.seed),'--cache-mib',str(a.cache_mib),
                '--chunks',str(target//5_000_000),'--seconds',str(a.session_seconds),
                '--milestone',str(a.milestone),'--progress-every','100000000']
            command+=['--proposal-gpu',str(a.proposal_gpu),'--gpu-cache-mib',str(a.gpu_cache_mib),
                      '--cuda-arch',a.cuda_arch]
            if a.history_gpu is not None:command+=['--history-gpu',str(a.history_gpu)]
            if a.grade_gpu is not None:command+=['--grade-gpu',str(a.grade_gpu)]
            with (root/'runner.log').open('a') as log:
                child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                state['worker_pid']=child.pid;state['worker_starts']=state.get('worker_starts',0)+1;atomic(statepath,state)
                while True:
                    collect()
                    if backup is not None and backup.done():backup.result();backup=None
                    if child.poll() is not None:break
                    time.sleep(0.25)
                if child.returncode:raise subprocess.CalledProcessError(child.returncode,command)
            collect();result=json.loads((root/'PILOT.json').read_text());child=None
            if result['stop_reason'] not in ['target','session_time_budget']:
                state.update(status='STOPPED',reason=result['stop_reason']);break
        else:state.update(status='STOPPED',reason='test_milestone_limit')
        if a.max_milestones and len(state['reports'])>=a.max_milestones:
            state.update(status='STOPPED',reason='test_milestone_limit')
    except Exception as exc:
        state.update(status='FAILED',reason=repr(exc));raise
    finally:
        if child is not None and child.poll() is None:
            (root/'data/STOP').touch();child.wait()
        atomic(statepath,state)
        try:
            if backup is not None:backup.result()
        finally:pool.shutdown()

if __name__=='__main__':main()
