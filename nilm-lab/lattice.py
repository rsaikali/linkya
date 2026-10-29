import numpy as np, pandas as pd
from load import load,STEP
g,y=load(); yf=np.where(np.isnan(y),np.nan,y).astype(np.float64)
st=pd.read_pickle("steps.pkl"); st=st[(st.t>1.7612e9)&(st.step>900)]
am=[]
for r in st.itertuples():
    i=int((r.t-g[0])//STEP)
    # robust amplitude: median 20-60 s after the edge minus median 30-5 s before
    a=np.nanmedian(yf[i+4:i+12])-np.nanmedian(yf[i-6:i-1]) if i>10 else np.nan
    mm=r.mod
    anchor = abs(mm-864)<=3 or mm>=1431 or mm<=1
    am.append((a,anchor,r.dur,r.loc.strftime("%m-%d %H:%M")))
d=pd.DataFrame(am,columns=["a","anchor","dur","when"]).dropna()
print("up steps >0.9kW since 10-21:",len(d),"| at heater anchors:",d.anchor.sum())
x=d[~d.anchor].a.values
h,e=np.histogram(x,bins=np.arange(900,6600,100))
for k in range(len(h)):
    if h[k]: print(f"{e[k]:5.0f}-{e[k+1]:5.0f} W {'#'*h[k]} {h[k]}")
print("anchor steps:",np.round(np.percentile(d[d.anchor].a,[5,50,95]),0))
print("\n--- robust heater edge amplitude (anchors)")
aa=d[d.anchor].a.values; aa=aa[(aa>2800)&(aa<3500)]
med=np.median(aa); sig=1.4826*np.median(np.abs(aa-med)); print("median %.0f  robust sigma %.0f  (n=%d)"%(med,sig,len(aa)))
z=d[~d.anchor].copy(); z["z"]=(z.a-med)/sig
c=z[(z.a>2400)&(z.a<3700)].sort_values("when")
print("non-anchor up-edges 2.4-3.7 kW: %d ; |z|<3 (heater-compatible): %d ; z in [-12,-3] (radiator-pair zone): %d"%(len(c),(c.z.abs()<3).sum(),((c.z<-3)&(c.z>-12)).sum()))
print("heater-compatible (|z|<3):",", ".join(f"{r.when}({r.a:.0f}W,{r.dur:.0f}s)" for r in c[c.z.abs()<3].itertuples()))
print("nearest below: ",", ".join(f"{r.when}({r.a:.0f})" for r in c[(c.z<-3)&(c.z>-6)].itertuples()))
