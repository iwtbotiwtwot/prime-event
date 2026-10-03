"""Read live timings and benchmark isolated history/checkpoint work without changing a run.

Run on the pod with its NumPy environment. Diagnostic writes use a temporary
directory outside the production root. No RNG draws or production state changes.
"""
import collections
import cProfile
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time

root = Path(sys.argv[1] if len(sys.argv) > 1 else '/root/prime-u5-production')
os.environ['OMP_WAIT_POLICY'] = 'PASSIVE'
sys.path.insert(0, str(root / 'source'))
import pilot_runner as runner
from accelerated import Accelerator

cp_raw = (root / 'data/CHECKPOINT.json').read_bytes()
cp = json.loads(cp_raw)
if (root / 'data/HEAD.json').exists():
    from journal import load
    cp = load(root / 'data')
rows = []
for line in (root / 'data/TIMINGS.jsonl').read_text().splitlines():
    try:
        rows.append(json.loads(line))
    except json.JSONDecodeError:
        pass  # The live writer can leave an incomplete final line while sampled.
keys = ['seconds', 'banks', 'rng', 'proposal', 'sieve', 'consume', 'grade', 'compression', 'durable_write']
out = dict(observed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           checkpoint_sha256=hashlib.sha256(cp_raw).hexdigest(),
           decisions=cp['next_n']-2, fp=cp['fp'], fn=cp['fn'],
           checkpoint_bytes=len(cp_raw), records=len(cp['records']),
           source_identity=cp['config']['accelerator'], windows=[], history=[], checkpoint=[])
for lo, hi in [(1,2),(5,6),(10,11),(20,21),(40,41),(60,61),(80,81),(90,91)]:
    a = [r for r in rows if lo*1e9 <= r['first'] < hi*1e9]
    if a:
        out['windows'].append(dict(billions=[lo,hi], chunks=len(a),
            mean_ms={k:statistics.mean(r[k] for r in a if k in r)*1000 for k in keys},
            loop_million_per_second=5/statistics.mean(r['seconds'] for r in a)))

acc = Accelerator(root/'source', runner.Kernels(), 'cpu', 8)
class MeasuredKernels:
    def __init__(self):
        self.reset()
    def reset(self):
        self.seconds=collections.defaultdict(float)
        self.calls=collections.Counter()
    def call(self, name, *args):
        t=time.perf_counter()
        result=getattr(acc, name)(*args)
        self.seconds[name]+=time.perf_counter()-t
        self.calls[name]+=1
        return result
    def mark(self,*args): return self.call('mark',*args)
    def index(self,*args): return self.call('index',*args)

k=MeasuredKernels()
for n in [1_000_000_002,20_000_000_002,90_000_000_002]:
    if n >= cp['next_n']: continue
    history=runner.History(cp['records'], 2*1024**3, k)
    history.banks(n)  # Load only the actual committed records this window needs.
    measurements=[]
    for _ in range(5):
        k.reset(); start=time.perf_counter(); b=history.banks(n); elapsed=time.perf_counter()-start
        measurements.append(dict(total_ms=elapsed*1000,
            mark_ms=k.seconds['mark']*1000, index_ms=k.seconds['index']*1000,
            python_and_dispatch_ms=(elapsed-sum(k.seconds.values()))*1000,
            calls=dict(k.calls)))
    profile=cProfile.Profile(); profile.enable(); history.banks(n); profile.disable()
    functions=sorted(profile.getstats(),key=lambda x:x.inlinetime,reverse=True)[:12]
    out['history'].append(dict(first=n, measurements=measurements, cache=history.counters(),
        bank_sha256=hashlib.sha256(b.tobytes()).hexdigest(),
        profile=[dict(function=str(x.code) if isinstance(x.code,str) else
            f'{x.code.co_filename}:{x.code.co_firstlineno}:{x.code.co_name}',
            calls=x.callcount,self_ms=x.inlinetime*1000,total_ms=x.totaltime*1000) for x in functions]))

with tempfile.TemporaryDirectory(prefix='prime-throughput-diagnostic-',dir='/tmp') as td:
    dest=Path(td)/'CHECKPOINT.json'
    for count in [200,4000,len(cp['records'])]:
        snapshot={**cp,'records':cp['records'][:count]}
        # Truncated objects are serialization benchmarks, not resumable checkpoints.
        m=[]
        for _ in range(5):
            t=time.perf_counter(); cpu=time.process_time()
            blob=(json.dumps(snapshot,sort_keys=True)+'\n').encode()
            encoding=time.perf_counter()-t; encoding_cpu=time.process_time()-cpu
            t=time.perf_counter(); runner.atomic(dest,blob); write=time.perf_counter()-t
            m.append(dict(encode_ms=encoding*1000,encode_cpu_ms=encoding_cpu*1000,
                          write_fsync_ms=write*1000))
        out['checkpoint'].append(dict(records=count,bytes=len(blob),measurements=m))
out['finished_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
print(json.dumps(out,indent=2))
