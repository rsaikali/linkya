import json,numpy as np,pandas as pd
from detect import *
from edgepair import *
from refine2 import snap
def overlap(a,b,m=120): return a["start"]<b["end"]+m and a["end"]>b["start"]-m
def pipeline(d0=None,seg_path="seg_sepoct.json"):
    g,y=grid10(); d0=d0 or pd.Timestamp("2026-09-01",tz="Europe/Paris").timestamp()
    Aall=anchor_cycles(g,y,g[0],g[-1],lambda t:np.full(len(t),3010.0)); cal=calibrate(g,y,Aall)
    A=[a for a in Aall if a["start"]>=d0]
    for a in A: a["src"]="anchor"
    E=[e for e in find(g,y,cal) if e["start"]>=d0 and hc_flag(np.array([e["start"]]))[0]>0]
    keep=list(A)
    for e in sorted(E,key=lambda r:-r["dur"]):                      # dedupe adjacent peaks: keep the longest
        if not any(overlap(e,k,30) for k in keep): keep.append(e)
    for s in json.load(open(seg_path)):
        if not ((s["conf"]>=0.7 and 2450<=s["avg_w"]<=3500) or (s["conf"]>=0.9 and 2200<=s["avg_w"]<=3600)): continue
        if any(overlap(s,k,60) for k in keep): continue
        ref=float(ref_curve(np.array([s["start"]]))[0]); i,j=snap(g,y,s,0.55*ref)
        if j-i<24: continue
        keep.append(dict(start=float(g[i]),end=float(g[j]),dur=float((j-i)*DT),src="net",conf=s["conf"]))
    keep.sort(key=lambda r:r["start"])
    for r in keep:
        ref=float(ref_curve(np.array([r["start"]]))[0]); r["wh"]=0.985*ref*r["dur"]/3600
    return keep
if __name__=="__main__":
    D=pipeline(); json.dump(D,open("det_hybrid.json","w"))
    from collections import Counter
    print("detections",len(D),dict(Counter(r["src"] for r in D)),"kWh %.1f"%(sum(r["wh"] for r in D)/1000))
