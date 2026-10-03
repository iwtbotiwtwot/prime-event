"""Native planning and parallel marking of authenticated actual event history."""
import ctypes as C
import numpy as np

def bind(original, source, threads):
    lib=C.CDLL(str(source/'history_native.so'));u=C.c_uint64;v=C.c_void_p
    lib.history_plan.argtypes=[u,u,u];lib.history_plan.restype=v
    lib.history_size.argtypes=[v];lib.history_size.restype=u
    lib.history_ids.argtypes=[v,v];lib.history_free.argtypes=[v]
    lib.history_apply.argtypes=[v,v,v,v,v,C.c_int];lib.history_apply.restype=C.c_int
    class NativeHistory(original):
        def banks(self, first):
            count=5_000_000
            if not self.records:return np.zeros(count,np.uint8)
            plan=lib.history_plan(first,count,len(self.records))
            if not plan:raise RuntimeError('History planner requested unavailable records')
            try:
                ids=np.empty(lib.history_size(plan),np.uint64);lib.history_ids(plan,ids.ctypes.data)
                # Strong references keep arrays alive even if the LRU evicts them.
                arrays=[self.get(int(j)) for j in ids]
                pointers=np.array([a.ctypes.data for a in arrays],np.uint64)
                sizes=np.array([len(a) for a in arrays],np.uint64)
                ranks=np.array([self.records[int(j)]['rank'] for j in ids],np.uint64)
                banks=np.zeros(count,np.uint8)
                if lib.history_apply(plan,pointers.ctypes.data,sizes.ctypes.data,ranks.ctypes.data,banks.ctypes.data,threads):
                    raise RuntimeError('Native history marking failed')
                return banks
            finally:lib.history_free(plan)
    return NativeHistory
