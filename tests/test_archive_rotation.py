"""Destructive cleanup gates and archive recovery, using disposable small files."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
import pod_archive as a
from verify_pod_archive import verify

@unittest.skipUnless(shutil.which('zstd'),'zstd required')
class ArchiveTests(unittest.TestCase):
    def test_verify_before_cleanup_recovery_and_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'active';mirror=Path(temp)/'mirror'
            (root/'data').mkdir(parents=True);(root/'source').mkdir();(mirror/'data').mkdir(parents=True)
            raw=b'original scientific journal\n'*100
            file=root/'data/chunk_00000.npz';file.write_bytes(raw);copy=mirror/'data'/file.name;copy.write_bytes(raw)
            cp=dict(config=dict(seed=42),records=[dict(path=str(file),sha256=hashlib.sha256(raw).hexdigest())],next_n=5000002)
            (root/'data/CHECKPOINT.json').write_text(json.dumps(cp));(root/'source/source.py').write_text('# immutable source\n')
            self.assertEqual(a.prepare(root,mirror,100*1024**3)['status'],'WAITING')
            batch=a.prepare(root,mirror,1);archive=Path(batch['path'])
            # Simulate termination between archive rename and ledger commit.
            a.atomic(root/'archive_state/INDEX.json',dict(next_chunk=0,batches=[]))
            recovered=a.prepare(root,mirror,1);self.assertEqual(recovered['sha256'],batch['sha256'])
            receipt=verify(archive,batch)
            bad=dict(receipt,sha256='0'*64)
            with self.assertRaises(ValueError):a.acknowledge(root,mirror,bad)
            self.assertTrue(copy.exists());self.assertTrue(archive.exists());self.assertEqual(file.read_bytes(),raw)
            # Outer checksum alone cannot certify corrupted inner content.
            decoded=subprocess.check_output(['zstd','-q','-d','-c',str(archive)]);changed=io.BytesIO()
            with tarfile.open(fileobj=io.BytesIO(decoded)) as src,tarfile.open(fileobj=changed,mode='w') as dst:
                for member in src:
                    content=src.extractfile(member).read()
                    if member.name=='data/chunk_00000.npz':content=b'X'+content[1:]
                    dst.addfile(member,io.BytesIO(content))
            corrupt=archive.with_name('corrupt.tar.zst');corrupt.write_bytes(subprocess.check_output(['zstd','-q','-c'],input=changed.getvalue()))
            altered=dict(batch,sha256=a.file_sha(corrupt),bytes=corrupt.stat().st_size)
            with self.assertRaises(ValueError):verify(corrupt,altered)
            # A symlinked backup directory must not turn cleanup into deletion
            # of active history, even though content hashes would match.
            (mirror/'data').rename(mirror/'saved-data');(mirror/'data').symlink_to(root/'data',target_is_directory=True)
            with self.assertRaises(RuntimeError):a.acknowledge(root,mirror,receipt)
            self.assertEqual(file.read_bytes(),raw)
            (mirror/'data').unlink();(mirror/'saved-data').rename(mirror/'data')
            result=a.acknowledge(root,mirror,receipt)
            self.assertEqual(result['status'],'CLEANED');self.assertFalse(copy.exists());self.assertFalse(archive.exists())
            self.assertEqual(file.read_bytes(),raw)
            self.assertEqual(a.acknowledge(root,mirror,receipt)['status'],'CLEANED')
            self.assertEqual(a.prepare(root,mirror,1)['status'],'WAITING')

if __name__=='__main__':unittest.main()
