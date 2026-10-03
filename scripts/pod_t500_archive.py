"""100 GiB trigger: compress on pod, download, verify on T500, acknowledge cleanup."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
from pod_t500_backup import MOUNT,DEFAULT,SSH,HOST,atomic
from verify_pod_archive import verify

HELPER='/tmp/prime-u5-throughput/scripts/pod_archive.py'
def remote(action,root,mirror,threshold,receipt=None):
    command=['python',HELPER,action,'--root',root,'--mirror',mirror,'--threshold',str(threshold)]
    raw=subprocess.check_output(SSH+[HOST,shlex.join(command)],input=json.dumps(receipt).encode() if receipt else None,timeout=43200)
    return json.loads(raw)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--remote-root',default='/root/prime-u5-production');p.add_argument('--remote-mirror',default='/root/prime-u5-backup');p.add_argument('--destination',type=Path,default=DEFAULT)
    p.add_argument('--threshold',type=int,default=100*1024**3);a=p.parse_args()
    lock=open(Path(tempfile.gettempdir())/'prime-event-t500-backup.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if not os.path.ismount(MOUNT):raise RuntimeError('T500 is not mounted; no fallback destination allowed')
    dest=a.destination.resolve();dest.relative_to(MOUNT.resolve());folder=dest/'archives';folder.mkdir(parents=True,exist_ok=True)
    state=Path.home()/'.local/state/prime-event-pod';state.mkdir(parents=True,exist_ok=True)
    batch=remote('prepare',a.remote_root,a.remote_mirror,a.threshold)
    if batch['status']=='WAITING':
        batch.update(source_root=a.remote_root,destination=str(folder))
        atomic(state/'archive-status.json',(json.dumps(batch,indent=2)+'\n').encode());print(json.dumps(batch));return
    name=Path(batch['path']).name;assert name.startswith('u5_seed') and name.endswith('.tar.zst')
    final=folder/name;partial=folder/(name+'.partial');sidecar=folder/(name+'.expected.json');receiptpath=folder/(name+'.verified.json')
    atomic(sidecar,(json.dumps(batch,indent=2)+'\n').encode())
    if not final.exists():
        needed=batch['bytes']-(partial.stat().st_size if partial.exists() else 0)
        if shutil.disk_usage(MOUNT).free<needed+20*1024**3:raise RuntimeError('T500 cannot receive archive while preserving 20 GiB reserve')
        subprocess.run(['rsync','--partial','--append-verify','-e',shlex.join(SSH),HOST+':'+batch['path'],str(partial)],check=True,timeout=43200)
        receipt=verify(partial,batch)
        with partial.open('rb') as f:os.fsync(f.fileno())
        os.replace(partial,final);receipt['destination']=str(final)
    else:receipt=verify(final,batch)
    atomic(receiptpath,(json.dumps(receipt,indent=2)+'\n').encode())
    fd=os.open(folder,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    # Only a verified, durable T500 copy can authorize container cleanup.
    cleaned=remote('ack',a.remote_root,a.remote_mirror,a.threshold,receipt)
    result=dict(status='VERIFIED_AND_CLEANED',source_root=a.remote_root,archive=str(final),receipt=receipt,container=cleaned,drive_action='User uploads, verifies, then removes the T500 archive. Keep sidecar receipts.')
    atomic(state/'archive-status.json',(json.dumps(result,indent=2)+'\n').encode())
    atomic(folder/(name+'.cleanup.json'),(json.dumps(cleaned,indent=2)+'\n').encode())
    if shutil.which('notify-send'):subprocess.run(['notify-send','Prime-event archive ready',f"Batch {batch['batch_id']}: verified on T500; ready for your Drive upload."],check=False)
    print(json.dumps(result))
if __name__=='__main__':main()
