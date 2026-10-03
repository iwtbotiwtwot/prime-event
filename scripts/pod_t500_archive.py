"""100 GiB trigger: compress on pod, download, verify on T500, acknowledge cleanup."""
import argparse
import fcntl
import hashlib
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
T500_HOST=os.environ.get('PRIME_EVENT_T500_HOST','lilhelper@10.77.0.2')
T500_ROOT=Path(os.environ.get('PRIME_EVENT_T500_ROOT','/home/lilhelper/SAM_Research_Project'))
T500_SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','StrictHostKeyChecking=yes',
          '-i',os.environ.get('PRIME_EVENT_T500_IDENTITY',str(Path.home()/'.ssh/id_ed25519'))]
VERIFY_WORKER='''import hashlib,json
from pathlib import Path
import sys
job=json.load(sys.stdin)
scope={'__name__':'storage_host_verifier'}
exec(job['source'],scope)
receipt=scope['verify'](Path(job['path']),job['expected'])
receipt.update(destination=job['destination'],verification_host=job['host'],
               verification_source_sha256=hashlib.sha256(job['source'].encode()).hexdigest())
print(json.dumps(receipt))
'''

def storage_path(path):
    # Match the mounted filesystem to the SSH destination before moving a
    # verification read off the workstation. Never infer a different host.
    raw=subprocess.check_output(['findmnt','-rn','-o','FSTYPE,SOURCE','-T',str(MOUNT)],text=True)
    mounts={tuple(line.split(maxsplit=1)) for line in raw.splitlines() if line.strip()}
    if mounts!={('fuse.sshfs',T500_HOST+':'+str(T500_ROOT))}:
        raise RuntimeError('T500 mount does not match its configured verification host and path')
    return T500_ROOT/path.resolve().relative_to(MOUNT.resolve())

def verify_on_storage_host(path,expected):
    # Execute exactly the repository verifier, including the transport hash,
    # manifest, every member checksum and decompressor exit. Only JSON returns
    # over SSH; both reads of the large archive stay on its storage machine.
    source=Path(__file__).with_name('verify_pod_archive.py').read_text()
    job=dict(source=source,path=str(storage_path(path)),expected=expected,
             destination=str(path.resolve()),host=T500_HOST)
    command=T500_SSH+[T500_HOST,shlex.join(['python3','-c',VERIFY_WORKER])]
    receipt=json.loads(subprocess.check_output(command,input=json.dumps(job).encode(),timeout=43200))
    if receipt.get('status')!='VERIFIED' or receipt.get('members_verified',0)<=0:
        raise ValueError('Storage host did not return a complete verification receipt')
    for key in ['batch_id','sha256','manifest_sha256','bytes','through_decisions']:
        if receipt.get(key)!=expected[key]:raise ValueError('Storage verification receipt mismatch: '+key)
    if receipt.get('verification_source_sha256')!=hashlib.sha256(source.encode()).hexdigest():
        raise ValueError('Storage host verifier identity mismatch')
    return receipt

def remote(action,root,mirror,threshold,receipt=None):
    command=['python',HELPER,action,'--root',root,'--mirror',mirror,'--threshold',str(threshold)]
    raw=subprocess.check_output(SSH+[HOST,shlex.join(command)],input=json.dumps(receipt).encode() if receipt else None,timeout=43200)
    return json.loads(raw)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--remote-root',default='/root/prime-u5-production');p.add_argument('--remote-mirror',default='/root/prime-u5-backup');p.add_argument('--destination',type=Path,default=DEFAULT)
    p.add_argument('--threshold',type=int,default=100*1024**3)
    p.add_argument('--verify-locally',action='store_true',help='Read the archive through the mounted T500 for verification')
    a=p.parse_args();verifier=verify if a.verify_locally else verify_on_storage_host
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
        if partial.exists() and partial.stat().st_size>batch['bytes']:
            raise ValueError('Partial archive is larger than its expected size; inspect before retry')
        phase=dict(status='COPYING',batch_id=batch['batch_id'],archive=str(final),
                   source_root=a.remote_root,bytes=batch['bytes'])
        atomic(state/'archive-status.json',(json.dumps(phase,indent=2)+'\n').encode())
        # A complete partial still needs every verification check, but avoids
        # repeating the network transfer after an interrupted verification.
        if not partial.exists() or partial.stat().st_size!=batch['bytes']:
            subprocess.run(['rsync','--partial','--append-verify','-e',shlex.join(SSH),HOST+':'+batch['path'],str(partial)],check=True,timeout=43200)
        phase.update(status='VERIFYING',verification_host='workstation' if a.verify_locally else T500_HOST)
        atomic(state/'archive-status.json',(json.dumps(phase,indent=2)+'\n').encode())
        receipt=verifier(partial,batch)
        with partial.open('rb') as f:os.fsync(f.fileno())
        os.replace(partial,final);receipt['destination']=str(final)
    else:receipt=verifier(final,batch)
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
