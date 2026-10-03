"""Conditional error bounds from all frozen phase/bank/incoming-state tables."""
import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path
import numpy as np

root=Path(__file__).resolve().parents[2]
raw=gzip.decompress((root/'production/u5/u5_cdf.npy.gz').read_bytes())
cdf=np.load(io.BytesIO(raw));transition=np.diff(cdf,axis=-1,prepend=0)
even=np.arange(0,128,2);rows=[]
for bank in range(4):
    probabilities=[]
    for phase in range(35):
        t=transition[phase,bank]
        remaining=t[np.ix_(even,even)]@np.ones(64)
        remaining=t[np.ix_(even,even)]@remaining
        accept=t[:,even]@remaining
        probabilities.extend(1-accept if bank==0 else accept)
    rows.append(dict(bank=bank,event='miss given no return' if bank==0 else 'emit given return',
                     min=float(min(probabilities)),max=float(max(probabilities))))
print(json.dumps(dict(calculated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    cdf_sha256=hashlib.sha256(raw).hexdigest(),
    method='Three correlated readings using frozen float64 transition tables; all phases and incoming states; conditional gate probabilities, not unconditional closed-loop error rates.',
    bounds=rows),indent=2))
