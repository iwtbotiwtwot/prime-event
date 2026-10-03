"""Explicit GPU roles; authenticated CPU decoding owns the host history cache."""
import ctypes as C
from collections import OrderedDict
from pathlib import Path
import time
import numpy as np
from native_history import bind
ROOT=Path(__file__).resolve().parent

class GPUGrade:
    def __init__(self,original,device=2):
        self.original=original
        self.closed=False
        self.gpu=C.CDLL(str(ROOT/'gpu_grade.so'))
        self.gpu.gg_init.argtypes=[C.c_int]
        self.gpu.gg_grade.argtypes=[C.c_uint64,C.c_uint64]+[C.c_void_p]*5
        self.gpu.gg_close.argtypes=[]
        self.check(self.gpu.gg_init(device))
    @staticmethod
    def check(code):
        if code:raise RuntimeError(f'GPU role CUDA error {code}')
    def grade(self,*args):self.check(self.gpu.gg_grade(*args))
    def __getattr__(self,name):return getattr(self.original,name)
    def close(self):
        if not self.closed:self.check(self.gpu.gg_close());self.closed=True

def gpu_history_class(original,source,threads,workers,device=1,device_cache_bytes=16*1024**3):
    native=bind(original,source,threads,workers)
    planner=C.CDLL(str(ROOT/'history_gpu_plan.so'))
    u,p=C.c_uint64,C.c_void_p
    planner.history_plan.argtypes=[u,u,u];planner.history_plan.restype=p
    planner.history_size.argtypes=[p];planner.history_size.restype=u
    planner.history_ids.argtypes=[p,p]
    planner.history_range_count.argtypes=[p];planner.history_range_count.restype=u
    planner.history_ranges.argtypes=[p,p];planner.history_free.argtypes=[p]
    gpu=C.CDLL(str(ROOT/'gpu_history.so'))
    gpu.gh_init.argtypes=[C.c_int,u]
    gpu.gh_put.argtypes=[u,p,u,u,u]
    gpu.gh_drop.argtypes=[u]
    gpu.gh_apply.argtypes=[u,u,p,u,u,p]
    gpu.gh_close.argtypes=[]
    class GPUHistory(native):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.device_cache=OrderedDict();self.device_bytes=0
            self.device_misses=0;self.device_evictions=0
            self.released=False
            self.check(gpu.gh_init(device,len(self.records)))
        @staticmethod
        def check(code):
            if code:raise RuntimeError(f'GPU history CUDA error {code}')
        def banks(self,first):
            count=5_000_000
            if not self.records:return np.zeros(count,np.uint8)
            started=time.perf_counter();plan=planner.history_plan(first,count,len(self.records))
            if not plan:raise RuntimeError('GPU history planner requested unavailable records')
            planning=time.perf_counter()-started
            try:
                ids=np.empty(planner.history_size(plan),np.uint64)
                planner.history_ids(plan,ids.ctypes.data)
                keys=list(map(int,ids));needed=set(keys)
                # Resident device records were already authenticated at upload.
                # Load only new uploads and the tiny-period host search record.
                load_ids=[j for j in keys if j not in self.device_cache]
                if keys[0] not in load_ids:load_ids.insert(0,keys[0])
                before=self.counters();tick=time.perf_counter()
                arrays=dict(zip(load_ids,self._arrays(load_ids)))
                getting=time.perf_counter()-tick
                uploads=0
                tick=time.perf_counter()
                for j in keys:
                    if j in self.device_cache:
                        self.device_cache.move_to_end(j);continue
                    array=arrays[j]
                    while self.device_bytes+array.nbytes>device_cache_bytes:
                        evict=next((key for key in self.device_cache if key not in needed),None)
                        if evict is None:raise MemoryError('Required history exceeds the device cache')
                        size=self.device_cache.pop(evict);self.check(gpu.gh_drop(evict))
                        self.device_bytes-=size;self.device_evictions+=1
                    record=self.records[j]
                    self.check(gpu.gh_put(j,array.ctypes.data,len(array),record['rank'],record['first']))
                    self.device_cache[j]=array.nbytes;self.device_bytes+=array.nbytes
                    self.device_misses+=1;uploads+=1
                upload_seconds=time.perf_counter()-tick
                ranges=np.empty((planner.history_range_count(plan),4),np.uint64)
                planner.history_ranges(plan,ranges.ctypes.data)
                tiny=int(np.searchsorted(arrays[keys[0]],4094,side='right'))
                banks=np.empty(count,np.uint8);tick=time.perf_counter()
                self.check(gpu.gh_apply(first,count,ranges.ctypes.data,len(ranges),tiny,banks.ctypes.data))
                marking=time.perf_counter()-tick
                after=self.counters()
                self.last_stats=dict(records=len(ids),get_seconds=getting,
                    native_seconds=[planning,0,0,marking,0],cache_bytes=after['cache_bytes'],
                    cache_limit_bytes=self.limit,configured_cache_limit_bytes=self.configured_limit,
                    misses=after['misses']-before['misses'],evictions=after['evictions']-before['evictions'],
                    host_requested_records=len(load_ids),host_gpu_hits_skipped=len(keys)-len(load_ids),
                    gpu_upload_seconds=upload_seconds,gpu_uploads=uploads,
                    gpu_cache_bytes=self.device_bytes,gpu_cache_evictions=self.device_evictions,
                    gpu_mark_seconds=marking,range_count=len(ranges))
                return banks
            finally:planner.history_free(plan)
        def release_device(self):
            if not self.released:self.check(gpu.gh_close());self.released=True
    return GPUHistory
