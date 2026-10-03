"""Pull a committed pod snapshot to the mounted T500, verifying new chunks."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile

MOUNT=Path('/home/sam/mnt/lilhelper-t500')
DEFAULT=MOUNT/'POD_BACKUPS/prime-event/u5_seed9370001_20261003'
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','StrictHostKeyChecking=yes',
     '-p',os.environ.get('PRIME_EVENT_POD_PORT','12771'),
     '-i',os.environ.get('PRIME_EVENT_POD_IDENTITY',str(Path.home()/'.ssh/id_ed25519_runpod'))]
HOST=os.environ.get('PRIME_EVENT_POD_HOST','root@216.81.151.70')
def atomic(path,blob):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('wb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--remote-root',default='/root/prime-u5-production');p.add_argument('--destination',type=Path,default=DEFAULT);a=p.parse_args()
    lock=open(Path(tempfile.gettempdir())/'prime-event-t500-backup.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if not os.path.ismount(MOUNT):raise RuntimeError('T500 is not mounted; refusing a fallback copy to workstation disk')
    destination=a.destination.resolve();destination.relative_to(MOUNT.resolve())
    if shutil.disk_usage(MOUNT).free<20*1024**3:raise RuntimeError('T500 has less than the 20 GiB backup reserve')
    command='cat '+shlex.quote(a.remote_root+'/data/CHECKPOINT.json')
    raw=subprocess.check_output(SSH+[HOST,command],timeout=60);cp=json.loads(raw)
    destination.mkdir(parents=True,exist_ok=True);(destination/'data').mkdir(exist_ok=True)
    receipt_path=destination/'VERIFIED.json';previous=json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    count=int(previous.get('chunks',0));assert count<=len(cp['records'])
    if previous:assert previous['seed']==cp['config']['seed'] and previous['config']==cp['config']
    names=[]
    for r in cp['records']:
        path=Path(r['path']);assert str(path.parent)==a.remote_root+'/data' and re.fullmatch(r'chunk_\d+\.npz',path.name)
        names.append(path.name)
    with tempfile.NamedTemporaryFile('w',delete=False) as listing:
        listing.write('\n'.join(names)+'\n');files=listing.name
    try:
        subprocess.run(['rsync','-r','--ignore-existing','--files-from='+files,'-e',shlex.join(SSH),HOST+':'+a.remote_root+'/data/',str(destination/'data')+'/'],check=True,timeout=3300)
        subprocess.run(['rsync','-r','--ignore-existing','-e',shlex.join(SSH),HOST+':'+a.remote_root+'/source/',str(destination/'source')+'/'],check=True,timeout=300)
    finally:os.unlink(files)
    for r in cp['records'][count:]:
        file=destination/'data'/Path(r['path']).name
        with file.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        if digest!=r['sha256']:
            os.replace(file,file.with_suffix('.corrupt-'+datetime.datetime.now().strftime('%Y%m%dT%H%M%S')))
            raise RuntimeError('Backup checksum mismatch: '+file.name)
    atomic(destination/'data/CHECKPOINT.json',raw)
    receipt=dict(status='VERIFIED',verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        seed=cp['config']['seed'],config=cp['config'],chunks=len(cp['records']),decisions=cp['next_n']-2,
        fp=cp['fp'],fn=cp['fn'],checkpoint_sha256=hashlib.sha256(raw).hexdigest(),
        destination=str(destination),source_root=a.remote_root,new_chunks_verified=len(cp['records'])-count,
        restore_note='Restore source and journal files to the original pod root before resuming; checkpoint paths are absolute.')
    atomic(receipt_path,(json.dumps(receipt,indent=2)+'\n').encode())
    state=Path.home()/'.local/state/prime-event-pod';state.mkdir(parents=True,exist_ok=True)
    atomic(state/'t500-backup.json',(json.dumps(receipt,indent=2)+'\n').encode())
    print(json.dumps(receipt))
if __name__=='__main__':main()
