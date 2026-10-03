"""Exact accelerators for bounded u5 pilots; source/RNG semantics stay frozen."""
import ctypes as C
import os
import time
from pathlib import Path
import numpy as np

class Accelerator:
    def __init__(self, path, original, backend, threads):
        self.original, self.backend, self.threads = original, backend, threads
        self.mark, self.index = original.mark, original.index
        self.cdf = np.load(path / 'u5_cdf.npy')
        a = self.cdf.reshape(140,128,128)
        self.row = a[:,0,:].copy()
        self.low, self.high = a.min(axis=1), a.max(axis=1)
        self.lut = np.array([np.searchsorted(r,np.arange(4097)/4096,side='right') for r in self.row],np.uint16)
        self.lib = C.CDLL(str(path / 'accelerator.so'))
        u,v,i = C.c_uint64,C.c_void_p,C.c_int
        self.lib.propose.argtypes = [u,u]+[v]*8+[i]
        self.lib.propose.restype = None
        self.lib.consume.argtypes = [u,u]+[v]*6+[u,v,v,v]
        self.lib.consume.restype = i
        self.lib.sieve.argtypes = [u,u,v,i]
        self.lib.sieve.restype = None
        self.lib.grade.argtypes = [u,u]+[v]*5
        self.lib.grade.restype = None
        self.lib.mark_parallel.argtypes = [u,u,v,u,u,v,i]
        self.lib.mark_parallel.restype = i
        self.mark = lambda first,count,periods,size,rank,banks: self.lib.mark_parallel(first,count,periods,size,rank,banks,min(8,self.threads))
        self.counters = np.zeros(2,np.uint64)
        self.out = np.empty(5_000_000,np.uint32)
        self.timings = []
        if backend == 'gpu':
            self.gpu = C.CDLL(str(path / 'accelerator_gpu.so'))
            self.gpu.gpu_init.argtypes = [v]*4
            self.gpu.gpu_propose.argtypes = [u,u]+[v]*4
            self.check(self.gpu.gpu_init(*[x.ctypes.data for x in [self.row,self.low,self.high,self.lut]]))
    @staticmethod
    def check(code):
        if code: raise RuntimeError(f'CUDA error {code}')
    def advance(self, first,count,cdf,base,extra,banks,emit,prefix,prefix_count,status):
        # Only the initial window has newly created returns throughout the window.
        if first == 2:
            return self.original.advance(first,count,cdf,base,extra,banks,emit,prefix,prefix_count,status)
        if count > len(self.out): self.out = np.empty(count,np.uint32)
        t = time.perf_counter()
        if self.backend == 'gpu':
            self.check(self.gpu.gpu_propose(first,count,base,extra,banks,self.out.ctypes.data))
        else:
            self.lib.propose(first,count,*[x.ctypes.data for x in [self.row,self.low,self.high,self.lut]],base,extra,banks,self.out.ctypes.data,self.threads)
        proposal_time = time.perf_counter()-t
        t = time.perf_counter()
        result = self.lib.consume(first,count,cdf,base,extra,banks,emit,prefix,prefix_count,status,self.out.ctypes.data,self.counters.ctypes.data)
        self.timings.append(dict(first=first,proposal=proposal_time,consume=time.perf_counter()-t))
        return result
    def truth(self, first, count=5_000_000):
        result = np.empty(count,np.bool_)
        self.lib.sieve(first,count,result.ctypes.data,self.threads)
        return result
