"""Check container reserves as non-cache memory grows."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments/u5-throughput'))
from native_history import cache_allowance, GIB


class CacheBudgetTests(unittest.TestCase):
    def test_never_expands_past_configured_cache(self):
        self.assertEqual(cache_allowance(16*GIB,8*GIB,18*GIB,2*GIB,263*GIB),16*GIB)

    def test_metadata_growth_shrinks_decoded_cache(self):
        self.assertEqual(cache_allowance(192*GIB,100*GIB,160*GIB,2*GIB,263*GIB),153*GIB)

    def test_irreducible_overhead_does_not_create_a_negative_allowance(self):
        self.assertEqual(cache_allowance(192*GIB,0,250*GIB,2*GIB,263*GIB),0)

    def test_small_containers_use_a_proportional_reserve(self):
        self.assertEqual(cache_allowance(8*GIB,GIB,3*GIB,GIB//2,10*GIB),11*GIB//2)


if __name__=='__main__':unittest.main()
