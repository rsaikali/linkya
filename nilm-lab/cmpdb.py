import json,pandas as pd,numpy as np
from infer import fmt
H=json.load(open("det_hybrid.json"))
db=json.load(open("../det_before.json"))["detections"]
t0=pd.Timestamp("2026-09-01",tz="Europe/Paris").timestamp()
P=lambda s:pd.Timestamp(s).timestamp()
O=[dict(start=P(x["start_time"]),end=P(x["end_time"]),w=x["avg_power"],c=x["confidence_score"],e=x["energy_consumed"],inv=x["id"] in (11353,11376,10189,10150,10151,10729,10737)) for x in db if P(x["start_time"])>=t0]
ov=lambda a,b: a["start"]<b["end"] and a["end"]>b["start"]
print(f"old system Sep-Oct: {len(O)} detections, {sum(o['e'] for o in O)/1000:.1f} kWh ; hybrid: {len(H)} detections, {sum(h['wh'] for h in H)/1000:.1f} kWh")
onlyH=[h for h in H if not any(ov(h,o) for o in O)]
onlyO=[o for o in O if not any(ov(o,h) for h in H)]
print("\nhybrid-only (old system missed):",len(onlyH))
for h in onlyH: print("  ",fmt(h["start"]),"->",fmt(h["end"])[6:],"%4ds"%h["dur"],h["src"],"conf %.2f"%h["conf"])
print("\nold-only (hybrid rejects):",len(onlyO))
for o in onlyO: print("  ",fmt(o["start"]),"->",fmt(o["end"])[6:],"%4ds"%(o["end"]-o["start"]),"avgW %4d conf %.2f Wh %4d"%(o["w"],o["c"],o["e"]),"[invalidated FP]" if o["inv"] else "")
