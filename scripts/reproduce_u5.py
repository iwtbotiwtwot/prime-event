"""Build the frozen production source and run/restart a bounded raw prefix."""
import argparse,gzip,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'production/u5'
def prepare(dest):
 dest=dest.resolve();dest.mkdir(parents=True,exist_ok=True)
 for n,h in json.loads((SRC/'SOURCE.json').read_text())['files'].items():
  raw=gzip.decompress((SRC/(n+'.gz')).read_bytes()) if n.endswith('.npy') else (SRC/n).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=h:raise ValueError('Source mismatch: '+n)
  if (dest/n).exists() and (dest/n).read_bytes()!=raw:raise ValueError('Refusing to overwrite a different source: '+n)
  (dest/n).write_bytes(raw)
 for stem in ['reference','index']:subprocess.run(['g++','-O3','-std=c++17','-shared','-fPIC',str(dest/(stem+'.cpp')),'-o',str(dest/(stem+'.so'))],check=True)
 return dest
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workdir',type=Path,required=True);p.add_argument('--chunks',type=int,default=20,help='Total committed 5M chunks, including previous chunks');p.add_argument('--seed',type=int,default=9369001);p.add_argument('--workers',type=int,default=4);p.add_argument('--cache-mib',type=int,default=512);p.add_argument('--seconds',type=int,default=3600);a=p.parse_args()
 if a.chunks<1 or a.workers<1 or a.seconds<1:p.error('Positive chunks/workers/seconds required')
 dest=prepare(a.workdir/'source');env={**os.environ,'PRIME_SEED':str(a.seed),'PRIME_BACKEND':'cpu','PRIME_RNG_WORKERS':str(a.workers),'PRIME_WALL_SECONDS':str(a.seconds)}
 subprocess.run([sys.executable,str(dest/'runner.py'),'--root',str((a.workdir/'data').resolve()),'--until',str(a.chunks),'--cache-mib',str(a.cache_mib)],env=env,check=True)
 cp=json.loads((a.workdir/'data/CHECKPOINT.json').read_text());print(json.dumps({'through':cp['next_n']-1,'decisions':cp['next_n']-2,'fp':cp['fp'],'fn':cp['fn']}))
