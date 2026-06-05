"""Appliance management endpoints."""

import logging

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..db import db_manager
from ..events import bus
from ..ha_backfill import run_ha_backfill
from ..models import HaPublishUpdate


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/appliances", tags=["Appliances"])


@router.get("")
async def get_all_appliances():
    """
    Retrieves the list of all known electrical appliances.

    Returns:
        List of appliances with their characteristics
    """
    try:
        appliances = db_manager.get_all_appliances()
        return {"total": len(appliances), "appliances": appliances}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.patch("/{appliance_id}/ha-publish")
async def toggle_ha_publish(appliance_id: int, body: HaPublishUpdate):
    """
    Enables or disables HA publishing for an appliance.
    When enabled, generates ha_entity_id (sensor.nilm_<slug>) and
    ha-publish service will create a MQTT discovery entry in HA.
    """
    try:
        result = db_manager.update_ha_publish(appliance_id=appliance_id, enabled=body.enabled)
        if not result:
            raise HTTPException(status_code=404, detail=f"Appliance {appliance_id} not found")
        bus.publish("appliance_updated", {"id": appliance_id, "ha_publish": body.enabled})
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling ha_publish for appliance {appliance_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.post("/{appliance_id}/reset-energy")
async def reset_energy(appliance_id: int):
    """Reset the HA energy sensor to 0 (baseline = current total, keeps detections).
    Use after clearing the entity's corrupted statistics in HA."""
    try:
        baseline = db_manager.reset_energy(appliance_id)
        bus.publish("appliance_updated", {"id": appliance_id, "energy_reset": True})
        return {"status": "success", "baseline_kwh": baseline}
    except Exception as e:
        logger.error(f"Error resetting energy for appliance {appliance_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.post("/{appliance_id}/ha-backfill")
async def ha_backfill(appliance_id: int):
    """Inject all NILM detections as historical energy statistics into HA (recorder/import_statistics)."""
    appliances = db_manager.get_all_appliances()
    appliance = next((a for a in appliances if a["id"] == appliance_id), None)
    if not appliance:
        raise HTTPException(status_code=404, detail=f"Appliance {appliance_id} not found")
    if not appliance.get("ha_publish") or not appliance.get("ha_entity_id"):
        raise HTTPException(status_code=400, detail="ha_publish disabled or ha_entity_id missing")
    if not settings.ha_token:
        raise HTTPException(status_code=503, detail="HA_TOKEN not configured")

    detections = db_manager.get_detections_for_backfill(appliance_id)
    if not detections:
        return {"status": "no_detections"}

    try:
        result = await run_ha_backfill(settings.ha_url, settings.ha_token, appliance, detections)
    except Exception as e:
        logger.error(f"HA backfill failed for appliance {appliance_id}: {e}")
        raise HTTPException(status_code=502, detail=str(e))

    return result


@router.patch("/{appliance_id}")
async def update_appliance(appliance_id, appliance_data):
    """
    Updates an appliance name.

    Args:
        appliance_id: ID of the appliance to update
        appliance_data: New appliance data (name)

    Returns:
        Updated appliance
    """
    try:
        name = appliance_data.get("name")

        if not name:
            raise HTTPException(status_code=400, detail="Name is required")

        updated_appliance = db_manager.update_appliance(appliance_id=appliance_id, name=name)

        if not updated_appliance:
            raise HTTPException(status_code=404, detail=f"Appliance {appliance_id} not found")

        bus.publish("appliance_updated", {"id": appliance_id, "name": name})
        return updated_appliance
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating appliance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
