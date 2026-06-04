"""API route modules."""

from .appliances import router as appliances_router
from .consumption import router as consumption_router
from .detections import router as detections_router
from .events import router as events_router
from .nilm import router as nilm_router
from .signatures import router as signatures_router
from .system import router as system_router

__all__ = [
    "system_router",
    "consumption_router",
    "appliances_router",
    "signatures_router",
    "detections_router",
    "nilm_router",
    "events_router",
]
