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
    a=p.parse_args();root=a.root.resolve();root.mkdir(parents=True,exist_ok=True)
    if a.milestone<5_000_000 or a.milestone%5_000_000:p.error('milestone must be a positive multiple of 5M')
    lock=(root/'CAMPAIGN.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    (root/'data').mkdir(exist_ok=True)
    for sig in [signal.SIGINT,signal.SIGTERM]:signal.signal(sig,lambda *_:(root/'data/STOP').touch())
    identity=dict(seed=a.seed,milestone=a.milestone,cache_mib=a.cache_mib,backend='gpu',threads=8,workers=8)
    statepath=root/'CAMPAIGN.json'
    state=json.loads(statepath.read_text()) if statepath.exists() else dict(config=identity,started_utc=utc(),started_unix=time.time(),reports=[])
    assert state['config']==identity
    state.update(status='RUNNING',pid=os.getpid());state.pop('reason',None);atomic(statepath,state)
    atomic(root/'REPORTS.json',state['reports'])
    pool=ThreadPoolExecutor(max_workers=1);backup=None
    try:
        while not a.max_milestones or len(state['reports'])<a.max_milestones:
            if (root/'data/STOP').exists():state['status']='STOPPED';state['reason']='requested';break
            if backup is not None and backup.done():backup.result();backup=None
            target=(len(state['reports'])+1)*a.milestone
            cp_path=root/'data/CHECKPOINT.json'
            cp=json.loads(cp_path.read_text()) if cp_path.exists() else None
            current=cp['next_n']-2 if cp else 0
            assert current<=target
            if current<target:
                command=[sys.executable,str(HERE/'pilot.py'),'--workdir',str(root),'--backend','gpu',
                    '--pipeline','--threads','8','--workers','8','--seed',str(a.seed),'--cache-mib',str(a.cache_mib),
                    '--chunks',str(target//5_000_000),'--seconds','86300','--progress-every','100000000']
                with (root/'runner.log').open('a') as log:
                    subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
                result=json.loads((root/'PILOT.json').read_text())
                if result['stop_reason'] not in ['target','session_time_budget']:
                    state.update(status='STOPPED',reason=result['stop_reason']);break
                if result['stop_reason']=='session_time_budget':continue
                cp=json.loads(cp_path.read_text());assert cp['next_n']-2==target
            now=time.time();prior=state['reports'][-1] if state['reports'] else dict(unix=state['started_unix'],decisions=0,fp=0,fn=0)
            report=dict(milestone=len(state['reports'])+1,observed_utc=utc(),unix=now,seed=a.seed,
                decisions=target,through=cp['next_n']-1,fp=cp['fp'],fn=cp['fn'],errors=cp['fp']+cp['fn'],
                interval_fp=cp['fp']-prior['fp'],interval_fn=cp['fn']-prior['fn'],
                interval_seconds=now-prior['unix'],interval_per_second=(target-prior['decisions'])/(now-prior['unix']),
                cumulative_seconds=now-state['started_unix'],cumulative_per_second=target/(now-state['started_unix']),
                checkpoint_sha256=hashlib.sha256(cp_path.read_bytes()).hexdigest(),feedback='raw; no repair or correction')
            state['reports'].append(report);atomic(root/'milestones'/f'{target:015d}.json',report)
            atomic(statepath,state);atomic(root/'REPORTS.json',state['reports'])
            a.mirror.mkdir(parents=True,exist_ok=True);atomic(a.mirror/'REPORTS.json',state['reports']);atomic(a.mirror/'CAMPAIGN.json',state)
            print(json.dumps(report),flush=True)
            # The archive worker replaces duplicate per-milestone journal copies.
            if (root/'ARCHIVE_POLICY.json').exists():
                atomic(root/'BACKUP.json',dict(status='ARCHIVE_ROTATION',threshold_bytes=100*1024**3,
                    working_history_retained=True,updated_utc=utc()));continue
            # At most one backup is in flight; no unbounded queue or deletion.
            if backup is not None:backup.result()
            atomic(root/'BACKUP.json',dict(status='COPYING',milestone=target,updated_utc=utc()))
            backup=pool.submit(mirror,root,a.mirror,cp,target)
        else:state.update(status='STOPPED',reason='test_milestone_limit')
    except Exception as exc:
        state.update(status='FAILED',reason=repr(exc));raise
    finally:
        atomic(statepath,state)
        try:
            if backup is not None:backup.result()
        finally:pool.shutdown()

if __name__=='__main__':main()
