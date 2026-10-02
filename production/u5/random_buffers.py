"""Reusable RAM and exact disjoint subsequences of the original PCG64 streams."""
from concurrent.futures import ThreadPoolExecutor
import numpy as np

class RandomBuffers:
 def __init__(self,workers=6):
  # The pinned NumPy build marks large allocations for transparent huge pages.
  # Avoid allocation-time compaction; this does not change generated values.
  np.core.multiarray._set_madvise_hugepage(False)
  self.workers=workers;self.pool=ThreadPoolExecutor(max_workers=workers)
  self.capacity=0;self.u=self.v=None
 @staticmethod
 def fill(state,offset,out):
  bg=np.random.PCG64(0);bg.state=state;bg.advance(offset);np.random.Generator(bg).random(out=out)
 def draw(self,base,extra,count):
  if count>self.capacity:
   self.capacity=count;self.u=np.empty(count,np.float64);self.v=np.empty(2*count,np.float64)
  u=self.u[:count];v=self.v[:2*count]
  if count<65536:
   base.random(out=u);extra.random(out=v)
  else:
   work=[]
   for generator,array in [(base,u),(extra,v)]:
    state=generator.bit_generator.state;assert state['bit_generator']=='PCG64' and state['has_uint32']==0
    for i in range(self.workers):
     lo=len(array)*i//self.workers;hi=len(array)*(i+1)//self.workers
     work.append(self.pool.submit(self.fill,state,lo,array[lo:hi]))
   for f in work:f.result()
   base.bit_generator.advance(count);extra.bit_generator.advance(2*count)
  return u,v.reshape(count,2)
 def close(self):self.pool.shutdown()
