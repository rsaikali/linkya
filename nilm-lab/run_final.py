import json,numpy as np,pandas as pd
from infer import *
from refine2 import finalize
seg=json.load(open("seg_sepoct.json")); g,y=grid10(); out=[];rej=[]
for s in seg:
    r=finalize(g,y,s,float(ref_curve(np.array([s["start"]]))[0]))
    (out if r else rej).append((s,r))
print("net segments",len(seg),"accepted",len(out),"rejected",len(rej))
print("REJECTED:"); 
for s,_ in rej: print("  ",fmt(s["start"]),"->",fmt(s["end"])[6:],"dur %4ds conf %.2f avgW %4d"%(s["dur"],s["conf"],s["avg_w"]))
print("BOUNDARY CHANGES > 2 min:")
for s,r in out:
    if abs(r["start"]-s["start"])>120 or abs(r["end"]-s["end"])>120: print("  ",fmt(s["start"]),"->",fmt(s["end"])[6:],"=>",fmt(r["start"]),"->",fmt(r["end"])[6:],"plateau %d Wh %d"%(r["plateau"],r["wh"]))
json.dump([r for _,r in out],open("det_final.json","w"))
