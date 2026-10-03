"""Recovery boundaries: ignored tails, authenticated commits, and full snapshots."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('journal',Path(__file__).resolve().parents[1]/'experiments/u5-throughput/journal.py')
j=importlib.util.module_from_spec(spec);spec.loader.exec_module(j)

class JournalTests(unittest.TestCase):
    def test_buffered_recovery_corruption_and_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            cp=dict(config={},records=[{'initial':i} for i in range(64)],next_n=320000002,fp=0,fn=0)
            j.atomic(root/'CHECKPOINT.json',cp)
            writer=j.Writer(root,json.loads(json.dumps(cp)))
            blob=b'new immutable journal'
            record=dict(path=str(root/'chunk_00064.npz'),sha256=hashlib.sha256(blob).hexdigest())
            state=dict(next_n=325000002,fp=0,fn=0)
            writer.add(record,blob,state)
            self.assertEqual(j.load(root)['next_n'],320000002)
            writer.flush();head=(root/'HEAD.json').read_bytes()
            self.assertEqual(j.load(root)['next_n'],325000002)
            # Crash after appending bytes but before publishing HEAD.
            with (root/'COMMITS.jsonl').open('ab') as f:f.write(b'{unpublished interrupted tail')
            self.assertEqual(j.load(root)['next_n'],325000002)
            resumed=j.Writer(root,j.load(root))
            self.assertEqual((root/'COMMITS.jsonl').stat().st_size,json.loads(head)['offset'])
            resumed.snapshot();self.assertEqual(j.load(root)['records'][-1],record)
            # Reconstruct from base snapshot, then reject corrupted published log.
            j.atomic(root/'CHECKPOINT.json',cp)
            path=root/'COMMITS.jsonl';raw=path.read_bytes();path.write_bytes(raw.replace(b'325000002',b'325000003'))
            with self.assertRaises(ValueError):j.load(root)

    def test_data_written_before_publishing_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cp=dict(config={},records=[],next_n=2,fp=0,fn=0)
            j.atomic(root/'CHECKPOINT.json',cp);writer=j.Writer(root,cp)
            record=dict(path=str(root/'chunk_00000.npz'),sha256=j.sha(b'data'))
            original=j.atomic
            def inspect(path,obj):
                if path.name=='HEAD.json' and obj['sequence']:
                    self.assertEqual(Path(record['path']).read_bytes(),b'data')
                    self.assertEqual((root/'COMMITS.jsonl').stat().st_size,obj['offset'])
                original(path,obj)
            j.atomic=inspect
            try:writer.add(record,b'data',dict(next_n=5000002,fp=0,fn=0))
            finally:j.atomic=original
            self.assertEqual(j.load(root)['next_n'],5000002)

if __name__=='__main__':unittest.main()
