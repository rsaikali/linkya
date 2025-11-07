"""System and health check endpoints."""

from datetime import datetime

from fastapi import APIRouter

from ..config import settings

router = APIRouter(tags=["System"])


@router.get("/")
async def root():
    """API root entry point."""
    return {
        "message": "Linkya API",
        "version": settings.api_version,
        "endpoints": {
            "latest": "/api/consumption/latest",
            "history": "/api/consumption/history",
            "appliances": "/api/appliances",
            "detections": "/api/detections",
            "signatures_create": "POST /api/signatures",
            "ws_training": "/ws/training",
            "ws_consumption": "/ws/consumption",
            "ws_detections": "/ws/detections",
        },
    }


@router.get("/health")
async def health_check():
    """API health check."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
