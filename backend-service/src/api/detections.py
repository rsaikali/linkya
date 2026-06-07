"""Detection endpoints."""

import logging

import httpx
from fastapi import APIRouter, HTTPException

from ..config import settings
from ..db import db_manager
from ..events import bus


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/detections", tags=["Detections"])


async def _create_signature(pending: dict):
    """Forward a validate/reassign-derived signature to the nilm service."""
    if not pending:
        return
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(f"{settings.nilm_url}/signatures", json=pending)
            r.raise_for_status()
    except httpx.HTTPError as e:
        logger.error("nilm signature from feedback failed: %s", e)


@router.get("")
async def get_detected_appliances(model_name: str = None):
    detections = db_manager.get_detected_appliances(None, None, model_name=model_name)
    return {"total_detections": len(detections), "detections": detections}


@router.delete("")
async def delete_all_detections():
    result = db_manager.delete_all_detections()
    bus.publish("detections_cleared", {"deleted_count": result["deleted_count"]})
    return {"status": "success", "deleted_count": result["deleted_count"]}


@router.patch("/{detection_id}/validate")
async def validate_detection(detection_id):
    result = db_manager.validate_detection(detection_id, is_correct=True)
    if not result:
        raise HTTPException(status_code=404, detail="Détection non trouvée")
    pending = result.get("pending_signature")
    await _create_signature(pending)
    if pending:
        bus.publish("signature_added", {"appliance_name": pending.get("appliance_name", "")})
    bus.publish("detection_validated", {"id": detection_id, "correct": True})
    return {"status": "success", "detection": result}


@router.patch("/{detection_id}/invalidate")
async def invalidate_detection(detection_id):
    result = db_manager.validate_detection(detection_id, is_correct=False)
    if not result:
        raise HTTPException(status_code=404, detail="Détection non trouvée")
    pending = result.get("pending_signature")
    await _create_signature(pending)
    if pending:
        bus.publish("signature_added", {"appliance_name": pending.get("appliance_name", ""), "is_negative": True})
    bus.publish("detection_validated", {"id": detection_id, "correct": False})
    return {"status": "success", "detection": result}


@router.patch("/{detection_id}/reassign")
async def reassign_detection(detection_id, request: dict):
    appliance_name = request.get("appliance_name")
    if not appliance_name:
        raise HTTPException(status_code=400, detail="Le nom de l'appareil est requis")
    result = db_manager.reassign_detection(detection_id, appliance_name)
    if not result:
        raise HTTPException(status_code=404, detail="Détection non trouvée")
    pending = result.get("pending_signature")
    await _create_signature(pending)
    if pending:
        bus.publish("signature_added", {"appliance_name": pending.get("appliance_name", appliance_name)})
    bus.publish("detection_reassigned", {"id": detection_id, "appliance": appliance_name})
    return {"status": "success", "reassignment": result}
