"""Data engine for the heater-NILM lab: real Linky curve + templates + semi-synthetic injection."""
import numpy as np, pandas as pd
from load import load, STEP
DT=10                 # model grid, seconds
W=1440                # window length (4 h)
HREF=3010.0           # nominal heater step (W), anchors median
_cache={}
def grid10():
    if "g" in _cache: return _cache["g"],_cache["y"]
    g,y=load(); n=len(g)//2*2
    y2=y[:n].reshape(-1,2); y10=np.nanmedian(y2,axis=1); g10=g[:n:2]
    _cache["g"],_cache["y"]=g10,y10
    return g10,y10
def mod_local(t):
    """local minute-of-day for epoch seconds array t"""
    ts=pd.to_datetime(np.asarray(t),unit="s",utc=True).tz_convert("Europe/Paris")
    return (ts.hour*60+ts.minute+ts.second/60).values
def hc_flag(t):
    m=mod_local(t)
    return ((m>=1434)|(m<324)|((m>=864)&(m<1014))).astype(np.float32)
def idx(t): 
    g,_=grid10(); return int((t-g[0])//DT)

# ---------- templates ----------
def heater_templates():
    if "H" in _cache: return _cache["H"]
    g,y=grid10(); a=pd.read_csv("anchors.csv").dropna()
    a=a[(a.onset_s<60)&(a.dur_s>400)&(a.step<3700)&(a.step>2800)]
    T=[]
    for _,r in a.iterrows():
        day=pd.Timestamp(r.day,tz="Europe/Paris"); hh,mm=map(int,r.slot.split(":"))
        c=(day+pd.Timedelta(hours=hh,minutes=mm)).timestamp()+r.onset_s
        i=idx(c); n=int(r.dur_s/DT)
        if i<10 or i+n+10>=len(y): continue
        seg=y[i-6:i+n+6]
        if np.isnan(seg).any(): continue
        base=np.median(seg[:5]); pl=seg[8:6+n-2]-base
        if len(pl)<25 or np.ptp(np.percentile(pl,[5,95]))>400: continue
        T.append((c,(seg-base).astype(np.float32),6,6+n))      # (time, curve, edge_up_idx, edge_down_idx)
    _cache["H"]=T; return T
def radiator_templates(t_lo=1.7612e9,t_hi=1.8e9):
    """single flat pulses 1.0-1.7 kW lasting 3-45 min, from the real curve after the heating season began"""
    g,y=grid10(); df=pd.read_pickle("steps.pkl"); df=df[(df.t>t_lo)&(df.t<t_hi)&(df.step>1000)&(df.step<1700)&(df.dur>=180)&(df.dur<=2700)]
    T=[]
    for _,r in df.iterrows():
        i=idx(r.t); n=int(r.dur/DT)
        seg=y[i-8:i+n+8]
        if len(seg)<n+14 or np.isnan(seg).any(): continue
        base=np.median(seg[:5]); pl=seg[10:8+n-2]-base
        if len(pl)<10 or np.ptp(np.percentile(pl,[5,95]))>250: continue
        T.append((r.t,(seg-base).astype(np.float32)))
    return T
def negsig_templates(lo=2,hi=74):
    s=pd.read_csv("sigs.csv"); s=s[(s.is_negative=="t")&(s.id>=lo)&(s.id<=hi)]
    g,y=grid10(); T=[]
    for _,r in s.iterrows():
        i=idx(r.s)-6; j=idx(r.e)+6
        seg=y[i:j]
        if len(seg)<12 or np.isnan(seg).any() or len(seg)>1200: continue
        T.append((r.s,(seg-np.median(seg[:5])).astype(np.float32)))
    return T

# ---------- injection ----------
def stretch(seg,up,dn,new_n,rng):
    """change a heater cycle plateau length: crop the middle or extend by resampling the tail level"""
    n=dn-up
    if new_n==n: return seg
    head=seg[:up+min(n,36)]            # edge + first 6 min (droop part)
    tail=seg[dn-3:]                    # last 30 s of plateau + off edge
    body_len=new_n-(len(head)-up)-3
    if body_len<=0: return seg
    lvl=np.median(seg[max(up+n-12,up+10):dn-1]) if n>20 else np.median(seg[up+3:dn])
    body=lvl+rng.normal(0,10,body_len).astype(np.float32)
    return np.concatenate([head,body,tail]).astype(np.float32)
def synth_rect(rng,hard=0.6):
    amp=rng.uniform(2200,3800) if rng.random()<hard else rng.uniform(700,2200); n=int(rng.uniform(2,90)*60/DT)
    droop=rng.uniform(0,0.05)*amp; tau=rng.uniform(6,40)
    t=np.arange(n); s=amp-droop*(1-np.exp(-t/tau))
    s=np.concatenate([np.zeros(3),s,np.zeros(3)]).astype(np.float32); s[3:-3]+=rng.normal(0,12,n)
    return s
def synth_tpi_train(rng):
    """thermostat-cycled radiator pair: staggered pulse trains (period 15 min, widths 3-10 min)"""
    L=int(rng.uniform(40,180)*60/DT); s=np.zeros(L,np.float32); a1,a2=rng.uniform(1100,1650,2)
    per=int(900/DT); 
    for k,(a,off) in enumerate([(a1,0),(a2,int(per*rng.choice([0,0.5])))]):
        w=int(rng.uniform(180,600)/DT)
        for st in range(off,L,per):
            s[st:st+w]+=a
    return s
def synth_pair(rng):
    """two radiators switched on/off at nearly the same time: sum in the heater ambiguity band"""
    tot=rng.uniform(2300,3500); a1=tot*rng.uniform(0.38,0.62); a2=tot-a1; L=int(rng.uniform(4,70)*60/DT)
    s=np.zeros(L+8,np.float32); o=int(rng.integers(0,10)); e=int(rng.integers(0,10))
    s[3:3+L]+=a1; s[3+o:3+L-e]+=a2
    s[3:3+L]-=rng.uniform(0,0.04)*s[3:3+L]*(1-np.exp(-np.arange(L)/rng.uniform(6,40)))
    return s
class Engine:
    def __init__(s,seed=0,train=True):
        s.rng=np.random.default_rng(seed); g,y=grid10(); s.g,s.y=g,y
        Ht=heater_templates()
        # split by time: templates before 2026-09-01 for training, after for test
        cut=pd.Timestamp("2026-09-01",tz="Europe/Paris").timestamp()
        s.H=[h for h in Ht if (h[0]<cut)==train]
        R=radiator_templates()
        cutr=pd.Timestamp("2026-10-26",tz="Europe/Paris").timestamp()
        s.R=[r for r in R if (r[0]<cutr)==train]
        s.N=[n for n in negsig_templates() if (n[0]<pd.Timestamp("2026-06-01",tz="Europe/Paris").timestamp())==train or True]
        # quiet background windows: no value above 1.8 kW and no NaN, heater-free by construction
        s.bg=s._quiet_windows(train)
    def _quiet_windows(s,train):
        y=s.y; n=len(y); starts=np.arange(0,n-W,W//4)
        ok=[]
        cut=pd.Timestamp("2026-09-01",tz="Europe/Paris").timestamp()
        for i in starts:
            seg=y[i:i+W]
            if np.isnan(seg).any() or seg.max()>2400: continue
            if (s.g[i]<cut)!=train: continue
            ok.append(i)
        return np.array(ok)
    def add(s,x,tmpl,pos,amp_scale=1.0,mask=None):
        L=len(tmpl); 
        if pos<0 or pos+L>len(x): return None
        x[pos:pos+L]+=tmpl*amp_scale; return pos
    def make(s,hc_only=True,n_dis=None,force_heater=None):
        rng=s.rng; i0=int(rng.choice(s.bg)); x=s.y[i0:i0+W].astype(np.float32).copy()
        t=s.g[i0:i0+W]; hc=hc_flag(t); volt=float(np.clip(rng.normal(1,0.03),0.92,1.08))
        tgt=np.zeros(W,np.float32); st=np.zeros(W,np.float32)
        # heater cycles: only inside HC windows (physical gate)
        nh=force_heater if force_heater is not None else rng.choice([0,1,1,2])
        hc_idx=np.where(hc>0)[0]
        for _ in range(nh):
            if len(hc_idx)==0 or not s.H: break
            h=s.H[rng.integers(len(s.H))]; seg,up,dn=h[1],h[2],h[3]
            new_n=int(np.clip((dn-up)*np.exp(rng.normal(0,0.6)),30,360))
            seg=stretch(seg,up,dn,new_n,rng); up2=up; dn2=up+new_n
            # onset: near an HC opening or inside the window
            if rng.random()<0.5:
                # opening = rising edge of hc flag
                op=np.where(np.diff(hc,prepend=hc[0])>0)[0]
                if len(op)==0: continue
                p=int(rng.choice(op))+int(rng.normal(-2,3))-up2
            else:
                p=int(rng.choice(hc_idx))-up2
            if p<0 or p+len(seg)>W: continue
            x[p:p+len(seg)]+=seg*volt
            st[p+up2:p+dn2]=1; tgt[p+up2:p+dn2]=np.maximum(tgt[p+up2:p+dn2],(seg[up2:dn2])*volt)
        # distractors (anywhere, overlapping allowed)
        nd=n_dis if n_dis is not None else rng.integers(0,6)
        for _ in range(nd):
            k=rng.random()
            if k<0.25 and s.R: tm=s.R[rng.integers(len(s.R))][1]; sc=volt
            elif k<0.40 and s.N: tm=s.N[rng.integers(len(s.N))][1]; sc=1.0
            elif k<0.60: tm=synth_rect(rng); sc=volt
            elif k<0.80: tm=synth_pair(rng); sc=volt
            else: tm=synth_tpi_train(rng); sc=volt
            p=int(rng.integers(0,max(1,W-len(tm)))); 
            if p+len(tm)<=W: x[p:p+len(tm)]+=tm*sc
        return x,st,tgt,hc,volt
