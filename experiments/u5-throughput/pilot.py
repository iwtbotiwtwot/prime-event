"""Build and run an isolated, finite exact-replay throughput pilot."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from runtime_config import SOURCE_FILES, add_gpu_arguments, validate_gpu_arguments, accelerator_identity, gpu_options

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
    p.add_argument('--history-threads',type=int,default=12)
    p.add_argument('--milestone',type=int,default=0,help='Publish durable milestones without restarting (0 disables)')
    p.add_argument('--seconds',type=int,default=120)
    p.add_argument('--pipeline',action='store_true')
    p.add_argument('--cache-mib',type=int,default=4096)
    p.add_argument('--progress-every',type=int,default=0,help='Refresh committed progress every N decisions (0 disables)')
    add_gpu_arguments(p)
    args = p.parse_args()
    validate_gpu_arguments(p,args,args.backend,args.pipeline)
    if min(args.chunks,args.threads,args.workers,args.history_threads,args.seconds,args.cache_mib)<1 or args.progress_every<0: p.error('positive limits required')
    if args.milestone<0 or args.milestone%5_000_000:p.error('milestone must be a nonnegative multiple of 5M')
    spec = importlib.util.spec_from_file_location('prepare', ROOT/'scripts/reproduce_u5.py')
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    dest = module.prepare(args.workdir/'source')
    files = SOURCE_FILES
    identity = {name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in files}
    for name in files: (dest/name).write_bytes((HERE/name).read_bytes())
    subprocess.run(['g++','-O3','-march=native','-std=c++17','-shared','-fPIC','-fopenmp',str(dest/'accelerator.cpp'),'-o',str(dest/'accelerator.so')],check=True)
    subprocess.run(['g++','-O3','-march=native','-std=c++17','-shared','-fPIC','-fopenmp',str(dest/'native_history.cpp'),'-o',str(dest/'history_native.so')],check=True)
    if args.backend=='gpu':
        def cuda_build(name,output):
            subprocess.run(['/usr/local/cuda/bin/nvcc','-O3','-std=c++17','-shared','-Xcompiler','-fPIC',
                '-arch='+args.cuda_arch,str(dest/name),'-o',str(dest/output)],check=True)
        cuda_build('accelerator.cu','accelerator_gpu.so')
        if args.grade_gpu is not None:cuda_build('gpu_grade.cu','gpu_grade.so')
        if args.history_gpu is not None:
            (dest/'history_gpu_plan.cpp').write_text((dest/'native_history.cpp').read_text()+'\n'+(dest/'history_exports.cpp').read_text())
            subprocess.run(['g++','-O3','-march=native','-std=c++17','-shared','-fPIC','-fopenmp',
                str(dest/'history_gpu_plan.cpp'),'-o',str(dest/'history_gpu_plan.so')],check=True)
            cuda_build('gpu_history.cu','gpu_history.so')
    # Keep the archival runner untouched. Bind accelerator identity into pilot checkpoints.
    code = (dest/'runner.py').read_text()
    code = code.replace("config=dict(seed=", "config=dict(accelerator=json.loads(os.environ['PRIME_ACCELERATOR']),seed=")
    (dest/'pilot_runner.py').write_text(code)
    os.environ.update(PRIME_ACCELERATOR=json.dumps(accelerator_identity(HERE,args.backend,args.pipeline,args)),
        PRIME_SEED=str(args.seed),PRIME_BACKEND='cpu',PRIME_RNG_WORKERS=str(args.workers),
        PRIME_WALL_SECONDS=str(args.seconds),OMP_WAIT_POLICY='PASSIVE')
    sys.path.insert(0,str(dest))
    import pilot_runner as runner
    from accelerated import Accelerator
    original = runner.Kernels
    acc = Accelerator(dest,original(),args.backend,args.threads,
        proposal_gpu=args.proposal_gpu,history_gpu=args.history_gpu,grade_gpu=args.grade_gpu,
        gpu_cache_mib=args.gpu_cache_mib)
    acc.history_threads=args.history_threads
    runner.Kernels = lambda: acc
    runner.truth = acc.truth
    if args.milestone:
        def publish_milestone(obj):
            import time
            count=obj['next_n']-2;data=args.workdir/'data'
            marker=data/f'MILESTONE_{count:015d}.json'
            if marker.exists():
                prior=json.loads(marker.read_text())
                assert prior['decisions']==count and prior['seed']==args.seed
                assert prior['fp']==obj['fp'] and prior['fn']==obj['fn']
                return
            checkpoint=data/f'MILESTONE_{count:015d}.checkpoint.json'
            runner.atomic(checkpoint,obj)
            now=time.time()
            runner.atomic(marker,dict(decisions=count,through=obj['next_n']-1,seed=args.seed,
                fp=obj['fp'],fn=obj['fn'],unix=now,
                observed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(now)),
                checkpoint_path=str(checkpoint.resolve()),
                checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                worker_pid=os.getpid(),journal=obj.get('_journal')))
        runner.milestone_commit=publish_milestone
    if args.progress_every:
        import time
        atomic=runner.atomic;clock=time.monotonic();origin=None;previous=None
        def report_commit(obj):
            nonlocal origin,previous
            count=obj['next_n']-2;now=time.monotonic()
            if origin is None:origin=(count,clock)
            if previous is None or count-previous[0]>=args.progress_every:
                prior=previous or origin
                atomic(args.workdir/'data/PROGRESS.json',dict(status='RUNNING',seed=obj['config']['seed'],
                    decisions=count,through=obj['next_n']-1,fp=obj['fp'],fn=obj['fn'],
                    recent_per_second=(count-prior[0])/max(now-prior[1],1e-9),
                    session_per_second=(count-origin[0])/max(now-origin[1],1e-9),
                    updated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
                previous=(count,now)
        def observed_atomic(path,obj):
            atomic(path,obj)
            if path.name=='CHECKPOINT.json':report_commit(obj)
        runner.report_commit=report_commit
        runner.atomic=observed_atomic
    try:
        if args.pipeline:
            from pipeline import run
            result = run(runner,acc,(args.workdir/'data').resolve(),args.chunks,args.workers,args.seconds,
                args.cache_mib,args.milestone//5_000_000)
        else:
            result = runner.run((args.workdir/'data').resolve(),args.chunks,'indexed',args.cache_mib)
    finally:acc.close()
    result['accelerator'] = dict(backend=args.backend,files=identity,threads=args.threads,
        workers=args.workers,history_threads=args.history_threads,
        **gpu_options(args),
        fallback_readings=int(acc.counters[0]),changed_banks=int(acc.counters[1]),timings=acc.timings)
    (args.workdir/'PILOT.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__': main()
