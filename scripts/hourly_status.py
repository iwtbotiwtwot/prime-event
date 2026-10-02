"""Publish observed checkpoint counts; never extrapolate or modify the runner."""
import argparse,csv,datetime,fcntl,io,json,os,subprocess,tempfile
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
FILES=['evidence/live/latest.json','evidence/live/hourly.csv','docs/live-run.md']
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args],text=True).strip()
def atomic(p,text):
 p.parent.mkdir(parents=True,exist_ok=True);q=p.with_suffix(p.suffix+'.tmp');q.write_text(text);os.replace(q,p)
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--publish',action='store_true');a=p.parse_args()
 lock=open(Path(tempfile.gettempdir())/'prime-event-hourly-status.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if a.publish:
  if git('remote','get-url','origin')!='https://github.com/iwtbotiwtwot/prime-event.git':raise RuntimeError('Wrong repository')
  if git('branch','--show-current')!='main' or git('status','--porcelain'):raise RuntimeError('Hourly publication requires clean main')
  subprocess.run(['git','-C',str(ROOT),'pull','--ff-only','origin','main'],check=True)
 now=datetime.datetime.now(datetime.timezone.utc);hour=now.strftime('%Y-%m-%dT%H:00:00Z')
 with (a.source/'CHECKPOINT.json').open() as f:cp=json.load(f);stamp=datetime.datetime.fromtimestamp(os.fstat(f.fileno()).st_mtime,datetime.timezone.utc)
 if cp['config']['seed']!=9370001:raise ValueError('Unexpected seed')
 progress=json.loads((a.source/'PROGRESS.json').read_text());age=(now-stamp).total_seconds();state=progress.get('status','UNKNOWN')
 if age>120:state='STALE' if state=='RUNNING' else state
 row={'observed_utc':now.isoformat(timespec='seconds'),'chicago_time':now.astimezone(ZoneInfo('America/Chicago')).isoformat(timespec='seconds'),'checkpoint_utc':stamp.isoformat(timespec='seconds'),'seed':9370001,'decisions':cp['next_n']-2,'through':cp['next_n']-1,'false_events':cp['fp'],'missed_primes':cp['fn'],'total_errors':cp['fp']+cp['fn'],'status':state,'recent_decisions_per_second':progress.get('recent_per_second',''),'throughput_observed_utc':progress.get('updated_utc',''),'feedback':'raw; no repair or correction','cdf_sha256':cp['config']['cdf_sha256']}
 path=ROOT/FILES[1];old=list(csv.DictReader(path.open())) if path.exists() else []
 # One observed row per UTC hour. Missing offline hours are not invented.
 if not old or old[-1]['observed_utc'][:13]!=row['observed_utc'][:13]:old.append(row)
 else:old[-1]=row
 out=io.StringIO();writer=csv.DictWriter(out,fieldnames=list(row),lineterminator='\n');writer.writeheader();writer.writerows(old)
 atomic(ROOT/FILES[0],json.dumps(row,indent=2)+'\n');atomic(path,out.getvalue())
 lines=['# Live unrepaired u5 run — seed 9370001','',f"Observed **{row['chicago_time']}** (Chicago), **{row['observed_utc']}** (UTC).",'',f"**{row['decisions']:,} decisions; {row['false_events']} false events; {row['missed_primes']} missed primes. Status: {state}.**",'', 'One raw trajectory from candidate 2. No repair, correction, learner or reference veto. Prime truth scores the emitted decisions only. Counts are read from a committed checkpoint; throughput has its own observation timestamp in the JSON. This is a live snapshot, not a completed campaign.', '', '[Reproduce this method](latest-u5.md) · [Complete hourly CSV](../evidence/live/hourly.csv) · [Latest JSON](../evidence/live/latest.json)', '', 'Scheduled publication runs on the workstation. Check the observation time: if the workstation, mount or network is unavailable, this page remains a dated snapshot. Missing hours are not backfilled. The runner has no overall end date; checkpoint-preserving daily renewals stop on user request, low storage or failure.', '', '| Chicago observation | Decisions | False events | Missed primes | Total errors | Status |','|---|---:|---:|---:|---:|---|']
 for r in old[-48:]:lines.append(f"| {r['chicago_time']} | {int(r['decisions']):,} | {r['false_events']} | {r['missed_primes']} | {r['total_errors']} | {r['status']} |")
 atomic(ROOT/FILES[2],'\n'.join(lines)+'\n')
 if a.publish:
  subprocess.run(['git','-C',str(ROOT),'add','--',*FILES],check=True)
  if subprocess.run(['git','-C',str(ROOT),'diff','--cached','--quiet']).returncode:subprocess.run(['git','-C',str(ROOT),'commit','-m','Update hourly prime-event observation '+hour],check=True)
  subprocess.run(['git','-C',str(ROOT),'push','origin','main'],check=True)
 print(json.dumps(row))
if __name__=='__main__':main()
