"""HA energy publication via WebSocket recorder/import_statistics.

NILM energy is published as *external statistics* (statistic_id
"linkya:<slug>_energy", like Tibber/EDF integrations) — no MQTT entity, no
state_class, no recorder coupling. External statistics are the official way
to write hourly energy into the past, which NILM needs constantly: a cycle
is always detected after it happened, and re-detections rewrite history.
"""

import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import websockets


logger = logging.getLogger(__name__)


def _ha_entity_slug(ha_entity_id: str) -> str:
    """Mirror of ha-publish discovery.slug()."""
    s = ha_entity_id.replace("sensor.", "").replace("binary_sensor.", "")
    s = re.sub(r"[^a-z0-9_]", "_", s.lower())
    s = re.sub(r"_+", "_", s)
    return s.strip("_")


def _build_full_hourly_stats(detections: list[dict]) -> list[dict]:
    """
    Build hourly stats with carry-forward between detections.

    Every hour from the first detection to now is included so HA never sees
    the cumulative sum reset to 0 between detection hours (which causes spikes).
    Hours without detections carry the previous cumulative sum forward.

    Returns [{start: ISO, state: cum_kwh, sum: cum_kwh}].
    """
    hourly_add: dict = defaultdict(float)
    for det in detections:
        st = det["start_time"]
        en = det["end_time"]
        if hasattr(st, "tzinfo") and st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)
        if hasattr(en, "tzinfo") and en.tzinfo is None:
            en = en.replace(tzinfo=timezone.utc)

        total_secs = (en - st).total_seconds()
        energy_kwh = det["energy_wh"] / 1000.0

        if total_secs <= 0:
            hourly_add[st.replace(minute=0, second=0, microsecond=0)] += energy_kwh
            continue

        # Split energy proportionally across every hour boundary the cycle spans.
        cur = st
        while cur < en:
            hour_start = cur.replace(minute=0, second=0, microsecond=0)
            overlap_end = min(en, hour_start + timedelta(hours=1))
            overlap_secs = (overlap_end - cur).total_seconds()
            hourly_add[hour_start] += energy_kwh * overlap_secs / total_secs
            cur = hour_start + timedelta(hours=1)

    if not hourly_add:
        return []

    first_hour = min(hourly_add.keys())
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    stats = []
    cum = 0.0
    hour = first_hour
    while hour <= now:
        cum += hourly_add.get(hour, 0.0)
        stats.append({
            "start": hour.isoformat(),
            "state": round(cum, 4),
            "sum": round(cum, 4),
        })
        hour += timedelta(hours=1)

    return stats


async def _ws_send_recv(ws, payload: dict) -> dict:
    await ws.send(json.dumps(payload))
    return json.loads(await ws.recv())


async def run_ha_backfill(
    ha_url: str,
    ha_token: str,
    appliance: dict,
    detections: list[dict],
) -> dict:
    """
    Publish NILM energy history into HA as external statistics.

    Steps:
    1. Auth
    2. Clear existing statistics (a re-detect can lower past hourly sums;
       import alone only overwrites hours present in the new payload)
    3. Import all hourly entries with carry-forward (monotonic, no gaps)
    """
    slug = _ha_entity_slug(appliance["ha_entity_id"])
    statistic_id = f"linkya:{slug}_energy"
    energy_name = f"NILM {appliance['name']} Énergie"

    stats = _build_full_hourly_stats(detections)
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
        raw = json.loads(await ws.recv())
        if raw.get("type") != "auth_required":
            raise RuntimeError(f"Unexpected HA WS greeting: {raw}")

        auth_resp = await _ws_send_recv(ws, {"type": "auth", "access_token": ha_token})
        if auth_resp.get("type") != "auth_ok":
            raise RuntimeError(f"HA auth failed: {auth_resp}")

        clear_resp = await _ws_send_recv(ws, {
            "id": next_id(),
            "type": "recorder/clear_statistics",
            "statistic_ids": [statistic_id],
        })
        logger.info(f"Cleared statistics for {statistic_id}: {clear_resp.get('success')}")

        # Inject full hourly history (carry-forward, no gaps)
        logger.info(f"Injecting {len(stats)} hourly buckets → {stats[-1]['sum']} kWh total")
        import_resp = await _ws_send_recv(ws, {
            "id": next_id(),
            "type": "recorder/import_statistics",
            "metadata": {
                "has_mean": False,
                "has_sum": True,
                "name": energy_name,
                "source": "linkya",
                "statistic_id": statistic_id,
                "unit_of_measurement": "kWh",
            },
            "stats": stats,
        })

    return {
        "status": "ok" if import_resp.get("success") else "error",
        "entity_id": statistic_id,
        "hours_injected": len(stats),
        "total_kwh": stats[-1]["sum"],
        "ws_error": import_resp.get("error"),
    }
