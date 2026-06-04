"""Appliance management endpoints."""

import logging

from fastapi import APIRouter, HTTPException

from ..db import db_manager
from ..events import bus
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
