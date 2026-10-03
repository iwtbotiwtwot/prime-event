"""Display committed progress and throughput in a pod web terminal."""
import argparse
from collections import deque
import json
from pathlib import Path
import sys
import time

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('/root/prime-u5-production'))
    p.add_argument('--watch',type=float,help='Refresh every N seconds; Ctrl+C exits only the monitor')
    p.add_argument('--window',type=float,default=30,help='Rolling throughput measurement window in seconds')
    p.add_argument('--json',action='store_true',help='Include numeric throughput_m_per_second values')
    a=p.parse_args()
    if a.window<=0 or (a.watch is not None and a.watch<=0):p.error('positive time intervals required')
    samples=deque()
    try:
        while True:
            progress=json.loads((a.root/'data/PROGRESS.json').read_bytes())
            now=time.monotonic();status=progress['status']
            count=progress.get('decisions',progress.get('through',1)-1)
            measured=None;duration=None
            if status=='RUNNING':
                if samples and count<samples[-1][1]:samples.clear()
                samples.append((now,count))
                while len(samples)>2 and samples[1][0]<=now-a.window:samples.popleft()
                if len(samples)>1:
                    duration=now-samples[0][0]
                    measured=(count-samples[0][1])/duration/1e6
                recent=progress.get('recent_per_second')
            else:
                samples.clear();recent=None
            row=dict(status=status,decisions=count,through=count+1,
                fp=progress.get('fp',0),fn=progress.get('fn',0),
                errors=progress.get('fp',0)+progress.get('fn',0),
                throughput_m_per_second=recent/1e6 if recent is not None else None,
                measured_throughput_m_per_second=measured,measured_seconds=duration,
                updated_utc=progress['updated_utc'])
            try:
                row['memory_gib']=int(Path('/sys/fs/cgroup/memory.current').read_text())/1024**3
                row['memory_limit_gib']=int(Path('/sys/fs/cgroup/memory.max').read_text())/1024**3
            except (OSError,ValueError):pass
            if a.json:
                print(json.dumps(row),flush=True)
            else:
                if a.watch and sys.stdout.isatty():print('\033[2J\033[H',end='')
                lines=[f"Status: {status}    Updated: {row['updated_utc']}",
                       f"Committed decisions: {count:,}    Through: {count+1:,}",
                       f"FP: {row['fp']:,}    FN: {row['fn']:,}    Errors: {row['errors']:,}"]
                if recent is not None:lines.append(f"Throughput (latest commit group): {recent/1e6:,.2f} M decisions/s")
                if measured is not None:lines.append(f"Throughput (observed {duration:.1f}s): {measured:,.2f} M decisions/s")
                if status=='RESTORING':lines.append(f"History restored: {progress.get('restored_chunks',0):,} / {progress.get('total_chunks',0):,} chunks")
                if 'memory_limit_gib' in row:lines.append(f"Container memory: {row['memory_gib']:.1f} / {row['memory_limit_gib']:.1f} GiB (includes file cache)")
                print('\n'.join(lines)+'\n',flush=True)
            if a.watch is None:break
            time.sleep(a.watch)
    except KeyboardInterrupt:pass

if __name__=='__main__':main()
