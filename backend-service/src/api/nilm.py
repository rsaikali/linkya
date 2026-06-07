"""NILM endpoints — thin proxy to the nilm service + model reads from DB."""

import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from ..config import settings
from ..db import db_manager
from ..ha_backfill import run_ha_backfill


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


@router.post("/publish")
async def trigger_publish(background_tasks: BackgroundTasks):
    """Backfill all NILM detections into HA as historical energy statistics."""
    if not settings.ha_token:
        raise HTTPException(status_code=503, detail="HA_TOKEN non configuré")

    appliances = db_manager.get_all_appliances()
    targets = [a for a in appliances if a.get("ha_publish") and a.get("ha_entity_id")]
    if not targets:
        return {"status": "skipped", "reason": "Aucun appareil avec ha_publish actif"}

    async def _do_publish():
        results = []
        for appliance in targets:
            detections = db_manager.get_detections_for_backfill(appliance["id"])
            if not detections:
                results.append({"name": appliance["name"], "status": "no_detections"})
                continue
            try:
                result = await run_ha_backfill(settings.ha_url, settings.ha_token, appliance, detections)
                logger.info("publish %s: %d h → %.3f kWh", appliance["name"],
                            result.get("hours_injected", 0), result.get("total_kwh", 0.0))
                results.append({"name": appliance["name"], **result})
            except Exception as e:
                logger.error("publish %s failed: %s", appliance["name"], e)
                results.append({"name": appliance["name"], "status": "error", "error": str(e)})
        return results

    background_tasks.add_task(_do_publish)
    return {"status": "started", "appliances": len(targets)}


@router.get("/models")
async def get_models():
    """All trained models, newest first. is_champion flags the active detection model."""
    try:
        result = await _get_nilm("/models")
        return result
    except httpx.HTTPError:
        # Fallback to DB if nilm service is down.
        model = db_manager.get_latest_nilm_model()
        return {"models": [model] if model else [], "total": 1 if model else 0}


@router.post("/models/{model_id}/promote")
async def promote_model(model_id: int):
    """Promote a challenger model to champion. Detection uses it immediately."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(f"{settings.nilm_url}/models/{model_id}/promote")
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        logger.error("nilm /models/%d/promote failed: %s", model_id, e)
        raise HTTPException(status_code=502, detail="Service NILM injoignable")


async def _get_nilm(path: str) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{settings.nilm_url}{path}")
        r.raise_for_status()
        return r.json()


@router.get("/scorecard")
async def get_scorecard(
    appliance: str = Query(..., description="Appliance name"),
    window_days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
):
    """Per-appliance NILM scorecard: kWh, cycles, confidence, recovered share."""
    result = db_manager.get_scorecard(appliance, window_days)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Appliance '{appliance}' not found")
    return result


@router.get("/history")
async def get_history(
    appliance: str = Query(..., description="Appliance name"),
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
):
    """Daily kWh series — one float per day, zeros for quiet days, oldest first."""
    result = db_manager.get_history(appliance, days)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Appliance '{appliance}' not found")
    return result


@router.get("/cycles")
async def get_cycles(
    appliance: str = Query(..., description="Appliance name"),
    limit: int = Query(60, ge=1, le=500, description="Max number of cycles to return"),
):
    """Recent detection cycles (hour + duration_min) and computed peak_hours."""
    result = db_manager.get_cycles(appliance, limit)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Appliance '{appliance}' not found")
    return result


@router.delete("/models")
async def delete_models():
    """Delete all models (DB rows + .keras files via nilm service)."""
    try:
        return await _post_nilm("/models/delete")
    except httpx.HTTPError as e:
        logger.error("nilm /models/delete failed: %s", e)
        raise HTTPException(status_code=502, detail="Service NILM injoignable")
