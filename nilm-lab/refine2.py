import numpy as np
from lab import DT
from refine import _step
def snap(t,y,seg,amin):
    """snap start/end to the strongest step edge (>= amin) within +-90 s of the net's boundaries"""
    s=int((seg["start"]-t[0])//DT); e=int((seg["end"]-t[0])//DT); out=[]
    for k,(c,sign) in enumerate([(s,+1),(e,-1)]):
        lo,hi=max(c-9,3),min(c+10,len(y)-10)
        cand=[(i,sign*_step(y,i)) for i in range(lo,hi)]
        cand=[(i,d) for i,d in cand if d==d and d>=amin]
        if not cand: out.append(c); continue
        mx=max(d for _,d in cand); best=[i for i,d in cand if d>=0.9*mx]    # strongest, then closest to the net's boundary
        out.append(min(best,key=lambda i:abs(i-c)))
    return out
def finalize(t,y,seg,ref,min_conf=0.7):
    """accept rule + boundary snapping + curve-based energy. returns dict or None"""
    A_net=seg["avg_w"]
    ok = (seg["conf"]>=min_conf and 2450<=A_net<=3500) or (seg["conf"]>=0.9 and 2200<=A_net<=3600)
    if not ok: return None
    s,e=snap(t,y,seg,0.55*ref)
    if e-s<24: return None
    base=np.nanmedian(y[max(s-8,0):max(s-1,1)])
    pl=np.nanmedian(y[s+12:e-3])-base
    return dict(start=float(t[s]),end=float(t[e]),dur=float((e-s)*DT),conf=seg["conf"],plateau=float(pl),base=float(base),
                wh=float(max(min(pl,1.1*ref),0)*(e-s)*DT/3600))
