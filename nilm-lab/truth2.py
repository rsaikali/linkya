import json,numpy as np,pandas as pd
from truth import plug
from infer import fmt
P=lambda s:pd.Timestamp(s).timestamp()
db=json.load(open("../det_before.json"))["detections"]
t0=P("2026-08-30T00:00:00+02:00")
leg=[dict(start=P(x["start_time"]),end=P(x["end_time"]),w=x["avg_power"],c=x["confidence_score"]) for x in db if P(x["start_time"])>=t0]
new=[d for d in json.load(open("det_port.json")) if d["start"]>=t0]
print("legacy detections since 08-30:",len(leg),"| new engine:",len(new))
ov=lambda s,e,x:s<x["end"]+60 and e>x["start"]-60
tot={"legacy":0,"new":0}; n_ep=0
for name in ["four","lave_vaisselle","lave_linge"]:
    S=[s for s in plug(name) if s[1]-s[0]>=240 and s[0]>=t0]
    n_ep+=len(S); a=[s for s in S if any(ov(s[0],s[1],x) for x in leg)]; b=[s for s in S if any(ov(s[0],s[1],x) for x in new)]
    tot["legacy"]+=len(a); tot["new"]+=len(b)
    print(f"{name:15s} episodes {len(S):3d} | legacy detections overlap {len(a):2d} | new engine overlap {len(b):2d}")
    for s in a: print("    legacy FP-like:",fmt(s[0]),"->",fmt(s[1])[6:],"max %.0fW"%s[2])
print("TOTAL appliance episodes",n_ep,tot)
# legacy detections falling inside ANY of these episodes (reverse view)
allep=[]
for name in ["four","lave_vaisselle","lave_linge"]: allep+=[(name,)+tuple(s) for s in plug(name) if s[1]-s[0]>=240 and s[0]>=t0]
bad=[x for x in leg if any(x["start"]<e[2] and x["end"]>e[1] for e in allep)]
print("legacy detections inside an appliance episode:",len(bad),"/",len(leg))
for x in bad: print("   ",fmt(x["start"]),"->",fmt(x["end"])[6:],"avgW %d conf %.2f"%(x["w"],x["c"]))
