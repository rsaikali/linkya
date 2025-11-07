"""NILM training and detection endpoints."""

import glob
import logging
import os

from fastapi import APIRouter, HTTPException

from ..config import get_celery_app
from ..db import db_manager
from ..utils.redis_client import get_redis_client


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nilm", tags=["NILM"])


@router.post("/train")
async def trigger_nilm_training():
    """
    Lance l'entraînement manuel du modèle NILM.

    Annule automatiquement tous les entraînements en cours ou en attente
    avant de lancer le nouveau.

    Returns:
        Task ID and status
    """
    try:
        celery_app = get_celery_app()
        logger.info("Lancement de l'entraînement NILM")

        # Incrémenter un compteur pour marquer ce training comme légitime
        training_generation = 0
        redis_client = get_redis_client()
        if redis_client:
            try:
                # Incrémenter atomiquement le compteur de génération
                training_generation = redis_client.incr("nilm:training:generation")
                logger.info(f"Nouvelle génération de training: {training_generation}")
            except Exception as e:
                logger.warning(f"Impossible d'incrémenter génération: {e}")

        # Envoyer la nouvelle tâche avec la génération en argument
        task = celery_app.send_task(
            "train_nilm_model",
            args=[2, training_generation],
            queue="nilm",
            routing_key="nilm.train_nilm_model",
        )  # min_signatures, generation

        logger.info(f"Tâche d'entraînement créée: {task.id}")

        return {
            "status": "pending",
            "message": "Entraînement du modèle NILM lancé",
            "task_id": str(task.id),
        }

    except Exception as e:
        logger.error(
            f"Erreur lors du lancement de l'entraînement: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.post("/detect")
async def trigger_nilm_detection():
    """
    Lance la détection automatique d'appareils par NILM.

    Returns:
        Task ID and status
    """
    try:
        celery_app = get_celery_app()
        logger.info("Lancement de la détection NILM")

        # Envoyer la tâche à la queue NILM
        task = celery_app.send_task(
            "detect_nilm_appliances",
            queue="nilm",
            routing_key="nilm.detect_nilm_appliances",
        )

        logger.info(f"Tâche de détection créée: {task.id}")

        return {
            "status": "pending",
            "message": "Détection NILM lancée",
            "task_id": str(task.id),
        }

    except Exception as e:
        logger.error(
            f"Erreur lors du lancement de la détection: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.get("/models")
async def get_nilm_models():
    """
    Récupère le dernier modèle NILM entraîné.

    Returns:
        Le dernier modèle avec ses métriques, ou None si aucun modèle
    """
    try:
        model = db_manager.get_latest_nilm_model()

        if model:
            return {"models": [model], "total": 1}
        else:
            return {"models": [], "total": 0}

    except Exception as e:
        logger.error(
            f"Erreur lors de la récupération des modèles: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.delete("/models")
async def delete_all_nilm_models():
    """
    Supprime tous les modèles NILM de la base de données et du filesystem.

    Returns:
        Confirmation de suppression avec statistiques

    Raises:
        HTTPException 500: Erreur serveur
    """
    try:
        # Supprimer tous les modèles de la base de données
        deleted_count = db_manager.delete_all_models()

        deleted_files = []
        errors = []

        # Nettoyer tous les fichiers dans /models
        models_dir = "/models"
        if os.path.exists(models_dir):
            all_files = glob.glob(os.path.join(models_dir, "*.keras"))
            all_files += glob.glob(os.path.join(models_dir, "*.metadata.json"))

            for file_path in all_files:
                try:
                    os.remove(file_path)
                    deleted_files.append(file_path)
                    logger.info(f"Fichier supprimé: {file_path}")
                except OSError as e:
                    errors.append(f"Fichier {file_path}: {str(e)}")

        logger.info(
            f"Suppression terminée: "
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
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")
