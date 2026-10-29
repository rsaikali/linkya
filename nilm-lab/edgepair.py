"""Matched edge-pair detector: up/down edges of heater amplitude, flat plateau between, inside an HC window."""
import numpy as np, pandas as pd
from scipy.ndimage import median_filter
from lab import *
def edge_series(y):
    yy=pd.Series(y).ffill().bfill().values; mf=median_filter(yy,size=3,mode="nearest")
    d=np.zeros(len(yy)); d[2:-2]=mf[3:-1]-mf[:-4]       # median(y[i:i+3]) - median(y[i-3:i])
    return d,yy
def calibrate(g,y,anchor_list):
    """edge amplitude stats from certain anchors -> (mu_up,sig_up,mu_dn,sig_dn)"""
    d,_=edge_series(y); U=[];Dn=[]
    for a in anchor_list:
        i=int((a["start"]-g[0])//DT); j=int((a["end"]-g[0])//DT)
        wi=d[i-3:i+4]; wj=d[j-3:j+4]
        U.append(wi.max()); Dn.append(-wj.min())
    U=np.array(U);Dn=np.array(Dn)
    f=lambda x:(float(np.median(x)),float(1.4826*np.median(np.abs(x-np.median(x)))))
    return f(U)+f(Dn)
def find(g,y,cal,k=4.0,min_s=240,max_s=5400):
    mu_u,s_u,mu_d,s_d=cal; d,yy=edge_series(y); s_u=max(s_u,35); s_d=max(s_d,35)
    # local maxima of up-edges / minima of down-edges
    up=[i for i in range(3,len(d)-3) if d[i]>=mu_u-k*s_u and d[i]<=mu_u+k*s_u and d[i]==d[i-2:i+3].max()]
    dn=np.array([i for i in range(3,len(d)-3) if -d[i]>=mu_d-k*s_d and -d[i]<=mu_d+k*s_d and d[i]==d[i-2:i+3].min()])
    out=[]
    for i in up:
        c=dn[(dn>i+min_s//DT)&(dn<i+max_s//DT)]
        if len(c)==0: continue
        j=int(c[0])
        base=np.median(yy[i-8:i-1]); pl=yy[i+6:j-2]-base
        if len(pl)<20 or np.percentile(pl,10)<0.8*(mu_d) or np.percentile(pl,90)>mu_u+6*s_u+150: continue   # plateau must stay at heater level (no other load moving)
        out.append(dict(start=float(g[i]),end=float(g[j]),dur=float((j-i)*DT),src="edgepair",conf=0.95,up=float(d[i]),dn=float(-d[j])))
    return out
