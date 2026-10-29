import numpy as np, pandas as pd
from load import load,STEP
g,y=load(); yf=np.where(np.isnan(y),np.nan,y).astype(np.float64)
a=pd.read_csv("anchors.csv").dropna()
a=a[(a.onset_s<60)&(a.dur_s>400)]
rows=[]
for _,r in a.iterrows():
    day=pd.Timestamp(r.day,tz="Europe/Paris"); hh,mm=map(int,r.slot.split(":"))
    c=(day+pd.Timedelta(hours=hh,minutes=mm)).timestamp()+r.onset_s
    i=int((c-g[0])//STEP); n=int(r.dur_s/STEP)
    base=np.nanmedian(yf[i-14:i-2])
    s1=np.nanmedian(yf[i+3:i+9])-base          # 15-45 s after edge
    s2=np.nanmedian(yf[i+30:i+42])-base        # 2.5-3.5 min
    pl=np.nanmedian(yf[max(i+n-24,i+43):i+n-4])-base  # last 2 min of cycle
    dn=base-np.nanmedian(yf[i+n+3:i+n+12]) if i+n+12<len(yf) else np.nan
    rows.append((day.date(),r.slot,s1,s2,pl,-(dn) if dn==dn else np.nan,r.dur_s))
d=pd.DataFrame(rows,columns=["day","slot","s_15s","s_3min","s_end","dn","dur"])
d["t"]=pd.to_datetime(d.day)
d=d.sort_values(["t","slot"]).reset_index(drop=True)
print(d[["s_15s","s_3min","s_end"]].describe().round(0).T.to_string())
# consecutive-anchor differences
for c in ["s_15s","s_3min","s_end"]:
    x=d[c].values; dd=np.diff(x)
    print(c,"consecutive diff: median|d| %.0f  std %.0f (robust %.0f)"%(np.median(np.abs(dd)),np.std(dd),1.4826*np.median(np.abs(dd-np.median(dd)))))
# monthly drift
d["m"]=pd.to_datetime(d.day).dt.to_period("M")
print(d.groupby("m")[["s_15s","s_3min","s_end"]].median().round(0).to_string())
# same-day 14:24 vs 23:54
w=d.pivot_table(index="day",columns="slot",values="s_3min")
print("same day (23:54-14:24) mean %.0f std %.0f"%((w["23:54"]-w["14:24"]).mean(),(w["23:54"]-w["14:24"]).std()))
d.to_pickle("anchor_feat.pkl")
