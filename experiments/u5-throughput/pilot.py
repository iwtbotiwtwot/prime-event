"""Build and run an isolated, finite exact-replay throughput pilot."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workdir',required=True,type=Path)
    p.add_argument('--backend',choices=['cpu','gpu'],default='cpu')
    p.add_argument('--chunks',type=int,default=20)
    p.add_argument('--seed',type=int,default=9369001)
    p.add_argument('--threads',type=int,default=16)
    p.add_argument('--workers',type=int,default=8)
    p.add_argument('--seconds',type=int,default=120)
    p.add_argument('--pipeline',action='store_true')
    p.add_argument('--cache-mib',type=int,default=4096)
    p.add_argument('--progress-every',type=int,default=0,help='Refresh committed progress every N decisions (0 disables)')
    args = p.parse_args()
    if min(args.chunks,args.threads,args.workers,args.seconds,args.cache_mib)<1 or args.progress_every<0: p.error('positive limits required')
    spec = importlib.util.spec_from_file_location('prepare', ROOT/'scripts/reproduce_u5.py')
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    dest = module.prepare(args.workdir/'source')
    files = ['accelerator.cpp','accelerator.cu','accelerated.py','pilot.py','pipeline.py']
    identity = {name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in files}
    for name in files: (dest/name).write_bytes((HERE/name).read_bytes())
    subprocess.run(['g++','-O3','-std=c++17','-shared','-fPIC','-fopenmp',str(dest/'accelerator.cpp'),'-o',str(dest/'accelerator.so')],check=True)
    if args.backend=='gpu':
        subprocess.run(['/usr/local/cuda/bin/nvcc','-O3','-std=c++17','-shared','-Xcompiler','-fPIC','-arch=sm_86',str(dest/'accelerator.cu'),'-o',str(dest/'accelerator_gpu.so')],check=True)
    # Keep the archival runner untouched. Bind accelerator identity into pilot checkpoints.
    code = (dest/'runner.py').read_text()
    code = code.replace("config=dict(seed=", "config=dict(accelerator=json.loads(os.environ['PRIME_ACCELERATOR']),seed=")
    (dest/'pilot_runner.py').write_text(code)
    os.environ.update(PRIME_ACCELERATOR=json.dumps(dict(backend=args.backend,pipeline=args.pipeline,files=identity)),
        PRIME_SEED=str(args.seed),PRIME_BACKEND='cpu',PRIME_RNG_WORKERS=str(args.workers),
        PRIME_WALL_SECONDS=str(args.seconds),OMP_WAIT_POLICY='PASSIVE')
    sys.path.insert(0,str(dest))
    import pilot_runner as runner
    from accelerated import Accelerator
    original = runner.Kernels
    acc = Accelerator(dest,original(),args.backend,args.threads)
    runner.Kernels = lambda: acc
    runner.truth = acc.truth
    if args.progress_every:
        import time
        atomic=runner.atomic;clock=time.monotonic();origin=None;previous=None
        def observed_atomic(path,obj):
            nonlocal origin,previous
            atomic(path,obj)
            if path.name!='CHECKPOINT.json':return
            count=obj['next_n']-2;now=time.monotonic()
            if origin is None:origin=(count,clock)
            if previous is None or count-previous[0]>=args.progress_every:
                prior=previous or origin
                atomic(path.parent/'PROGRESS.json',dict(status='RUNNING',seed=obj['config']['seed'],
                    decisions=count,through=obj['next_n']-1,fp=obj['fp'],fn=obj['fn'],
                    recent_per_second=(count-prior[0])/max(now-prior[1],1e-9),
                    session_per_second=(count-origin[0])/max(now-origin[1],1e-9),
                    updated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
                previous=(count,now)
        runner.atomic=observed_atomic
    if args.pipeline:
        from pipeline import run
        result = run(runner,acc,(args.workdir/'data').resolve(),args.chunks,args.workers,args.seconds,args.cache_mib)
    else:
        result = runner.run((args.workdir/'data').resolve(),args.chunks,'indexed',args.cache_mib)
    result['accelerator'] = dict(backend=args.backend,files=identity,threads=args.threads,
        workers=args.workers,fallback_readings=int(acc.counters[0]),changed_banks=int(acc.counters[1]),timings=acc.timings)
    (args.workdir/'PILOT.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__': main()
