"""
Import historical NILM detections into HA long-term statistics.

Uses HA WebSocket API command "recorder/import_statistics".
The REST /api/recorder/import_statistics doesn't exist — only WebSocket.

Strategy:
  - Build full hourly grid (zero-fill gaps between first and last detection).
  - Send all buckets → HA upserts by (statistic_id, start_of_hour).
  - On re-backfill (new model), gaps that used to have detections are zeroed.
"""

import json
from datetime import datetime, timedelta, timezone

from loguru import logger

import websockets

from .config import settings
from .database import repo
from .discovery import EXTERNAL_SOURCE, external_stat_id


async def backfill_appliance(appliance: dict) -> bool:
    """
    Push hourly energy buckets to HA via WebSocket recorder/import_statistics.
    Returns True on success, False on error (non-blocking).
    """
    app_id = appliance["id"]
    app_name = appliance["name"]
    stat_id = external_stat_id(appliance["ha_entity_id"])

    detections = repo.get_detections_for_backfill(app_id)
    if not detections:
        logger.info(f"Backfill {app_name}: no detections, skipping")
        return True

    logger.info(f"Backfill {app_name}: {len(detections)} détections → hourly grid")

    # ── Build hourly energy map ───────────────────────────────────────────────
    hourly: dict[datetime, float] = {}
    for det in detections:
        start = det["start_time"]
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        bucket = start.replace(minute=0, second=0, microsecond=0)
        hourly[bucket] = hourly.get(bucket, 0.0) + det["energy_wh"]

    if not hourly:
        return True

    # ── Full grid (zero-fill) from first to last detected hour ───────────────
    first_hour = min(hourly)
    last_hour = max(hourly)
    cumulative = 0.0
    stats = []
    current = first_hour
    while current <= last_hour:
        cumulative += hourly.get(current, 0.0)
        stats.append({
            "start": current.isoformat(),
            "state": round(cumulative / 1000.0, 3),
            "sum": round(cumulative / 1000.0, 3),
        })
        current += timedelta(hours=1)

    total_kwh = cumulative / 1000.0
    n_detected = sum(1 for v in hourly.values() if v > 0)

    # ── WebSocket call ────────────────────────────────────────────────────────
    ws_url = settings.ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"

    try:
        async with websockets.connect(ws_url, open_timeout=10) as ws:
            # Step 1: auth_required
            msg = json.loads(await ws.recv())
            if msg.get("type") != "auth_required":
                raise RuntimeError(f"Unexpected first message: {msg}")

            # Step 2: authenticate
            await ws.send(json.dumps({"type": "auth", "access_token": settings.ha_token}))
            msg = json.loads(await ws.recv())
            if msg.get("type") != "auth_ok":
                raise RuntimeError(f"Auth failed: {msg}")

            # Step 3: import_statistics
            cmd = {
                "id": 1,
                "type": "recorder/import_statistics",
                "metadata": {
                    "has_mean": False,
                    "has_sum": True,
                    "name": f"NILM {app_name} Énergie",
                    "source": EXTERNAL_SOURCE,
                    "statistic_id": stat_id,
                    "unit_of_measurement": "kWh",
                },
                "stats": stats,
            }
            await ws.send(json.dumps(cmd))
            result = json.loads(await ws.recv())

            if result.get("success") is False:
                raise RuntimeError(f"HA error: {result.get('error')}")

        logger.info(
            f"Backfill {app_name}: OK — "
            f"{n_detected}/{len(stats)} heures avec détection, "
            f"{total_kwh:.3f} kWh → {stat_id}"
        )
        return True

    except Exception as e:
        logger.warning(f"Backfill {app_name} failed (non-bloquant): {e}")
        return False
