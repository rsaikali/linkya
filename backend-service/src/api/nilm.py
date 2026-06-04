"""NILM endpoints — thin proxy to the nilm service + model reads from DB."""

import logging

import httpx
from fastapi import APIRouter, HTTPException

from ..config import settings
from ..db import db_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nilm", tags=["NILM"])

_TIMEOUT = 10.0


async def _post_nilm(path: str) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(f"{settings.nilm_url}{path}")
        r.raise_for_status()
        return r.json()


@router.post("/train")
async def trigger_training():
    """Kick off training in the nilm service (runs in background there)."""
    try:
        return await _post_nilm("/train")
    except httpx.HTTPError as e:
        logger.error("nilm /train failed: %s", e)
        raise HTTPException(status_code=502, detail="Service NILM injoignable")


@router.post("/detect")
async def trigger_detection():
    """Run detection over the full available history."""
    try:
        return await _post_nilm("/detect")
    except httpx.HTTPError as e:
        logger.error("nilm /detect failed: %s", e)
        raise HTTPException(status_code=502, detail="Service NILM injoignable")


@router.get("/models")
async def get_models():
    model = db_manager.get_latest_nilm_model()
    return {"models": [model], "total": 1} if model else {"models": [], "total": 0}


@router.delete("/models")
async def delete_models():
    """Delete all models (DB rows + .keras files via nilm service)."""
    try:
        return await _post_nilm("/models/delete")
    except httpx.HTTPError as e:
        logger.error("nilm /models/delete failed: %s", e)
        raise HTTPException(status_code=502, detail="Service NILM injoignable")
