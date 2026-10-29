import sys,json,numpy as np,pandas as pd
from infer import *
mp=sys.argv[1]; thr=float(sys.argv[2]) if len(sys.argv)>2 else 0.5
m=keras.models.load_model(mp,compile=False)
g,y=grid10()
d0=pd.Timestamp("2026-09-01",tz="Europe/Paris").timestamp(); i0=idx(d0); i1=len(g)
t,p,q=run(m,i0,i1)
seg=segments(t,p,q,thr)
np.save("p_sepoct.npy",np.stack([t,p,q]))
a=pd.read_csv("anchors.csv").dropna(); a=a[(a.onset_s<60)&(a.dur_s>400)]
A=[]
for r in a.itertuples():
    day=pd.Timestamp(r.day,tz="Europe/Paris"); hh,mm=map(int,r.slot.split(":"))
    c=(day+pd.Timedelta(hours=hh,minutes=mm)).timestamp()+r.onset_s
    if c>=d0: A.append((c,c+r.dur_s))
hit=0;err=[];derr=[]
for s,e in A:
    ov=[x for x in seg if x["start"]<e and x["end"]>s]
    if ov:
        hit+=1; b=max(ov,key=lambda x:min(x["end"],e)-max(x["start"],s)); err.append(b["start"]-s); derr.append(b["end"]-e)
print(f"anchors Sep-Oct: {len(A)}  detected {hit} ({hit/len(A):.1%}); onset err median {np.median(err):.0f}s p90 {np.percentile(np.abs(err),90):.0f}s; end err median {np.median(derr):.0f}s p90 {np.percentile(np.abs(derr),90):.0f}s")
anch_t=[(s,e) for s,e in A]
extra=[x for x in seg if not any(x["start"]<e+300 and x["end"]>s-300 for s,e in anch_t)]
hcm=lambda ts: hc_flag(np.array([ts]))[0]
print(f"segments total {len(seg)}; non-anchor segments {len(extra)} (in HC window: {sum(hcm(x['start'])>0 for x in extra)})")
for x in extra: print("  ",fmt(x["start"]),"->",fmt(x["end"])[6:],"dur %4ds"%x["dur"],"conf %.2f"%x["conf"],"avgW %4d"%x["avg_w"],"Wh %4d"%x["wh"],"HC" if hcm(x["start"])>0 else "HP")
json.dump(seg,open("seg_sepoct.json","w"))
