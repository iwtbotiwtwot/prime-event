"""Qualify the packaged GPU runner against frozen, mature and recovered journals."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import numpy as np
from journal import atomic, load
from runtime_config import add_gpu_arguments, accelerator_identity, validate_gpu_arguments

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--mature-chunks', type=int, default=400)
    add_gpu_arguments(parser)
    args = parser.parse_args()
    validate_gpu_arguments(parser, args)
    if args.mature_chunks < 1:
        parser.error('positive mature chunk count required')
    root = args.workdir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    production = args.production.resolve()
    assert (production/'data/STOP').exists()
    original_sha = hashlib.sha256((production/'data/CHECKPOINT.json').read_bytes()).hexdigest()
    original = load(production/'data')
    # Qualification preserves observed raw errors as well as zero-error runs.
    # Mature comparison below requires exact cumulative FP/FN agreement.
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')

    def command(target, chunks, seed=9369001, backend='gpu'):
        cmd = [sys.executable, str(HERE/'pilot.py'), '--workdir', str(target),
               '--backend', backend, '--pipeline', '--threads', '8', '--workers', '8',
               '--history-threads', '12', '--seed', str(seed), '--cache-mib', '4096',
               '--chunks', str(chunks), '--seconds', '600', '--cuda-arch', args.cuda_arch]
        if backend == 'gpu':
            cmd += ['--proposal-gpu', str(args.proposal_gpu), '--gpu-cache-mib', str(args.gpu_cache_mib)]
            for role in ('history_gpu', 'grade_gpu'):
                if getattr(args, role) is not None:
                    cmd += ['--'+role.replace('_','-'), str(getattr(args, role))]
        return cmd

    def run(cmd, log):
        with log.open('w') as out:
            subprocess.run(cmd, env=env, stdout=out, stderr=subprocess.STDOUT, check=True)

    def compare(left, right, start=0, end=None):
        cmd=[sys.executable,str(HERE/'compare_journals.py'),str(left),str(right),'--start-chunk',str(start)]
        if end is not None:cmd+=['--chunks',str(end)]
        return json.loads(subprocess.check_output(cmd,env=env,text=True))

    fresh = root/'fresh'
    if not (fresh/'PILOT.json').exists():
        run(command(fresh, 20), root/'fresh.log')
    frozen = json.loads(subprocess.check_output([sys.executable, str(REPO/'scripts/check_u5_replay.py'),
                                               str(fresh)], env=env, text=True))
    assert load(fresh/'data')['config']['accelerator'] == accelerator_identity(HERE, 'gpu', True, args)
    print(json.dumps(dict(phase='FROZEN_PREFIX', **frozen)), flush=True)

    end = len(original['records'])
    start = end-args.mature_chunks
    assert start >= 4
    origin = copy.deepcopy(original)
    origin.pop('_journal', None)
    origin['records'] = origin['records'][:start]
    record = origin['records'][-1]
    assert hashlib.sha256(Path(record['path']).read_bytes()).hexdigest() == record['sha256']
    with np.load(record['path'], allow_pickle=False) as stored:
        meta = json.loads(stored['metadata'].tobytes())
    for key in ('status', 'base_rng', 'extra_rng', 'next_n'):
        origin[key] = meta[key]
    origin['config']['cache_mib'] = 4096
    origin['config']['accelerator'] = accelerator_identity(HERE, 'gpu', True, args)
    mature = root/'mature'
    (mature/'data').mkdir(parents=True)
    atomic(mature/'data/CHECKPOINT.json', origin)
    run(command(mature, end, original['config']['seed']), root/'mature.log')
    actual = load(mature/'data')
    for key in ('status', 'base_rng', 'extra_rng', 'next_n', 'fp', 'fn'):
        assert actual[key] == original[key], key
    mature_comparison = compare(production, mature, start)
    print(json.dumps(dict(phase='MATURE_PREFIX', **mature_comparison)), flush=True)

    observed_error = None
    if original['fp']==1 and original['fn']==0:
        # Replay the first observed raw false event, including its effect on
        # hidden state and subsequent RNG draws. Historical error is retained.
        first_error=json.loads(subprocess.check_output(['grep','-m','1','-E',
            '"fp": [1-9]|"fn": [1-9]',str(production/'data/TIMINGS.jsonl')],text=True))
        error_step=first_error['step'];error_start=max(4,error_step-32);error_end=min(end,error_step+168)
        error_origin=copy.deepcopy(original);error_origin.pop('_journal',None)
        error_origin['records']=error_origin['records'][:error_start]
        with np.load(error_origin['records'][-1]['path'],allow_pickle=False) as stored:
            before_error=json.loads(stored['metadata'].tobytes())
        for key in ('status','base_rng','extra_rng','next_n'):error_origin[key]=before_error[key]
        error_origin.update(fp=0,fn=0)
        error_origin['config']['cache_mib']=4096
        error_origin['config']['accelerator']=accelerator_identity(HERE,'gpu',True,args)
        replay=root/'observed-error';(replay/'data').mkdir(parents=True)
        atomic(replay/'data/CHECKPOINT.json',error_origin)
        run(command(replay,error_end,original['config']['seed']),root/'observed-error.log')
        actual_error=load(replay/'data');assert actual_error['fp']==1 and actual_error['fn']==0
        with np.load(original['records'][error_end-1]['path'],allow_pickle=False) as stored:
            expected_error=json.loads(stored['metadata'].tobytes())
        for key in ('status','base_rng','extra_rng','next_n'):assert actual_error[key]==expected_error[key],key
        observed_error=compare(production,replay,error_start,error_end)
        with np.load(original['records'][error_step]['path'],allow_pickle=False) as stored:
            original_errors=json.loads(stored['metadata'].tobytes())['errors']
        observed_error.update(original_errors=original_errors,fp=1,fn=0)
        print(json.dumps(dict(phase='OBSERVED_ERROR',**observed_error)),flush=True)

    fault, control = root/'interrupted', root/'cpu-control'
    with (root/'interrupted.log').open('w') as log:
        proc = subprocess.Popen(command(fault, 200), env=env, stdout=log,
                                stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic()+180
            while True:
                if proc.poll() is not None:
                    raise RuntimeError('Pilot exited before interruption')
                head = fault/'data/HEAD.json'
                if head.exists() and json.loads(head.read_bytes())['sequence'] >= 80:
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError('No durable group commit')
                time.sleep(0.02)
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
    count = len(load(fault/'data')['records'])
    (fault/'data'/f'chunk_{count+3:05d}.npz').write_bytes(b'uncommitted orphan')
    run(command(fault, 200), root/'resumed.log')
    run(command(control, 200, backend='cpu'), root/'cpu-control.log')
    recovery = compare(control, fault)
    assert json.loads((fault/'PILOT.json').read_text())['orphan_quarantined'] >= 1
    assert (production/'data/STOP').exists()
    assert hashlib.sha256((production/'data/CHECKPOINT.json').read_bytes()).hexdigest() == original_sha
    report = dict(status='PASS', source_files=accelerator_identity(HERE, 'gpu', True, args)['files'],
                  accelerator=accelerator_identity(HERE, 'gpu', True, args),
                  production_checkpoint_sha256=original_sha, production_checkpoint_unchanged=True,
                  observed_error=observed_error,
                  frozen_prefix=frozen, mature_prefix=mature_comparison, recovery=recovery,
                  durable_chunks_at_kill=count, orphan_quarantined=True,
                  observed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    atomic(root/'INTEGRATION_QUALIFICATION.json', report)
    print(json.dumps(report), flush=True)

if __name__ == '__main__':
    main()
