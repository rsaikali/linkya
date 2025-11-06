"""Main FastAPI backend for Nilmia."""

import asyncio
import json
import logging
import redis
import redis.asyncio as aioredis
from datetime import datetime, timedelta
from typing import Optional, Set

from fastapi import FastAPI, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import db_manager

# Logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Redis client for publishing real-time events
try:
    redis_client = redis.from_url(
        settings.celery_broker_url,
        decode_responses=True
    )
    logger.info("✅ Redis client initialized for real-time events")
except Exception as e:
    logger.warning(f"⚠️ Redis client init failed: {e}")
    redis_client = None

# Pydantic models
class SignatureCreate(BaseModel):
    """Model for creating a new appliance signature."""
    appliance_name: str
    start_time: str  # ISO format
    end_time: str    # ISO format

# FastAPI application creation
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS configuration to allow requests from the frontend
# Note: WebSocket connections bypass CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (safe for WebSocket + public API)
    allow_credentials=False,  # Must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["System"])
async def root():
    """API root entry point."""
    return {
        "message": "Nilmia API",
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


@app.get("/health", tags=["System"])
async def health_check():
    """API health check."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/consumption/latest", tags=["Consumption"])
async def get_latest_consumption():
    """
    Retrieves the latest energy consumption value.

    Returns:
        Latest measurement with timestamp, power, index, temperature
    """
    try:
        data = db_manager.get_latest_consumption()
        if not data:
            raise HTTPException(status_code=404, detail="Aucune donnée disponible")
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.get("/api/consumption/history", tags=["Consumption"])
async def get_consumption_history(
    interval: str = Query(
        default="auto",
        description="Aggregation interval (auto, raw, 1 minute, 5 minutes, 15 minutes, 1 hour)"
    ),
):
    """
    Retrieves all consumption history data.

    Args:
        interval: Data aggregation interval (auto adapts to data range)

    Returns:
        List of consumption points aggregated by interval
    """
    try:
        # Get min/max timestamps from database
        all_data_range = db_manager.get_consumption_time_range()
        if not all_data_range:
            raise HTTPException(
                status_code=404,
                detail="Aucune donnée disponible"
            )
        start_time_dt = all_data_range['min_time']
        end_time_dt = all_data_range['max_time']
        
        # Auto-determine optimal interval based on data range
        if interval == "auto":
            duration_hours = (end_time_dt - start_time_dt).total_seconds() / 3600
            if duration_hours <= 6:
                interval = "raw"
            elif duration_hours <= 24:
                interval = "1 minute"
            elif duration_hours <= 72:
                interval = "5 minutes"
            elif duration_hours <= 168:
                interval = "10 minutes"
            else:
                interval = "1 hour"

        data = db_manager.get_consumption_history(
            start_time_dt, end_time_dt, interval
        )
        if not data:
            raise HTTPException(
                status_code=404,
                detail="Aucune donnée disponible pour cette période"
            )

        return {
            "start_time": start_time_dt.isoformat(),
            "end_time": end_time_dt.isoformat(),
            "interval": interval,
            "data_points": len(data),
            "data": data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.get("/api/appliances", tags=["Appliances"])
async def get_all_appliances():
    """
    Retrieves the list of all known electrical appliances.

    Returns:
        List of appliances with their characteristics
    """
    try:
        appliances = db_manager.get_all_appliances()
        return {
            "total": len(appliances),
            "appliances": appliances,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.patch("/api/appliances/{appliance_id}", tags=["Appliances"])
async def update_appliance(appliance_id: int, appliance_data: dict):
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
            raise HTTPException(
                status_code=400, detail="Name is required"
            )
        
        updated_appliance = db_manager.update_appliance(
            appliance_id=appliance_id,
            name=name
        )
        
        if not updated_appliance:
            raise HTTPException(
                status_code=404, detail=f"Appliance {appliance_id} not found"
            )
        
        return updated_appliance
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating appliance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.get("/api/signatures", tags=["Signatures"])
async def get_all_signatures():
    """
    Retrieves all signatures.

    Returns:
        List of all signatures with appliance information
    """
    try:
        signatures = db_manager.get_all_signatures_with_appliance()
        
        return {
            "total": len(signatures),
            "signatures": signatures,
        }
    except Exception as e:
        logger.error(f"Error retrieving signatures: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Server error: {str(e)}"
        )


@app.delete("/api/signatures", tags=["Signatures"])
async def delete_all_signatures():
    """
    Supprime toutes les signatures de la base de données.

    Returns:
        Message de confirmation avec le nombre de signatures supprimées
    """
    try:
        result = db_manager.delete_all_signatures()
        
        return {
            "status": "success",
            "message": f"{result['signatures_deleted']} signature(s) supprimée(s)",
            "signatures_deleted": result['signatures_deleted']
        }
    except Exception as e:
        logger.error(f"Erreur lors de la suppression des signatures: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.delete("/api/signatures/{signature_id}", tags=["Signatures"])
async def delete_signature(signature_id: int):
    """
    Deletes a specific signature.

    Args:
        signature_id: ID of the signature to delete

    Returns:
        Confirmation message
    """
    try:
        result = db_manager.delete_signature(signature_id)
        if not result:
            raise HTTPException(status_code=404, detail="Signature non trouvée")

        return {
            "status": "success",
            "message": f"Signature supprimée: {result['appliance_name']}",
            "signature": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la signature {signature_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.delete("/api/detections", tags=["Detections"])
async def delete_all_detections():
    """
    Supprime toutes les détections de la base de données.

    Returns:
        Message de confirmation avec le nombre de détections supprimées
    """
    try:
        result = db_manager.delete_all_detections()
        
        # Publish detections_cleared event to Redis for WebSocket streaming
        if redis_client:
            try:
                import json
                from datetime import datetime
                message = json.dumps({
                    "event": "detections_cleared",
                    "data": {
                        "deleted_count": result['deleted_count']
                    },
                    "timestamp": datetime.utcnow().isoformat()
                })
                redis_client.publish("detections:updates", message)
                logger.info(f"📢 Published detections_cleared to Redis ({result['deleted_count']} deleted)")
            except Exception as e:
                logger.error(f"Failed to publish detections_cleared to Redis: {e}")

        return {
            "status": "success",
            "message": f"{result['deleted_count']} détection(s) supprimée(s)",
            "deleted_count": result['deleted_count']
        }
    except Exception as e:
        logger.error(f"Erreur lors de la suppression des détections: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.patch("/api/detections/{detection_id}/validate", tags=["Detections"])
async def validate_detection(detection_id: int):
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
            "detection": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la validation de la détection {detection_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.patch("/api/detections/{detection_id}/invalidate", tags=["Detections"])
async def invalidate_detection(detection_id: int):
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
            "detection": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'invalidation de la détection {detection_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.patch("/api/detections/{detection_id}/reassign", tags=["Detections"])
async def reassign_detection(detection_id: int, request: dict):
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
                status_code=400,
                detail="Le nom de l'appareil est requis"
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
            "reassignment": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Erreur lors de la réassignation de la détection "
            f"{detection_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.get("/api/detections", tags=["Detections"])
async def get_detected_appliances():
    """
    Récupère toutes les détections d'appareils par le NILM.

    Returns:
        Liste de toutes les détections avec informations sur les appareils
    """
    try:
        # Récupérer toutes les détections (pas de filtre temporel)
        detections = db_manager.get_detected_appliances(None, None)
        logger.info(f"🔍 get_detected_appliances returned {len(detections)} detections")

        result = {
            "start_time": None,
            "end_time": None,
            "total_detections": len(detections),
            "detections": detections,
        }
        logger.info(f"🔍 Returning response with {len(result['detections'])} detections")
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur: {str(e)}"
        )


@app.post("/api/signatures", tags=["Signatures"])
async def create_signature(signature: SignatureCreate):
    """
    Crée une nouvelle signature d'appareil pour l'entraînement NILM.
    
    Cette endpoint envoie une tâche Celery au service NILM pour traiter
    la signature et ajouter les données d'entraînement.
    
    Args:
        signature: Données de la signature (appliance_name, start_time, end_time)
    
    Returns:
        Confirmation message with signature details
    """
    try:
        from .config import get_celery_app
        
        celery_app = get_celery_app()
        logger.info(
            f"Création de signature pour {signature.appliance_name} "
            f"de {signature.start_time} à {signature.end_time}"
        )
        
        # Envoyer la tâche au service NILM
        task = celery_app.send_task(
            'add_nilm_signature',
            args=[
                signature.appliance_name,
                signature.start_time,
                signature.end_time,
                False  # is_negative=False (signature positive)
            ],
            queue='nilm',
            routing_key='nilm.add_nilm_signature'
        )
        
        logger.info(f"Tâche de création de signature créée: {task.id}")
        
        return {
            "status": "success",
            "message": f"Signature créée pour {signature.appliance_name}",
            "task_id": str(task.id),
            "appliance_name": signature.appliance_name,
            "start_time": signature.start_time,
            "end_time": signature.end_time
        }
        
    except Exception as e:
        logger.error(
            f"Erreur lors de la création de la signature: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur: {str(e)}"
        )


@app.post("/api/nilm/train", tags=["NILM"])
async def trigger_nilm_training():
    """
    Lance l'entraînement manuel du modèle NILM.
    
    Annule automatiquement tous les entraînements en cours ou en attente
    avant de lancer le nouveau.
    
    Returns:
        Task ID and status
    """
    try:
        from .config import get_celery_app
        
        celery_app = get_celery_app()
        logger.info("Lancement de l'entraînement NILM")
        
        # Incrémenter un compteur pour marquer ce training comme légitime
        training_generation = 0
        if redis_client:
            try:
                # Incrémenter atomiquement le compteur de génération
                training_generation = redis_client.incr(
                    "nilm:training:generation"
                )
                logger.info(
                    f"Nouvelle génération de training: {training_generation}"
                )
            except Exception as e:
                logger.warning(
                    f"Impossible d'incrémenter génération: {e}"
                )
        
        # 4. Envoyer la nouvelle tâche avec la génération en argument
        task = celery_app.send_task(
            'train_nilm_model',
            args=[2, training_generation],  # min_signatures, generation
            queue='nilm',
            routing_key='nilm.train_nilm_model'
        )
        
        logger.info(f"Tâche d'entraînement créée: {task.id}")
        
        return {
            "status": "pending",
            "message": "Entraînement du modèle NILM lancé",
            "task_id": str(task.id),
        }
        
    except Exception as e:
        logger.error(
            f"Erreur lors du lancement de l'entraînement: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur: {str(e)}"
        )




@app.post("/api/nilm/detect", tags=["NILM"])
async def trigger_nilm_detection():
    """
    Lance la détection automatique d'appareils par NILM.
    
    Returns:
        Task ID and status
    """
    try:
        from .config import get_celery_app
        
        celery_app = get_celery_app()
        logger.info("Lancement de la détection NILM")
        
        # Envoyer la tâche à la queue NILM
        task = celery_app.send_task(
            'detect_nilm_appliances',
            queue='nilm',
            routing_key='nilm.detect_nilm_appliances'
        )
        
        logger.info(f"Tâche de détection créée: {task.id}")
        
        return {
            "status": "pending",
            "message": "Détection NILM lancée",
            "task_id": str(task.id),
        }
        
    except Exception as e:
        logger.error(f"Erreur lors du lancement de la détection: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur: {str(e)}"
        )


@app.get("/api/nilm/models", tags=["NILM"])
async def get_nilm_models(
    page: int = Query(default=1, ge=1, description="Numéro de page"),
    per_page: int = Query(default=10, ge=1, le=100, description="Nombre d'éléments par page"),
):
    """
    Récupère l'historique des modèles NILM entraînés avec pagination.
    
    Args:
        page: Numéro de page (commence à 1)
        per_page: Nombre de modèles par page (1-100)
    
    Returns:
        Liste paginée des modèles avec leurs métriques
    """
    try:
        models = db_manager.get_nilm_models_paginated(page=page, per_page=per_page)
        
        return {
            "page": page,
            "per_page": per_page,
            "total": models["total"],
            "total_pages": models["total_pages"],
            "models": models["models"],
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des modèles: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur: {str(e)}"
        )


@app.delete("/api/nilm/models/{model_id}", tags=["NILM"])
async def delete_nilm_model(model_id: int):
    """
    Supprime un modèle NILM de la base de données et du filesystem.

    Args:
        model_id: ID du modèle à supprimer

    Returns:
        Confirmation de suppression avec détails

    Raises:
        HTTPException 404: Modèle non trouvé
        HTTPException 500: Erreur serveur
    """
    import os

    try:
        # Supprimer de la base de données
        result = db_manager.delete_nilm_model(model_id)
        
        # Supprimer les fichiers du filesystem
        model_name = result.get("model_name")
        model_path = result.get("model_path")
        deleted_files = []
        
        if model_path and os.path.exists(model_path):
            try:
                # Supprimer le fichier .keras
                os.remove(model_path)
                deleted_files.append(model_path)
                logger.info(f"Fichier modèle supprimé: {model_path}")
                
                # Supprimer le fichier metadata JSON
                metadata_path = model_path.replace(".keras", ".metadata.json")
                if os.path.exists(metadata_path):
                    os.remove(metadata_path)
                    deleted_files.append(metadata_path)
                    logger.info(f"Fichier metadata supprimé: {metadata_path}")
                        
            except OSError as e:
                logger.warning(f"Erreur lors de la suppression des fichiers: {e}")
        
        return {
            "message": "Modèle supprimé avec succès",
            "model_id": result["id"],
            "model_name": model_name,
            "deleted_files": deleted_files,
        }
        
    except ValueError as e:
        # Modèle non trouvé
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Erreur lors de la suppression du modèle {model_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur: {str(e)}"
        )


@app.delete("/api/nilm/models", tags=["NILM"])
async def delete_all_nilm_models():
    """
    Supprime TOUS les modèles NILM de la base de données et
    du filesystem.

    Returns:
        Confirmation de suppression avec statistiques

    Raises:
        HTTPException 500: Erreur serveur
    """
    import os
    import glob

    try:
        # Récupérer tous les modèles avant de les supprimer
        models_data = db_manager.get_nilm_models_paginated(
            page=1, per_page=1000
        )
        all_models = models_data.get("models", [])
        
        deleted_count = 0
        deleted_files = []
        errors = []
        
        # Supprimer chaque modèle de la base de données
        for model in all_models:
            try:
                model_id = model.get("id")
                model_path = model.get("model_path")
                
                # Supprimer de la base de données
                db_manager.delete_nilm_model(model_id)
                deleted_count += 1
                
                # Supprimer les fichiers du filesystem
                if model_path and os.path.exists(model_path):
                    try:
                        # Supprimer le fichier .keras
                        os.remove(model_path)
                        deleted_files.append(model_path)
                        
                        # Supprimer le fichier metadata JSON
                        metadata_path = model_path.replace(
                            ".keras", ".metadata.json"
                        )
                        if os.path.exists(metadata_path):
                            os.remove(metadata_path)
                            deleted_files.append(metadata_path)
                    except OSError as e:
                        errors.append(
                            f"Fichier {model_path}: {str(e)}"
                        )
            except Exception as e:
                errors.append(f"Modèle {model_id}: {str(e)}")
        
        # Nettoyer les fichiers orphelins dans /models
        try:
            models_dir = "/models"
            if os.path.exists(models_dir):
                orphan_files = glob.glob(
                    os.path.join(models_dir, "*.keras")
                )
                orphan_files += glob.glob(
                    os.path.join(models_dir, "*.metadata.json")
                )
                
                for file_path in orphan_files:
                    try:
                        os.remove(file_path)
                        deleted_files.append(file_path)
                        logger.info(f"Fichier orphelin supprimé: {file_path}")
                    except OSError as e:
                        errors.append(f"Fichier orphelin {file_path}: {str(e)}")
        except Exception as e:
            logger.warning(f"Erreur lors du nettoyage des fichiers orphelins: {e}")
        
        logger.info(
            f"Suppression de tous les modèles terminée: "
            f"{deleted_count} modèle(s), {len(deleted_files)} fichier(s)"
        )
        
        return {
            "message": f"{deleted_count} modèle(s) supprimé(s) avec succès",
            "deleted_count": deleted_count,
            "deleted_files": deleted_files,
            "errors": errors if errors else None,
        }
        
    except Exception as e:
        logger.error(
            f"Erreur lors de la suppression de tous les modèles: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur: {str(e)}"
        )


# ============================================================================
# ============================================================================
# Export/Import CSV des signatures
# ============================================================================


@app.get("/api/signatures/export", tags=["Signatures"])
async def export_signatures():
    """
    Exporte toutes les signatures au format CSV.

    Returns:
        Fichier CSV avec colonnes: appliance_name, start_time, end_time, is_negative
    """
    import csv
    from io import StringIO
    from fastapi.responses import Response

    try:
        signatures = db_manager.get_all_signatures_with_appliance()

        # Créer le CSV en mémoire
        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "appliance_name",
            "start_time",
            "end_time",
            "is_negative"
        ])

        # Données
        for sig in signatures:
            writer.writerow([
                sig["appliance_name"],
                sig["start_time"],
                sig["end_time"],
                sig.get("is_negative", False)
            ])

        csv_content = output.getvalue()

        # Générer le nom du fichier avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"nilmia_signatures_{timestamp}.csv"

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'export CSV: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur lors de l'export: {str(e)}"
        )


@app.post("/api/signatures/import")
async def import_signatures(file: UploadFile):
    """
    Importe des signatures depuis un fichier CSV.

    Le CSV doit contenir les colonnes:
    appliance_name, start_time, end_time, is_negative (optionnel)

    Args:
        file: Fichier CSV uploadé (multipart/form-data)

    Returns:
        Rapport d'import avec nombre de succès et erreurs détaillées
    """
    import csv
    from io import StringIO

    # Helper function to publish progress to WebSocket
    def publish_progress_sync(event: str, data: dict):
        """Publish import progress to Redis for WebSocket streaming"""
        try:
            if redis_client:
                message = json.dumps({
                    "event": event,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat()
                })
                redis_client.publish("import:progress", message)
                logger.info(f"📢 Published {event} to Redis")
        except Exception as e:
            logger.error(f"Failed to publish progress to Redis: {e}")

    try:
        # Publish import_start event
        publish_progress_sync("import_start", {
            "status": "started",
            "filename": file.filename
        })

        # Lire le contenu du CSV
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Premier passage : compter les lignes totales
        lines = content_str.strip().split('\n')
        total_lines_expected = len(lines) - 1  # -1 pour le header
        
        csv_reader = csv.DictReader(StringIO(content_str))

        # Valider les colonnes requises
        required_columns = {
            "appliance_name",
            "start_time",
            "end_time"
        }
        if not required_columns.issubset(csv_reader.fieldnames or []):
            publish_progress_sync("import_error", {
                "error": f"Colonnes requises: {', '.join(required_columns)}"
            })
            raise HTTPException(
                status_code=422,
                detail=f"Colonnes requises: {', '.join(required_columns)}"
            )

        # Supprimer toutes les signatures existantes avant l'import
        logger.info("Suppression de toutes les signatures existantes...")
        delete_result = db_manager.delete_all_signatures()
        logger.info(
            f"{delete_result['signatures_deleted']} signature(s) supprimée(s)"
        )

        publish_progress_sync("import_progress", {
            "status": "deleted_old_signatures",
            "count": delete_result['signatures_deleted'],
            "total_expected": total_lines_expected
        })

        # Importer ligne par ligne
        from .config import get_celery_app
        celery_app = get_celery_app()

        processed_lines = 0
        success_count = 0
        error_count = 0
        errors = []

        for line_num, row in enumerate(csv_reader, start=2):
            processed_lines += 1

            try:
                # Valider les champs
                appliance_name = row["appliance_name"].strip()
                start_time = row["start_time"].strip()
                end_time = row["end_time"].strip()
                
                # is_negative est optionnel (par défaut False)
                is_negative_str = row.get("is_negative", "False").strip()
                is_negative = is_negative_str.lower() in (
                    'true', '1', 'yes', 'oui'
                )

                if not appliance_name:
                    raise ValueError(
                        "Le nom de l'appareil ne peut pas être vide"
                    )

                # Valider les timestamps
                start_dt = datetime.fromisoformat(start_time)
                end_dt = datetime.fromisoformat(end_time)

                if start_dt >= end_dt:
                    raise ValueError(
                        "start_time doit être antérieur à end_time"
                    )

                # Créer la signature via Celery
                celery_app.send_task(
                    'add_nilm_signature',
                    args=(
                        appliance_name,
                        start_time,
                        end_time
                    ),
                    kwargs={'is_negative': is_negative},
                    queue='nilm_cnn',
                    routing_key="nilm.add_nilm_signature"
                )

                success_count += 1

                # Publish progress every 5 lines
                if processed_lines % 5 == 0:
                    progress_percent = int(
                        (processed_lines / total_lines_expected) * 100
                    ) if total_lines_expected > 0 else 0
                    publish_progress_sync("import_progress", {
                        "total_lines": processed_lines,
                        "success_count": success_count,
                        "error_count": error_count,
                        "progress_percent": progress_percent
                    })

            except ValueError as e:
                error_count += 1
                errors.append({
                    "line": line_num,
                    "error": str(e)
                })
            except Exception as e:
                error_count += 1
                errors.append({
                    "line": line_num,
                    "error": f"Erreur inattendue: {str(e)}"
                })

        # Publish import_complete event
        publish_progress_sync("import_complete", {
            "status": "completed",
            "total_lines": processed_lines,
            "success_count": success_count,
            "error_count": error_count
        })

        return {
            "status": "completed",
            "signatures_deleted": delete_result["signatures_deleted"],
            "total_lines": processed_lines,
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'import CSV: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur lors de l'import: {str(e)}"
        )


# --- WebSocket Manager for Training Logs ---
class TrainingLogsManager:
    """Manages WebSocket connections for real-time training logs."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.redis_client = None
        self.pubsub = None
        self.listener_task = None
    
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection."""
        # Accept connection from any origin for WebSocket
        # (WebSocket origin checking is handled differently than HTTP CORS)
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")
        
        # Start Redis listener if not already running
        if not self.listener_task:
            await self.start_redis_listener()
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def start_redis_listener(self):
        """Start listening to Redis Pub/Sub channel."""
        try:
            redis_url = settings.celery_broker_url.replace('redis://', '')
            host_port = redis_url.split('/')[0]
            
            self.redis_client = await aioredis.from_url(
                f"redis://{host_port}",
                decode_responses=True
            )
            self.pubsub = self.redis_client.pubsub()
            await self.pubsub.subscribe("training:logs")
            
            logger.info("✅ Started Redis listener for training:logs")
            
            # Start background task
            self.listener_task = asyncio.create_task(self._listen_redis())
            
        except Exception as e:
            logger.error(f"Failed to start Redis listener: {e}")
    
    async def _listen_redis(self):
        """Background task that listens to Redis and broadcasts to WebSockets."""
        logger.info("🎧 Redis listener task started")
        try:
            async for message in self.pubsub.listen():
                logger.debug(f"📨 Redis message received: {message}")
                if message['type'] == 'message':
                    data = message['data']
                    logger.info(f"📢 Broadcasting to {len(self.active_connections)} clients")
                    await self.broadcast(data)
        except Exception as e:
            logger.error(f"Error in Redis listener: {e}", exc_info=True)
        finally:
            logger.info("🔚 Redis listener task ending")
            if self.pubsub:
                await self.pubsub.unsubscribe("training:logs")
                await self.pubsub.close()
            if self.redis_client:
                await self.redis_client.close()
    
    async def broadcast(self, message: str):
        """Broadcast message to all connected WebSocket clients."""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.add(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


training_logs_manager = TrainingLogsManager()


# --- WebSocket Manager for Consumption Updates ---
class ConsumptionUpdatesManager:
    """Manages WebSocket connections for real-time consumption data."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.redis_client = None
        self.pubsub = None
        self.listener_task = None
    
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Consumption WS connected. Total: {len(self.active_connections)}")
        
        if not self.listener_task:
            await self.start_redis_listener()
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        self.active_connections.discard(websocket)
        logger.info(f"Consumption WS disconnected. Total: {len(self.active_connections)}")
    
    async def start_redis_listener(self):
        """Start listening to Redis Pub/Sub channel."""
        try:
            redis_url = settings.celery_broker_url.replace('redis://', '')
            host_port = redis_url.split('/')[0]
            
            self.redis_client = await aioredis.from_url(
                f"redis://{host_port}",
                decode_responses=True
            )
            self.pubsub = self.redis_client.pubsub()
            await self.pubsub.subscribe("consumption:updates")
            
            logger.info("✅ Started Redis listener for consumption:updates")
            self.listener_task = asyncio.create_task(self._listen_redis())
            
        except Exception as e:
            logger.error(f"Failed to start consumption Redis listener: {e}")
    
    async def _listen_redis(self):
        """Background task that listens to Redis and broadcasts to WebSockets."""
        logger.info("🎧 Consumption Redis listener task started")
        try:
            async for message in self.pubsub.listen():
                if message['type'] == 'message':
                    data = message['data']
                    logger.debug(f"📢 Broadcasting consumption to {len(self.active_connections)} clients")
                    await self.broadcast(data)
        except Exception as e:
            logger.error(f"Error in consumption Redis listener: {e}", exc_info=True)
        finally:
            logger.info("🔚 Consumption Redis listener task ending")
            if self.pubsub:
                await self.pubsub.unsubscribe("consumption:updates")
                await self.pubsub.close()
            if self.redis_client:
                await self.redis_client.close()
    
    async def broadcast(self, message: str):
        """Broadcast message to all connected WebSocket clients."""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to consumption WebSocket: {e}")
                disconnected.add(connection)
        
        for conn in disconnected:
            self.disconnect(conn)


consumption_updates_manager = ConsumptionUpdatesManager()


# --- WebSocket Manager for Detection Updates ---
class DetectionUpdatesManager:
    """Manages WebSocket connections for real-time detection updates."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.redis_client = None
        self.pubsub = None
        self.listener_task = None
    
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Detection WS connected. Total: {len(self.active_connections)}")
        
        if not self.listener_task:
            await self.start_redis_listener()
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        self.active_connections.discard(websocket)
        logger.info(f"Detection WS disconnected. Total: {len(self.active_connections)}")
    
    async def start_redis_listener(self):
        """Start listening to Redis Pub/Sub channel."""
        try:
            redis_url = settings.celery_broker_url.replace('redis://', '')
            host_port = redis_url.split('/')[0]
            
            self.redis_client = await aioredis.from_url(
                f"redis://{host_port}",
                decode_responses=True
            )
            self.pubsub = self.redis_client.pubsub()
            await self.pubsub.subscribe("detections:updates")
            
            logger.info("✅ Started Redis listener for detections:updates")
            self.listener_task = asyncio.create_task(self._listen_redis())
            
        except Exception as e:
            logger.error(f"Failed to start detection Redis listener: {e}")
    
    async def _listen_redis(self):
        """Background task that listens to Redis and broadcasts to WebSockets."""
        logger.info("🎧 Detection Redis listener task started")
        try:
            async for message in self.pubsub.listen():
                if message['type'] == 'message':
                    data = message['data']
                    logger.debug(f"📢 Broadcasting detection to {len(self.active_connections)} clients")
                    await self.broadcast(data)
        except Exception as e:
            logger.error(f"Error in detection Redis listener: {e}", exc_info=True)
        finally:
            logger.info("🔚 Detection Redis listener task ending")
            if self.pubsub:
                await self.pubsub.unsubscribe("detections:updates")
                await self.pubsub.close()
            if self.redis_client:
                await self.redis_client.close()
    
    async def broadcast(self, message: str):
        """Broadcast message to all connected WebSocket clients."""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to detection WebSocket: {e}")
                disconnected.add(connection)
        
        for conn in disconnected:
            self.disconnect(conn)


detection_updates_manager = DetectionUpdatesManager()


# --- WebSocket Manager for Import Progress ---
class ImportProgressManager:
    """Manages WebSocket connections for real-time import progress."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.redis_client = None
        self.pubsub = None
        self.listener_task = None
    
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Import WS connected. Total: {len(self.active_connections)}")
        
        if not self.listener_task:
            await self.start_redis_listener()
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        self.active_connections.discard(websocket)
        logger.info(f"Import WS disconnected. Total: {len(self.active_connections)}")
    
    async def start_redis_listener(self):
        """Start listening to Redis Pub/Sub channel."""
        try:
            redis_url = settings.celery_broker_url.replace('redis://', '')
            host_port = redis_url.split('/')[0]
            
            self.redis_client = await aioredis.from_url(
                f"redis://{host_port}",
                decode_responses=True
            )
            self.pubsub = self.redis_client.pubsub()
            await self.pubsub.subscribe("import:progress")
            
            logger.info("✅ Started Redis listener for import:progress")
            self.listener_task = asyncio.create_task(self._listen_redis())
            
        except Exception as e:
            logger.error(f"Failed to start import Redis listener: {e}")
    
    async def _listen_redis(self):
        """Background task that listens to Redis and broadcasts to WebSockets."""
        logger.info("🎧 Import Redis listener task started")
        try:
            async for message in self.pubsub.listen():
                if message['type'] == 'message':
                    data = message['data']
                    logger.debug(f"📢 Broadcasting import progress to {len(self.active_connections)} clients")
                    await self.broadcast(data)
        except Exception as e:
            logger.error(f"Error in import Redis listener: {e}", exc_info=True)
        finally:
            logger.info("🔚 Import Redis listener task ending")
            if self.pubsub:
                await self.pubsub.unsubscribe("import:progress")
                await self.pubsub.close()
            if self.redis_client:
                await self.redis_client.close()
    
    async def broadcast(self, message: str):
        """Broadcast message to all connected WebSocket clients."""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to import WebSocket: {e}")
                disconnected.add(connection)
        
        for conn in disconnected:
            self.disconnect(conn)


import_progress_manager = ImportProgressManager()


@app.websocket("/ws/training")
async def websocket_training_logs(websocket: WebSocket):
    """
    WebSocket endpoint for real-time training logs.
    
    Clients connect to this endpoint to receive live updates during model training.
    Events include: training_start, epoch_start, epoch_end, batch_update, training_complete.
    """
    # Accept WebSocket connection (bypasses CORS for WebSocket)
    await training_logs_manager.connect(websocket)
    try:
        # Keep connection alive and wait for messages
        while True:
            # Wait for any client message (heartbeat, commands, etc.)
            try:
                data = await websocket.receive_text()
                # Echo back for now (can add commands later)
                logger.debug(f"Received from client: {data}")
            except Exception as recv_error:
                logger.debug(f"Receive error (client may have closed): {recv_error}")
                break
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
        training_logs_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        training_logs_manager.disconnect(websocket)


@app.websocket("/ws/consumption")
async def websocket_consumption_updates(websocket: WebSocket):
    """
    WebSocket endpoint for real-time consumption data updates.
    
    Clients connect to receive live consumption data as it arrives from sync-service.
    Events include: new_consumption with latest PAPP, temperature, counters.
    """
    await consumption_updates_manager.connect(websocket)
    try:
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received from consumption client: {data}")
            except Exception as recv_error:
                logger.debug(f"Consumption receive error: {recv_error}")
                break
    except WebSocketDisconnect:
        logger.info("Consumption WebSocket client disconnected")
        consumption_updates_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Consumption WebSocket error: {e}")
        consumption_updates_manager.disconnect(websocket)


@app.websocket("/ws/detections")
async def websocket_detection_updates(websocket: WebSocket):
    """
    WebSocket endpoint for real-time detection updates.
    
    Clients connect to receive live NILM detection results as they are created.
    Events include: new_detection with appliance, timing, power, confidence.
    """
    await detection_updates_manager.connect(websocket)
    try:
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received from detection client: {data}")
            except Exception as recv_error:
                logger.debug(f"Detection receive error: {recv_error}")
                break
    except WebSocketDisconnect:
        logger.info("Detection WebSocket client disconnected")
        detection_updates_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Detection WebSocket error: {e}")
        detection_updates_manager.disconnect(websocket)


@app.websocket("/ws/import")
async def websocket_import_progress(websocket: WebSocket):
    """
    WebSocket endpoint for real-time import progress updates.
    
    Clients connect to receive live progress during CSV signature import.
    Events include: import_start, import_progress, import_complete.
    """
    await import_progress_manager.connect(websocket)
    try:
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received from import client: {data}")
            except Exception as recv_error:
                logger.debug(f"Import receive error: {recv_error}")
                break
    except WebSocketDisconnect:
        logger.info("Import WebSocket client disconnected")
        import_progress_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Import WebSocket error: {e}")
        import_progress_manager.disconnect(websocket)

