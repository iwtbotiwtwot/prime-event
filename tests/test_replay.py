import hashlib,json,tempfile,unittest
from pathlib import Path
import numpy as np
from prime_event.engine import Engine,Guard,StopRequested,disk_state,build,repair_periods
from prime_event.source import prepare
from prime_event.learner import OnlineGate

class ReplayTests(unittest.TestCase):
 def test_scalar_replay_restart_both_sources_and_profiles(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);binary=build(root/'build');guard=Guard(root,disk_state(root)['device'],reserve=0,probe=lambda _: {'device':disk_state(root)['device'],'available':10**12,'total':2*10**12})
   for source in ['baseline','balanced']:
    package=prepare(source,root/source)
    for profile in ['uniform','rough']:
     seed=1000063;path=root/(source+'_'+profile);e=Engine(path,seed,profile,1000,package,binary,guard,cache_bytes=16)
     table=np.load(package/'data'/f'cdf_{profile}.npy');initial=np.load(package/'data/initial_cdf.npy');base=np.random.default_rng(seed);extra=np.random.default_rng(seed+1000000);state=int(np.searchsorted(initial,base.random(),side='right'));events=[];checksum=1469598103934665603
     for batch in range(3):
      u=base.random(1000);v=extra.random((1000,2));emit=[];bank_array=[]
      for k in range(1000):
       n=2+batch*1000+k;bits=0
       for rank,p in enumerate(events):
        if n%p==0:bits|=1<<(rank%2)
       accept=True;bank_array.append(bits)
       for reading in [v[k,0],v[k,1],u[k]]:
        state=int(np.flatnonzero(table[(n-2)%35,bits,state]>reading)[0]);checksum=((checksum^state)*1099511628211)&((1<<64)-1);accept &= state%2==0
       emit.append(accept)
       if accept:events.append(n)
      e.step();meta,periods=e.read_chunk(e.records[-1][0]);expected=np.flatnonzero(emit).astype(np.uint64)+2+batch*1000
      np.testing.assert_array_equal(periods,expected);self.assertEqual(meta['bank_sha256'],hashlib.sha256(np.array(bank_array,np.uint8).tobytes()).hexdigest());self.assertEqual(e.status.tolist(),[state,len(events),checksum]);self.assertEqual(e.base.bit_generator.state,base.bit_generator.state);self.assertEqual(e.extra.bit_generator.state,extra.bit_generator.state)
      if batch==0:e=Engine(path,seed,profile,1000,package,binary,guard,cache_bytes=16)
 def test_disk_guard_and_repair(self):
  for free,writing,reserve in [(100,0,0),(99,0,0),(120,15,10)]:
   g=Guard('.',1,reserve=reserve,probe=lambda _,f=free:{'device':1,'available':f,'total':1000})
   with self.assertRaises(StopRequested):g.check(writing)
  p=repair_periods(np.array([2,3,4,7],np.uint64),[{'index':4,'kind':'composite_emission'},{'index':5,'kind':'missed_prime'}]);self.assertEqual(p.tolist(),[2,3,5,7])
 def test_learner_predict_before_train(self):
  model=OnlineGate();banks=np.array([0,1,2,3],np.uint8);emit=np.array([1,1,0,1],np.uint8);saved=model.snapshot();keys,pred,before=model.predict(banks,emit);self.assertEqual(saved,model.snapshot());np.testing.assert_array_equal(pred,emit)
  model.observe(2,keys,pred,emit,banks,np.array([True,False,False,False]),before);self.assertEqual(model.evaluated,0);self.assertEqual(model.predict(banks,emit)[1].tolist(),[1,0,0,0]);self.assertEqual(OnlineGate(model.snapshot()).snapshot(),model.snapshot())
if __name__=='__main__':unittest.main()
