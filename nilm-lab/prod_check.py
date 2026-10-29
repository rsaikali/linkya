import sys,time,json
sys.path.insert(0,"/tmp/nilm_new")
from datetime import datetime,timedelta,timezone
from src.database import db_manager
db_manager.set_meta=lambda *a,**k: None          # read-only check: do not write the profile cache
from src import matched_engine as me
t=time.time(); profiles,ids,wanted=me.get_profiles(); print("get_profiles %.1fs"%(time.time()-t),{n:[(round(m.mu_up),round(m.sig_up),round(m.mu_dn),round(m.sig_dn),m.n,len(m.neg)) for m in ms] for n,ms in profiles.items()},"wanted",wanted)
me.get_profiles=lambda: (profiles,ids,wanted)    # reuse
end=datetime.now(timezone.utc); 
for label,start in [("last 2h",end-timedelta(hours=2)),("Oct 20-29",datetime(2026,10,20,tzinfo=timezone.utc))]:
    t=time.time(); ev,handled,cov=me.detect(start,end); print(f"{label}: {len(ev)} events, covered={cov}, {time.time()-t:.1f}s")
    if label=="Oct 20-29":
        for e in ev[-6:]: print("   ",e["start_time"].astimezone().strftime("%m-%d %H:%M"),"->",e["end_time"].astimezone().strftime("%H:%M"),"avgW %.0f"%e["avg_power"],"Wh %.0f"%e["energy_wh"],"conf %.2f"%e["confidence_score"],e["features"])
