import numpy as np, pandas as pd
from load import load,STEP
g,y=load()
yf=np.where(np.isnan(y),0,y).astype(np.float64)
# robust step finder: median(after 4..14 samples) - median(before 12..2)
from scipy.ndimage import median_filter
n=len(y)
def rolling_med(a,w): return median_filter(a,size=w,mode="nearest")
m_b=rolling_med(yf,11)            # 55 s window
up=[]
d=np.zeros(n)
d[14:-14]=m_b[14+6:n-14+6][:n-28]-m_b[14-6-0:n-14-6][:n-28] if False else 0
# simpler vectorised: after-before with shifted medians
after=np.roll(m_b,-9); before=np.roll(m_b,9)
dl=after-before
cand=np.where(dl>1200)[0]
# local maxima grouping
ev=[];last=-999
for i in cand:
    if i-last>6:
        seg=dl[i:i+8]; j=i+int(np.argmax(seg)); ev.append(j); 
    last=i
ev=np.array(sorted(set(ev)))
print("up steps >1.2kW:",len(ev))
rows=[]
for i in ev:
    b=np.median(yf[i-14:i-2]); 
    # end of plateau: first sustained drop below b+0.5*step
    st=np.median(yf[i+4:i+12])-b
    j=i+12
    while j<n-4 and np.median(yf[j:j+4])>b+0.5*st: j+=1
    dur=(j-i)*STEP
    t=pd.Timestamp(g[i],unit="s",tz="UTC").tz_convert("Europe/Paris")
    rows.append((g[i],t,st,dur,b,np.median(yf[i+12:max(j-4,i+13)])-b if j-i>20 else np.nan))
df=pd.DataFrame(rows,columns=["t","loc","step","dur","base","plateau"])
df["mod"]=df["loc"].dt.hour*60+df["loc"].dt.minute
df.to_pickle("steps.pkl")
print(df.describe().round(0).to_string())
