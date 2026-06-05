"""HA historical statistics backfill via WebSocket recorder/import_statistics."""

import json
import logging
import re
from collections import defaultdict
from datetime import timezone

import websockets


logger = logging.getLogger(__name__)


def _ha_entity_slug(ha_entity_id: str) -> str:
    """Mirror of ha-publish discovery.slug()."""
    s = ha_entity_id.replace("sensor.", "").replace("binary_sensor.", "")
    s = re.sub(r"[^a-z0-9_]", "_", s.lower())
    s = re.sub(r"_+", "_", s)
    return s.strip("_")


def _build_hourly_stats(detections: list[dict]) -> list[dict]:
    """
    Group detections by hour of start_time.
    Returns [{start: ISO, state: cumulative_kwh, sum: cumulative_kwh}] sorted by hour.
    """
    hourly: dict = defaultdict(float)
    for det in detections:
        st = det["start_time"]
        if hasattr(st, "tzinfo") and st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)
        hour = st.replace(minute=0, second=0, microsecond=0)
        hourly[hour] += det["energy_wh"] / 1000.0

    cum = 0.0
    stats = []
    for hour in sorted(hourly.keys()):
        cum += hourly[hour]
        stats.append({
            "start": hour.isoformat(),
            "state": round(cum, 4),
            "sum": round(cum, 4),
        })
    return stats


async def run_ha_backfill(
    ha_url: str,
    ha_token: str,
    appliance: dict,
    detections: list[dict],
) -> dict:
    """
    Import NILM energy history into HA via recorder/import_statistics.

    Looks up the actual HA entity_id by unique_id from the entity registry,
    then injects hourly cumulative kWh statistics.
    """
    slug = _ha_entity_slug(appliance["ha_entity_id"])
    energy_unique_id = f"linkya_{slug}_energy"
    energy_name = f"NILM {appliance['name']} Énergie"

    stats = _build_hourly_stats(detections)
    if not stats:
        return {"status": "no_detections"}

    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    msg_id = 0

    def next_id() -> int:
        nonlocal msg_id
        msg_id += 1
        return msg_id

    async with websockets.connect(ws_url) as ws:
        # Auth
        raw = await ws.recv()
        msg = json.loads(raw)
        if msg.get("type") != "auth_required":
            raise RuntimeError(f"Unexpected HA WS message: {msg}")

        await ws.send(json.dumps({"type": "auth", "access_token": ha_token}))
        raw = await ws.recv()
        msg = json.loads(raw)
        if msg.get("type") != "auth_ok":
            raise RuntimeError(f"HA auth failed: {msg}")

        # Resolve entity_id from registry
        eid = next_id()
        await ws.send(json.dumps({"id": eid, "type": "config/entity_registry/list"}))
        raw = await ws.recv()
        msg = json.loads(raw)
        entities = msg.get("result") or []
        entity = next((e for e in entities if e.get("unique_id") == energy_unique_id), None)
        if not entity:
            raise RuntimeError(
                f"No HA entity with unique_id '{energy_unique_id}'. "
                "Make sure ha-publish has announced discovery at least once."
            )
        statistic_id = entity["entity_id"]
        logger.info(f"Backfill target: {statistic_id} ({len(stats)} hourly buckets, {stats[-1]['sum']} kWh total)")

        # Import statistics
        eid = next_id()
        await ws.send(json.dumps({
            "id": eid,
            "type": "recorder/import_statistics",
            "metadata": {
                "has_mean": False,
                "has_sum": True,
                "name": energy_name,
                "source": "recorder",
                "statistic_id": statistic_id,
                "unit_of_measurement": "kWh",
            },
            "stats": stats,
        }))
        raw = await ws.recv()
        msg = json.loads(raw)

    return {
        "status": "ok" if msg.get("success") else "error",
        "entity_id": statistic_id,
        "buckets": len(stats),
        "total_kwh": stats[-1]["sum"] if stats else 0,
        "ws_result": msg.get("result"),
        "ws_error": msg.get("error"),
    }
