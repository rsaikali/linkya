"""Hybrid heater detector: contactor-anchor rule + TCN for top-ups; energy = fixed-resistor physics."""
import json,numpy as np,pandas as pd
from infer import *
from refine import _step
OPEN=[(14*60+24),(23*60+54)]     # HC window openings (local minutes) - heater contactor closes ~25 s before
def anchor_cycles(g,y,d0,d1,ref_fn):
    out=[]
    days=pd.date_range(pd.Timestamp(d0,unit="s",tz="UTC").tz_convert("Europe/Paris").normalize(),pd.Timestamp(d1,unit="s",tz="UTC").tz_convert("Europe/Paris").normalize(),freq="D",tz="Europe/Paris")
    for day in days:
        for om in OPEN:
            c=(day+pd.Timedelta(minutes=om)).timestamp(); ci=int((c-g[0])//DT)
            if ci<30 or ci+200>len(y): continue
            ref=float(ref_fn(np.array([c]))[0]); best=None
            for i in range(ci-9,ci+25):
                d=_step(y,i,a=3,gap=0)             # 30 s median after vs before
                if d==d and d>=0.8*ref and (best is None or d>best[1]+150 or (abs(d-best[1])<=150 and False)): best=(i,d)
            if best is None: continue
            on=best[0]
            # first edge of the rise: walk back while still rising
            while on>3 and _step(y,on-1,a=3,gap=0)>=0.5*ref: on-=1
            base=np.nanmedian(y[max(on-8,0):max(on-1,1)])
            if not (np.nanmedian(y[on+18:on+30])-base>=0.7*ref): continue
            end=None
            for i in range(on+36,min(on+2000,len(y)-8)):
                if -_step(y,i,a=3,gap=0)>=0.75*ref: end=i; break
            if end is None: continue
            out.append(dict(start=float(g[on]),end=float(g[end]),dur=float((end-on)*DT),src="anchor",conf=1.0,base=float(base)))
    return out
def run(seg_path="seg_sepoct.json",d0=None):
    g,y=grid10(); d0=d0 or pd.Timestamp("2026-09-01",tz="Europe/Paris").timestamp(); d1=g[-1]
    A=anchor_cycles(g,y,d0,d1,ref_curve)
    segs=json.load(open(seg_path)); N=[]
    for s in segs:
        if not ((s["conf"]>=0.7 and 2450<=s["avg_w"]<=3500) or (s["conf"]>=0.9 and 2200<=s["avg_w"]<=3600)): continue
        if any(s["start"]<a["end"]+120 and s["end"]>a["start"]-120 for a in A): continue    # already explained by an anchor
        from refine2 import snap
        ref=float(ref_curve(np.array([s["start"]]))[0]); i,j=snap(g,y,s,0.55*ref)
        if j-i<24: continue
        N.append(dict(start=float(g[i]),end=float(g[j]),dur=float((j-i)*DT),src="net",conf=s["conf"]))
    D=sorted(A+N,key=lambda r:r["start"])
    for r in D:
        ref=float(ref_curve(np.array([r["start"]]))[0]); r["wh"]=0.985*ref*r["dur"]/3600
    return D
if __name__=="__main__":
    D=run(); json.dump(D,open("det_hybrid.json","w"))
    print("hybrid detections",len(D),"anchor",sum(r["src"]=="anchor" for r in D),"net",sum(r["src"]=="net" for r in D),"total kWh %.1f"%(sum(r["wh"] for r in D)/1000))
