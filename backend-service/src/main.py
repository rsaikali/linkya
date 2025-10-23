"""Backend FastAPI principal pour Nilmia."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import settings
from .database import db_manager

# Configuration du logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Modèles Pydantic
class SignatureCreate(BaseModel):
    """Modèle pour créer une nouvelle signature d'appareil."""
    appliance_name: str
    start_time: str  # Format ISO
    end_time: str    # Format ISO
    description: Optional[str] = None

# Création de l'application FastAPI
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
)

# Configuration CORS pour permettre les requêtes depuis le frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Point d'entrée racine de l'API."""
    return {
        "message": "Nilmia API",
        "version": settings.api_version,
        "endpoints": {
            "latest": "/api/consumption/latest",
            "history": "/api/consumption/history",
            "appliances": "/api/appliances",
            "detections": "/api/detections",
            "signatures_create": "POST /api/signatures",
            "stream_latest": "/api/stream/consumption/latest",
            "stream_detections": "/api/stream/detections",
            "stream_appliances": "/api/stream/appliances",
        },
    }


@app.get("/health")
async def health_check():
    """Vérification de l'état de santé de l'API."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/consumption/latest")
async def get_latest_consumption():
    """
    Récupère la dernière valeur de consommation d'énergie.

    Returns:
        Dernière mesure avec timestamp, puissance, index, température
    """
    try:
        data = db_manager.get_latest_consumption()
        if not data:
            raise HTTPException(status_code=404, detail="Aucune donnée disponible")
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.get("/api/consumption/history")
async def get_consumption_history(
    hours: int = Query(default=None, description="Nombre d'heures d'historique (pour périodes longues)"),
    minutes: int = Query(default=None, description="Nombre de minutes d'historique (pour courtes périodes)"),
    interval: str = Query(default="5 minutes", description="Intervalle d'agrégation (ex: '5 minutes', '1 hour')"),
):
    """
    Récupère l'historique de consommation sur une période donnée.

    Args:
        hours: Nombre d'heures d'historique à récupérer (pour périodes >= 1 heure)
        minutes: Nombre de minutes d'historique à récupérer (pour périodes < 1 heure)
        interval: Intervalle d'agrégation des données

    Returns:
        Liste des points de consommation agrégés par intervalle
    """
    try:
        # Déterminer la période à récupérer
        if minutes is not None and minutes > 0:
            delta = timedelta(minutes=minutes)
        elif hours is not None and hours > 0:
            # Valider les heures (1-168)
            if hours < 1 or hours > 168:
                raise HTTPException(status_code=422, detail="hours doit être entre 1 et 168")
            delta = timedelta(hours=hours)
        else:
            # Valeur par défaut: 24 heures
            delta = timedelta(hours=24)

        end_time = datetime.now()
        start_time = end_time - delta

        data = db_manager.get_consumption_history(start_time, end_time, interval)
        if not data:
            raise HTTPException(status_code=404, detail="Aucune donnée disponible pour cette période")

        return {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "interval": interval,
            "data_points": len(data),
            "data": data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.get("/api/appliances")
async def get_all_appliances():
    """
    Récupère la liste de tous les appareils électriques connus.

    Returns:
        Liste des appareils avec leurs caractéristiques
    """
    try:
        appliances = db_manager.get_all_appliances()
        return {
            "total": len(appliances),
            "appliances": appliances,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.get("/api/appliances/{appliance_id}/signatures")
async def get_appliance_signatures(appliance_id: int):
    """
    Récupère toutes les signatures d'un appareil spécifique.

    Args:
        appliance_id: ID de l'appareil

    Returns:
        Liste des signatures avec leurs détails
    """
    try:
        signatures = db_manager.get_appliance_signatures(appliance_id)
        return {
            "appliance_id": appliance_id,
            "total": len(signatures),
            "signatures": signatures,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


class ApplianceUpdate(BaseModel):
    """Modèle pour mettre à jour un appareil."""
    name: Optional[str] = None
    description: Optional[str] = None


@app.patch("/api/appliances/{appliance_id}")
async def update_appliance(
    appliance_id: int,
    update_data: ApplianceUpdate
):
    """
    Met à jour le nom et/ou la description d'un appareil.

    Args:
        appliance_id: ID de l'appareil à modifier
        update_data: Données à mettre à jour (name et/ou description)

    Returns:
        Appareil mis à jour
    """
    try:
        # Valider qu'au moins un champ est fourni
        if update_data.name is None and update_data.description is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Au moins un champ (name ou description) "
                    "doit être fourni"
                )
            )
        
        # Valider le nom s'il est fourni
        if update_data.name is not None and not update_data.name.strip():
            raise HTTPException(
                status_code=422,
                detail="Le nom ne peut pas être vide"
            )
        
        # Nettoyer les données
        name = update_data.name.strip() if update_data.name else None
        description = (
            update_data.description.strip()
            if update_data.description
            else None
        )
        
        result = db_manager.update_appliance(
            appliance_id,
            name=name,
            description=description
        )
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail="Appareil non trouvé"
            )
        
        return {
            "status": "success",
            "message": "Appareil mis à jour",
            "appliance": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Erreur lors de la mise à jour de l'appareil "
            f"{appliance_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur: {str(e)}"
        )


@app.delete("/api/appliances/{appliance_id}")
async def delete_appliance(appliance_id: int):
    """
    Supprime un appareil et toutes ses signatures/détections associées.

    Args:
        appliance_id: ID de l'appareil à supprimer

    Returns:
        Message de confirmation
    """
    try:
        result = db_manager.delete_appliance(appliance_id)
        if not result:
            raise HTTPException(status_code=404, detail="Appareil non trouvé")
        
        return {
            "status": "success",
            "message": f"Appareil supprimé (signatures: {result['signatures_deleted']}, détections: {result['detections_deleted']})"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de l'appareil {appliance_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.delete("/api/detections/{detection_id}")
async def delete_detection(detection_id: int):
    """
    Supprime une détection spécifique.

    Args:
        detection_id: ID de la détection à supprimer

    Returns:
        Message de confirmation avec informations de la détection supprimée
    """
    try:
        result = db_manager.delete_detection(detection_id)
        if not result:
            raise HTTPException(status_code=404, detail="Détection non trouvée")
        
        return {
            "status": "success",
            "message": f"Détection supprimée: {result['appliance_name']}",
            "detection": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la détection {detection_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.get("/api/detections")
async def get_detected_appliances(
    hours: int = Query(default=None, description="Nombre d'heures d'historique (pour périodes longues)"),
    minutes: int = Query(default=None, description="Nombre de minutes d'historique (pour courtes périodes)"),
    page: int = Query(default=1, ge=1, description="Numéro de page (commence à 1)"),
    per_page: int = Query(default=10, ge=1, le=100, description="Nombre d'éléments par page (max 100)"),
):
    """
    Récupère les détections d'appareils par le NILM avec pagination.

    Args:
        hours: Nombre d'heures d'historique à récupérer
        minutes: Nombre de minutes d'historique à récupérer
        page: Numéro de page (commence à 1)
        per_page: Nombre d'éléments par page (max 100)

    Returns:
        Liste paginée des détections avec informations sur les appareils
    """
    try:
        # Déterminer la période à récupérer
        start_time = None
        end_time = None
        
        if minutes is not None and minutes > 0:
            delta = timedelta(minutes=minutes)
            end_time = datetime.now()
            start_time = end_time - delta
        elif hours is not None and hours > 0:
            # Valider les heures (max 1 an = 8760h)
            if hours < 1 or hours > 8760:
                raise HTTPException(
                    status_code=422,
                    detail="hours doit être entre 1 et 8760"
                )
            delta = timedelta(hours=hours)
            end_time = datetime.now()
            start_time = end_time - delta
        elif hours == 0 or minutes == 0:
            # hours=0 ou minutes=0 signifie "toutes les détections"
            start_time = None
            end_time = None
        else:
            # Valeur par défaut: 24 heures
            delta = timedelta(hours=24)
            end_time = datetime.now()
            start_time = end_time - delta

        detections = db_manager.get_detected_appliances(start_time, end_time)
        
        # Pagination
        total = len(detections)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_detections = detections[start_idx:end_idx]
        
        total_pages = (total + per_page - 1) // per_page

        return {
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": end_time.isoformat() if end_time else None,
            "total_detections": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "detections": paginated_detections,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.post("/api/signatures")
async def create_signature(signature: SignatureCreate):
    """
    Crée une nouvelle signature d'appareil pour l'entraînement NILM.
    
    Cette endpoint envoie une tâche Celery au service NILM pour traiter
    la signature et ajouter les données d'entraînement.
    
    Args:
        signature: Données de la signature (appliance_name, start_time, end_time, description)
    
    Returns:
        Status de la tâche Celery
    """
    try:
        logger.info(f"Création de signature pour: {signature.appliance_name}")
        
        # Valider les timestamps
        try:
            start_dt = datetime.fromisoformat(signature.start_time)
            end_dt = datetime.fromisoformat(signature.end_time)
            
            logger.debug(f"start_dt: {start_dt} (tzinfo: {start_dt.tzinfo})")
            logger.debug(f"end_dt: {end_dt} (tzinfo: {end_dt.tzinfo})")
            
            # S'assurer que les deux datetimes ont le même type de timezone
            if start_dt.tzinfo is None and end_dt.tzinfo is not None:
                start_dt = start_dt.replace(tzinfo=end_dt.tzinfo)
                logger.debug(f"start_dt après normalisation: {start_dt}")
            elif start_dt.tzinfo is not None and end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=start_dt.tzinfo)
                logger.debug(f"end_dt après normalisation: {end_dt}")
                
        except ValueError as e:
            logger.error(f"Format de timestamp invalide: {str(e)}")
            raise HTTPException(status_code=422, detail=f"Format de timestamp invalide: {str(e)}")
        
        # Log détaillé avant comparaison
        logger.info(f"Comparaison: {start_dt} >= {end_dt} = {start_dt >= end_dt}")
        
        if start_dt >= end_dt:
            logger.error(f"start_time >= end_time: {start_dt} >= {end_dt}")
            raise HTTPException(
                status_code=422,
                detail=f"start_time doit être antérieur à end_time ({start_dt} >= {end_dt})"
            )
        
        if not signature.appliance_name.strip():
            logger.error("appliance_name vide")
            raise HTTPException(
                status_code=422,
                detail="appliance_name ne peut pas être vide"
            )
        
        # Utiliser l'instance Celery singleton depuis config
        from .config import get_celery_app
        
        celery_app = get_celery_app()
        logger.info("Celery app récupérée")
        
        # Envoyer la tâche à la queue NILM-CNN
        task = celery_app.send_task(
            'add_cnn_signature',
            args=(
                signature.appliance_name,
                signature.start_time,
                signature.end_time,
                signature.description or ""
            ),
            queue='nilm_cnn',
            routing_key='nilm_cnn.add_cnn_signature'
        )
        
        logger.info(f"Tâche Celery créée: {task.id}")
        
        response = {
            "status": "pending",
            "message": f"Signature en cours de traitement pour {signature.appliance_name}",
            "task_id": str(task.id),
            "appliance_name": signature.appliance_name,
            "start_time": signature.start_time,
            "end_time": signature.end_time,
        }
        
        logger.info(f"Réponse: {response}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la création de signature: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur lors de la création de la signature: {str(e)}"
        )


@app.post("/api/nilm/train")
async def trigger_nilm_training():
    """
    Lance l'entraînement manuel du modèle NILM-CNN.
    
    Envoie une tâche Celery pour entraîner le modèle CNN avec toutes les signatures disponibles.
    
    Returns:
        Status de la tâche Celery
    """
    try:
        from .config import get_celery_app
        
        celery_app = get_celery_app()
        logger.info("Lancement de l'entraînement NILM-CNN")
        
        # Envoyer la tâche à la queue NILM-CNN
        task = celery_app.send_task(
            'train_cnn_model',
            queue='nilm_cnn',
            routing_key='nilm_cnn.train_cnn_model'
        )
        
        logger.info(f"Tâche d'entraînement créée: {task.id}")
        
        return {
            "status": "pending",
            "message": "Entraînement du modèle NILM-CNN lancé",
            "task_id": str(task.id),
        }
        
    except Exception as e:
        logger.error(f"Erreur lors du lancement de l'entraînement: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur: {str(e)}"
        )


@app.post("/api/nilm/detect")
async def trigger_nilm_detection():
    """
    Lance la détection manuelle d'appareils avec NILM-CNN.
    
    Envoie une tâche Celery pour détecter les appareils dans les données récentes.
    
    Returns:
        Status de la tâche Celery
    """
    try:
        from .config import get_celery_app
        
        celery_app = get_celery_app()
        logger.info("Lancement de la détection NILM-CNN")
        
        # Envoyer la tâche à la queue NILM-CNN
        task = celery_app.send_task(
            'detect_cnn_appliances',
            queue='nilm_cnn',
            routing_key='nilm_cnn.detect_cnn_appliances'
        )
        
        logger.info(f"Tâche de détection créée: {task.id}")
        
        return {
            "status": "pending",
            "message": "Détection NILM-CNN lancée",
            "task_id": str(task.id),
        }
        
    except Exception as e:
        logger.error(f"Erreur lors du lancement de la détection: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur: {str(e)}"
        )


@app.get("/api/nilm/models")
async def get_nilm_models(
    page: int = Query(default=1, ge=1, description="Numéro de page"),
    per_page: int = Query(default=10, ge=1, le=100, description="Nombre d'éléments par page"),
):
    """
    Récupère l'historique des modèles NILM-CNN entraînés avec pagination.
    
    Args:
        page: Numéro de page (commence à 1)
        per_page: Nombre de modèles par page (1-100)
    
    Returns:
        Liste paginée des modèles avec leurs métriques
    """
    try:
        models = db_manager.get_cnn_models_paginated(page=page, per_page=per_page)
        
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


@app.delete("/api/nilm/models/{model_id}")
async def delete_nilm_model(model_id: int):
    """
    Supprime un modèle NILM-CNN de la base de données et du filesystem.
    
    Le modèle actif (is_active=true) ne peut pas être supprimé.
    
    Args:
        model_id: ID du modèle à supprimer
    
    Returns:
        Confirmation de suppression avec détails
        
    Raises:
        HTTPException 404: Modèle non trouvé
        HTTPException 400: Tentative de suppression du modèle actif
        HTTPException 500: Erreur serveur
    """
    import os
    
    try:
        # Supprimer de la base de données
        result = db_manager.delete_cnn_model(model_id)
        
        # Supprimer les fichiers du filesystem si le chemin existe
        model_path = result.get("model_path")
        deleted_files = []
        
        if model_path and os.path.exists(model_path):
            try:
                # Supprimer le fichier .keras
                os.remove(model_path)
                deleted_files.append(model_path)
                logger.info(f"Fichier modèle supprimé: {model_path}")
                
                # Supprimer le fichier metadata JSON associé
                metadata_path = model_path.replace(
                    "model_", "metadata_"
                ).replace(".keras", ".json")
                if os.path.exists(metadata_path):
                    os.remove(metadata_path)
                    deleted_files.append(metadata_path)
                    logger.info(f"Fichier metadata supprimé: {metadata_path}")
                
                # Supprimer le dossier logs TensorBoard si existant
                version = result.get("version")
                if version:
                    logs_dir = os.path.join(
                        os.path.dirname(model_path), "logs", version
                    )
                    if os.path.exists(logs_dir):
                        import shutil
                        shutil.rmtree(logs_dir)
                        deleted_files.append(f"{logs_dir}/ (directory)")
                        logger.info(f"Dossier logs supprimé: {logs_dir}")
                        
            except OSError as e:
                logger.warning(
                    f"Erreur lors de la suppression des fichiers: {e}"
                )
        
        return {
            "message": "Modèle supprimé avec succès",
            "model_id": result["id"],
            "version": result["version"],
            "deleted_files": deleted_files,
        }
        
    except ValueError as e:
        # Erreurs métier (modèle non trouvé ou actif)
        error_message = str(e)
        if "non trouvé" in error_message:
            raise HTTPException(status_code=404, detail=error_message)
        elif "actif" in error_message:
            raise HTTPException(status_code=400, detail=error_message)
        else:
            raise HTTPException(status_code=400, detail=error_message)
            
    except Exception as e:
        logger.error(
            f"Erreur lors de la suppression du modèle {model_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur: {str(e)}"
        )


# ============================================================================
# Server-Sent Events (SSE) - Streaming en temps réel
# ============================================================================


@app.get("/api/stream/consumption/latest")
async def stream_latest_consumption(
    update_interval: int = Query(default=1, ge=1, le=60, description="Intervalle de mise à jour en secondes"),
):
    """
    Stream Server-Sent Events de la dernière consommation en temps réel.
    
    Args:
        update_interval: Intervalle de mise à jour en secondes
    
    Returns:
        Stream d'événements SSE avec dernière consommation
    """
    async def generator():
        while True:
            try:
                data = db_manager.get_latest_consumption()
                if data:
                    event_data = json.dumps(data)
                    yield f"data: {event_data}\n\n"
                await asyncio.sleep(update_interval)
            except Exception as e:
                print(f"Erreur stream consumption: {str(e)}")
                await asyncio.sleep(update_interval)
    
    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def stream_detections_generator(hours: int = None, minutes: int = None, update_interval: int = 10):
    """
    Génère un stream des détections d'appareils.
    
    Args:
        hours: Nombre d'heures d'historique
        minutes: Nombre de minutes d'historique
        update_interval: Intervalle de mise à jour en secondes
    """
    # Déterminer la période à récupérer
    if minutes is not None and minutes > 0:
        delta = timedelta(minutes=minutes)
    elif hours is not None and hours > 0:
        # Valider les heures (1-168)
        if hours < 1 or hours > 168:
            hours = 24  # Fallback à 24h
        delta = timedelta(hours=hours)
    else:
        # Valeur par défaut: 24 heures
        delta = timedelta(hours=24)
    
    while True:
        try:
            end_time = datetime.now()
            start_time = end_time - delta
            detections = db_manager.get_detected_appliances(start_time, end_time)
            
            event_data = json.dumps({
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "total_detections": len(detections),
                "detections": detections,
            })
            yield f"data: {event_data}\n\n"
            await asyncio.sleep(update_interval)
        except Exception as e:
            print(f"Erreur dans stream_detections: {str(e)}")
            await asyncio.sleep(update_interval)


@app.get("/api/stream/detections")
async def stream_detections(
    hours: int = Query(default=None, description="Nombre d'heures d'historique"),
    minutes: int = Query(default=None, description="Nombre de minutes d'historique"),
    update_interval: int = Query(default=10, ge=1, le=60, description="Intervalle de mise à jour en secondes"),
):
    """
    Stream Server-Sent Events des détections NILM.
    
    Cette endpoint push les détections d'appareils au client.
    
    Args:
        hours: Nombre d'heures d'historique à récupérer
        minutes: Nombre de minutes d'historique à récupérer
        update_interval: Intervalle de mise à jour en secondes (1-60)
    
    Returns:
        Stream d'événements SSE avec détections NILM
    """
    return StreamingResponse(
        stream_detections_generator(hours, minutes, update_interval),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def stream_appliances_generator(update_interval: int = 30):
    """
    Génère un stream de la liste des appareils.
    
    Args:
        update_interval: Intervalle de mise à jour en secondes
    """
    while True:
        try:
            appliances = db_manager.get_all_appliances()
            event_data = json.dumps({
                "total": len(appliances),
                "appliances": appliances,
            })
            yield f"data: {event_data}\n\n"
            await asyncio.sleep(update_interval)
        except Exception as e:
            print(f"Erreur dans stream_appliances: {str(e)}")
            await asyncio.sleep(update_interval)


@app.get("/api/stream/appliances")
async def stream_appliances(
    update_interval: int = Query(default=30, ge=1, le=300, description="Intervalle de mise à jour en secondes"),
):
    """
    Stream Server-Sent Events de la liste des appareils.
    
    Args:
        update_interval: Intervalle de mise à jour en secondes (1-300)
    
    Returns:
        Stream d'événements SSE avec liste des appareils
    """
    return StreamingResponse(
        stream_appliances_generator(update_interval),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
