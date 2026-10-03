"""Verify archive transport hash and every member without extracting files."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

def require(condition,message):
    if not condition:raise ValueError(message)

def verify(path,expected):
    if path.stat().st_size!=expected['bytes']:raise ValueError('Archive size mismatch')
    with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    if digest!=expected['sha256']:raise ValueError('Archive SHA-256 mismatch')
    proc=subprocess.Popen(['zstd','-q','-d','-c',str(path)],stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:
            members=iter(tar);first=next(members);require(first.name=='MANIFEST.json' and first.isfile() and first.size<512*1024**2,'Invalid manifest member')
            raw=tar.extractfile(first).read();require(hashlib.sha256(raw).hexdigest()==expected['manifest_sha256'],'Manifest checksum mismatch')
            manifest=json.loads(raw);entries={e['name']:e for e in manifest['entries']}
            require(len(entries)==len(manifest['entries']),'Duplicate manifest names');seen=set()
            for member in members:
                require(member.isfile() and member.name in entries and member.name not in seen,'Unexpected archive member')
                entry=entries[member.name];require(member.size==entry['size'],'Member size mismatch');h=hashlib.sha256()
                with tar.extractfile(member) as f:
                    while block:=f.read(1024*1024):h.update(block)
                require(h.hexdigest()==entry['sha256'],'Member checksum mismatch: '+member.name);seen.add(member.name)
            require(seen==set(entries),'Missing archive members')
        # Drain any valid tar end padding so decompressor termination is checked.
        while proc.stdout.read(1024*1024):pass
        require(proc.wait()==0,'Decompression failed')
    except BaseException:proc.kill();proc.wait();raise
    finally:proc.stdout.close()
    return dict(status='VERIFIED',verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        batch_id=expected['batch_id'],sha256=digest,bytes=path.stat().st_size,
        manifest_sha256=expected['manifest_sha256'],members_verified=len(seen),
        destination=str(path.resolve()),through_decisions=manifest['through_decisions'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);p.add_argument('expected',type=Path);a=p.parse_args()
    print(json.dumps(verify(a.archive,json.loads(a.expected.read_text())),indent=2))
