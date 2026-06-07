"""Server-Sent Events: one stream for all live UI updates."""

import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..config import settings
from ..db import db_manager
from ..events import bus
from ..ha_backfill import run_ha_backfill


logger = logging.getLogger(__name__)
router = APIRouter(tags=["Events"])


@router.get("/api/events")
async def events():
    """SSE stream. Frontend opens one EventSource and receives every event:
    signature_added, signature_deleted, appliance_updated, detection_new,
    detections_cleared, training_progress, training_complete, training_error.
    """
    return StreamingResponse(
        bus.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class InternalEvent(BaseModel):
    type: str
    data: dict = {}


async def _auto_ha_backfill():
    """After detection_complete: reinject all NILM detections as historical
    HA energy statistics for every ha_publish appliance.  Runs as a background
    task so the /internal/event response is not delayed."""
    if not settings.ha_token:
        logger.info("auto-backfill skipped: HA_TOKEN not set")
        return

    appliances = db_manager.get_all_appliances()
    targets = [a for a in appliances if a.get("ha_publish") and a.get("ha_entity_id")]

    if not targets:
        return

    logger.info("auto-backfill: %d appliance(s)", len(targets))
    bus.publish("ha_backfill_start", {"count": len(targets)})

    results = []
    for appliance in targets:
        detections = db_manager.get_detections_for_backfill(appliance["id"])
        if not detections:
            logger.info("auto-backfill %s: no detections, skip", appliance["name"])
            continue
        try:
            result = await run_ha_backfill(
                settings.ha_url, settings.ha_token, appliance, detections
            )
            logger.info(
                "auto-backfill %s: %d h → %.3f kWh",
                appliance["name"],
                result.get("hours_injected", 0),
                result.get("total_kwh", 0.0),
            )
            results.append({"name": appliance["name"], **result})
        except Exception as e:
            logger.error("auto-backfill %s failed: %s", appliance["name"], e)
            results.append({"name": appliance["name"], "status": "error", "error": str(e)})

    bus.publish("ha_backfill_complete", {"results": results})


@router.post("/internal/event")
async def push_event(
    evt: InternalEvent,
    background_tasks: BackgroundTasks,
    x_internal_token: str = Header(default=""),
):
    """Internal-only: the nilm service posts training/detection progress here
    so the backend can fan it out over SSE. Token-gated when INTERNAL_TOKEN is set.
    """
    if settings.internal_token and x_internal_token != settings.internal_token:
        raise HTTPException(status_code=403, detail="Forbidden")
    bus.publish(evt.type, evt.data)

    # Backfill only after a full detection run (not cron 2h window).
    if evt.type == "detection_complete" and evt.data.get("full_detect"):
        background_tasks.add_task(_auto_ha_backfill)

    return {"ok": True}
