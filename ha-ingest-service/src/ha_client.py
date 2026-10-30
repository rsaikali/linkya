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
    await _pull(
        settings.ha_entity_papp,
        db_manager.get_last_timestamp(),
        lambda points: [{"time": ts, "papp": int(v)} for ts, v in points],
        db_manager.bulk_insert,
    )


async def sync_energy():
    """Pull HA history of the Linky energy index (sensor.linky_east, kWh) into linky_energy: the reference for total consumption."""
    await _pull(
        settings.ha_entity_energy,
        db_manager.get_last_energy_timestamp(),
        lambda points: [{"time": ts, "kwh": v} for ts, v in points],
        db_manager.bulk_insert_energy,
    )


async def _pull(entity, last_ts, to_rows, insert):
    now = datetime.now(timezone.utc)

    if last_ts and last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=timezone.utc)

    start = last_ts if last_ts else now - timedelta(days=settings.ha_backfill_days)

    if (now - start).total_seconds() < 60:
        logger.debug(f"{entity} up to date, skipping backfill")
        return

    log = logger.info if now - start >= timedelta(days=1) else logger.debug  # periodic pulls stay quiet
    log(f"Backfill {entity} from {start.isoformat()} ({(now - start).days}d)")

    headers = {
        "Authorization": f"Bearer {settings.ha_token}",
        "Content-Type": "application/json",
    }

    total = 0
    current = start

    async with httpx.AsyncClient(timeout=30) as client:
        while current < now:
            chunk_end = min(current + timedelta(days=1), now)
            rows = to_rows(await _fetch_points(client, headers, current, chunk_end, entity))
            if rows:
                inserted = insert(rows)
                total += inserted
                logger.debug(f"  {current.date()} → {inserted} points")
            current = chunk_end
            await asyncio.sleep(0.2)  # be gentle with HA

    log(f"Backfill {entity} complete: {total} points inserted")


async def _fetch_points(
    client: httpx.AsyncClient,
    headers: dict,
    start: datetime,
    end: datetime,
    entity: str,
) -> list[tuple[datetime, float]]:
    # Use Z suffix (no +00:00) to avoid URL-encoding issues with the + character
    start_iso = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = end.strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"{settings.ha_url}/api/history/period/{start_iso}"
    params = {
        "filter_entity_id": entity,
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

    points = []
    for point in data[0]:
        state = point.get("state", "")
        if state in ("unavailable", "unknown", ""):
            continue
        try:
            value = float(state)
            ts_str = point.get("last_changed") or point.get("last_updated", "")
            points.append((datetime.fromisoformat(ts_str.replace("Z", "+00:00")), value))
        except (ValueError, KeyError):
            continue

    return points
