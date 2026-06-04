"""Push live events to the backend SSE bus (fire-and-forget)."""

import logging
import os

import httpx


logger = logging.getLogger(__name__)

_BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")


def emit(event_type: str, data: dict) -> None:
    """Best-effort POST to backend /internal/event. Never raises."""
    try:
        httpx.post(
            f"{_BACKEND_URL}/internal/event",
            json={"type": event_type, "data": data},
            timeout=3.0,
        )
    except Exception as e:
        logger.debug("emit %s failed: %s", event_type, e)
