"""Detection management endpoints."""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from ..db import db_manager
from ..utils.redis_client import get_redis_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/detections", tags=["Detections"])


@router.get("")
async def get_detected_appliances():
    """
    Récupère toutes les détections d'appareils par le NILM.

    Returns:
        Liste de toutes les détections avec informations sur les appareils
    """
    try:
        # Récupérer toutes les détections (pas de filtre temporel)
        detections = db_manager.get_detected_appliances(None, None)
        logger.info(f"get_detected_appliances returned {len(detections)} detections")

        result = {
            "start_time": None,
            "end_time": None,
            "total_detections": len(detections),
            "detections": detections,
        }
        logger.info(f"Returning response with {len(result['detections'])} detections")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.delete("")
async def delete_all_detections():
    """
    Supprime toutes les détections de la base de données.

    Returns:
        Message de confirmation avec le nombre de détections supprimées
    """
    try:
        result = db_manager.delete_all_detections()

        # Publish detections_cleared event to Redis for WebSocket streaming
        redis_client = get_redis_client()
        if redis_client:
            try:
                message = json.dumps(
                    {
                        "event": "detections_cleared",
                        "data": {"deleted_count": result["deleted_count"]},
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                redis_client.publish("detections:updates", message)
                logger.info(
                    f"Published detections_cleared to Redis ({result['deleted_count']} deleted)"
                )
            except Exception as e:
                logger.error(f"Failed to publish detections_cleared to Redis: {e}")

        return {
            "status": "success",
            "message": f"{result['deleted_count']} détection(s) supprimée(s)",
            "deleted_count": result["deleted_count"],
        }
    except Exception as e:
        logger.error(f"Erreur lors de la suppression des détections: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.patch("/{detection_id}/validate")
async def validate_detection(detection_id):
    """
    Marque une détection comme correcte pour l'apprentissage par feedback.

    Args:
        detection_id: ID de la détection à valider

    Returns:
        Message de confirmation avec informations de la détection validée
    """
    try:
        result = db_manager.validate_detection(detection_id, is_correct=True)
        if not result:
            raise HTTPException(status_code=404, detail="Détection non trouvée")

        return {
            "status": "success",
            "message": f"Détection validée comme correcte: {result['appliance_name']}",
            "detection": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Erreur lors de la validation de la détection {detection_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.patch("/{detection_id}/invalidate")
async def invalidate_detection(detection_id):
    """
    Marque une détection comme incorrecte pour l'apprentissage par feedback.

    Args:
        detection_id: ID de la détection à invalider

    Returns:
        Message de confirmation avec informations de la détection invalidée
    """
    try:
        result = db_manager.validate_detection(detection_id, is_correct=False)
        if not result:
            raise HTTPException(status_code=404, detail="Détection non trouvée")

        return {
            "status": "success",
            "message": f"Détection marquée comme incorrecte: {result['appliance_name']}",
            "detection": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Erreur lors de l'invalidation de la détection {detection_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.patch("/{detection_id}/reassign")
async def reassign_detection(detection_id, request):
    """
    Reassigns a detection to the correct appliance.
    Creates a positive signature for the correct appliance
    and hides the detection from the list.

    Args:
        detection_id: ID of the detection to reassign
        request: JSON with 'appliance_name' field

    Returns:
        Message de confirmation avec informations de réassignation
    """
    try:
        appliance_name = request.get("appliance_name")
        if not appliance_name:
            raise HTTPException(
                status_code=400, detail="Le nom de l'appareil est requis"
            )

        result = db_manager.reassign_detection(detection_id, appliance_name)
        if not result:
            raise HTTPException(status_code=404, detail="Détection non trouvée")

        return {
            "status": "success",
            "message": (
                f"Détection réassignée de {result['incorrect_appliance']} "
                f"à {result['correct_appliance']}"
            ),
            "reassignment": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Erreur lors de la réassignation de la détection "
            f"{detection_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")
