"""Renew clean time-limited sessions of the same seed; never restart errors/STOP."""
import argparse,datetime,hashlib,json,os,shutil,subprocess
from pathlib import Path
def decision(progress,stop,free):
 if stop:return 'owner_stop'
 if free<20*1024**3:return 'storage_reserve'
 if progress.get('status')=='STOPPED' and progress.get('reason')=='session_time_budget':return 'renew'
 return 'keep_current_or_require_operator'
def main():
 p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--runner',type=Path,required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--dry-run',action='store_true');a=p.parse_args()
 blocked=a.manifest.parent/'RENEWAL_BLOCKED'
 if blocked.exists():print('failure_requires_operator');return
 progress=json.loads((a.root/'PROGRESS.json').read_text());action=decision(progress,(a.root/'STOP').exists(),shutil.disk_usage(a.root).free);print(action,flush=True)
 if action!='renew' or a.dry_run:return
 # Current managed job must have fully released its allocation before renewal.
 units=subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--plain','--no-legend','sam-r3-prime-u5-*.service'],text=True)
 if units.strip():return
 for name,h in json.loads(a.manifest.read_text())['files'].items():
  if hashlib.sha256((a.runner.parent/name).read_bytes()).hexdigest()!=h:raise ValueError('Production source changed: '+name)
 cp=json.loads((a.root/'CHECKPOINT.json').read_text());assert cp['config']['seed']==9370001 and cp['config']['cache_mib']==4096
 name='prime-u5-renew-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')
 env={**os.environ,'PRIME_BACKEND':'cpu','PRIME_SEED':'9370001','PRIME_RNG_WORKERS':'4','PRIME_WALL_SECONDS':'86300'}
 result=subprocess.run([str(a.project/'.venv-r3/bin/python'),str(a.project/'CURRENT_REVISION/engines/SLC/gen3/resources.py'),'run','--name',name,'--role','cpu','--seconds','86400','--','taskset','-c','1-7','env','PRIME_BACKEND=cpu','PRIME_SEED=9370001','PRIME_RNG_WORKERS=4','PRIME_WALL_SECONDS=86300',str(a.project/'.venv-r3/bin/python'),str(a.runner),'--root',str(a.root),'--until','9223372036854775807','--cache-mib','4096'],cwd=a.project,env=env)
 if result.returncode:
  blocked.write_text('Managed renewal failed with exit '+str(result.returncode)+'; inspect before removing this block.\n')
  raise SystemExit(result.returncode)
if __name__=='__main__':main()
