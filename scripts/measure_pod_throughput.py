"""Measure committed production decisions after restoration using durable HEAD."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

def counters(path):
    return {line.split()[0]:int(line.split()[1]) for line in path.read_text().splitlines()}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('/root/prime-u5-production'))
    p.add_argument('--seconds',type=int,default=120)
    p.add_argument('--interval',type=int,default=30)
    p.add_argument('--restore-timeout',type=int,default=1200)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    if min(a.seconds,a.interval,a.restore_timeout)<1:p.error('positive time limits required')
    points=[];deadline=time.monotonic()+a.restore_timeout
    while True:
        campaign=json.loads((a.root/'CAMPAIGN.json').read_bytes())
        progress=json.loads((a.root/'data/PROGRESS.json').read_bytes())
        if campaign['status']!='RUNNING':raise RuntimeError(campaign)
        if progress['status']=='RUNNING':break
        if time.monotonic()>deadline:raise TimeoutError('Restoration did not finish')
        print(json.dumps(dict(phase='WAITING_FOR_RUNNING',progress=progress)),flush=True)
        time.sleep(min(a.interval,30))
    def sample():
        head=json.loads((a.root/'data/HEAD.json').read_bytes());clock=time.monotonic()
        progress=json.loads((a.root/'data/PROGRESS.json').read_bytes())
        state=json.loads((a.root/'CAMPAIGN.json').read_bytes())
        for pid in (state['pid'],state['worker_pid']):os.kill(pid,0)
        if state['status']!='RUNNING' or progress['status']!='RUNNING':raise RuntimeError(state)
        point=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            monotonic=clock,head=head,decisions=head['sequence']*5_000_000,progress=progress,
            controller_pid=state['pid'],worker_pid=state['worker_pid'],
            memory_current_bytes=int(Path('/sys/fs/cgroup/memory.current').read_text()),
            memory_limit_bytes=int(Path('/sys/fs/cgroup/memory.max').read_text()),
            memory_events=counters(Path('/sys/fs/cgroup/memory.events')),
            cpu_stat=counters(Path('/sys/fs/cgroup/cpu.stat')),
            gpu=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.used,utilization.gpu',
                                         '--format=csv,noheader'],text=True).strip())
        if points:
            prior=points[-1]
            point['interval_per_second']=(point['decisions']-prior['decisions'])/(clock-prior['monotonic'])
        points.append(point)
        print(json.dumps(point),flush=True)
    sample();started=points[0]['monotonic']
    while time.monotonic()-started<a.seconds:
        time.sleep(min(a.interval,max(0,a.seconds-(time.monotonic()-started))))
        sample()
    duration=points[-1]['monotonic']-started
    decisions=points[-1]['decisions']-points[0]['decisions']
    sys.path.insert(0,str(a.root/'source'))
    from journal import load
    cp=load(a.root/'data')
    identity=cp['config']['accelerator']['files']
    for name,digest in identity.items():
        assert hashlib.sha256((a.root/'source'/name).read_bytes()).hexdigest()==digest,name
    rows=[]
    with (a.root/'data/TIMINGS.jsonl').open('rb') as f:
        f.seek(0,2);f.seek(max(0,f.tell()-128*1024))
        for line in f.read().splitlines()[1:]:
            try:row=json.loads(line)
            except json.JSONDecodeError:continue
            if points[0]['head']['sequence']<=row['step']<points[-1]['head']['sequence']:rows.append(row)
    result=dict(status='PASS',measurement='durable HEAD sequence delta over monotonic elapsed time',
        seconds=duration,new_decisions=decisions,per_second=decisions/duration,
        fp=cp['fp'],fn=cp['fn'],validated_decisions=cp['next_n']-2,config=cp['config'],
        source_files=identity,samples=points,
        min_interval_per_second=min(x['interval_per_second'] for x in points[1:]),
        max_interval_per_second=max(x['interval_per_second'] for x in points[1:]),
        cpu_throttled_delta=points[-1]['cpu_stat']['nr_throttled']-points[0]['cpu_stat']['nr_throttled'],
        memory_event_deltas={k:points[-1]['memory_events'][k]-points[0]['memory_events'][k]
                             for k in points[0]['memory_events']},
        recent_timing_rows=len(rows))
    if rows:
        result['latest_bank_details']=rows[-1]['bank_details']
        result['recent_stage_mean_ms']={k:statistics.mean(r[k]*1000 for r in rows)
                                      for k in ('banks','rng','proposal','sieve','consume','grade','compression','durable_write')}
    output=a.output or a.root/'GPU_ROLES_LIVE_THROUGHPUT.json'
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('samples','config','source_files')}),flush=True)

if __name__=='__main__':main()
