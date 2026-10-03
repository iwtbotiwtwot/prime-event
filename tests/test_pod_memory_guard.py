"""Check that cache reclaim leaves application memory and protected file data alone."""
import errno
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pod_memory_guard as guard


class MemoryGuardTests(unittest.TestCase):
    def sample(self, headroom, **stats):
        return dict(headroom_bytes=headroom*guard.GIB, stats={key: value*guard.GIB for key, value in stats.items()})

    def test_does_not_reclaim_when_headroom_is_adequate(self):
        self.assertEqual(guard.requested_bytes(self.sample(32, file=40)), 0)

    def test_file_cache_ceiling_even_with_plenty_of_headroom(self):
        self.assertEqual(guard.requested_bytes(self.sample(200, file=60)), 16*guard.GIB)

    def test_checkpoint_pause_depends_on_non_file_memory(self):
        high=dict(limit_bytes=263*guard.GIB,stats=dict(anon=241*guard.GIB,kernel=2*guard.GIB,file=8*guard.GIB))
        cached=dict(limit_bytes=263*guard.GIB,stats=dict(anon=25*guard.GIB,kernel=2*guard.GIB,file=220*guard.GIB))
        self.assertTrue(guard.needs_pause(high))
        self.assertFalse(guard.needs_pause(cached))

    def test_batch_and_file_cache_floor(self):
        self.assertEqual(guard.requested_bytes(self.sample(20, file=100)), 16*guard.GIB)
        self.assertEqual(guard.requested_bytes(self.sample(20, file=12)), 4*guard.GIB)

    def test_anonymous_dirty_mapped_and_shared_memory_do_not_count_as_reclaimable(self):
        self.assertEqual(guard.requested_bytes(self.sample(1, anon=250, file=8)), 0)
        self.assertEqual(guard.requested_bytes(self.sample(1, file=40, shmem=8,
                         file_mapped=16, file_dirty=4, file_writeback=4)), 0)

    def test_reclaim_error_is_reported_without_a_less_restricted_retry(self):
        with patch.object(Path, 'open', side_effect=OSError(errno.EINVAL, 'Unsupported')) as opening, \
             patch.object(guard,'no_swap_available',return_value=False):
            result = guard.reclaim(Path('/disposable'), guard.GIB)
        self.assertEqual(result['status'], 'ERROR')
        self.assertEqual(opening.call_count, 1)

    def test_older_kernel_fallback_requires_verified_no_swap(self):
        successful=MagicMock()
        with patch.object(Path,'open',side_effect=[OSError(errno.EINVAL,'Unsupported'),successful]) as opening, \
             patch.object(guard,'no_swap_available',return_value=True):
            result=guard.reclaim(Path('/disposable'),guard.GIB)
        self.assertEqual(result['status'],'RECLAIMED')
        self.assertEqual(result['mode'],'verified_no_swap_fallback')
        self.assertEqual(opening.call_count,2)

    def test_partial_reclaim_is_retained(self):
        with patch.object(Path, 'open', side_effect=OSError(errno.EAGAIN, 'Partial reclaim')):
            result = guard.reclaim(Path('/disposable'), guard.GIB)
        self.assertEqual(result['status'], 'PARTIAL')


if __name__ == '__main__':
    unittest.main()
