import numpy as np, pandas as pd
from load import load,STEP
g,y=load(); yf=np.where(np.isnan(y),np.nan,y).astype(np.float64)
def edge_idx(i0):
    k=i0-6+int(np.nanargmax(np.diff(yf[i0-6:i0+7]))); return k+1   # first sample at the new level
def tr(i,dur):
    base=np.nanmedian(yf[i-14:i-3]); n=int(dur/STEP)
    if n<90: return None
    s=yf[i-1:i+n]-base
    p0=np.nanmedian(s[1:3])            # first 5-15 s: "spike"
    pA=np.nanmedian(s[6:12])           # 30-60 s
    pB=np.nanmedian(s[60:72]) if n>=72 else np.nan   # 5-6 min
    pC=np.nanmedian(s[n-14:n-4])       # end of cycle
    if np.isnan([p0,pA,pB]).any() or pB<400: return None
    seg=s[3:n-4]
    if np.ptp(np.percentile(seg,[3,97]))>0.12*pB+80: return None   # another load moved: not clean
    return dict(P=pB,spike=(p0-pA)/pB,d_30_330=(pA-pB)/pB,d_330_end=(pB-pC)/pB,first=(s[1]-pB)/pB)
rows=[]
a=pd.read_csv("anchors.csv").dropna(); a=a[(a.onset_s<60)&(a.dur_s>480)&(a.step<3700)&(a.step>2800)]
for r in a.itertuples():
    day=pd.Timestamp(r.day,tz="Europe/Paris"); hh,mm=map(int,r.slot.split(":"))
    c=(day+pd.Timedelta(hours=hh,minutes=mm)).timestamp()+r.onset_s; i=edge_idx(int((c-g[0])//STEP))
    t=tr(i,r.dur_s)
    if t: t["cls"]="HEATER"; rows.append(t)
st=pd.read_pickle("steps.pkl"); st=st[(st.t>1.7612e9)&(st.step>1000)&(st.dur>=480)&(st.dur<5400)]
for r in st.itertuples():
    mm=r.mod
    if abs(mm-864)<=3 or mm>=1431 or mm<=1: continue
    i=edge_idx(int((r.t-g[0])//STEP)); t=tr(i,r.dur)
    if t:
        P=t["P"]; t["cls"]="rad %s"%("1.2-1.5kW" if P<1700 else ("1.9-2.3kW" if P<2400 else "2.4-3.4kW")); rows.append(t)
d=pd.DataFrame(rows)
pd.set_option("display.width",200)
print(d.groupby("cls").agg(n=("P","size"),P=("P","median"),spike_pct=("spike",lambda x:100*np.median(x)),droop_30s_5min_pct=("d_30_330",lambda x:100*np.median(x)),
      p10=("d_30_330",lambda x:100*np.percentile(x,10)),p90=("d_30_330",lambda x:100*np.percentile(x,90)),late_drift_pct=("d_330_end",lambda x:100*np.median(x))).round(2).to_string())
d.to_pickle("trans.pkl")
