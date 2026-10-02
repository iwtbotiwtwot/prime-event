"""Bounded raw source runner with actual-history quotient chunk index."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse,json,hashlib,io,zipfile,time,ctypes,math,signal,shutil,fcntl
from pathlib import Path
from collections import OrderedDict,defaultdict
import numpy as np
np.core.multiarray._set_madvise_hugepage(False)
from random_buffers import RandomBuffers
P=Path(__file__).resolve().parent;W=5000000

def sha(b):return hashlib.sha256(b).hexdigest()
def digest(a):return sha(a.tobytes())
def atomic(path,obj):
 blob=obj if isinstance(obj,bytes) else (json.dumps(obj,sort_keys=True)+'\n').encode();tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('wb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path);fd=os.open(path.parent,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)
def pack(meta,events):
 gaps=np.diff(np.concatenate((np.array([meta['first']],np.uint64),events))).astype('<u4');out=io.BytesIO()
 with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
  for key,a in [('period_gaps',gaps),('metadata',np.frombuffer(json.dumps(meta,sort_keys=True).encode(),np.uint8))]:
   b=io.BytesIO();np.lib.format.write_array(b,a,allow_pickle=False);z.writestr(key+'.npy',b.getvalue())
 return out.getvalue()
def unpack(raw):
 with np.load(io.BytesIO(raw),allow_pickle=False) as z:m=json.loads(z['metadata'].tobytes());a=np.cumsum(z['period_gaps'],dtype=np.uint64)+np.uint64(m.get('first',m.get('first_n')))
 assert len(a)==m['period_count'] and digest(a)==m['period_sha256'];return m,a
class Kernels:
 def __init__(self):
  self.lib=ctypes.CDLL(str(P/'reference.so'));u=ctypes.c_uint64;v=ctypes.c_void_p;self.mark=self.lib.mark_periods;self.mark.argtypes=[u,u,v,u,u,v];self.mark.restype=ctypes.c_int;self.advance=self.lib.advance_segment;self.advance.argtypes=[u,u]+[v]*6+[u,v];self.advance.restype=ctypes.c_int;self.idxlib=ctypes.CDLL(str(P/'index.so'));self.index=self.idxlib.mark_ranges;self.index.argtypes=[u,u,v,u,u,v,u,v];self.index.restype=ctypes.c_int
class History:
 def __init__(self,records,limit,kernels):
  self.records=records;self.limit=limit;self.k=kernels;self.cache=OrderedDict();self.bytes=0;self.peak=0;self.hits=self.misses=self.evictions=self.read_bytes=0
 def get(self,j):
  if j in self.cache:self.hits+=1;a=self.cache.pop(j);self.cache[j]=a;return a
  self.misses+=1;r=self.records[j];raw=Path(r['path']).read_bytes();self.read_bytes+=len(raw);assert sha(raw)==r['sha256'];m,a=unpack(raw);assert len(a)==r['count'] and m.get('first',m.get('first_n'))==r['first']
  while self.cache and self.bytes+a.nbytes>self.limit:_,old=self.cache.popitem(last=False);self.bytes-=old.nbytes;self.evictions+=1
  if a.nbytes<=self.limit:self.cache[j]=a;self.bytes+=a.nbytes;self.peak=max(self.peak,self.bytes)
  return a
 def counters(self):return dict(hits=self.hits,misses=self.misses,evictions=self.evictions,read_bytes=self.read_bytes,cache_bytes=self.bytes,peak_bytes=self.peak)
 def banks(self,first):
  b=np.zeros(W,np.uint8)
  if not self.records:return b
  end=first+W-1;smallend=min(W,first-1)
  for j in range((smallend-2)//W+1):
   a=self.get(j);size=int(np.searchsorted(a,smallend,side='right'));assert self.k.mark(first,W,a.ctypes.data,size,self.records[j]['rank'],b.ctypes.data)==0
  plan=defaultdict(list)
  for q in range(2,end//(W+1)+1):
   lo=max(W+1,(first+q-1)//q);hi=min(first-1,end//q)
   if lo>hi:continue
   for j in range((lo-2)//W,(hi-2)//W+1):plan[j].append((q,max(lo,2+j*W),min(hi,1+(j+1)*W)))
  for j,ranges in sorted(plan.items()):
   a=self.get(j);arr=np.array(ranges,np.uint64);assert self.k.index(first,W,a.ctypes.data,len(a),self.records[j]['rank'],arr.ctypes.data,len(arr),b.ctypes.data)==0
  return b

def truth(first):
 end=first+W-1;lim=math.isqrt(end);small=np.ones(lim+1,bool);small[:2]=False
 for p in range(2,math.isqrt(lim)+1):
  if small[p]:small[p*p::p]=False
 out=np.ones(W,bool)
 for p in np.flatnonzero(small):
  p=int(p);n=max(p*p,((first+p-1)//p)*p)
  if n<=end:out[n-first::p]=False
 return out

def run(root,until,mode,cache_mib):
 assert np.__version__=='1.26.4';root.mkdir(parents=True,exist_ok=True);writer_lock=(root/'WRITER.lock').open('a');fcntl.flock(writer_lock,fcntl.LOCK_EX|fcntl.LOCK_NB);k=Kernels();draw_buffers=RandomBuffers(int(os.environ.get('PRIME_RNG_WORKERS','1')));bridge=None
 assert os.environ.get('PRIME_BACKEND','cpu')=='cpu'
 stop_requested=[]
 for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,lambda signum,frame:stop_requested.append(signum))
 cdf=np.load(P/'u5_cdf.npy');initial=np.load(P/'u5_initial.npy');config=dict(seed=int(os.environ.get('PRIME_SEED','9369001')),extra_seed=int(os.environ.get('PRIME_SEED','9369001'))+1000000,backend=os.environ.get('PRIME_BACKEND','cpu'),gpu_batch=int(os.environ.get('PRIME_GPU_BATCH','262144')),chunk=W,mode=mode,cache_mib=cache_mib,cdf_sha256=sha((P/'u5_cdf.npy').read_bytes()),initial_sha256=sha((P/'u5_initial.npy').read_bytes()),kernel_sha256=sha((P/'reference.cpp').read_bytes()),index_sha256=sha((P/'index.cpp').read_bytes()),numpy=np.__version__);base=np.random.default_rng(config['seed']);extra=np.random.default_rng(config['extra_seed']);cp_path=root/'CHECKPOINT.json';orphan_count=0
 restore_started=time.perf_counter()
 if cp_path.exists():
  cp=json.loads(cp_path.read_text());assert cp['config']==config;records=cp['records'];status=np.array(cp['status'],np.uint64);base.bit_generator.state=cp['base_rng'];extra.bit_generator.state=cp['extra_rng'];first=cp['next_n'];fp=cp['fp'];fn=cp['fn'];rank=0
  for j,r in enumerate(records):assert r['rank']==rank and r['first']==2+j*W;rank+=r['count']
  assert rank==int(status[1]) and first==2+len(records)*W
  if records:
   raw=Path(records[-1]['path']).read_bytes();assert sha(raw)==records[-1]['sha256'];m,a=unpack(raw);assert m['status']==cp['status'] and m['base_rng']==cp['base_rng'] and m['extra_rng']==cp['extra_rng']
  for p in root.glob('chunk_*.npz'):
   if int(p.stem.split('_')[1])>=len(records):
    q=root/'quarantine';q.mkdir(exist_ok=True);assert not (q/p.name).exists();os.replace(p,q/p.name);orphan_count+=1
 else:
  records=[];status=np.array([np.searchsorted(initial,base.random(),side='right'),0,1469598103934665603],np.uint64);first=2;fp=fn=0
  cp=dict(config=config,records=records,status=status.tolist(),base_rng=base.bit_generator.state,extra_rng=extra.bit_generator.state,next_n=first,fp=fp,fn=fn);atomic(cp_path,cp)
 history=History(records,cache_mib*1024**2,k);resident=np.empty(0,np.uint64)
 if mode=='resident' and records:resident=np.concatenate([history.get(j) for j in range(len(records))])
 restore_seconds=time.perf_counter()-restore_started;rows=[];startstep=len(records);begin=time.perf_counter()
 stop_reason='target'
 while len(records)<until:
  if stop_requested or (root/'STOP').exists():stop_reason='requested';break
  if time.perf_counter()-begin>=float(os.environ.get('PRIME_WALL_SECONDS','86400')):stop_reason='session_time_budget';break
  if shutil.disk_usage(root).free<20*1024**3:stop_reason='storage_reserve';break
  step=len(records);start=time.perf_counter();before=history.counters();t=time.perf_counter()
  if mode=='indexed':banks=history.banks(first)
  else:banks=np.zeros(W,np.uint8);assert k.mark(first,W,resident.ctypes.data,len(resident),0,banks.ctypes.data)==0
  bankseconds=time.perf_counter()-t;t=time.perf_counter();us,vs=draw_buffers.draw(base,extra,W);rngseconds=time.perf_counter()-t;t=time.perf_counter();emit=np.zeros(W,np.uint8);empty=np.empty(0,np.uint8);assert k.advance(first,W,cdf.ctypes.data,us.ctypes.data,vs.ctypes.data,banks.ctypes.data,emit.ctypes.data,empty.ctypes.data,0,status.ctypes.data)==0;transitionseconds=time.perf_counter()-t;t=time.perf_counter();events=np.flatnonzero(emit).astype(np.uint64)+first
  if mode=='resident':resident=np.concatenate((resident,events))
  ref=truth(first);wrong=np.flatnonzero(emit.astype(bool)!=ref);errors=[dict(n=int(first+i),kind='FN' if ref[i] else 'FP') for i in wrong];fpi=int(np.count_nonzero(emit&~ref));fni=int(np.count_nonzero((emit==0)&ref));fp+=fpi;fn+=fni;gradeseconds=time.perf_counter()-t;t=time.perf_counter();meta=dict(first=first,next_n=first+W,source=config['cdf_sha256'],status=status.tolist(),base_rng=base.bit_generator.state,extra_rng=extra.bit_generator.state,period_count=len(events),period_sha256=digest(events),bank_sha256=digest(banks),emission_sha256=digest(np.packbits(emit,bitorder='little')),errors=errors,fp=fpi,fn=fni,previous_sha256=records[-1]['sha256'] if records else None);blob=pack(meta,events);h=sha(blob);compressseconds=time.perf_counter()-t;t=time.perf_counter();file=root/f'chunk_{step:05d}.npz';atomic(file,blob);rec=dict(first=first,count=len(events),rank=int(status[1])-len(events),path=str(file),sha256=h);records.append(rec);first+=W;cp=dict(config=config,records=records,status=status.tolist(),base_rng=base.bit_generator.state,extra_rng=extra.bit_generator.state,next_n=first,fp=fp,fn=fn);atomic(cp_path,cp);writeseconds=time.perf_counter()-t
  elapsed=time.perf_counter()-start;after=history.counters();rows.append(dict(step=step,first=first-W,seconds=elapsed,banks=bankseconds,rng=rngseconds,transitions=transitionseconds,history_and_truth=gradeseconds,compression=compressseconds,durable_write=writeseconds,cache={key:after[key]-before[key] for key in ['hits','misses','evictions','read_bytes']},fp=fpi,fn=fni))
  with (root/'TIMINGS.jsonl').open('a') as timing:timing.write(json.dumps(rows[-1])+'\n')
  if len(records)%10==0:
   window=rows[-min(100,len(rows)):];atomic(root/'PROGRESS.json',dict(status='RUNNING',pid=os.getpid(),updated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),seed=config['seed'],through=first-1,decisions=first-2,events=int(status[1]),fp=fp,fn=fn,session_per_second=(first-2-startstep*W)/(time.perf_counter()-begin),recent_per_second=len(window)*W/sum(x['seconds'] for x in window),recent_chunks=len(window),last_chunk=rows[-1],cache=history.counters(),peak_rss_kib=__import__('resource').getrusage(__import__('resource').RUSAGE_SELF).ru_maxrss));print(root.name,'CHUNKS',len(records),flush=True)
 elapsed=time.perf_counter()-begin;draw_buffers.close();out=dict(status='PASS',stop_reason=stop_reason,root=str(root),mode=mode,start_step=startstep,end_step=len(records),new_decisions=(len(records)-startstep)*W,seconds=elapsed,per_second=(len(records)-startstep)*W/elapsed,restore_seconds=restore_seconds,orphan_quarantined=orphan_count,cache=history.counters(),rows=rows,through=first-1,events=int(status[1]),fp=fp,fn=fn,peak_rss_kib=__import__('resource').getrusage(__import__('resource').RUSAGE_SELF).ru_maxrss);
 if bridge is not None:out['gpu']={'batch':bridge.batch,'qualification':bridge.qualified,'timings':bridge.times}
 atomic(root/'PROGRESS.json',dict(status='STOPPED',reason=stop_reason,through=first-1,fp=fp,fn=fn,per_second=out['per_second'],updated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())));atomic(root/f'RUN_{startstep:05d}_{len(records):05d}.json',out);print(json.dumps({k:v for k,v in out.items() if k!='rows'}),flush=True);return out
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--until',type=int,required=True);a.add_argument('--mode',choices=['indexed','resident'],default='indexed');a.add_argument('--cache-mib',type=int,default=8);args=a.parse_args();run(args.root,args.until,args.mode,args.cache_mib)
