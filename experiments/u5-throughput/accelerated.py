"""Exact accelerators for bounded u5 pilots; source/RNG semantics stay frozen."""
import ctypes as C
import os
import time
from pathlib import Path
import numpy as np

class SelectedGPU:
    """Restore this role's CUDA device on every calling worker thread."""
    def __init__(self,lib,device):
        self.lib,self.device=lib,device
        self.lib.gpu_select.argtypes=[C.c_int]
    def _call(self,name,*args):
        Accelerator.check(self.lib.gpu_select(self.device))
        return getattr(self.lib,name)(*args)
    def gpu_pin(self,*args):return self._call('gpu_pin',*args)
    def gpu_unpin(self,*args):return self._call('gpu_unpin',*args)
    def gpu_propose(self,*args):return self._call('gpu_propose',*args)

class Accelerator:
    def __init__(self, path, original, backend, threads,proposal_gpu=0,
                 history_gpu=None,grade_gpu=None,gpu_cache_mib=16384):
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
        self.history_threads = threads
        self.history_gpu,self.gpu_cache_mib=history_gpu,gpu_cache_mib
        self.role_cleanups=[]
        self._pinned = {}
        if backend == 'gpu':
            self.gpu = C.CDLL(str(path / 'accelerator_gpu.so'))
            self.gpu.gpu_init.argtypes = [v]*4
            self.gpu.gpu_propose.argtypes = [u,u]+[v]*4
            self.gpu.gpu_pin.argtypes = [v,u]
            self.gpu.gpu_unpin.argtypes = [v]
            self.gpu.gpu_select.argtypes = [i]
            self.check(self.gpu.gpu_select(proposal_gpu))
            self.check(self.gpu.gpu_init(*[x.ctypes.data for x in [self.row,self.low,self.high,self.lut]]))
            self.gpu=SelectedGPU(self.gpu,proposal_gpu)
        if grade_gpu is not None:
            from gpu_roles import GPUGrade
            self.lib=GPUGrade(self.lib,grade_gpu)
            self.role_cleanups.append(self.lib.close)
    @staticmethod
    def check(code):
        if code: raise RuntimeError(f'CUDA error {code}')
    def pin(self, array):
        if self.backend != 'gpu': return
        address = array.ctypes.data
        if address not in self._pinned:
            self.check(self.gpu.gpu_pin(address,array.nbytes))
            # Keep the allocation alive until its registration is removed.
            self._pinned[address] = array
        elif self._pinned[address].nbytes != array.nbytes:
            raise RuntimeError('Registered GPU buffer changed size')
    def close(self):
        while self.role_cleanups:self.role_cleanups.pop()()
        if self.backend == 'gpu':
            for address in list(self._pinned):
                self.check(self.gpu.gpu_unpin(address))
                del self._pinned[address]
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
