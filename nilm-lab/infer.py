import numpy as np, pandas as pd, os
os.environ["TF_CPP_MIN_LOG_LEVEL"]="3"
import keras
from lab import *
from model import features
def ref_curve(t,anchor_pkl="anchor_feat.pkl",span=11):
    """rolling-median anchor level (s_3min) -> reference at times t. Deployment: same, from daily auto-detected anchors."""
    a=pd.read_pickle(anchor_pkl); a=a[(a.s_3min>2700)&(a.s_3min<3400)].copy()
    ts=[pd.Timestamp(str(r.day)+" "+r.slot,tz="Europe/Paris").timestamp() for r in a.itertuples()]
    v=pd.Series(a.s_3min.values,index=ts).sort_index().rolling(span,center=True,min_periods=3).median()
    return np.interp(t,v.index.values,v.values)
def run(model,i0,i1,hop=W//2):
    """probability + power (W) for grid indices [i0,i1) of the real curve"""
    g,y=grid10(); n=i1-i0
    yy=pd.Series(y[i0:i1]).ffill().bfill().values.astype(np.float32); t=g[i0:i1]
    hc=hc_flag(t); ref=ref_curve(t)
    P=np.zeros(n); Q=np.zeros(n); Wt=np.zeros(n); win=np.hanning(W)+1e-3
    starts=list(range(0,max(n-W,0)+1,hop));
    if starts[-1]+W<n: starts.append(n-W)
    B=64
    for b in range(0,len(starts),B):
        ss=starts[b:b+B]
        X=np.stack([features(yy[s:s+W][None],hc[s:s+W][None],np.array([ref[s+W//2]]))[0] for s in ss])
        ps,pw=model.predict(X,verbose=0,batch_size=B)
        for k,s in enumerate(ss):
            P[s:s+W]+=ps[k,:,0]*win; Q[s:s+W]+=pw[k,:,0]*win; Wt[s:s+W]+=win
    return t,P/np.maximum(Wt,1e-9),Q/np.maximum(Wt,1e-9)*HREF
def segments(t,p,q,thr=0.5,min_s=240,merge_s=90):
    on=p>thr; seg=[]; i=0; n=len(on)
    while i<n:
        if on[i]:
            j=i
            while j<n and on[j]: j+=1
            seg.append([i,j]); i=j
        else: i+=1
    m=[]
    for a,b in seg:
        if m and (a-m[-1][1])*DT<=merge_s: m[-1][1]=b
        else: m.append([a,b])
    out=[]
    for a,b in m:
        if (b-a)*DT<min_s: continue
        out.append(dict(start=t[a],end=t[b-1]+DT,dur=(b-a)*DT,conf=float(p[a:b].mean()),pmax=float(p[a:b].max()),
                        wh=float(q[a:b].sum()*DT/3600),avg_w=float(q[a:b].mean())))
    return out
def fmt(ts): return pd.Timestamp(ts,unit="s",tz="UTC").tz_convert("Europe/Paris").strftime("%m-%d %H:%M")
