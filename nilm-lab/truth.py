import sys,json
sys.path.insert(0,"/Users/rsaikali/workspace/linkya/nilm-service")
import numpy as np,pandas as pd
from src.nilm.detectors import matched_filter as mf
from infer import fmt
TZ="Europe/Paris"
def plug(name,thr=300,gap=420):
    a=np.loadtxt(f"plugs/{name}.csv",delimiter=","); t,w=a[:,0],a[:,1]
    on=w>thr; segs=[]; i=0
    while i<len(t):
        if on[i]:
            j=i
            while j+1<len(t) and (on[j+1] or (t[j+1]-t[j])<gap and w[j+1]>thr*0.3): j+=1
            segs.append([t[i],t[min(j+1,len(t)-1)],w[i:j+1].max(),w[i:j+1].mean()]); i=j+1
        else: i+=1
    # merge segments closer than gap
    m=[]
    for s in segs:
        if m and s[0]-m[-1][1]<gap: m[-1][1]=s[1]; m[-1][2]=max(m[-1][2],s[2])
        else: m.append(s)
    return m
if __name__=="__main__":
    det=json.load(open("det_port.json")); ov=lambda s,e,x:s<x["end"]+60 and e>x["start"]-60
    for name in ["four","lave_vaisselle","lave_linge","laveur_cuisine","irobot_aspirateur"]:
        S=plug(name); S=[s for s in S if s[1]-s[0]>=240]
        hit=[(s,[d for d in det if ov(s[0],s[1],d)]) for s in S]
        n_hit=sum(1 for s,d in hit if d)
        print(f"{name:18s} episodes>=4min: {len(S):3d}  overlapping a heater detection: {n_hit}")
        for s,d in hit:
            if d: print("     ",fmt(s[0]),"->",fmt(s[1])[6:],"max %.0f W"%s[2],"| detection",[ (fmt(x['start'])[6:],x['source']) for x in d][:2])
