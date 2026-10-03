"""Kill/restart an isolated pilot and compare its complete journal with v1."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--old-code',type=Path,required=True)
a=p.parse_args();a.root.mkdir(exist_ok=False)
here=Path(__file__).resolve().parent
def command(code,root):
    return [sys.executable,str(code/'pilot.py'),'--workdir',str(root),'--backend','gpu','--pipeline',
        '--threads','8','--workers','8','--seed','9369001','--cache-mib','4096','--chunks','200','--seconds','300']
fault=a.root/'interrupted';control=a.root/'control'
with (a.root/'interrupted.log').open('w') as log:
    proc=subprocess.Popen(command(here,fault),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    try:
        deadline=time.monotonic()+180
        while True:
            if proc.poll() is not None:raise RuntimeError('Pilot exited before interruption; inspect log')
            hp=fault/'data/HEAD.json'
            if hp.exists() and json.loads(hp.read_text())['sequence']>=80:break
            if time.monotonic()>deadline:raise TimeoutError('No durable group commit')
            time.sleep(0.02)
        time.sleep(0.1);os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    finally:
        if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
from journal import load
cp=load(fault/'data');count=len(cp['records'])
(fault/'data'/f'chunk_{count+3:05d}.npz').write_bytes(b'uncommitted orphan')
with (a.root/'resumed.log').open('w') as log:
    subprocess.run(command(here,fault),stdout=log,stderr=subprocess.STDOUT,check=True)
with (a.root/'control.log').open('w') as log:
    subprocess.run(command(a.old_code,control),stdout=log,stderr=subprocess.STDOUT,check=True)
comparison=json.loads(subprocess.check_output([sys.executable,str(here/'compare_journals.py'),str(control),str(fault)],text=True))
result=json.loads((fault/'PILOT.json').read_text())
if result['orphan_quarantined']<1:raise AssertionError('Orphan was not quarantined')
report=dict(status='PASS',durable_chunks_at_kill=count,orphan_quarantined=result['orphan_quarantined'],comparison=comparison)
(a.root/'QUALIFICATION.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
