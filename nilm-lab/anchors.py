import numpy as np, pandas as pd, sys
from load import load,STEP
g,y=load()
loc=pd.to_datetime(g,unit="s",utc=True).tz_convert("Europe/Paris")
print("points",len(g),"nan",np.isnan(y).mean().round(3), loc[0],loc[-1])
def med(a,i,j):
    s=a[max(i,0):j]; s=s[~np.isnan(s)]
    return np.median(s) if len(s) else np.nan
rows=[]
days=pd.date_range(loc[0].normalize(),loc[-1].normalize(),freq="D",tz="Europe/Paris")
for day in days:
    for hh,mm in [(14,24),(23,54)]:
        c=day+pd.Timedelta(hours=hh,minutes=mm)
        ci=int((c.timestamp()-g[0])//STEP)
        if ci<100 or ci>len(g)-800: continue
        lo,hi=ci-int(300/STEP),ci+int(360/STEP)   # +-5 min / +6 min
        best=None
        for i in range(lo,hi):
            b=med(y,i-12,i-2); a=med(y,i+4,i+14)
            if np.isnan(a) or np.isnan(b): continue
            dl=a-b
            if best is None or dl>best[0]: best=(dl,i,b,a)
        if best is None or best[0]<2000: rows.append((str(day.date()),f"{hh}:{mm}",np.nan,np.nan,np.nan,np.nan,np.nan)); continue
        dl,i,b,a=best
        # end: first time level drops below b + 0.4*dl, sustained
        j=i+12
        while j<len(y)-6 and not (np.nanmedian(y[j:j+4])<b+0.4*dl): j+=1
        dur=(j-i)*STEP
        plateau=np.nanmedian(y[i+10:max(j-6,i+11)])-b
        rows.append((str(day.date()),f"{hh}:{mm}",(g[i]-c.timestamp()),dl,plateau,dur,b))
df=pd.DataFrame(rows,columns=["day","slot","onset_s","step","plateau","dur_s","base"])
df.to_csv("anchors.csv",index=False)
ok=df.dropna()
print(len(df),"slots;",len(ok),"with a step>=2kW")
print(ok.groupby("slot")[["onset_s","step","plateau","dur_s"]].describe().T.round(0).to_string())
