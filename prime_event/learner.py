"""Independent per-seed, prequential calibration of the frozen event gate.

Features are available before reference labels: two return-bank bits and the
source gate's decision. No integer identity, primality label or other seed's
future observations enter prediction. Labels train only after prediction.
"""
import hashlib,json
import numpy as np

class OnlineGate:
 VERSION='BANK_GATE_PREQUENTIAL_V1'
 def __init__(self,saved=None):
  self.counts=np.zeros((8,2),np.uint64);self.trained=0;self.evaluated=0;self.fp=self.fn=self.veto_fp=self.veto_fn=0;self.chunks=0;self.first_n=None
  if saved:
   assert saved['version']==self.VERSION
   self.counts=np.array(saved['counts'],np.uint64)
   for key in ['trained','evaluated','fp','fn','veto_fp','veto_fn','chunks','first_n']:setattr(self,key,saved[key])
 def snapshot(self):
  return {'version':self.VERSION,'counts':self.counts.tolist(),**{key:getattr(self,key) for key in ['trained','evaluated','fp','fn','veto_fp','veto_fn','chunks','first_n']}}
 def predict(self,banks,emit):
  # Hierarchical empirical calibration: the bank-only parent pools both gate
  # outcomes; each leaf receives fixed strength32 of this past-only parent.
  parent=self.counts.reshape(4,2,2).sum(axis=1).astype(np.float64)
  prior=(parent[:,1]+1)/(parent.sum(axis=1)+2)
  probabilities=(self.counts[:,1]+32*np.repeat(prior,2))/(self.counts.sum(axis=1)+32)
  decisions=(probabilities>=.5).astype(np.uint8)
  if self.trained==0:decisions=np.tile(np.array([0,1],np.uint8),4)
  keys=banks*2+emit
  prediction=decisions[keys]
  return keys,prediction,{'trained_before':self.trained,'model_before_sha256':hashlib.sha256(json.dumps(self.snapshot(),sort_keys=True).encode()).hexdigest(),'probabilities':probabilities.tolist(),'decisions':decisions.tolist(),'warmup':self.trained==0}
 def observe(self,first,keys,prediction,emit,banks,truth,before):
  def score(a):
   wrong=np.flatnonzero(a.astype(bool)!=truth)
   return {'fp':int(np.count_nonzero(a&~truth)),'fn':int(np.count_nonzero((a==0)&truth)), 'errors':[{'index':int(first+k),'kind':'missed_prime' if truth[k] else 'composite_emission'} for k in wrong]}
  result=score(prediction);veto=score(emit&(banks==0));result.update(before)
  result.update({'version':self.VERSION,'first_n':first,'count':len(emit),'prediction_sha256':hashlib.sha256(np.packbits(prediction,bitorder='little').tobytes()).hexdigest(),'fixed_veto':veto})
  counts=np.bincount(keys.astype(np.int64)*2+truth.astype(np.int64),minlength=16).reshape(8,2).astype(np.uint64)
  self.counts+=counts;self.trained+=len(emit);self.chunks+=1
  if self.first_n is None:self.first_n=first
  if not before['warmup']:
   self.evaluated+=len(emit);self.fp+=result['fp'];self.fn+=result['fn'];self.veto_fp+=veto['fp'];self.veto_fn+=veto['fn']
  result['training_counts']=counts.tolist();result['model_after']=self.snapshot()
  return result
