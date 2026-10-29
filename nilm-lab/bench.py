"""Generalisation benchmark: same code, 4 appliances, signatures from the first 60 % of the timeline, test on the rest."""
import sys,json
sys.path.insert(0,"/Users/rsaikali/workspace/linkya/nilm-service")
import numpy as np,pandas as pd
from src.nilm.detectors import matched_filter as mf
from infer import fmt
raw=pd.read_csv("linky.csv.gz",names=["t","p"]); T=raw.t.values; Pw=raw.p.values.astype(float)
def curve(a,b):
    i,j=np.searchsorted(T,[a,b]); return T[i:j],Pw[i:j]
def plug_cycles(name,thr,gap=200,min_s=240):
    a=np.loadtxt(f"plugs/{name}.csv",delimiter=","); t,w=a[:,0],a[:,1]; on=w>thr; segs=[]; i=0
    while i<len(t):
        if on[i]:
            j=i
            while j+1<len(t) and (on[j+1] or t[j+1]-t[j]<gap and on[min(j+2,len(t)-1)]): j+=1
            segs.append([t[i],t[min(j+1,len(t)-1)]]); i=j+1
        else: i+=1
    m=[]
    for s in segs:
        if m and s[0]-m[-1][1]<gap: m[-1][1]=s[1]
        else: m.append(s)
    return [(a,b) for a,b in m if b-a>=min_s]
def anchors():
    a=pd.read_csv("anchors.csv").dropna(); a=a[(a.onset_s<60)&(a.dur_s>400)&(a.step<3700)&(a.step>2800)]
    out=[]
    for r in a.itertuples():
        hh,mm=map(int,r.slot.split(":")); s=pd.Timestamp(f"{r.day} {hh:02d}:{mm:02d}",tz="Europe/Paris").timestamp()+r.onset_s
        out.append((s,s+r.dur_s))
    return sorted(out)
TRUTH={"chauffe_eau":anchors(),"four":plug_cycles("four",1500),"lave_vaisselle":plug_cycles("lave_vaisselle",1500),"lave_linge":plug_cycles("lave_linge",1000)}
t_plug0=pd.Timestamp("2026-08-30",tz="Europe/Paris").timestamp()
sets={}
for k,v in TRUTH.items():
    v=[c for c in v if (k=="chauffe_eau" or c[0]>=t_plug0)]
    sets[k]=v
cut={}
for k,v in sets.items():
    cut[k]=v[int(0.6*len(v))][0] if k!="chauffe_eau" else pd.Timestamp("2026-09-01",tz="Europe/Paris").timestamp()
print("episodes (train/test):",{k:(sum(c[0]<cut[k] for c in v),sum(c[0]>=cut[k] for c in v)) for k,v in sets.items()})
train={k:{"positive":[c for c in v if c[0]<cut[k]]} for k,v in sets.items()}
profiles,report=mf.build_profiles(train,curve)
for k,r in report.items(): print(f"{k:15s} {r}")
for k,ms in profiles.items():
    for m_ in ms: print(f"   {k:15s} mode up {m_.mu_up:6.0f}±{m_.sig_up:4.0f} dn {m_.mu_dn:6.0f}±{m_.sig_dn:4.0f} dur {m_.dur_min:5.0f}-{m_.dur_max:6.0f}s n={m_.n}")
# detection on the test period, 2 h rolling windows like the cron
t0=min(cut[k] for k in profiles); t1=T[-1]; ev=[]; cur=t0
while cur<t1:
    lo,hi=cur,min(cur+7200,t1); t,p=curve(lo-3600,hi)
    if len(t)>20: ev=[e for e in ev if not (lo<=e["start"]<hi)]+mf.detect(t,p,profiles,from_epoch=lo)
    cur+=900
ov=lambda s,e,x:s<x["end"]+120 and e>x["start"]-120
print("\nper appliance on the test period:")
for k,pr in profiles.items():
    test=[c for c in sets[k] if c[0]>=cut[k]]; mine=[e for e in ev if e["appliance"]==k and e["start"]>=cut[k]]
    rec=sum(any(ov(a,b,e) for e in mine) for a,b in test); prec=[any(ov(a,b,e) for a,b in sets[k]) for e in mine]
    others=[(kk,c) for kk,v in sets.items() if kk!=k and kk in profiles for c in v if c[0]>=cut[kk]]
    conf=[e for e in mine if any(ov(c[0],c[1],e) for _,c in others)]
    print(f"  {k:15s} truth cycles {len(test):3d} recall {rec}/{len(test)} ({rec/max(len(test),1):.0%})  detections {len(mine):3d}  matching a truth cycle {sum(prec)} ({sum(prec)/max(len(mine),1):.0%})  fell on ANOTHER appliance's cycle: {len(conf)}")
json.dump(ev,open("ev_bench.json","w"))
