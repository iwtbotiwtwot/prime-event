"""Pod-side 100 GiB archive rotation. Never delete active feedback history."""
import argparse
import datetime
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

GIB=1024**3
def sha(raw):return hashlib.sha256(raw).hexdigest()
def file_sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def atomic(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('wb') as f:f.write(json.dumps(obj,sort_keys=True).encode()+b'\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
class CheckedReader:
    def __init__(self,path):self.file=path.open('rb');self.hash=hashlib.sha256()
    def read(self,n=-1):
        raw=self.file.read(n);self.hash.update(raw);return raw
    def close(self):self.file.close()

def prepare(root,mirror,threshold):
    state=root/'archive_state';state.mkdir(exist_ok=True)
    indexpath=state/'INDEX.json';index=json.loads(indexpath.read_text()) if indexpath.exists() else dict(next_chunk=0,batches=[])
    if index['batches'] and index['batches'][-1]['status']!='CLEANED':return index['batches'][-1]
    batch_id=len(index['batches'])+1
    saved_manifest=state/f'MANIFEST_{batch_id:06d}.json'
    # Recover a completed atomic rename if the process exited before indexing.
    if saved_manifest.exists():
        old=json.loads(saved_manifest.read_text());candidate=mirror/'archives'/f'u5_seed{old["seed"]}_batch_{batch_id:06d}.tar.zst'
        if candidate.exists():
            if old['first_chunk']!=index['next_chunk']:raise RuntimeError('Archive recovery cursor mismatch')
            batch=dict(status='PREPARED',batch_id=batch_id,path=str(candidate),bytes=candidate.stat().st_size,
                sha256=file_sha(candidate),manifest_sha256=sha(saved_manifest.read_bytes()),
                first_chunk=old['first_chunk'],end_chunk=old['end_chunk'],journal_bytes=old['journal_bytes'],through_decisions=old['through_decisions'])
            index['batches'].append(batch);atomic(indexpath,index);return batch
    if (root/'data/HEAD.json').exists():
        import importlib.util
        spec=importlib.util.spec_from_file_location('pod_commit_journal',root/'source/journal.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        cp=module.load(root/'data')
        # Archives contain a standalone full snapshot, not a dependency on the
        # running append-only log. Restore starts a new journal at this snapshot.
        cp.pop('_journal',None)
        cpraw=json.dumps(cp,sort_keys=True).encode()+b'\n'
    else:
        cpraw=(root/'data/CHECKPOINT.json').read_bytes();cp=json.loads(cpraw)
    first=index['next_chunk'];records=cp['records'][first:]
    sources=[];total=0
    for i,rec in enumerate(records,first):
        path=Path(rec['path']);assert path==root/'data'/f'chunk_{i:05d}.npz' and not path.is_symlink()
        size=path.stat().st_size;total+=size;sources.append((f'data/{path.name}',path,size,rec['sha256']))
    if total<threshold:return dict(status='WAITING',unarchived_journal_bytes=total,threshold_bytes=threshold,next_chunk=first)
    # Existing NPZ journals are already compressed. Limit compression CPU use.
    needed=total+len(sources)*1024+64*1024**2+20*GIB
    if shutil.disk_usage(root).free<needed:raise RuntimeError('Insufficient container space for archive plus 20 GiB reserve')
    folder=mirror/'archives';folder.mkdir(parents=True,exist_ok=True)
    target=folder/f'u5_seed{cp["config"]["seed"]}_batch_{batch_id:06d}.tar.zst'
    if target.exists():raise RuntimeError('Unindexed archive exists; inspect before retry: '+str(target))
    extra={'snapshot/CHECKPOINT.json':cpraw}
    for name in ['CAMPAIGN.json','REPORTS.json','BACKUP.json']:
        if (root/name).exists():extra['snapshot/'+name]=(root/name).read_bytes()
    for file in sorted((root/'source').iterdir()):
        if file.is_file() and file.suffix in ['.py','.cpp','.cu','.npy','.json']:extra['source/'+file.name]=file.read_bytes()
    config=cp['config'];pinned=dict(config.get('accelerator',{}).get('files',{}))
    for name,key in [('u5_cdf.npy','cdf_sha256'),('u5_initial.npy','initial_sha256'),('reference.cpp','kernel_sha256'),('index.cpp','index_sha256')]:
        if key in config:pinned[name]=config[key]
    for name,digest in pinned.items():
        if 'source/'+name not in extra or sha(extra['source/'+name])!=digest:
            raise RuntimeError('Source changed during snapshot or failed its checkpoint hash: '+name)
    entries=[dict(name=name,size=size,sha256=digest) for name,_,size,digest in sources]
    entries += [dict(name=name,size=len(raw),sha256=sha(raw)) for name,raw in extra.items()]
    manifest=dict(format=1,batch_id=batch_id,seed=cp['config']['seed'],created_utc=now(),
        first_chunk=first,end_chunk=len(cp['records']),through_decisions=cp['next_n']-2,
        journal_bytes=total,threshold_bytes=threshold,checkpoint_sha256=sha(cpraw),entries=entries,
        scope='Incremental journals plus checkpoint; restore all preceding batches as well. Active feedback history is retained on the pod.')
    manifest_raw=json.dumps(manifest,sort_keys=True).encode()+b'\n';temporary=target.with_suffix('.partial')
    atomic(saved_manifest,manifest)
    with temporary.open('wb') as output:
        proc=subprocess.Popen(['zstd','-q','-T2','-3','-c'],stdin=subprocess.PIPE,stdout=output)
        try:
            with tarfile.open(fileobj=proc.stdin,mode='w|') as tar:
                def add_bytes(name,raw):
                    info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o644;tar.addfile(info,io.BytesIO(raw))
                add_bytes('MANIFEST.json',manifest_raw)
                for name,path,size,digest in sources:
                    reader=CheckedReader(path)
                    try:
                        info=tarfile.TarInfo(name);info.size=size;info.mode=0o644;tar.addfile(info,reader)
                        if reader.hash.hexdigest()!=digest:raise RuntimeError('Source journal checksum mismatch: '+name)
                    finally:reader.close()
                for name,raw in extra.items():add_bytes(name,raw)
            proc.stdin.close()
            if proc.wait()!=0:raise RuntimeError('zstd compression failed')
            output.flush();os.fsync(output.fileno())
        except BaseException:
            proc.kill();proc.wait();raise
    os.replace(temporary,target)
    batch=dict(status='PREPARED',batch_id=batch_id,path=str(target),bytes=target.stat().st_size,
        sha256=file_sha(target),manifest_sha256=sha(manifest_raw),first_chunk=first,
        end_chunk=len(cp['records']),journal_bytes=total,through_decisions=cp['next_n']-2)
    atomic(state/f'MANIFEST_{batch_id:06d}.json',manifest);index['batches'].append(batch);atomic(indexpath,index)
    return batch

def acknowledge(root,mirror,receipt):
    state=root/'archive_state';indexpath=state/'INDEX.json';index=json.loads(indexpath.read_text());batch=index['batches'][-1]
    if receipt['status']!='VERIFIED':raise RuntimeError('A verified T500 receipt is required')
    for key in ['batch_id','sha256','manifest_sha256','bytes']:
        if receipt[key]!=batch[key]:raise ValueError('Verification receipt mismatch: '+key)
    manifest=json.loads((state/f'MANIFEST_{batch["batch_id"]:06d}.json').read_text())
    if receipt['members_verified']!=len(manifest['entries']):raise ValueError('Incomplete archive verification')
    if batch['status']=='CLEANED':return batch
    archive=Path(batch['path'])
    if archive.parent!=mirror/'archives':raise ValueError('Unexpected archive path')
    if archive.exists() and file_sha(archive)!=batch['sha256']:raise ValueError('Container archive changed')
    batch.update(status='VERIFIED_ON_T500',verified_utc=receipt['verified_utc'],destination=receipt['destination'])
    atomic(state/f'T500_RECEIPT_{batch["batch_id"]:06d}.json',receipt);atomic(indexpath,index)
    removed=0
    for entry in manifest['entries']:
        if not entry['name'].startswith('data/'):continue
        # Delete only redundant mirror copies. The running trajectory's files
        # under root/data are dependencies and MUST NOT be removed.
        path=mirror/entry['name']
        if path.parent!=mirror/'data' or path==root/entry['name']:raise ValueError('Refusing active-history deletion')
        if path.exists():
            if path.is_symlink() or path.resolve()!=path or path.resolve().is_relative_to(root) or file_sha(path)!=entry['sha256']:
                raise RuntimeError('Refusing to remove an unexpected backup file: '+str(path))
            path.unlink();removed+=1
    archive.unlink(missing_ok=True)
    batch.update(status='CLEANED',removed_redundant_chunks=removed,active_history_retained=True,cleaned_utc=now())
    index['next_chunk']=batch['end_chunk'];atomic(indexpath,index);return batch

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','ack']);p.add_argument('--root',type=Path,required=True);p.add_argument('--mirror',type=Path,required=True)
    p.add_argument('--threshold',type=int,default=100*GIB);a=p.parse_args();root=a.root.resolve();mirror=a.mirror.resolve()
    if root==mirror or root in mirror.parents or mirror in root.parents:p.error('Active root and mirror must be separate directories')
    lock=(root/'ARCHIVE.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if a.threshold<1:p.error('Positive threshold required')
    result=prepare(root,mirror,a.threshold) if a.action=='prepare' else acknowledge(root,mirror,json.load(__import__('sys').stdin))
    print(json.dumps(result))
if __name__=='__main__':main()
