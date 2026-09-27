"""Portable three-runner/one-follower orchestration, with no remote services."""
import json,os,signal,time,traceback,multiprocessing as mp
from multiprocessing import shared_memory
from multiprocessing.connection import wait
from pathlib import Path
import numpy as np
from .engine import Engine,Guard,StopRequested,atomic,build,disk_state,grade,sha
from .source import prepare

def checker(conns,stop):
 buffers={}
 try:
  while not stop.is_set() and conns:
   for c in wait(conns,timeout=.5):
    req=c.recv()
    if req['op']=='done':conns.remove(c);c.close();continue
    name=req['buffer']
    if name not in buffers:buffers[name]=shared_memory.SharedMemory(name=name)
    a=np.ndarray((2,req['capacity']),np.uint8,buffer=buffers[name].buf);n=req['count']
    out=grade(req['first_n'],a[0,:n],a[1,:n],req['model']);c.send(out)
 except (EOFError,BrokenPipeError):
  if not stop.is_set():stop.set();raise
 finally:
  for b in buffers.values():b.close()

def teacher_main(conns,stop,cpu,error_conn):
 os.sched_setaffinity(0,{cpu});signal.signal(signal.SIGINT,signal.SIG_IGN)
 try:checker(conns,stop)
 except BaseException:
  stop.set();error_conn.send({'error':traceback.format_exc(),'role':'follower'})
 finally:error_conn.close()

def generate(result,teacher,stop,args,branch,package,binary,device,buffer_name):
 signal.signal(signal.SIGINT,signal.SIG_IGN);shm=shared_memory.SharedMemory(name=buffer_name)
 try:
  root=Path(args.output);guard=Guard(root,device,stop);a=np.ndarray((2,args.chunk),np.uint8,buffer=shm.buf)
  def judge(first,banks,emit,model):
   guard.check();n=len(emit);a[0,:n]=banks;a[1,:n]=emit
   try:
    teacher.send({'op':'grade','first_n':first,'count':n,'capacity':args.chunk,'buffer':buffer_name,'model':model})
    while not teacher.poll(.25):guard.check()
    guard.check();return teacher.recv()
   except (EOFError,BrokenPipeError):
    if stop.is_set():raise StopRequested('STOP_REQUESTED')
    raise
  e=Engine(root/branch['name'],branch['seed'],'uniform',args.chunk,package,binary,guard,cache_bytes=args.cache_mib*1024**2,cpu=branch['cpu'],mode=branch['mode'],judge=judge)
  while e.next_n<=args.until:e.step(min(args.chunk,args.until-e.next_n+1))
  teacher.send({'op':'done'});result.send({'status':'COMPLETE','branch':branch['name'],'snapshot':e.snapshot()})
 except StopRequested as exc:stop.set();result.send({'status':'STOPPED','branch':branch['name'],'reason':str(exc)})
 except BaseException:stop.set();result.send({'status':'FAILED','branch':branch['name'],'error':traceback.format_exc()})
 finally:shm.close();teacher.close();result.close()

def fork(source,destination,branch,chunk):
 source=Path(source);cp=json.loads((source/'CHECKPOINT.json').read_text())
 if cp['config']['seed']!=branch['seed'] or cp['config']['chunk']!=chunk or cp['config']['profile']!='uniform':raise ValueError('Fork needs the same seed/chunk and uniform profile')
 if cp['fp'] or cp['fn']:raise ValueError('Choose an error-free fork prefix before the event being studied')
 if cp.get('repair_mode','control')!='control':raise ValueError('Fork from an unassisted trajectory')
 if destination.exists():raise ValueError('Fork destination exists; resume without --fork-from')
 destination.mkdir()
 for f in source.glob('chunk_*.npz'):
  if int(f.stem.split('_')[1])<cp['next_n']:os.link(f,destination/f.name)
 cp['repair_mode']=branch['mode'];atomic(destination/'CHECKPOINT.json',cp)
 atomic(destination/'FORK.json',{'parent_checkpoint_sha256':sha(source/'CHECKPOINT.json'),'through':cp['next_n']-1,'immutable_prefix_hardlinks':True})

def run(args):
 root=Path(args.output).resolve();root.mkdir(parents=True,exist_ok=True);args.output=root
 if (root/'STOP_LATCH.json').exists():raise ValueError('Stop latched; inspect and explicitly archive STOP_LATCH.json before resume')
 allowed=sorted(os.sched_getaffinity(0));cores=[int(x) for x in args.cores.split(',')] if args.cores else allowed[:4]
 if len(cores)!=4 or len(set(cores))!=4 or not set(cores)<=set(allowed):raise ValueError('follow requires four distinct allowed CPU IDs')
 device=disk_state(root)['device'];Guard(root,device).check();package=prepare(args.source,root/'source');binary=build(root/'build')
 branches=[{'name':'control','seed':args.seed,'mode':'control','cpu':cores[0]},{'name':'repair','seed':args.seed,'mode':'repair','cpu':cores[1]},{'name':'other_repair','seed':args.other_seed,'mode':'repair','cpu':cores[2]}]
 if bool(args.fork_from)!=bool(args.other_fork_from):raise ValueError('Supply both fork directories, or neither')
 if args.fork_from:
  for b in branches:fork(args.other_fork_from if b['name']=='other_repair' else args.fork_from,root/b['name'],b,args.chunk)
 ctx=mp.get_context('spawn');stop=ctx.Event();buffers=[];children=[];pairs=[ctx.Pipe() for _ in branches];teacher_error,teacher_send=ctx.Pipe(duplex=False);results=[];reason=None
 handlers={s:signal.signal(s,lambda *_:stop.set()) for s in [signal.SIGTERM,signal.SIGINT]}
 teacher=ctx.Process(target=teacher_main,args=([x[0] for x in pairs],stop,cores[3],teacher_send));teacher.start();teacher_send.close()
 for a,b in pairs:a.close()
 last=0;checks=0
 try:
  for branch,pair in zip(branches,pairs):
   shm=shared_memory.SharedMemory(create=True,size=2*args.chunk);buffers.append(shm);parent,child=ctx.Pipe(duplex=False)
   proc=ctx.Process(target=generate,args=(child,pair[1],stop,args,branch,str(package),str(binary),device,shm.name));proc.start();child.close();pair[1].close();children.append((proc,parent,branch))
  pending=list(children)
  while pending:
   if time.monotonic()-checks>=5:
    try:
     Guard(root,device).check()
     if (root/'STOP').exists():raise StopRequested('STOP_FILE')
    except Exception as exc:reason=str(exc);stop.set()
    checks=time.monotonic()
   for item in pending[:]:
    proc,conn,branch=item
    if conn.poll():
     try:r=conn.recv()
     except EOFError:r={'status':'FAILED','branch':branch['name'],'error':'Worker exited without result'}
     results.append(r);pending.remove(item)
     if r['status']!='COMPLETE':stop.set();reason=r.get('reason',r.get('error'))
    elif not proc.is_alive():stop.set();reason='Worker failed without result';pending.remove(item)
   if teacher_error.poll():
    try:r=teacher_error.recv();stop.set();reason=r.get('error')
    except EOFError:pass
   if time.monotonic()-last>=60:
    rows=[]
    for b in branches:
     cp=root/b['name']/'CHECKPOINT.json'
     if cp.exists():
      c=json.loads(cp.read_text());rows.append({'branch':b['name'],'through':c['next_n']-1,'raw_fp':c['fp'],'raw_fn':c['fn'],'learner':c.get('learner')})
    atomic(root/'STATUS.json',{'status':'STOPPING' if stop.is_set() else 'RUNNING','branches':rows,'disk':disk_state(root)});print(json.dumps({'status':'RUNNING','branches':rows}),flush=True);last=time.monotonic()
   time.sleep(.1)
  status='COMPLETE' if len(results)==3 and all(r['status']=='COMPLETE' for r in results) else 'STOPPED'
  atomic(root/'RESULT.json',{'status':status,'source':args.source,'branches':results,'roles':branches,'follower_cpu':cores[3]})
  atomic(root/'STATUS.json',{'status':status,'branches':results,'disk':disk_state(root)})
  if status!='COMPLETE':atomic(root/'STOP_LATCH.json',{'reason':reason or 'MANUAL_STOP'})
  print(json.dumps({'status':status,'branches':[{'branch':r['branch'],'status':r['status']} for r in results]}))
 finally:
  stop.set()
  for proc,_,_ in children:
   proc.join(10)
   if proc.is_alive():proc.terminate();proc.join(5)
  teacher.join(10)
  if teacher.is_alive():teacher.terminate();teacher.join(5)
  for b in buffers:b.close();b.unlink()
  for s,h in handlers.items():signal.signal(s,h)
