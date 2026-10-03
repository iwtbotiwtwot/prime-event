"""Run the real archive checks in a separate storage-side Python process."""
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import pod_archive
import pod_t500_archive as archive


@unittest.skipUnless(shutil.which('zstd'),'zstd required')
class StorageVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name);root=base/'active';mirror=base/'mirror'
        (root/'data').mkdir(parents=True);(root/'source').mkdir();mirror.mkdir()
        raw=b'authenticated scientific history\n'*100
        journal=root/'data/chunk_00000.npz';journal.write_bytes(raw)
        cp=dict(config=dict(seed=42),next_n=5000002,
                records=[dict(path=str(journal),sha256=hashlib.sha256(raw).hexdigest())])
        (root/'data/CHECKPOINT.json').write_text(json.dumps(cp))
        (root/'source/source.py').write_text('# retained source\n')
        self.batch=pod_archive.prepare(root,mirror,1)
        self.mount=base/'mount';self.mount.mkdir()
        self.storage=base/'storage';self.storage.mkdir()
        self.path=self.mount/'batch.tar.zst.partial'
        self.stored=self.storage/self.path.name
        shutil.copyfile(self.batch['path'],self.stored)
        self.original_output=subprocess.check_output
        self.host='storage@localhost';self.calls=[];self.wrong_mount=False
        for name,value in [('MOUNT',self.mount),('T500_ROOT',self.storage),('T500_HOST',self.host)]:
            context=patch.object(archive,name,value);context.start();self.addCleanup(context.stop)

    def execute(self,command,**kwargs):
        self.calls.append(command)
        if command[0]=='findmnt':
            host='wrong@host' if self.wrong_mount else self.host
            line=f'fuse.sshfs {host}:{self.storage}\n'
            return line+line
        self.assertEqual(command[-2],self.host)
        # Execute the exact transmitted worker and verifier, with real zstd,
        # using disposable storage rather than an SSH connection.
        kwargs.setdefault('stderr',subprocess.PIPE)
        return self.original_output(shlex.split(command[-1]),**kwargs)

    def test_complete_archive_verified_without_reading_mounted_file(self):
        self.assertFalse(self.path.exists())
        with patch.object(archive.subprocess,'check_output',side_effect=self.execute):
            receipt=archive.verify_on_storage_host(self.path,self.batch)
        self.assertEqual(receipt['status'],'VERIFIED')
        self.assertEqual(receipt['sha256'],self.batch['sha256'])
        self.assertEqual(receipt['members_verified'],3)
        self.assertEqual(receipt['destination'],str(self.path))
        self.assertEqual(receipt['verification_host'],self.host)

    def test_corrupted_storage_copy_blocks_verification(self):
        data=self.stored.read_bytes();self.stored.write_bytes(b'X'+data[1:])
        with patch.object(archive.subprocess,'check_output',side_effect=self.execute):
            with self.assertRaises(subprocess.CalledProcessError):
                archive.verify_on_storage_host(self.path,self.batch)
        self.assertTrue(Path(self.batch['path']).exists())

    def test_mismatched_mount_blocks_storage_host_access(self):
        self.wrong_mount=True
        with patch.object(archive.subprocess,'check_output',side_effect=self.execute):
            with self.assertRaises(RuntimeError):
                archive.verify_on_storage_host(self.path,self.batch)
        self.assertEqual(len(self.calls),1)


if __name__=='__main__':unittest.main()
