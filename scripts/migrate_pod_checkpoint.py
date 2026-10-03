"""Pin a paused checkpoint to a qualified runtime without changing its science."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--code', type=Path, required=True)
    p.add_argument('--cache-mib', type=int)
    p.add_argument('--qualification', type=Path)
    preliminary, _ = p.parse_known_args()
    sys.path.insert(0, str(preliminary.code.resolve()))
    from runtime_config import add_gpu_arguments, validate_gpu_arguments, accelerator_identity, gpu_options
    add_gpu_arguments(p)
    a = p.parse_args()
    validate_gpu_arguments(p, a)
    if a.cache_mib is not None and a.cache_mib < 1:
        p.error('cache size must be positive')
    data = a.root/'data'
    if not (data/'STOP').exists():
        raise RuntimeError('A STOP marker is required before migration')
    campaign_lock = (a.root/'CAMPAIGN.lock').open('a')
    fcntl.flock(campaign_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    writer_lock = (data/'WRITER.lock').open('a')
    fcntl.flock(writer_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    spec = importlib.util.spec_from_file_location('migration_journal', a.code/'journal.py')
    j = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(j)
    cp = j.load(data)
    old = json.loads(json.dumps(cp))
    accelerator = cp['config']['accelerator']
    identity = accelerator_identity(a.code, accelerator['backend'], accelerator['pipeline'], a)
    qualification = None
    if a.qualification:
        qualification = json.loads(a.qualification.read_text())
        if (qualification['status'] != 'PASS' or qualification['source_files'] != identity['files']
                or qualification.get('accelerator') != identity):
            raise ValueError('Qualification does not match the target runtime')
    elif a.history_gpu is not None or a.grade_gpu is not None:
        raise ValueError('GPU roles require a matching replay qualification receipt')
    cp['config']['accelerator'] = identity
    if a.cache_mib is not None:
        cp['config']['cache_mib'] = a.cache_mib
    if cp['config'] == old['config']:
        raise RuntimeError('Already migrated')
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    j.atomic(a.root/f'CHECKPOINT_BEFORE_{stamp}.json', old)
    record = dict(utc=stamp, decisions=cp['next_n']-2, previous_config=old['config'],
                  new_config=cp['config'], qualification=qualification,
                  qualification_sha256=hashlib.sha256(a.qualification.read_bytes()).hexdigest()
                  if a.qualification else None)
    j.atomic(a.root/f'MIGRATION_{stamp}.json', record)
    j.atomic(data/'CHECKPOINT.json', cp)
    if j.load(data) != cp or {k:v for k,v in cp.items() if k != 'config'} != {k:v for k,v in old.items() if k != 'config'}:
        raise AssertionError('Migration changed scientific state or journal recovery')
    state_path = a.root/'CAMPAIGN.json'
    if state_path.exists():
        state = json.loads(state_path.read_text())
        j.atomic(a.root/f'CAMPAIGN_BEFORE_{stamp}.json', state)
        state['previous_scheduling_config'] = state['config']
        state['config'] = dict(state['config'], cache_mib=cp['config']['cache_mib'], **gpu_options(a))
        j.atomic(state_path, state)
    print(json.dumps(dict(status='MIGRATED', decisions=cp['next_n']-2,
                          fp=cp['fp'], fn=cp['fn'], accelerator=identity)))
if __name__=='__main__':main()
