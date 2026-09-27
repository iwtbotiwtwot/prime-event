"""Frozen binary64 tables and independently executable source construction."""
import gzip,hashlib,json,math,os,uuid
from pathlib import Path
import numpy as np
ROOT=Path(__file__).parent/'sources'
def digest(data):return hashlib.sha256(data).hexdigest()
def prepare(name,destination):
 src=ROOT/name;dest=Path(destination);dest.mkdir(parents=True,exist_ok=True)
 record=json.loads((src/'SOURCE.json').read_text())
 for relative,wanted in record['data_files'].items():
  path=dest/relative;path.parent.mkdir(parents=True,exist_ok=True)
  if path.exists():
   if digest(path.read_bytes())!=wanted:raise ValueError(f'Source hash mismatch: {path}')
   continue
  raw=gzip.decompress((src/(Path(relative).name+'.gz')).read_bytes())
  if digest(raw)!=wanted:raise ValueError('Frozen source archive hash mismatch')
  tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_bytes(raw);os.replace(tmp,path)
 (dest/'SOURCE.json').write_bytes((src/'SOURCE.json').read_bytes())
 return dest

def reconstruct(name,destination):
 """Rebuild from the documented microscopic model. Frozen tables pin replay."""
 recipe=json.loads((ROOT/'RECIPE.json').read_text());src=recipe['mixed_source'];out=Path(destination);out.mkdir(parents=True,exist_ok=False)
 pair=4.;triple=2.
 if name=='balanced':
  a=math.log(math.cosh(8))/2
  def field(t):return (4*math.log(math.cosh(2*t))-math.log(math.cosh(4*t)))/2
  lo,hi=2.,3.
  for _ in range(64):
   mid=(lo+hi)/2
   if field(mid)<a:lo=mid
   else:hi=mid
  triple=(lo+hi)/2
 W=np.array(src['patterns'],float);h=np.array(src['hidden_fields'],float);W[:2]*=pair;h[:2]*=pair;W[2:]*=triple;h[2:]*=triple
 states=np.array([[1 if n>>j&1 else -1 for j in range(7)] for n in range(128)]);models={};cache={}
 for bits in range(4):
  i=1 if bits&1 else -1;j=1 if bits&2 else -1;b=np.column_stack([states[:,0],np.full(128,i),np.full(128,j),np.ones(128)])
  E=-np.sum(states[:,1:]*(b@W.T+h),axis=1);Q=np.zeros((128,128))
  for n in range(128):
   for bit in range(7):
    z=n^(1<<bit);Q[z,n]=1/(1+math.exp(float(E[z]-E[n])))
   Q[n,n]=-sum(Q[:,n])
  pi=np.exp(-(E-E.min()));pi/=sum(pi) if name=='baseline' else pi.sum();models[bits]=(Q,pi)
 def transition(bits,duration):
  key=(bits,float(duration).hex())
  if key in cache:return cache[key]
  Q=models[bits][0];lam=max(-np.diag(Q));s=max(0,math.ceil(math.log2(lam*duration)));mu=lam*duration/2**s;B=np.eye(128)+Q/lam;term=np.eye(128);weight=math.exp(-mu);T=weight*term
  for k in range(1,100):
   term=B@term;weight*=mu/k;T+=weight*term;nw=weight*mu/(k+1);tail=nw/(1-mu/(k+2))
   if tail*2**s<1e-17:break
  else:raise ArithmeticError('Uniformization did not converge')
  for _ in range(s):T=T@T
  if T.min()<0 or np.max(abs(T.sum(axis=0)-1))>=1e-9:raise ArithmeticError('Invalid transition matrix')
  T/=T.sum(axis=0);cache[key]=T;return T
 for profile in recipe['profiles']:
  cdf=np.empty((35,4,128,128))
  for phase,x in enumerate(profile['exposure']):
   for bits in range(4):
    T=transition(bits,512*float(x)/3);C=np.cumsum(T,axis=0);C[-1]=1.;cdf[phase,bits]=C.T
  np.save(out/f'cdf_{profile["name"]}.npy',cdf)
 initial=np.cumsum(models[0][1]);initial[-1]=1.;np.save(out/'initial_cdf.npy',initial)
 comparisons={}
 import io
 for f in sorted(out.glob('*.npy')):
  frozen=gzip.decompress((ROOT/name/(f.name+'.gz')).read_bytes());a=np.load(io.BytesIO(frozen));b=np.load(f)
  comparisons[f.name]={'bitwise_file_match':digest(f.read_bytes())==digest(frozen),'max_abs_difference':float(np.max(abs(a-b))),'reconstructed_sha256':digest(f.read_bytes()),'frozen_sha256':digest(frozen)}
 report={'source':name,'pair_strength':pair,'triple_strength':triple,'numpy':np.__version__,'comparisons':comparisons,'note':'BLAS/platform rounding may change reconstructed tables. Use frozen hash-verified tables for exact historical trajectory replay.'}
 (out/'RECONSTRUCTION.json').write_text(json.dumps(report,indent=2)+'\n');return report
