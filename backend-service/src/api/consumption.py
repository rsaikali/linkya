"""Consumption data endpoints."""

import logging
import time

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ..db import db_manager


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/consumption", tags=["Consumption"])

# In-memory cache for the heavy history query: avoids hitting the DB on every
# page load.  TTL = 55s so the browser Cache-Control (55s) and this always
# stay in sync — one fresh DB query per minute maximum.
_HISTORY_CACHE_TTL = 55
_history_cache: dict = {}   # key → (payload, expires_at)


def _cache_key(interval: str) -> str:
    return interval


def _get_cached(key: str):
    entry = _history_cache.get(key)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    return None


def _set_cached(key: str, payload: dict) -> None:
    _history_cache[key] = (payload, time.monotonic() + _HISTORY_CACHE_TTL)


@router.get("/latest")
async def get_latest_consumption():
    try:
        data = db_manager.get_latest_consumption()
        if not data:
            raise HTTPException(status_code=404, detail="Aucune donnée disponible")
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.get("/history")
async def get_consumption_history(
    interval=Query(
        default="auto",
        description="Aggregation interval (auto, raw, 1 minute, 5 minutes, 15 minutes, 1 hour)",
    )
):
    try:
        # Serve from in-memory cache when fresh.
        cache_key = _cache_key(interval)
        cached = _get_cached(cache_key)
        if cached:
            logger.debug("consumption/history cache hit (interval=%s)", interval)
            return JSONResponse(
                content=cached,
                headers={"Cache-Control": f"public, max-age={_HISTORY_CACHE_TTL}"},
            )

        all_data_range = db_manager.get_consumption_time_range()
        if not all_data_range:
            raise HTTPException(status_code=404, detail="Aucune donnée disponible")
        start_time_dt = all_data_range["min_time"]
        end_time_dt = all_data_range["max_time"]

        if interval == "auto":
            duration_hours = (end_time_dt - start_time_dt).total_seconds() / 3600
            if duration_hours <= 6:
                interval = "raw"
            elif duration_hours <= 24:
                interval = "1 minute"
            elif duration_hours <= 72:
                interval = "5 minutes"
            elif duration_hours <= 168:
                interval = "10 minutes"
            else:
                interval = "1 hour"

        data = db_manager.get_consumption_history(start_time_dt, end_time_dt, interval)
        if not data:
            raise HTTPException(status_code=404, detail="Aucune donnée disponible pour cette période")

        payload = {
            "start_time": start_time_dt.isoformat(),
            "end_time": end_time_dt.isoformat(),
            "interval": interval,
            "data_points": len(data),
            "data": data,
        }

        _set_cached(cache_key, payload)
        logger.debug("consumption/history cache miss — %d pts (interval=%s)", len(data), interval)

        return JSONResponse(
            content=payload,
            headers={"Cache-Control": f"public, max-age={_HISTORY_CACHE_TTL}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")
