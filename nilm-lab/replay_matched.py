"""Replay src.nilm.detectors.matched_filter on the real curve, in cron-like rolling windows, vs the legacy detections."""
import sys,json,time
sys.path.insert(0,"/Users/rsaikali/workspace/linkya/nilm-service")
import numpy as np,pandas as pd
from src.nilm.detectors import matched_filter as mf
TZ="Europe/Paris"; W=mf.parse_windows("23:54-05:24,14:24-16:54"); AM=mf.parse_times("14:24,23:54")
raw=pd.read_csv("/private/tmp/claude-501/-Users-rsaikali-workspace-ha-heaters/15e798e1-18da-4c57-bb15-18237577550d/scratchpad/nilm/linky.csv.gz",names=["t","p"])
t=raw.t.values;p=raw.p.values.astype(float)
# 1) calibration on the whole history (what the daily profile job would do over 30 days)
g,y=mf.to_grid(t,p); d,_=mf.edge_series(y); prof=mf.calibrate(g,y,d,AM,TZ); print("profile",prof)
# 2) rolling 2h windows every 5 min on Sep-Oct with 1h of context (cron behaviour); keep events with start in the window, last write wins
a=pd.Timestamp("2026-09-01",tz=TZ).timestamp(); b=t[-1]
ev={}; t0=time.time(); k=0
step=300.0
cur=a
while cur<b:
    lo,hi=cur,min(cur+7200,b)
    m=(t>=lo-3600)&(t<=hi)
    if m.sum()>20:
        out=mf.detect(t[m],p[m],prof,W,AM,TZ,from_epoch=lo,now_epoch=None)
        # a cron run rewrites its window: drop earlier events that started inside it
        ev={s:e for s,e in ev.items() if not (lo<=s<hi)}
        for e in out: ev[e["start"]]=e
    cur+=step; k+=1
print("runs",k,"time %.1fs (%.0f ms/run)"%(time.time()-t0,1000*(time.time()-t0)/k))
res=sorted(ev.values(),key=lambda e:e["start"])
json.dump(res,open("/private/tmp/claude-501/-Users-rsaikali-workspace-ha-heaters/15e798e1-18da-4c57-bb15-18237577550d/scratchpad/nilm/det_port.json","w"))
from collections import Counter
print("cycles",len(res),dict(Counter(e["source"] for e in res)),"kWh %.1f"%(sum(0.985*prof.ref*(e["end"]-e["start"])/3600 for e in res)/1000))
