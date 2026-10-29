import sys
sys.path.insert(0,"/Users/rsaikali/workspace/linkya/nilm-service")
import numpy as np,pandas as pd,json
from src.nilm.detectors import matched_filter as mf
exec(open("bench.py").read().split("TRUTH=")[0].split("def anchors")[0])   # curve()
sg=pd.read_csv("sigs.csv"); P=sg[sg.is_negative=="f"]; N=sg[sg.is_negative=="t"]
train={"chauffe_eau":{"positive":[(r.s,r.e) for r in P.itertuples()],"negative":[(r.s,r.e) for r in N.itertuples() if r.id<=74]}}
profiles,report=mf.build_profiles(train,curve); print(report)
for m in profiles.get("chauffe_eau",[]): print("mode up %.0f±%.0f dn %.0f±%.0f dur %.0f-%.0f n=%d neg=%d"%(m.mu_up,m.sig_up,m.mu_dn,m.sig_dn,m.dur_min,m.dur_max,m.n,len(m.neg)))
# recall on all certain anchors (Sep-Oct = never seen by the 35 signatures)
a=pd.read_csv("anchors.csv").dropna(); a=a[(a.onset_s<60)&(a.dur_s>400)&(a.step<3700)&(a.step>2800)]
A=[]
for r in a.itertuples():
    hh,mm=map(int,r.slot.split(":")); s=pd.Timestamp(f"{r.day} {hh:02d}:{mm:02d}",tz="Europe/Paris").timestamp()+r.onset_s; A.append((s,s+r.dur_s))
t0=pd.Timestamp("2026-09-01",tz="Europe/Paris").timestamp(); A=[c for c in A if c[0]>=t0]
ev=[];cur=t0
while cur<T[-1]:
    lo,hi=cur,min(cur+7200,T[-1]); t,p=curve(lo-3600,hi)
    if len(t)>20: ev=[e for e in ev if not (lo<=e["start"]<hi)]+mf.detect(t,p,profiles,from_epoch=lo)
    cur+=900
ov=lambda s,e,x:s<x["end"]+120 and e>x["start"]-120
rec=sum(any(ov(a_,b_,e) for e in ev) for a_,b_ in A)
print("anchors never used for learning (after 06-10): recall %d/%d = %.0f%% ; detections %d"%(rec,len(A),100*rec/len(A),len(ev)))

json.dump([{"start":e["start"],"end":e["end"],"source":"matched","conf":e["conf"],"avg_w":e["avg_w"]} for e in ev],open("det_port.json","w"))
