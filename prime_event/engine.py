"""Bounded-memory exact recurrence scheduling and durable worker chunks."""
import os,json,time,hashlib,ctypes,subprocess,io,zipfile,math,uuid
from pathlib import Path
import numpy as np
from .learner import OnlineGate
HERE=Path(__file__).resolve().parent
class StopRequested(Exception):pass
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def atomic(path,value):
 path=Path(path);raw=(json.dumps(value,sort_keys=True)+'\n').encode();tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
 with tmp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path);fd=os.open(path.parent,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)
def pack(arrays):
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
  for name,array in arrays.items():
   buf=io.BytesIO();np.lib.format.write_array(buf,np.asarray(array),allow_pickle=False);z.writestr(name+'.npy',buf.getvalue())
 return out.getvalue()
def disk_state(path):
 s=os.statvfs(path);return {'available':s.f_bavail*s.f_frsize,'total':s.f_blocks*s.f_frsize,'device':os.stat(path).st_dev}
class Guard:
 def __init__(self,path,device,stop=None,reserve=256*1024**2,probe=disk_state):self.path=Path(path);self.device=device;self.stop=stop;self.reserve=reserve;self.probe=probe
 def check(self,write_bytes=0):
  if self.stop is not None and self.stop.is_set():raise StopRequested('STOP_REQUESTED')
  d=self.probe(self.path)
  if d['device']!=self.device:raise StopRequested('T500_DEVICE_CHANGED')
  if d['available']*10<=d['total']:raise StopRequested('DISK_AT_OR_BELOW_10_PERCENT')
  if write_bytes and d['available']-write_bytes-self.reserve<=d['total']//10:raise StopRequested('DISK_COMMIT_RESERVE')
  return d
def build(root):
 root=Path(root);root.mkdir(parents=True,exist_ok=True);binary=root/'kernel.so';manifest=root/'BUILD.json';source_hash=sha(HERE/'kernel.cpp')
 if binary.exists() and manifest.exists():
  m=json.loads(manifest.read_text())
  if m['source_sha256']==source_hash and m['binary_sha256']==sha(binary):return binary
 subprocess.run(['g++','-O3','-std=c++17','-fPIC','-shared',str(HERE/'kernel.cpp'),'-o',str(binary)],check=True)
 atomic(manifest,{'source_sha256':source_hash,'binary_sha256':sha(binary),'compiler':subprocess.check_output(['g++','--version'],text=True).splitlines()[0]});return binary
def reference(first,count):
 end=first+count-1;limit=math.isqrt(end);small=np.ones(limit+1,dtype=np.bool_);small[:2]=False
 for p in range(2,math.isqrt(limit)+1):
  if small[p]:small[p*p::p]=False
 truth=np.ones(count,dtype=np.bool_)
 for pp in np.flatnonzero(small):
  p=int(pp);begin=max(p*p,((first+p-1)//p)*p)
  if begin<=end:truth[begin-first::p]=False
 return truth
def repair_periods(periods,errors):
 remove=np.array([e['index'] for e in errors if e['kind']=='composite_emission'],np.uint64)
 insert=np.array([e['index'] for e in errors if e['kind']=='missed_prime'],np.uint64)
 if len(remove):periods=periods[~np.isin(periods,remove)]
 if len(insert):periods=np.sort(np.concatenate((periods,insert)))
 return periods

def grade(first,banks,emit,saved):
 model=OnlineGate(saved);keys,prediction,before=model.predict(banks,emit)
 truth=reference(first,len(emit))
 learning=model.observe(first,keys,prediction,emit,banks,truth,before)
 wrong=np.flatnonzero(emit.astype(bool)!=truth)
 return {'fp':int(np.count_nonzero(emit&~truth)),'fn':int(np.count_nonzero((emit==0)&truth)),'errors':[{'index':int(first+k),'kind':'missed_prime' if truth[k] else 'composite_emission'} for k in wrong],'learning':learning}

class Engine:
 def __init__(self,root,seed,profile,chunk,package,binary,guard,cache_bytes=2*1024**3,cpu=None,mode="control",judge=None):
  assert mode in ("control","repair");self.mode=mode;self.judge=judge;self.raw_events=0
  if cpu is not None:os.sched_setaffinity(0,{cpu})
  self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.guard=guard;guard.check();self.cache=[];self.cache_count=0;self.cache_limit=cache_bytes//8
  self.package=Path(package);src=json.loads((self.package/'SOURCE.json').read_text())
  for name,h in src['data_files'].items():assert sha(self.package/name)==h,'Source-array hash mismatch'
  self.table=np.load(self.package/'data'/f'cdf_{profile}.npy');initial=np.load(self.package/'data/initial_cdf.npy')
  self.config={'schema':'PRIME_SEGMENTED_GAPS_V2','seed':seed,'profile':profile,'chunk':chunk,'source_sha256':sha(self.package/'SOURCE.json'),'kernel_sha256':sha(HERE/'kernel.cpp'),'numpy_version':np.__version__}
  assert np.__version__=='1.26.4','Pinned RNG version required'
  self.lib=ctypes.CDLL(str(binary));self.mark=self.lib.mark_periods;self.mark.argtypes=[ctypes.c_uint64,ctypes.c_uint64,ctypes.c_void_p,ctypes.c_uint64,ctypes.c_uint64,ctypes.c_void_p];self.mark.restype=ctypes.c_int
  self.advance=self.lib.advance_segment;self.advance.argtypes=[ctypes.c_uint64,ctypes.c_uint64]+[ctypes.c_void_p]*6+[ctypes.c_uint64,ctypes.c_void_p];self.advance.restype=ctypes.c_int
  self.base=np.random.default_rng(seed);self.extra=np.random.default_rng(seed+1000000);self.status=np.array([int(np.searchsorted(initial,self.base.random(),side='right')),0,1469598103934665603],np.uint64)
  self.next_n=2;self.chunks=0;self.previous=None;self.fp=0;self.fn=0;self.records=[];self.learner=OnlineGate()
  self.checkpoint=self.root/'CHECKPOINT.json';self.started=time.monotonic();self.start_n=2
  if self.checkpoint.exists():self.restore()
  else:
   assert not list(self.root.glob('chunk_*.npz')),'Unbound chunk data'
   atomic(self.checkpoint,self.snapshot())
  self.start_n=self.next_n
 def add_cache(self,a):
  n=min(len(a),self.cache_limit-self.cache_count)
  if n>0:self.cache.append(a[:n].copy());self.cache_count+=n
 def snapshot(self):return {'config':self.config,'next_n':self.next_n,'chunks':self.chunks,'status':[int(x) for x in self.status],'base_rng':self.base.bit_generator.state,'extra_rng':self.extra.bit_generator.state,'previous_sha256':self.previous,'fp':self.fp,'fn':self.fn,'learner':self.learner.snapshot(),'repair_mode':self.mode,'raw_events':self.raw_events}
 def read_chunk(self,file):
  with np.load(file,allow_pickle=False) as z:
   meta=json.loads(z['metadata'].tobytes());periods=np.cumsum(z['period_gaps'],dtype=np.uint64)+np.uint64(meta['first_n'])
  assert len(periods)==meta['period_count'],'Period count mismatch'
  assert hashlib.sha256(periods.astype('<u8').tobytes()).hexdigest()==meta['period_sha256'],'Committed periods hash mismatch'
  assert len(periods)==0 or (periods[0]>=meta['first_n'] and periods[-1]<meta['next_n'] and np.all(periods[1:]>periods[:-1])),'Invalid periods'
  if meta.get('repair_mode')=='repair':periods=repair_periods(periods,meta['errors'])
  return meta,periods
 def restore(self):
  saved=json.loads(self.checkpoint.read_text());assert saved.get('repair_mode',self.mode)==self.mode,'Repair mode mismatch';assert saved['config']==self.config,'Resume scientific configuration mismatch'
  files=sorted(self.root.glob('chunk_*.npz'));chain=None;next_n=2;events=0;fp=fn=0;lastmeta=None;seen=0
  for file in files:
   self.guard.check()
   if int(file.name.split('_')[1])>=saved['next_n']:
    dest=self.root/'uncommitted';dest.mkdir(exist_ok=True);os.replace(file,dest/(file.name+'.'+str(time.time_ns())));continue
   checkhash=sha(file);meta,periods=self.read_chunk(file)
   assert meta['config']==self.config and meta['first_n']==next_n and meta['previous_sha256']==chain,'Chunk chain broken'
   self.records.append((file,events,len(periods)));self.add_cache(periods)
   events+=len(periods);self.raw_events+=meta['period_count'];next_n+=meta['count'];fp+=meta['fp'];fn+=meta['fn'];chain=checkhash;lastmeta=meta;seen+=1
  assert next_n==saved['next_n'] and events==saved['status'][1] and chain==saved['previous_sha256'] and seen==saved['chunks'] and fp==saved['fp'] and fn==saved['fn'],'Checkpoint/trace mismatch'
  assert saved.get('raw_events',self.raw_events)==self.raw_events,'Raw event checkpoint mismatch'
  if lastmeta:
   assert lastmeta['status']==saved['status'] and lastmeta['base_rng']==saved['base_rng'] and lastmeta['extra_rng']==saved['extra_rng'],'RNG/state checkpoint mismatch'
  self.next_n=next_n;self.chunks=seen;self.previous=chain;self.fp=fp;self.fn=fn;self.status=np.array(saved['status'],np.uint64);self.base.bit_generator.state=saved['base_rng'];self.extra.bit_generator.state=saved['extra_rng']
  self.learner=OnlineGate(saved.get('learner'))
  if lastmeta and 'learning' in lastmeta:assert lastmeta['learning']['model_after']==self.learner.snapshot(),'Learner checkpoint mismatch'
 def mark_history(self,banks):
  cutoff=(self.next_n+len(banks)-1)//2;rank=0
  def mark(a,rank):
   self.guard.check();size=int(np.searchsorted(a,cutoff,side='right'));assert self.mark(self.next_n,len(banks),a.ctypes.data,size,rank,banks.ctypes.data)==0
   return size<len(a)
  for a in self.cache:
   if mark(a,rank):return
   rank+=len(a)
  for file,start,size in self.records:
   if start+size<=rank:continue
   _,a=self.read_chunk(file);a=a[rank-start:]
   if mark(a,rank):return
   rank+=len(a)
 def step(self,count=None):
  self.guard.check();count=self.config['chunk'] if count is None else count;first=self.next_n
  if first+count>=2**63:raise StopRequested('INTEGER_IMPLEMENTATION_LIMIT')
  t=time.monotonic();banks=np.zeros(count,np.uint8);self.mark_history(banks);mark_seconds=time.monotonic()-t
  self.guard.check();u=self.base.random(count);v=self.extra.random((count,2));emit=np.zeros(count,np.uint8);prefix_count=max(0,min(count,4098-first));prefix=np.empty((prefix_count,3),np.uint8)
  assert self.advance(first,count,self.table.ctypes.data,u.ctypes.data,v.ctypes.data,banks.ctypes.data,emit.ctypes.data,prefix.ctypes.data,prefix_count,self.status.ctypes.data)==0
  del u,v
  self.guard.check()
  if self.judge is not None:review=self.judge(first,banks,emit,self.learner.snapshot())
  else:review=grade(first,banks,emit,self.learner.snapshot())
  self.learner=OnlineGate(review['learning']['model_after']);learning=review['learning'];errors=review['errors'];fps=review['fp'];fns=review['fn']
  periods=np.flatnonzero(emit).astype('<u8')+np.uint64(first);raw_periods=periods.tobytes();period_hash=hashlib.sha256(raw_periods).hexdigest();after=first+count
  raw_status=[int(x) for x in self.status];self.raw_events+=len(periods)
  effective=repair_periods(periods,errors) if self.mode=='repair' else periods
  self.status[1]=int(self.status[1])+len(effective)-len(periods)
  meta={'raw_status':raw_status,'repair_mode':self.mode,'feedback_period_count':len(effective),'config':self.config,'first_n':first,'count':count,'next_n':after,'status':[int(x) for x in self.status],'base_rng':self.base.bit_generator.state,'extra_rng':self.extra.bit_generator.state,'previous_sha256':self.previous,'period_count':len(periods),'period_sha256':period_hash,'fp':fps,'fn':fns,'errors':errors,'learning':learning}
  # Store one lossless event representation. Emission and bank traces are
  # reconstructible from these events; hashes retain comparison evidence.
  meta['emission_sha256']=hashlib.sha256(np.packbits(emit,bitorder='little').tobytes()).hexdigest()
  meta['bank_sha256']=hashlib.sha256(banks.tobytes()).hexdigest()
  gaps=np.diff(np.concatenate((np.array([first],dtype=np.uint64),periods))).astype('<u4' if count<=2**32-1 else '<u8')
  blob=pack({'period_gaps':gaps,'prefix_states':prefix,'metadata':np.frombuffer(json.dumps(meta,sort_keys=True).encode(),np.uint8)})
  self.guard.check(len(blob)+65536)
  # Only committed state is resumable; any interruption before checkpoint leaves
  # a detectable, recoverable suffix. RAM draws are discarded if this write is refused.
  file=self.root/f'chunk_{first:020d}_{after-1:020d}.npz';tmp=file.with_suffix('.tmp')
  with tmp.open('wb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
  os.replace(tmp,file);self.previous=hashlib.sha256(blob).hexdigest();self.next_n=after;self.chunks+=1;self.fp+=fps;self.fn+=fns
  atomic(self.checkpoint,self.snapshot());self.records.append((file,int(self.status[1])-len(effective),len(effective)));self.add_cache(effective)
  elapsed=time.monotonic()-t;out=self.progress();out.update({'last_chunk_seconds':elapsed,'last_mark_seconds':mark_seconds,'last_errors':errors,'learning':{'first_n':self.learner.first_n,'trained':self.learner.trained,'evaluated':self.learner.evaluated,'fp':self.learner.fp,'fn':self.learner.fn,'fixed_veto_fp':self.learner.veto_fp,'fixed_veto_fn':self.learner.veto_fn},'trace_bytes':len(blob),'raw_period_equivalent_bytes':len(raw_periods)})
  atomic(self.root/'PROGRESS.json',out);return out
 def progress(self):return {'seed':self.config['seed'],'profile':self.config['profile'],'checked_through':self.next_n-1,'events':self.raw_events,'feedback_events':int(self.status[1]),'repair_mode':self.mode,'chunks':self.chunks,'fp':self.fp,'fn':self.fn,'exact_so_far':self.fp+self.fn==0,'cache_bytes':self.cache_count*8,'pid':os.getpid(),'affinity':sorted(os.sched_getaffinity(0)),'updated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'session_candidates_per_second':(self.next_n-self.start_n)/max(.001,time.monotonic()-self.started)}
