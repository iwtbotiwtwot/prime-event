"""Portable bounded-memory runs; reference labels are used only after generation."""
import argparse,json,os,signal,threading,time
for variable in ["OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"]:os.environ[variable]="1"
from pathlib import Path
from .source import prepare,reconstruct
from .engine import Engine,Guard,StopRequested,atomic,build,disk_state

def run_one(args):
 root=Path(args.output).resolve();root.mkdir(parents=True,exist_ok=True)
 if (root/'STOP_LATCH.json').exists():raise ValueError('Stop latched: inspect and archive STOP_LATCH.json explicitly before resume')
 stop=threading.Event();done=threading.Event();reason={};device=disk_state(root)['device'];guard=Guard(root,device,stop)
 guard.check();package=prepare(args.source,root/'source');binary=build(root/'build')
 def halt(why):reason.setdefault('reason',why);stop.set()
 handlers={s:signal.signal(s,lambda sig,frame:halt('MANUAL_SIGNAL_'+str(sig))) for s in [signal.SIGINT,signal.SIGTERM]}
 def watch():
  while not done.wait(5):
   try:
    Guard(root,device).check()
    if (root/'STOP').exists():halt('STOP_FILE')
   except Exception as exc:halt(str(exc))
 thread=threading.Thread(target=watch,daemon=True);thread.start()
 try:
  e=Engine(root/'trajectory',args.seed,args.profile,args.chunk,package,binary,guard,cache_bytes=args.cache_mib*1024**2,mode='repair' if args.mode=='checked-repair' else 'control')
  last=0
  while e.next_n<=args.until:
   p=e.step(min(args.chunk,args.until-e.next_n+1))
   if time.monotonic()-last>=args.progress_seconds:print(json.dumps(p),flush=True);last=time.monotonic()
  atomic(root/'RESULT.json',{'status':'COMPLETE','source':args.source,'checked_through':e.next_n-1,'snapshot':e.snapshot()});print(json.dumps({'status':'COMPLETE',**e.progress()}))
 except StopRequested as exc:
  halt(str(exc));atomic(root/'STOP_LATCH.json',reason);print(json.dumps({'status':'STOPPED',**reason}))
 except BaseException:
  atomic(root/'STOP_LATCH.json',{'reason':'RUN_FAILURE'});raise
 finally:
  done.set();thread.join(6)
  for s,h in handlers.items():signal.signal(s,h)

def verify(args):
 rows=json.loads(Path(args.evidence).read_text());matches=[r for r in rows if r['experiment']==args.experiment and r['seed']==args.seed and r['profile']==args.profile]
 if len(matches)!=1:raise ValueError('Expected one published trajectory')
 expected=matches[0];actual=json.loads((Path(args.output)/'RESULT.json').read_text());cp=actual['snapshot']
 assert actual['status']=='COMPLETE','Run is not complete'
 assert actual['source']==('baseline' if args.experiment=='baseline-matched' else 'balanced'),'Source differs'
 assert cp['config']['seed']==args.seed and cp['config']['profile']==args.profile,'Seed/profile differs'
 if cp.get('repair_mode')!='control':raise ValueError('Historical comparisons require raw, unassisted mode')
 assert actual['checked_through']==expected['through'],'Horizon mismatch'
 assert cp['fp']==expected['fp'] and cp['fn']==expected['fn'],'Error totals differ'
 assert cp['status']==expected['terminal_status'],'Terminal microscopic state/event count/checksum differs'
 print(json.dumps({'status':'PASS','experiment':args.experiment,'seed':args.seed,'profile':args.profile,'through':expected['through'],'terminal_status':cp['status']}))

def main():
 p=argparse.ArgumentParser(prog='prime-event');sub=p.add_subparsers(dest='command',required=True)
 r=sub.add_parser('run',help='Run/resume one raw or checked-repair trajectory')
 r.add_argument('--source',choices=['baseline','balanced'],default='balanced');r.add_argument('--seed',type=int,default=1000000);r.add_argument('--profile',choices=['uniform','rough'],default='uniform');r.add_argument('--until',type=int,default=1000000);r.add_argument('--chunk',type=int,default=5000000);r.add_argument('--cache-mib',type=int,default=256);r.add_argument('--mode',choices=['raw','checked-repair'],default='raw');r.add_argument('--output',type=Path,required=True);r.add_argument('--progress-seconds',type=float,default=60)
 s=sub.add_parser('rebuild-source');s.add_argument('--source',choices=['baseline','balanced'],default='balanced');s.add_argument('--output',type=Path,required=True)
 v=sub.add_parser('verify');v.add_argument('--evidence',type=Path,default=Path('evidence/trajectories.json'));v.add_argument('--experiment',choices=['baseline-matched','balanced-matched','balanced-fresh'],required=True);v.add_argument('--seed',type=int,required=True);v.add_argument('--profile',choices=['uniform','rough'],default='uniform');v.add_argument('--output',type=Path,required=True)
 f=sub.add_parser('follow',help='Three generators and one checking/training follower');f.add_argument('--output',type=Path,required=True);f.add_argument('--source',choices=['baseline','balanced'],default='balanced');f.add_argument('--seed',type=int,default=20000001);f.add_argument('--other-seed',type=int,default=20000002);f.add_argument('--until',type=int,default=1000000);f.add_argument('--chunk',type=int,default=5000000);f.add_argument('--cache-mib',type=int,default=256);f.add_argument('--cores',help='Four distinct allowed CPU IDs, e.g. 0,1,2,3');f.add_argument('--fork-from',type=Path,help='Directory containing a completed portable trajectory (same seed); links its committed prefix');f.add_argument('--other-fork-from',type=Path,help='Corresponding completed trajectory for the other seed')
 a=p.parse_args()
 if a.command in ('run','follow') and (a.until<2 or a.chunk<1 or a.chunk>2**32-1 or a.cache_mib<0):p.error('until>=2, 1<=chunk<=2^32-1 and cache-mib>=0 required')
 if a.command=='run':run_one(a)
 elif a.command=='rebuild-source':print(json.dumps(reconstruct(a.source,a.output),indent=2))
 elif a.command=='verify':verify(a)
 elif a.command=='follow':
  from .follower import run
  run(a)
if __name__=='__main__':main()
