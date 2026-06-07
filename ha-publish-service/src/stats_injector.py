"""Inject hourly ON-fraction statistics into HA recorder after new detections."""

from datetime import timedelta

import httpx
from loguru import logger

from .config import settings
from .discovery import slug as make_slug


async def discover_statistic_ids(appliances: list[dict]) -> dict[str, str]:
    """Query HA /api/states once to find statistic_id for each appliance numeric sensor.

    Matches entities whose entity_id contains the appliance slug and ends with '_etat'.
    Returns {ha_entity_id: statistic_id}.
    """
    mapping: dict[str, str] = {}
    if not settings.ha_token:
        logger.warning("stats_injector: HA_TOKEN not set — numeric stats injection disabled")
        return mapping
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{settings.ha_url}/api/states",
                headers={"Authorization": f"Bearer {settings.ha_token}"},
                timeout=15,
            )
            r.raise_for_status()
            states = r.json()
    except Exception as exc:
        logger.warning(f"stats_injector: HA states lookup failed: {exc}")
        return mapping

    for appliance in appliances:
        eid = appliance["ha_entity_id"]
        s = make_slug(eid)
        for state in states:
            sid = state["entity_id"]
            if sid.startswith("sensor.") and s in sid and sid.endswith("_etat"):
                mapping[eid] = sid
                logger.info(f"stats_injector: {eid} → {sid}")
                break
        else:
            logger.warning(f"stats_injector: statistic_id not found for {eid} (slug={s})")

    return mapping


async def inject_for_new_detections(
    appliance_id: int,
    ha_entity_id: str,
    statistic_id: str,
    new_detections: list[dict],
    repo,
) -> None:
    """Compute hourly ON-fractions for hours touched by new_detections, push to HA."""
    affected: set = set()
    for det in new_detections:
        h = det["start"].replace(minute=0, second=0, microsecond=0)
        while h < det["end"]:
            affected.add(h)
            h += timedelta(hours=1)

    if not affected:
        return

    stats = []
    for h in sorted(affected):
        h_end = h + timedelta(hours=1)
        detections = repo.get_detections_in_hour(appliance_id, h, h_end)
        total_secs = sum(
            max(0.0, (min(end, h_end) - max(start, h)).total_seconds())
            for start, end in detections
        )
        frac = round(total_secs / 3600, 4)
        stats.append({"start": h.isoformat(), "mean": frac, "min": frac, "max": frac})

    payload = {
        "statistic_id": statistic_id,
        "name": f"NILM {ha_entity_id} État",
        "source": "recorder",
        "unit_of_measurement": "",
        "has_mean": True,
        "has_sum": False,
        "stats": stats,
    }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{settings.ha_url}/api/services/recorder/import_statistics",
                headers={
                    "Authorization": f"Bearer {settings.ha_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=15,
            )
            r.raise_for_status()
        logger.info(
            f"stats_injector: {len(stats)} hour bucket(s) injected for {ha_entity_id}"
        )
    except Exception as exc:
        logger.error(f"stats_injector: HA inject failed for {ha_entity_id}: {exc}")
