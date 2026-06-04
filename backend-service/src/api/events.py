"""Server-Sent Events: one stream for all live UI updates."""

import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..events import bus

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


@router.post("/internal/event")
async def push_event(evt: InternalEvent):
    """Internal-only: the nilm service posts training/detection progress here
    so the backend can fan it out over SSE. Reachable only on the Docker network.
    """
    bus.publish(evt.type, evt.data)
    return {"ok": True}
