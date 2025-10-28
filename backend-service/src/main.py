"""Backend FastAPI principal pour Nilmia."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, UploadFile
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


@app.get("/api/signatures")
async def get_all_signatures(
    page: int = Query(default=1, ge=1, description="Numéro de page"),
    per_page: int = Query(default=20, ge=1, le=100, description="Signatures par page"),
):
    """
    Récupère toutes les signatures avec pagination.

    Args:
        page: Numéro de page (commence à 1)
        per_page: Nombre de signatures par page (1-100)

    Returns:
        Liste paginée des signatures avec informations de l'appareil
    """
    try:
        # Utiliser la fonction existante qui retourne toutes les signatures
        all_signatures = db_manager.get_all_signatures_with_appliance()
        
        # Calculer la pagination
        total = len(all_signatures)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0
        
        # Extraire la page demandée
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        signatures_page = all_signatures[start_idx:end_idx]
        
        return {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "signatures": signatures_page,
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des signatures: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.delete("/api/signatures/{signature_id}")
async def delete_signature(signature_id: int):
    """
    Supprime une signature spécifique.

    Args:
        signature_id: ID de la signature à supprimer

    Returns:
        Message de confirmation
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


@app.delete("/api/detections")
async def delete_all_detections():
    """
    Supprime toutes les détections de la base de données.

    Returns:
        Message de confirmation avec le nombre de détections supprimées
    """
    try:
        result = db_manager.delete_all_detections()

        return {
            "status": "success",
            "message": f"{result['deleted_count']} détection(s) supprimée(s)",
            "deleted_count": result['deleted_count']
        }
    except Exception as e:
        logger.error(f"Erreur lors de la suppression des détections: {str(e)}")
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


@app.patch("/api/detections/{detection_id}/validate")
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


@app.patch("/api/detections/{detection_id}/invalidate")
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
        signature: Données de la signature (appliance_name, start_time, end_time)
    
    Returns:
        Status de la tâche Celery
    """
    try:
        logger.info(f"Création de signature pour: {signature.appliance_name}")

        # Valider les timestamps et les normaliser
        try:
            start_dt = datetime.fromisoformat(signature.start_time)
            end_dt = datetime.fromisoformat(signature.end_time)
            # S'assurer que les deux datetimes ont le même tzinfo si possible
            if start_dt.tzinfo is None and end_dt.tzinfo is not None:
                start_dt = start_dt.replace(tzinfo=end_dt.tzinfo)
            elif start_dt.tzinfo is not None and end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=start_dt.tzinfo)
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
                ""
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


@app.post("/api/nilm/enrich")
async def trigger_signature_enrichment():
    """
    Lance l'enrichissement manuel des signatures avec les cycles détectés.
    
    Envoie une tâche Celery pour enrichir toutes les signatures existantes
    avec les cycles/états détectés par le modèle S2P actif.
    
    Returns:
        Status de la tâche Celery
    """
    try:
        from .config import get_celery_app
        
        celery_app = get_celery_app()
        logger.info("Lancement de l'enrichissement des signatures")
        
        # Envoyer la tâche à la queue NILM-CNN
        task = celery_app.send_task(
            'enrich_cnn_signatures',
            queue='nilm_cnn',
            routing_key='nilm_cnn.enrich_cnn_signatures'
        )
        
        logger.info(f"Tâche d'enrichissement créée: {task.id}")
        
        return {
            "status": "pending",
            "message": "Enrichissement des signatures lancé",
            "task_id": str(task.id),
        }
        
    except Exception as e:
        logger.error(f"Erreur lors du lancement de l'enrichissement: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur: {str(e)}"
        )


@app.post("/api/nilm/models/backup")
async def create_model_backup():
    """
    Crée une sauvegarde manuelle du modèle 'current' en le copiant vers 'backup'.

    L'ancien modèle 'backup' est archivé. Cette opération permet de créer
    un point de restauration avant d'effectuer des modifications importantes.

    Returns:
        Confirmation de la création du backup

    Raises:
        HTTPException 404: Aucun modèle 'current' trouvé
        HTTPException 500: Erreur serveur
    """
    import os
    import shutil
    from sqlalchemy import text

    try:
        with db_manager.get_session() as session:
            # Vérifier qu'un modèle 'current' existe
            current_query = text("""
                SELECT id, version, model_path
                FROM cnn_models
                WHERE model_status = 'current'
                LIMIT 1
            """)
            current_result = session.execute(current_query).fetchone()

            if not current_result:
                raise HTTPException(
                    status_code=404,
                    detail="Aucun modèle 'current' à sauvegarder"
                )

            current_id, current_version, current_path = current_result

            # Archiver l'ancien backup
            session.execute(text("""
                UPDATE cnn_models
                SET model_status = 'archived'
                WHERE model_status = 'backup'
            """))

            # Dupliquer le modèle current en backup
            duplicate_query = text("""
                INSERT INTO cnn_models
                (version, model_type, architecture, training_date,
                 num_signatures, num_classes, metrics, model_path,
                 model_status, training_duration_seconds)
                SELECT
                    version || '_backup_' || TO_CHAR(NOW(), 'YYYYMMDD_HH24MISS'),
                    model_type,
                    architecture,
                    training_date,
                    num_signatures,
                    num_classes,
                    metrics,
                    REPLACE(model_path, 'current', 'backup_' || TO_CHAR(NOW(), 'YYYYMMDD_HH24MISS')),
                    'backup',
                    training_duration_seconds
                FROM cnn_models
                WHERE id = :current_id
                RETURNING id, version, model_path
            """)

            result = session.execute(
                duplicate_query,
                {"current_id": current_id}
            ).fetchone()

            backup_id, backup_version, backup_path = result

            # Copier les fichiers physiques
            if os.path.exists(current_path):
                # Copier le fichier .keras
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                shutil.copy2(current_path, backup_path)

                # Copier le fichier metadata
                current_metadata = current_path.replace('.keras', '.metadata.json')
                backup_metadata = backup_path.replace('.keras', '.metadata.json')
                if os.path.exists(current_metadata):
                    shutil.copy2(current_metadata, backup_metadata)

            session.commit()

            logger.info(
                f"✅ Backup manuel créé: {current_version} → {backup_version}"
            )

            return {
                "status": "success",
                "message": "Backup créé avec succès",
                "current_id": current_id,
                "current_version": current_version,
                "backup_id": backup_id,
                "backup_version": backup_version,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Erreur lors de la création du backup: {str(e)}",
            exc_info=True
        )
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

    Si le modèle 'current' est supprimé, le modèle 'backup' est automatiquement
    promu en 'current' pour garantir qu'il y a toujours un modèle actif.

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
                # Même nom que le modèle avec .metadata.json
                metadata_path = model_path.replace(".keras", ".metadata.json")
                if os.path.exists(metadata_path):
                    os.remove(metadata_path)
                    deleted_files.append(metadata_path)
                    logger.info("Fichier metadata supprimé: %s", metadata_path)
                
                # Supprimer le dossier logs TensorBoard si existant
                version = result.get("version")
                if version:
                    # Structure: /app/models/tensorboard/multi_gru/version
                    logs_dir = os.path.join(
                        os.path.dirname(model_path),
                        "tensorboard", "multi_gru", version
                    )
                    if os.path.exists(logs_dir):
                        import shutil
                        shutil.rmtree(logs_dir)
                        deleted_files.append(f"{logs_dir}/ (directory)")
                        logger.info("Dossier logs supprimé: %s", logs_dir)
                        
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


# ============================================================================
# Export/Import CSV des signatures
# ============================================================================


@app.get("/api/signatures/export")
async def export_signatures():
    """
    Exporte toutes les signatures au format CSV.

    Returns:
        Fichier CSV avec colonnes: appliance_name, appliance_description, start_time, end_time
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
            "appliance_description",
            "start_time",
            "end_time",
            "is_negative"
        ])

        # Données
        for sig in signatures:
            writer.writerow([
                sig["appliance_name"],
                sig["appliance_description"],
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


class SignatureImportResult(BaseModel):
    """Modèle pour le résultat d'import de signatures."""
    total_lines: int
    success_count: int
    error_count: int
    errors: list[dict[str, str]]


@app.post("/api/signatures/import")
async def import_signatures(file: UploadFile):
    """
    Importe des signatures depuis un fichier CSV.

    Le CSV doit contenir les colonnes: appliance_name, appliance_description, start_time, end_time

    Args:
        file: Fichier CSV uploadé (multipart/form-data)

    Returns:
        Rapport d'import avec nombre de succès et erreurs détaillées
    """
    import csv
    from io import StringIO

    try:
        # Lire le contenu du CSV
        content = await file.read()
        content_str = content.decode('utf-8')
        csv_reader = csv.DictReader(StringIO(content_str))

        # Valider les colonnes requises
        required_columns = {
            "appliance_name",
            "appliance_description",
            "start_time",
            "end_time"
        }
        if not required_columns.issubset(csv_reader.fieldnames or []):
            raise HTTPException(
                status_code=422,
                detail=f"Colonnes requises: {', '.join(required_columns)}"
            )

        # Supprimer toutes les signatures existantes avant l'import
        logger.info("Suppression de toutes les signatures existantes avant import...")
        delete_result = db_manager.delete_all_signatures()
        logger.info(f"{delete_result['signatures_deleted']} signature(s) supprimée(s)")

        # Importer ligne par ligne
        from .config import get_celery_app
        celery_app = get_celery_app()

        total_lines = 0
        success_count = 0
        error_count = 0
        errors = []

        for line_num, row in enumerate(csv_reader, start=2):
            total_lines += 1

            try:
                # Valider les champs
                appliance_name = row["appliance_name"].strip()
                appliance_description = row["appliance_description"].strip()
                start_time = row["start_time"].strip()
                end_time = row["end_time"].strip()
                
                # is_negative est optionnel (par défaut False)
                is_negative_str = row.get("is_negative", "False").strip()
                is_negative = is_negative_str.lower() in ('true', '1', 'yes', 'oui')

                if not appliance_name:
                    raise ValueError("Le nom de l'appareil ne peut pas être vide")

                # Valider les timestamps
                start_dt = datetime.fromisoformat(start_time)
                end_dt = datetime.fromisoformat(end_time)

                if start_dt >= end_dt:
                    raise ValueError(
                        "start_time doit être antérieur à end_time"
                    )

                # Créer la signature via Celery
                celery_app.send_task(
                    'add_cnn_signature',
                    args=(
                        appliance_name,
                        start_time,
                        end_time,
                        appliance_description or ""
                    ),
                    kwargs={'is_negative': is_negative},
                    queue='nilm_cnn',
                    routing_key='nilm_cnn.add_cnn_signature'
                )

                success_count += 1

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

        return {
            "status": "completed",
            "signatures_deleted": delete_result["signatures_deleted"],
            "total_lines": total_lines,
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
