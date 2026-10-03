"""Native planning and parallel marking of authenticated actual event history."""
import ctypes as C
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
import numpy as np

GIB=1024**3

def cache_allowance(configured, cached, anonymous, kernel, limit):
    """Charge non-cache application memory before budgeting decoded history."""
    reserve=min(48*GIB,max(2*GIB,limit//5))
    overhead=max(0,anonymous+kernel-cached)
    return max(0,min(configured,limit-reserve-overhead))

def bind(original, source, threads, decode_workers=8):
    lib=C.CDLL(str(source/'history_native.so'));u=C.c_uint64;v=C.c_void_p
    lib.history_plan.argtypes=[u,u,u];lib.history_plan.restype=v
    lib.history_size.argtypes=[v];lib.history_size.restype=u
    lib.history_ids.argtypes=[v,v];lib.history_free.argtypes=[v]
    lib.history_apply_offsets.argtypes=[v,v,v,v,v,C.c_int];lib.history_apply_offsets.restype=C.c_int
    lib.history_timings.argtypes=[v]
    globals_=original.get.__globals__
    unpack=globals_.get('unpack');sha=globals_.get('sha')
    class NativeHistory(original):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self._loader=None;self.last_stats={}
            self.configured_limit=self.limit;self._budget_calls=0
            self.rebudget()
        def rebudget(self):
            try:
                cgroup=Path('/sys/fs/cgroup')
                limit=int((cgroup/'memory.max').read_text())
                stats=dict((k,int(v)) for k,v in
                           (line.split() for line in (cgroup/'memory.stat').read_text().splitlines()))
            except (OSError,ValueError):return
            self.limit=cache_allowance(self.configured_limit,self.bytes,stats['anon'],stats['kernel'],limit)
            while self.cache and self.bytes>self.limit:
                _,old=self.cache.popitem(last=False);self.bytes-=old.nbytes;self.evictions+=1
        def counters(self):
            values=super().counters()
            values.update(cache_limit_bytes=self.limit,configured_cache_limit_bytes=self.configured_limit)
            return values
        def close(self):
            if self._loader is not None:
                self._loader.shutdown();self._loader=None
        def compact(self,j,events):
            if events.dtype==np.uint32:return events
            first=2+j*5_000_000
            if len(events) and (int(events[0])<first or int(events[-1])>=first+5_000_000):
                raise ValueError('History event outside its authenticated chunk')
            return (events-np.uint64(first)).astype(np.uint32)
        def _decode(self,j):
            record=self.records[j];raw=Path(record['path']).read_bytes()
            if sha(raw)!=record['sha256']:raise ValueError('History digest mismatch')
            meta,events=unpack(raw)
            if len(events)!=record['count'] or meta.get('first',meta.get('first_n'))!=record['first']:
                raise ValueError('History record mismatch')
            return self.compact(j,events),len(raw)
        def _touch(self,j,events):
            if j in self.cache:self.bytes-=self.cache.pop(j).nbytes
            while self.cache and self.bytes+events.nbytes>self.limit:
                _,old=self.cache.popitem(last=False);self.bytes-=old.nbytes;self.evictions+=1
            if events.nbytes<=self.limit:
                self.cache[j]=events;self.bytes+=events.nbytes;self.peak=max(self.peak,self.bytes)
        def get(self,j):
            if unpack and sha and 'path' in self.records[j]:
                if j in self.cache:
                    self.hits+=1;events=self.cache.pop(j);self.cache[j]=events;return events
                self.misses+=1;events,size=self._decode(j);self.read_bytes+=size
                self._touch(j,events);return events
            # Preserve support for custom in-memory histories and test oracles.
            absolute=super().get(j)
            compact=self.compact(j,absolute)
            if compact is not absolute and j in self.cache and self.cache[j] is absolute:
                self.cache[j]=compact;self.bytes+=compact.nbytes-absolute.nbytes
            return compact
        def _arrays(self,ids):
            self._budget_calls+=1
            if self._budget_calls%128==0:self.rebudget()
            ids=[int(j) for j in ids]
            if not (unpack and sha) or not all('path' in self.records[j] for j in ids):
                return [self.get(j) for j in ids]
            # Strong references retain every hit even if inserting another
            # required record evicts it. Only this caller mutates LRU state.
            ready={j:self.cache[j] for j in ids if j in self.cache}
            missing=[j for j in ids if j not in ready]
            if len(missing)<2:return [self.get(j) for j in ids]
            if self._loader is None:self._loader=ThreadPoolExecutor(max_workers=decode_workers)
            jobs={j:self._loader.submit(self._decode,j) for j in missing}
            arrays=[]
            for j in ids:
                if j in ready:self.hits+=1;events=ready[j]
                else:
                    events,size=jobs[j].result();self.misses+=1;self.read_bytes+=size
                self._touch(j,events);arrays.append(events)
            return arrays
        def required_ids(self, first):
            plan=lib.history_plan(first,5_000_000,len(self.records))
            if not plan:raise RuntimeError('History planner requested unavailable records')
            try:
                ids=np.empty(lib.history_size(plan),np.uint64);lib.history_ids(plan,ids.ctypes.data)
                return ids.tolist()
            finally:lib.history_free(plan)
        def banks(self, first):
            count=5_000_000
            if not self.records:return np.zeros(count,np.uint8)
            plan=lib.history_plan(first,count,len(self.records))
            if not plan:raise RuntimeError('History planner requested unavailable records')
            try:
                ids=np.empty(lib.history_size(plan),np.uint64);lib.history_ids(plan,ids.ctypes.data)
                # Strong references keep arrays alive even if the LRU evicts them.
                before=self.counters();started=time.perf_counter();arrays=self._arrays(ids)
                get_seconds=time.perf_counter()-started
                pointers=np.array([a.ctypes.data for a in arrays],np.uint64)
                sizes=np.array([len(a) for a in arrays],np.uint64)
                ranks=np.array([self.records[int(j)]['rank'] for j in ids],np.uint64)
                banks=np.zeros(count,np.uint8)
                if lib.history_apply_offsets(plan,pointers.ctypes.data,sizes.ctypes.data,ranks.ctypes.data,banks.ctypes.data,threads):
                    raise RuntimeError('Native history marking failed')
                phases=np.empty(5,np.float64);lib.history_timings(phases.ctypes.data)
                after=self.counters()
                self.last_stats=dict(records=len(ids),get_seconds=get_seconds,
                    native_seconds=phases.tolist(),cache_bytes=after['cache_bytes'],
                    cache_limit_bytes=self.limit,configured_cache_limit_bytes=self.configured_limit,
                    misses=after['misses']-before['misses'],evictions=after['evictions']-before['evictions'])
                return banks
            finally:lib.history_free(plan)
    return NativeHistory
