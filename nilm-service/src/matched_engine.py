"""Glue between the matched-filter detector and the database: signatures, curve, cached profiles.

Profiles are learned from each appliance's signatures (see nilm/detectors/matched_filter.py), cached in nilm_meta and
rebuilt when the signatures change or the cache is a week old. Appliances without a usable profile stay on the legacy
matcher.
"""

import json
import logging
import time
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import text

from .config import settings
from .database import db_manager
from .nilm.detectors import matched_filter as mf

logger = logging.getLogger(__name__)

META_KEY = "matched_profiles"
MAX_AGE_S = 7 * 86400.0
CHUNK_S = 14 * 86400.0  # full-history detection is processed in chunks


def fetch(a, b):
    """Curve samples (epoch seconds, W) in [a, b], with the last known level carried in at a (HA only emits changes)."""
    with db_manager.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT EXTRACT(EPOCH FROM time), papp FROM linky_realtime WHERE time >= to_timestamp(:a) AND time <= to_timestamp(:b) ORDER BY time"
            ),
            {"a": a, "b": b},
        ).fetchall()
        prev = conn.execute(
            text(
                "SELECT EXTRACT(EPOCH FROM time), papp FROM linky_realtime WHERE time < to_timestamp(:a) AND time >= to_timestamp(:a) - interval '2 hours' ORDER BY time DESC LIMIT 1"
            ),
            {"a": a},
        ).fetchone()
    t = [float(r[0]) for r in rows if r[1] is not None]
    v = [float(r[1]) for r in rows if r[1] is not None]
    if prev is not None and prev[1] is not None:
        t, v = [a] + t, [float(prev[1])] + v
    return np.asarray(t), np.asarray(v)


def _signatures():
    """({name: {"positive": [(start, end)], "negative": [...]}}, {name: id}, fingerprint)."""
    with db_manager.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT a.id, a.name, EXTRACT(EPOCH FROM s.start_time), EXTRACT(EPOCH FROM s.end_time), s.is_negative, s.id "
                "FROM nilm_signatures s JOIN nilm_appliances a ON a.id = s.appliance_id ORDER BY s.id"
            )
        ).fetchall()
    sigs, ids = {}, {}
    for aid, name, a, b, neg, _sid in rows:
        ids[name] = aid
        sigs.setdefault(name, {"positive": [], "negative": []})["negative" if neg else "positive"].append((float(a), float(b)))
    fingerprint = (
        f"v{mf.VERSION}|"
        + ";".join(f"{n}:{len(v['positive'])}/{len(v['negative'])}" for n, v in sorted(sigs.items()))
        + f"|{rows[-1][5] if rows else 0}"
    )
    return sigs, ids, fingerprint


def _load_cache():
    with db_manager.engine.connect() as conn:
        row = conn.execute(text("SELECT value FROM nilm_meta WHERE key = :k"), {"k": META_KEY}).fetchone()
    try:
        return json.loads(row[0]) if row else None
    except ValueError:
        return None


def _fingerprint_ok(cache, fp):
    return bool(cache) and cache.get("fingerprint") == fp and time.time() - cache.get("built_at", 0) < MAX_AGE_S


def cached_cover():
    """True if the cached profiles are fresh and serve every appliance that has signatures (no rebuild, no heavy query)."""
    sigs, _ids, fp = _signatures()
    cache = _load_cache()
    wanted = {n for n, s in sigs.items() if len(s["positive"]) >= 2}
    return _fingerprint_ok(cache, fp) and wanted <= set(cache.get("profiles", {}))


def status():
    """Engine per appliance and why, for the API / UI."""
    sigs, _ids, fp = _signatures()
    cache = _load_cache() or {}
    with db_manager.engine.connect() as conn:
        names = [r[0] for r in conn.execute(text("SELECT name FROM nilm_appliances ORDER BY id")).fetchall()]
    out = {}
    for name in names:
        pos = len(sigs.get(name, {}).get("positive", []))
        modes = cache.get("profiles", {}).get(name)
        why = cache.get("report", {}).get(name)
        if settings.nilm_engine == "legacy":
            engine, why = "legacy", "NILM_ENGINE=legacy"
        elif modes:
            engine = "matched"
        else:
            engine = "legacy"
            why = why or ("fewer than %d positive signatures (%d)" % (mf.MIN_SIGNATURES, pos) if pos < mf.MIN_SIGNATURES else "profile not built yet")
        out[name] = {
            "engine": engine,
            "reason": why,
            "positive_signatures": pos,
            "trained_at": cache.get("built_at") if engine == "matched" else None,
            "modes": [
                {
                    "up_w": round(m["mu_up"]),
                    "down_w": round(m["mu_dn"]),
                    "signatures": m["n"],
                    "power_w": round(m.get("level") or 0.5 * (m["mu_up"] + m["mu_dn"])),
                }
                for m in (modes or [])
            ],
        }
    served = [n for n, a in out.items() if a["engine"] == "matched"]
    model = None  # what HA shows as "the model" when the matched filter serves every appliance
    if settings.nilm_engine == "matched" and served and len(served) == len(out):
        model = {
            "name": "matched_filter_v%d" % mf.VERSION,
            "type": "MatchedFilter",
            "trained_at": cache.get("built_at"),
            "num_signatures": sum(out[n]["positive_signatures"] for n in served),
            "num_appliances": len(served),
        }
    return {
        "setting": settings.nilm_engine,
        "profile_built_at": cache.get("built_at"),
        "profile_current": _fingerprint_ok(cache, fp),
        "appliances": out,
        "model": model,
    }


def get_profiles():
    """({appliance: [Profile]}, {appliance: id}, names_to_cover). Rebuilds the cache when stale."""
    sigs, ids, fp = _signatures()
    cache = _load_cache()
    if _fingerprint_ok(cache, fp):
        profiles = {n: [mf.Profile.from_dict(m) for m in ms] for n, ms in cache["profiles"].items()}
    else:
        t0 = time.time()
        profiles, report = mf.build_profiles({n: s for n, s in sigs.items() if len(s["positive"]) >= mf.MIN_SIGNATURES}, fetch)
        for name, why in report.items():
            logger.info("matched profile %s: %s", name, why)
        logger.info("matched profiles rebuilt in %.1fs (%d appliance(s))", time.time() - t0, len(profiles))
        db_manager.set_meta(
            META_KEY,
            json.dumps(
                {
                    "fingerprint": fp,
                    "built_at": time.time(),
                    "report": report,
                    "profiles": {n: [m.to_dict() for m in ms] for n, ms in profiles.items()},
                }
            ),
        )
    wanted = {n for n, s in sigs.items() if len(s["positive"]) >= 2}
    return profiles, ids, wanted


def detect(start_time, end_time):
    """Matched-filter detections in [start_time, end_time] in the legacy event format.

    Returns (events, handled) where handled = appliance names served by a profile; covered = every appliance with
    signatures is handled, so the legacy matcher can be skipped.
    """
    profiles, ids, wanted = get_profiles()
    if not profiles:
        return [], set(), False
    a, b = start_time.timestamp(), end_time.timestamp()
    events = []
    t = a
    while t < b:
        hi = min(t + CHUNK_S, b)
        times, values = fetch(t - 3600.0, hi)
        if len(times):
            events += mf.detect(times, values, profiles, from_epoch=t, now_epoch=time.time())
        t = hi
    out = []
    for e in events:
        dur = e["end"] - e["start"]
        out.append(
            {
                "appliance_id": ids[e["appliance"]],
                "appliance_name": e["appliance"],
                "signature_id": None,
                "start_time": datetime.fromtimestamp(e["start"], timezone.utc),
                "end_time": datetime.fromtimestamp(e["end"], timezone.utc),
                "avg_power": e["avg_w"],
                "energy_wh": e["avg_w"] * dur / 3600.0,
                "confidence_score": e["conf"],
                "model_name": "matched_filter_v%d" % mf.VERSION,
                "features": {"detection_method": "matched_filter", "composite": e["composite"], "provisional": e["provisional"]},
            }
        )
    return out, set(profiles), set(profiles) >= wanted
