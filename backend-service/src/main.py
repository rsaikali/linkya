"""Backend FastAPI principal pour Nilmia."""

import asyncio
import json
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import settings
from .database import db_manager

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
    hours: int = Query(default=24, ge=1, le=168, description="Nombre d'heures d'historique (max 7 jours)"),
    interval: str = Query(default="5 minutes", description="Intervalle d'agrégation (ex: '5 minutes', '1 hour')"),
):
    """
    Récupère l'historique de consommation sur une période donnée.

    Args:
        hours: Nombre d'heures d'historique à récupérer (1-168)
        interval: Intervalle d'agrégation des données

    Returns:
        Liste des points de consommation agrégés par intervalle
    """
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

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
    hours: int = Query(default=24, ge=1, le=168, description="Nombre d'heures d'historique (max 7 jours)"),
):
    """
    Récupère les détections d'appareils par le NILM.

    Args:
        hours: Nombre d'heures d'historique à récupérer

    Returns:
        Liste des détections avec informations sur les appareils
    """
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        detections = db_manager.get_detected_appliances(start_time, end_time)

        return {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_detections": len(detections),
            "detections": detections,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


# ============================================================================
# Server-Sent Events (SSE) - Streaming en temps réel
# ============================================================================


async def stream_latest_consumption_generator(update_interval: int = 5):
    """
    Génère un stream de la dernière consommation.
    
    Args:
        update_interval: Intervalle de mise à jour en secondes
    """
    while True:
        try:
            data = db_manager.get_latest_consumption()
            if data:
                event_data = json.dumps(data)
                yield f"data: {event_data}\n\n"
            await asyncio.sleep(update_interval)
        except Exception as e:
            print(f"Erreur dans stream_latest_consumption: {str(e)}")
            await asyncio.sleep(update_interval)


@app.get("/api/stream/consumption/latest")
async def stream_latest_consumption(
    update_interval: int = Query(default=5, ge=1, le=60, description="Intervalle de mise à jour en secondes"),
):
    """
    Stream Server-Sent Events de la dernière consommation en temps réel.
    
    Cette endpoint push les données de consommation au client toutes les N secondes.
    
    Args:
        update_interval: Intervalle de mise à jour en secondes (1-60)
    
    Returns:
        Stream d'événements SSE avec dernière consommation
        
    Exemple d'utilisation (JavaScript):
        ```javascript
        const eventSource = new EventSource('/api/stream/consumption/latest?update_interval=5');
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Nouvelle consommation:', data);
        };
        ```
    """
    return StreamingResponse(
        stream_latest_consumption_generator(update_interval),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def stream_detections_generator(hours: int = 24, update_interval: int = 10):
    """
    Génère un stream des détections d'appareils.
    
    Args:
        hours: Nombre d'heures d'historique
        update_interval: Intervalle de mise à jour en secondes
    """
    while True:
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
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
    hours: int = Query(default=24, ge=1, le=168, description="Nombre d'heures d'historique"),
    update_interval: int = Query(default=10, ge=1, le=60, description="Intervalle de mise à jour en secondes"),
):
    """
    Stream Server-Sent Events des détections NILM.
    
    Cette endpoint push les détections d'appareils au client.
    
    Args:
        hours: Nombre d'heures d'historique à récupérer (1-168)
        update_interval: Intervalle de mise à jour en secondes (1-60)
    
    Returns:
        Stream d'événements SSE avec détections NILM
    """
    return StreamingResponse(
        stream_detections_generator(hours, update_interval),
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
