import numpy as np, pandas as pd
STEP=5  # seconds
def load():
    d=pd.read_csv("/private/tmp/claude-501/-Users-rsaikali-workspace-ha-heaters/15e798e1-18da-4c57-bb15-18237577550d/scratchpad/nilm/linky.csv.gz",names=["t","p"])
    d=d.drop_duplicates("t").sort_values("t")
    t=d.t.values; p=d.p.values.astype(np.float32)
    t0=np.floor(t[0]/STEP)*STEP; n=int((t[-1]-t0)//STEP)+1
    grid=t0+STEP*np.arange(n)
    idx=np.searchsorted(t,grid,side="right")-1
    y=p[np.clip(idx,0,None)].copy()
    age=grid-t[np.clip(idx,0,None)]
    y[age>7200]=np.nan   # hole: no data for >2h
    return grid,y
