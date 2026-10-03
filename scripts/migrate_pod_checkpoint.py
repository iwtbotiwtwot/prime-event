"""Explicitly pin a stopped checkpoint to the qualified throughput implementation."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import time

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--code',type=Path,required=True)
    a=p.parse_args();data=a.root/'data'
    lock=(data/'WRITER.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    spec=importlib.util.spec_from_file_location('migration_journal',a.code/'journal.py')
    j=importlib.util.module_from_spec(spec);spec.loader.exec_module(j)
    cp=j.load(data);old=json.loads(json.dumps(cp))
    names=['accelerator.cpp','accelerator.cu','accelerated.py','pilot.py','pipeline.py','native_history.cpp','native_history.py','journal.py']
    identity={name:hashlib.sha256((a.code/name).read_bytes()).hexdigest() for name in names}
    if cp['config']['accelerator']['files']==identity:raise RuntimeError('Already migrated')
    # Only scheduling/storage may change. Frozen scientific tables and kernels
    # stay pinned in config; replay qualification is retained separately.
    cp['config']['accelerator']['files']=identity
    stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
    j.atomic(a.root/f'CHECKPOINT_BEFORE_{stamp}.json',old)
    j.atomic(a.root/f'MIGRATION_{stamp}.json',dict(utc=stamp,decisions=cp['next_n']-2,
        previous_config=old['config'],new_config=cp['config'],qualification_required=True))
    j.atomic(data/'CHECKPOINT.json',cp)
    print(json.dumps(dict(status='MIGRATED',decisions=cp['next_n']-2,fp=cp['fp'],fn=cp['fn'],files=identity)))
if __name__=='__main__':main()
