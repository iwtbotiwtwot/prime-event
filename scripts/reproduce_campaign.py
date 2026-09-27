"""Explicitly requested batch reproduction; defaults to one worker."""
import argparse,concurrent.futures,json,subprocess,sys
from pathlib import Path

def execute(job):
 command,log=job;log.parent.mkdir(parents=True,exist_ok=True)
 with log.open('a') as f:subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,check=True)
 return str(log)
def main():
 p=argparse.ArgumentParser();p.add_argument('--experiment',choices=['baseline-matched','balanced-matched','balanced-fresh'],required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=1);p.add_argument('--until',type=int,default=1000000000);a=p.parse_args()
 if a.workers<1:p.error('workers must be positive')
 first,count=(10000000,16) if a.experiment=='balanced-fresh' else (1000000,64);source='baseline' if a.experiment.startswith('baseline') else 'balanced';jobs=[]
 for profile in ['uniform','rough']:
  for seed in range(first,first+count):
   root=a.output/f'{profile}_seed{seed}';jobs.append(([sys.executable,'-m','prime_event','run','--source',source,'--profile',profile,'--seed',str(seed),'--until',str(a.until),'--output',str(root)],root/'RUN.log'))
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
  for log in pool.map(execute,jobs):print(json.dumps({'finished_log':log}),flush=True)
if __name__=='__main__':main()
