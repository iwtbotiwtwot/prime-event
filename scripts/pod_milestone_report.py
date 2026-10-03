"""Fetch exact pod milestones and publish new reports without touching the run."""
import argparse
import csv
import fcntl
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
from pod_t500_backup import SSH,HOST

ROOT=Path(__file__).resolve().parents[1]
FILES=['evidence/pod/milestones.json','evidence/pod/milestones.csv','docs/pod-run.md']
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args],text=True).strip()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--publish',action='store_true');p.add_argument('--force',action='store_true');a=p.parse_args()
    lock=open(Path(tempfile.gettempdir())/'prime-event-hourly-status.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    remote="import json,pathlib; p=pathlib.Path('/root/prime-u5-production'); names=['CAMPAIGN.json','REPORTS.json','data/PROGRESS.json','BACKUP.json']; print(json.dumps({n:json.loads((p/n).read_text()) if (p/n).exists() else None for n in names}))"
    raw=subprocess.check_output(SSH+[HOST,'python -c '+shlex.quote(remote)],text=True,timeout=45)
    observed=json.loads(raw);campaign=observed['CAMPAIGN.json'];assert campaign['config']['seed']==9370001
    reports=observed['REPORTS.json'];progress=observed['data/PROGRESS.json'] or {}
    state_dir=Path.home()/'.local/state/prime-event-pod';state_dir.mkdir(parents=True,exist_ok=True)
    (state_dir/'latest.json').write_text(json.dumps(observed,indent=2)+'\n')
    target=ROOT/FILES[0];prior=json.loads(target.read_text()) if target.exists() else {}
    signature=(len(reports),campaign['status']);old=(len(prior.get('reports',[])),prior.get('status'))
    if signature==old and not a.force:
        if a.publish:subprocess.run(['git','-C',str(ROOT),'push','origin','main'],check=True)
        print(json.dumps(dict(status='NO_NEW_MILESTONE',reports=len(reports),progress=progress)));return
    if a.publish:
        assert git('remote','get-url','origin')=='https://github.com/iwtbotiwtwot/prime-event.git'
        if git('branch','--show-current')!='main' or git('status','--porcelain'):raise RuntimeError('Publication requires clean main; retry next minute')
        subprocess.run(['git','-C',str(ROOT),'pull','--ff-only','origin','main'],check=True)
    record=dict(seed=9370001,status=campaign['status'],reason=campaign.get('reason'),started_utc=campaign['started_utc'],
        reports=reports,launch_or_latest_observation=progress,config=campaign['config'],backup=observed['BACKUP.json'])
    receipt=state_dir/'t500-backup.json'
    backup=json.loads(receipt.read_text()) if receipt.exists() else None
    record['t500_backup']=backup if backup and backup['seed']==9370001 and backup['source_root']=='/root/prime-u5-production' else None
    archive_status=state_dir/'archive-status.json'
    archive=json.loads(archive_status.read_text()) if archive_status.exists() else None
    record['archive_rotation']=archive if archive and archive.get('source_root')=='/root/prime-u5-production' else None
    target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(record,indent=2)+'\n')
    columns=['observed_utc','decisions','fp','fn','errors','interval_fp','interval_fn','interval_per_second','cumulative_per_second','interval_seconds']
    out=io.StringIO();writer=csv.DictWriter(out,fieldnames=columns,extrasaction='ignore',lineterminator='\n');writer.writeheader();writer.writerows(reports);(ROOT/FILES[1]).write_text(out.getvalue())
    lines=['# Pod u5 run — reports every 100 billion decisions','',f"Seed **9370001**, started **{campaign['started_utc']}** at candidate 2 with empty history. Campaign status at this report: **{campaign['status']}**.",'',
        'This is a separate execution of the same seed as the workstation run, not additional independent seed exposure. The workstation trajectory is unchanged. All feedback is raw: no repair, learner or reference veto. Counts below come from committed checkpoints.', '',
        'Reports are generated at exactly 100B, 200B, 300B, and onward. Interval throughput divides the latest 100B committed decisions by elapsed wall time; cumulative throughput includes setup, restarts and pauses since launch. A workstation timer publishes newly retained pod reports every minute when connectivity is available. Delayed publication does not change the recorded milestone time.', '',
        '[Methodology and pilot predictions](throughput-pilot.md) · [Production controls and T500 backups](pod-production.md) · [GPU roles and current running throughput](pod-gpu-roles.md) · [JSON](../evidence/pod/milestones.json) · [CSV](../evidence/pod/milestones.csv)', '',
        'The 1.2T–1.3T interval includes the migration pause. The separate running-throughput measurement in the GPU role report excludes history restoration and that pause.', '',
        '| Milestone | Observed UTC | False events | Missed primes | Total errors | Interval M/s | Cumulative M/s |',
        '|---:|---|---:|---:|---:|---:|---:|']
    for r in reports:lines.append(f"| {r['decisions']//1000000000}B | {r['observed_utc']} | {r['fp']} | {r['fn']} | {r['errors']} | {r['interval_per_second']/1e6:.2f} | {r['cumulative_per_second']/1e6:.2f} |")
    if not reports:lines+=['','The first 100B report is pending.']
    lines+=['',f"Latest sampled progress when this page was published: **{progress.get('through',1)-1:,} decisions**, FP **{progress.get('fp',0)}**, FN **{progress.get('fn',0)}**, observed **{progress.get('updated_utc','pending')}**. This is a dated sample, not a continuously refreshed counter."]
    (ROOT/FILES[2]).write_text('\n'.join(lines)+'\n')
    if a.publish:
        subprocess.run(['git','-C',str(ROOT),'add','--',*FILES],check=True)
        if subprocess.run(['git','-C',str(ROOT),'diff','--cached','--quiet']).returncode:
            subprocess.run(['git','-C',str(ROOT),'commit','-m',f"Report pod u5: {len(reports)*100}B milestones, {campaign['status']}"],check=True)
        subprocess.run(['git','-C',str(ROOT),'push','origin','main'],check=True)
        if reports and len(reports)>len(prior.get('reports',[])) and shutil.which('notify-send'):
            r=reports[-1];subprocess.run(['notify-send','Prime-event milestone',f"{r['decisions']//1000000000}B: FP {r['fp']}, FN {r['fn']}, {r['interval_per_second']/1e6:.2f}M decisions/s"],check=False)
        if campaign['status'] in ['FAILED','STOPPED'] and campaign['status']!=prior.get('status') and shutil.which('notify-send'):
            subprocess.run(['notify-send','Prime-event pod '+campaign['status'],campaign.get('reason','Inspect campaign log')],check=False)
    print(json.dumps(dict(status='PUBLISHED' if a.publish else 'WRITTEN',milestones=len(reports))))
if __name__=='__main__':main()
