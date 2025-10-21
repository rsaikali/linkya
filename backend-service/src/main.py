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


@app.get("/api/detections")
async def get_detected_appliances(
    hours: int = Query(default=None, description="Nombre d'heures d'historique (pour périodes longues)"),
    minutes: int = Query(default=None, description="Nombre de minutes d'historique (pour courtes périodes)"),
):
    """
    Récupère les détections d'appareils par le NILM.

    Args:
        hours: Nombre d'heures d'historique à récupérer
        minutes: Nombre de minutes d'historique à récupérer

    Returns:
        Liste des détections avec informations sur les appareils
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

        detections = db_manager.get_detected_appliances(start_time, end_time)

        return {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_detections": len(detections),
            "detections": detections,
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
        except ValueError as e:
            logger.error(f"Format de timestamp invalide: {str(e)}")
            raise HTTPException(status_code=422, detail=f"Format de timestamp invalide: {str(e)}")
        
        if start_dt >= end_dt:
            logger.error("start_time >= end_time")
            raise HTTPException(
                status_code=422,
                detail="start_time doit être antérieur à end_time"
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
        
        # Envoyer la tâche à la queue NILM
        task = celery_app.send_task(
            'add_manual_signature',
            args=(
                signature.appliance_name,
                signature.start_time,
                signature.end_time,
                signature.description
            ),
            queue='nilm',
            routing_key='nilm.add_manual_signature'
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
