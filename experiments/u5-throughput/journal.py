"""Bounded group commits with an authenticated append-only checkpoint journal.

HEAD publishes only fsynced data and journal bytes. Full CHECKPOINT snapshots are
an acceleration for recovery, not the live commit marker. Readers take one HEAD
and replay exactly through its byte offset. Unpublished tails are ignored.
"""
import hashlib
import json
import os
from pathlib import Path
import time

ZERO='0'*64
def encoded(obj):return (json.dumps(obj,sort_keys=True,separators=(',',':'))+'\n').encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def atomic(path,obj):
    tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('wb') as f:f.write(encoded(obj));f.flush();os.fsync(f.fileno())
    os.replace(tmp,path);syncdir(path.parent)
def syncdir(path):
    fd=os.open(path,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
def load(root):
    root=Path(root)
    # Snapshot publication follows HEAD publication. Read snapshot first so a
    # concurrent snapshot replacement cannot put the snapshot ahead of our HEAD.
    cp=json.loads((root/'CHECKPOINT.json').read_bytes())
    if not (root/'HEAD.json').exists():return cp
    head=json.loads((root/'HEAD.json').read_bytes())
    position=cp.get('_journal',dict(offset=0,sha256=ZERO,sequence=len(cp['records'])))
    if position['offset']>head['offset']:raise ValueError('Checkpoint ahead of durable head')
    with (root/'COMMITS.jsonl').open('rb') as f:
        f.seek(position['offset'])
        while f.tell()<head['offset']:
            raw=f.readline(head['offset']-f.tell());entry=json.loads(raw)
            if entry['previous_sha256']!=position['sha256'] or entry['start']!=len(cp['records']):
                raise ValueError('Commit journal chain/sequence mismatch')
            cp['records'].extend(entry['records']);cp.update(entry['state'])
            position=dict(offset=f.tell(),sha256=sha(raw),sequence=len(cp['records']))
    if position!=head:raise ValueError('Commit journal does not match durable head')
    if cp['next_n']!=2+len(cp['records'])*5_000_000:raise ValueError('Commit boundary mismatch')
    cp['_journal']=head
    return cp

class Writer:
    def __init__(self,root,cp,progress=None,milestone_steps=0,milestone=None):
        self.root=Path(root);self.cp=cp;self.progress=progress
        self.milestone_steps=milestone_steps;self.milestone=milestone
        self.position=cp.get('_journal',dict(offset=0,sha256=ZERO,sequence=len(cp['records'])))
        self.pending=[];self.bytes=0;self.last=time.monotonic();self.snapshot_sequence=len(cp['records'])
        path=self.root/'COMMITS.jsonl'
        with path.open('ab'):pass
        with path.open('r+b') as f:f.truncate(self.position['offset']);f.flush();os.fsync(f.fileno())
        atomic(self.root/'HEAD.json',self.position)
    def add(self,record,blob,state):
        self.pending.append((dict(record),blob,state));self.bytes+=len(blob)
        # Keep early feedback dependencies durable; later at most 20 pending
        # chunks cannot return before the current preparation window ends.
        sequence=len(self.cp['records'])+len(self.pending)
        boundary=self.milestone_steps and sequence%self.milestone_steps==0
        if boundary or sequence<64 or len(self.pending)>=20 or self.bytes>=128*1024**2 or time.monotonic()-self.last>=1:
            self.flush()
    def flush(self):
        if not self.pending:return
        for record,blob,_ in self.pending:
            path=Path(record['path']);tmp=path.with_suffix('.npz.tmp')
            with tmp.open('wb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
            os.replace(tmp,path)
        syncdir(self.root)
        records=[x[0] for x in self.pending];state=self.pending[-1][2]
        raw=encoded(dict(previous_sha256=self.position['sha256'],start=len(self.cp['records']),records=records,state=state))
        with (self.root/'COMMITS.jsonl').open('ab') as f:
            f.write(raw);f.flush();os.fsync(f.fileno());offset=f.tell()
        self.position=dict(offset=offset,sha256=sha(raw),sequence=len(self.cp['records'])+len(records))
        atomic(self.root/'HEAD.json',self.position)
        self.cp['records'].extend(records);self.cp.update(state);self.cp['_journal']=self.position
        self.pending=[];self.bytes=0;self.last=time.monotonic()
        if self.progress:self.progress(self.cp)
        if self.milestone_steps and len(self.cp['records'])%self.milestone_steps==0:
            self.snapshot()
            if self.milestone:self.milestone(self.cp)
        elif len(self.cp['records'])-self.snapshot_sequence>=1000:self.snapshot()
    def snapshot(self):
        self.flush();atomic(self.root/'CHECKPOINT.json',self.cp);self.snapshot_sequence=len(self.cp['records'])
