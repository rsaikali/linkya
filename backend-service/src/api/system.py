"""Health check."""

from datetime import datetime

from fastapi import APIRouter


router = APIRouter(tags=["System"])


@router.get("/healthz")
async def healthz():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
