import numpy as np
from lab import DT
def _step(y,i,a=7,gap=1):
    """robust level change across sample i (median after - median before), 10 s grid"""
    b=y[max(i-a-gap,0):max(i-gap,1)]; f=y[i+gap:i+gap+a]
    if len(b)<3 or len(f)<3: return np.nan
    return np.nanmedian(f)-np.nanmedian(b)
def refine(t,y,seg,ref,tol=0.14):
    """Snap a net segment to real step edges of heater height; return None if no consistent up/down pair.
    seg: dict(start,end) epoch s ; t,y: 10 s grid arrays ; ref: heater step reference (W)"""
    s=int((seg["start"]-t[0])//DT); e=int((seg["end"]-t[0])//DT)
    ups=[(i,_step(y,i)) for i in range(max(s-18,3),min(s+36,len(y)-10))]
    ups=[(i,d) for i,d in ups if d==d and abs(d-ref)<tol*ref]
    if not ups: return None
    # best up edge = largest step among candidates, earliest on ties
    on=max(ups,key=lambda u:(round(u[1]/40),-u[0]))[0]
    base=np.nanmedian(y[max(on-8,0):on-1])
    A=np.nanmedian(y[on+12:on+36])-base           # plateau amplitude 2-6 min after onset
    if not (abs(A-ref*0.985)<tol*ref): return None
    dn=None
    for i in range(on+24,min(e+36,len(y)-10)):
        d=_step(y,i)
        if d==d and abs(-d-A)<tol*A:
            # first edge with the right height; skip if a same-height up edge follows within 60 s (flicker)
            dn=i; break
    if dn is None: return None
    pl=np.nanmedian(y[on+12:dn-3])-base
    return dict(start=float(t[on]),end=float(t[dn]),dur=float((dn-on)*DT),A=float(A),plateau=float(pl),base=float(base),
                wh=float(max(pl,0)*(dn-on)*DT/3600),conf=seg["conf"])
