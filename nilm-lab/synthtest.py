import sys,numpy as np,os
os.environ["TF_CPP_MIN_LOG_LEVEL"]="3"
import keras
from lab import *
from model import features
from infer import segments
m=keras.models.load_model(sys.argv[1],compile=False); thr=float(sys.argv[2]) if len(sys.argv)>2 else 0.5
e=Engine(7,False); rng=np.random.default_rng(5)
def predict(x,hc,volt):
    ref=np.array([HREF*volt*(1+rng.normal(0,0.010))]); X=features(x[None],hc[None],ref)
    p,q=m.predict(X,verbose=0); return p[0,:,0],q[0,:,0]*HREF
def trial(kind,amp=None,n=200):
    tp=fp=nseg=0; werr=[]; 
    for _ in range(n):
        i0=int(rng.choice(e.bg)); x=e.y[i0:i0+W].astype(np.float32).copy(); t=e.g[i0:i0+W]; hc=hc_flag(t); volt=float(np.clip(rng.normal(1,0.03),0.92,1.08))
        hci=np.where(hc>0)[0]
        if len(hci)<200: continue
        truth=None
        if kind in("heater","heater+rad"):
            h=e.H[rng.integers(len(e.H))]; seg,up,dn=h[1],h[2],h[3]
            p0=int(rng.choice(hci))-up
            if p0<0 or p0+len(seg)>W: continue
            x[p0:p0+len(seg)]+=seg*volt; truth=(p0+up,p0+dn)
        if kind=="heater+rad" and e.R:
            for _k in range(int(rng.integers(1,4))):
                r=e.R[rng.integers(len(e.R))][1]; pp=int(rng.integers(0,max(1,W-len(r))))
                if pp+len(r)<=W: x[pp:pp+len(r)]+=r*volt
        if kind=="rad_pair":               # two staggered radiators, sum = amp, 5-40 min, inside HC
            a1=amp*rng.uniform(0.4,0.6); a2=amp-a1; L=int(rng.uniform(5,40)*60/DT); p0=int(rng.choice(hci)); 
            if p0+L+20>W: continue
            x[p0:p0+L]+=a1*volt; q0=p0+int(rng.integers(0,12)); x[q0:q0+L-5]+=a2*volt
        if kind=="rect":                    # single resistive load of amplitude amp with random droop
            L=int(rng.uniform(5,40)*60/DT); p0=int(rng.choice(hci))
            if p0+L+20>W: continue
            s=synth_rect(rng); s=s/ s[3:-3].mean()*amp; x[p0:p0+len(s)]+= s[:W-p0]*volt if p0+len(s)<=W else 0
        p,q=predict(x,hc,volt); seg=segments(e.g[i0:i0+W],p,q,thr)
        nseg+=1
        if truth:
            ts,te=e.g[i0]+truth[0]*DT,e.g[i0]+truth[1]*DT
            ov=[s for s in seg if s["start"]<te and s["end"]>ts]
            tp+= 1 if ov else 0
            if ov: b=max(ov,key=lambda s:s["dur"]); werr.append((b["end"]-b["start"])/(te-ts))
        else:
            fp+= 1 if seg else 0
    return nseg,tp,fp,werr
print("thr",thr)
for k in ["heater","heater+rad"]:
    n,tp,fp,w=trial(k); print(f"{k:11s} windows {n}  recall {tp/n:.1%}  duration ratio median {np.median(w):.2f}")
print("false-positive rate on windows WITHOUT heater (resistive load in HC window):")
for kind in ["rect","rad_pair"]:
    row=[]
    for a in [1500,2000,2400,2600,2800,2900,3000,3100,3200,3400,3800]:
        n,tp,fp,w=trial(kind,a,120); row.append(f"{a/1000:.1f}kW:{fp/max(n,1):.0%}")
    print(f"  {kind:8s}"," ".join(row))
