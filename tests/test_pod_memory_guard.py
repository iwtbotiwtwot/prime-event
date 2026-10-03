"""Check that cache reclaim leaves application memory and protected file data alone."""
import errno
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pod_memory_guard as guard


class MemoryGuardTests(unittest.TestCase):
    def sample(self, headroom, **stats):
        return dict(headroom_bytes=headroom*guard.GIB, stats={key: value*guard.GIB for key, value in stats.items()})

    def test_does_not_reclaim_when_headroom_is_adequate(self):
        self.assertEqual(guard.requested_bytes(self.sample(32, file=100)), 0)

    def test_batch_and_file_cache_floor(self):
        self.assertEqual(guard.requested_bytes(self.sample(20, file=100)), 16*guard.GIB)
        self.assertEqual(guard.requested_bytes(self.sample(20, file=12)), 4*guard.GIB)

    def test_anonymous_dirty_mapped_and_shared_memory_do_not_count_as_reclaimable(self):
        self.assertEqual(guard.requested_bytes(self.sample(1, anon=250, file=8)), 0)
        self.assertEqual(guard.requested_bytes(self.sample(1, file=40, shmem=8,
                         file_mapped=16, file_dirty=4, file_writeback=4)), 0)

    def test_reclaim_error_is_reported_without_a_less_restricted_retry(self):
        with patch.object(Path, 'open', side_effect=OSError(errno.EINVAL, 'Unsupported')) as opening:
            result = guard.reclaim(Path('/disposable'), guard.GIB)
        self.assertEqual(result['status'], 'ERROR')
        self.assertEqual(opening.call_count, 1)

    def test_partial_reclaim_is_retained(self):
        with patch.object(Path, 'open', side_effect=OSError(errno.EAGAIN, 'Partial reclaim')):
            result = guard.reclaim(Path('/disposable'), guard.GIB)
        self.assertEqual(result['status'], 'PARTIAL')


if __name__ == '__main__':
    unittest.main()
