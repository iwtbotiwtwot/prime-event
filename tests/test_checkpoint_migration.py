"""A runtime migration must preserve durable science and reject unsafe targets."""
import copy
import fcntl
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
CODE=REPO/'experiments/u5-throughput'
sys.path.insert(0,str(CODE))
from runtime_config import accelerator_identity
spec=importlib.util.spec_from_file_location('migration_test_journal',CODE/'journal.py')
j=importlib.util.module_from_spec(spec);spec.loader.exec_module(j)

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.data=self.root/'data';self.data.mkdir()
        cp=dict(config=dict(seed=9370001,cache_mib=98304,cdf_sha256='frozen-cdf',
                            initial_sha256='frozen-state',accelerator=dict(backend='gpu',pipeline=True,files={})),
                records=[],next_n=2,fp=0,fn=0,status=[0,0,123],base_rng={'pcg64':'base'},extra_rng={'pcg64':'extra'})
        j.atomic(self.data/'CHECKPOINT.json',cp)
        writer=j.Writer(self.data,copy.deepcopy(cp))
        blob=b'authenticated committed history'
        writer.add(dict(path=str(self.data/'chunk_00000.npz'),sha256=j.sha(blob)),blob,
                   dict(next_n=5000002,fp=0,fn=0,status=[9,1,456],base_rng={'pcg64':'next-base'},extra_rng={'pcg64':'next-extra'}))
        self.before=j.load(self.data)
        self.raw_before=(self.data/'CHECKPOINT.json').read_bytes()
        self.head=(self.data/'HEAD.json').read_bytes()
        self.args=type('Roles',(),dict(proposal_gpu=0,history_gpu=1,grade_gpu=2,gpu_cache_mib=16384,cuda_arch='sm_120'))()
        identity=accelerator_identity(CODE,'gpu',True,self.args)
        self.qualification=self.root/'QUALIFICATION.json'
        j.atomic(self.qualification,dict(status='PASS',source_files=identity['files'],accelerator=identity))
        j.atomic(self.root/'CAMPAIGN.json',dict(status='STOPPED',config=dict(seed=9370001,cache_mib=98304)))
        self.command=[sys.executable,str(REPO/'scripts/migrate_pod_checkpoint.py'),'--root',str(self.root),
                      '--code',str(CODE),'--cache-mib','196608','--qualification',str(self.qualification),
                      '--proposal-gpu','0','--history-gpu','1','--grade-gpu','2','--cuda-arch','sm_120']

    def run_migration(self):
        return subprocess.run(self.command,text=True,capture_output=True)

    def test_published_suffix_rng_state_and_head_survive(self):
        (self.data/'STOP').touch()
        result=self.run_migration()
        self.assertEqual(result.returncode,0,result.stderr)
        after=j.load(self.data)
        self.assertEqual({k:v for k,v in after.items() if k!='config'},
                         {k:v for k,v in self.before.items() if k!='config'})
        self.assertEqual(after['config']['cdf_sha256'],'frozen-cdf')
        self.assertEqual(after['config']['initial_sha256'],'frozen-state')
        self.assertEqual(after['config']['cache_mib'],196608)
        self.assertEqual((self.data/'HEAD.json').read_bytes(),self.head)
        self.assertEqual(len(list(self.root.glob('CHECKPOINT_BEFORE_*.json'))),1)
        self.assertEqual(json.loads((self.root/'CAMPAIGN.json').read_bytes())['config']['history_gpu'],1)

    def test_stop_locks_and_qualification_gate_mutation(self):
        self.assertNotEqual(self.run_migration().returncode,0)
        (self.data/'STOP').touch()
        for path in (self.root/'CAMPAIGN.lock',self.data/'WRITER.lock'):
            with path.open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                self.assertNotEqual(self.run_migration().returncode,0)
        qualification=json.loads(self.qualification.read_bytes())
        qualification['accelerator']['grade_gpu']=0
        j.atomic(self.qualification,qualification)
        self.assertNotEqual(self.run_migration().returncode,0)
        self.assertEqual((self.data/'CHECKPOINT.json').read_bytes(),self.raw_before)
        self.assertEqual((self.data/'HEAD.json').read_bytes(),self.head)

if __name__=='__main__':unittest.main()
