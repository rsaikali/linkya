"""Home Assistant History API backfill."""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from loguru import logger

from .config import settings
from .database import db_manager


async def backfill():
    """
    Pull HA history for sensor.linky_sinsts and insert into linky_realtime.
    Resumes from last known timestamp; falls back to HA_BACKFILL_DAYS.
    Fetches day by day to avoid huge payloads.
    """
    last_ts = db_manager.get_last_timestamp()
    now = datetime.now(timezone.utc)

    if last_ts and last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=timezone.utc)

    start = last_ts if last_ts else now - timedelta(days=settings.ha_backfill_days)

    if (now - start).total_seconds() < 60:
        logger.info("DB up to date, skipping backfill")
        return

    logger.info(f"Backfill from {start.isoformat()} ({(now - start).days}d)")

    headers = {
        "Authorization": f"Bearer {settings.ha_token}",
        "Content-Type": "application/json",
    }

    total = 0
    current = start

    async with httpx.AsyncClient(timeout=30) as client:
        while current < now:
            chunk_end = min(current + timedelta(days=1), now)
            rows = await _fetch_chunk(client, headers, current, chunk_end)
            if rows:
                inserted = db_manager.bulk_insert(rows)
                total += inserted
                logger.debug(f"  {current.date()} → {inserted} points")
            current = chunk_end
            await asyncio.sleep(0.2)  # be gentle with HA

    logger.info(f"Backfill complete: {total} points inserted")


async def _fetch_chunk(
    client: httpx.AsyncClient,
    headers: dict,
    start: datetime,
    end: datetime,
) -> list[dict]:
    # Use Z suffix (no +00:00) to avoid URL-encoding issues with the + character
    start_iso = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = end.strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"{settings.ha_url}/api/history/period/{start_iso}"
    params = {
        "filter_entity_id": settings.ha_entity_papp,
        "end_time": end_iso,
        "minimal_response": "true",
        "no_attributes": "true",
    }

    try:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"HA API error for {start.date()}: {e}")
        return []

    data = resp.json()
    if not data or not data[0]:
        return []

    rows = []
    for point in data[0]:
        state = point.get("state", "")
        if state in ("unavailable", "unknown", ""):
            continue
        try:
            papp = int(float(state))
            ts_str = point.get("last_changed") or point.get("last_updated", "")
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            rows.append({"time": ts, "papp": papp})
        except (ValueError, KeyError):
            continue

    return rows
