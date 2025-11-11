"""Signature management and import/export endpoints."""

import csv
import json
import logging
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..config import get_celery_app
from ..db import db_manager
from ..models import SignatureCreate
from ..utils.redis_client import get_redis_client


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/signatures", tags=["Signatures"])


@router.get("")
async def get_all_signatures():
    """
    Retrieves all signatures.

    Returns:
        List of all signatures with appliance information
    """
    try:
        signatures = db_manager.get_all_signatures_with_appliance()

        return {"total": len(signatures), "signatures": signatures}
    except Exception as e:
        logger.error(f"Error retrieving signatures: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.post("")
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
        celery_app = get_celery_app()
        logger.info(f"Creation de signature for {signature.appliance_name} " f"de {signature.start_time} to {signature.end_time}")

        # Envoyer la tâche au service NILM
        task = celery_app.send_task(
            "add_nilm_signature",
            args=[signature.appliance_name, signature.start_time, signature.end_time, False],  # is_negative=False (signature positive)
            queue="nilm",
            routing_key="nilm.add_nilm_signature",
        )

        logger.info(f"Signature creation task created: {task.id}")
        return {
            "status": "success",
            "message": f"Signature créée pour {signature.appliance_name}",
            "task_id": str(task.id),
            "appliance_name": signature.appliance_name,
            "start_time": signature.start_time,
            "end_time": signature.end_time,
        }

    except Exception as e:
        logger.error(f"Error during la creation of signature: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.delete("")
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
            "signatures_deleted": result["signatures_deleted"],
        }
    except Exception as e:
        logger.error(f"Error deleting signatures: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.delete("/{signature_id}")
async def delete_signature(signature_id):
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

        return {"status": "success", "message": f"Signature supprimée: {result['appliance_name']}", "signature": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting signature {signature_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.get("/export")
async def export_signatures():
    """
    Exporte toutes les signatures au format CSV.

    Returns:
        Fichier CSV avec colonnes: appliance_name, start_time, end_time, is_negative
    """
    try:
        signatures = db_manager.get_all_signatures_with_appliance()

        # Créer le CSV en mémoire
        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(["appliance_name", "start_time", "end_time", "is_negative"])

        # Données
        for sig in signatures:
            writer.writerow([sig["appliance_name"], sig["start_time"], sig["end_time"], sig.get("is_negative", False)])

        csv_content = output.getvalue()

        # Générer le nom du fichier avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"linkya_signatures_{timestamp}.csv"

        return Response(content=csv_content, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except Exception as e:
        logger.error(f"Error during l'export CSV: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur serveur lors de l'export: {str(e)}")


@router.post("/import")
async def import_signatures(file):
    """
    Importe des signatures depuis un fichier CSV.

    Le CSV doit contenir les colonnes:
    appliance_name, start_time, end_time, is_negative (optionnel)

    Args:
        file: Fichier CSV uploadé (multipart/form-data)

    Returns:
        Rapport d'import avec nombre de succès et erreurs détaillées
    """

    # Helper function to publish progress to WebSocket
    def publish_progress_sync(event, data):
        """Publish import progress to Redis for WebSocket streaming"""
        try:
            redis_client = get_redis_client()
            if redis_client:
                message = json.dumps({"event": event, "data": data, "timestamp": datetime.utcnow().isoformat()})
                redis_client.publish("import:progress", message)
                logger.info(f"Published {event} to Redis")
        except Exception as e:
            logger.error(f"Failed to publish progress to Redis: {e}")

    try:
        # Publish import_start event
        publish_progress_sync("import_start", {"status": "started", "filename": file.filename})

        # Lire le contenu du CSV
        content = await file.read()
        content_str = content.decode("utf-8")

        # Premier passage : compter les lignes totales
        lines = content_str.strip().split("\n")
        total_lines_expected = len(lines) - 1  # -1 pour le header

        csv_reader = csv.DictReader(StringIO(content_str))

        # Valider les colonnes requises
        required_columns = {"appliance_name", "start_time", "end_time"}
        if not required_columns.issubset(csv_reader.fieldnames or []):
            publish_progress_sync("import_error", {"error": f"Colonnes requises: {', '.join(required_columns)}"})
            raise HTTPException(status_code=422, detail=f"Colonnes requises: {', '.join(required_columns)}")

        # Supprimer toutes les signatures existantes avant l'import
        logger.info("Deletion de toutes les signatures existantes...")
        delete_result = db_manager.delete_all_signatures()
        logger.info(f"{delete_result['signatures_deleted']} signature(s) supprimée(s)")

        publish_progress_sync(
            "import_progress",
            {"status": "deleted_old_signatures", "count": delete_result["signatures_deleted"], "total_expected": total_lines_expected},
        )

        # Importer ligne par ligne
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
                is_negative = is_negative_str.lower() in ("true", "1", "yes", "oui")

                if not appliance_name:
                    raise ValueError("Le nom de l'appareil ne peut pas être vide")

                # Valider les timestamps
                start_dt = datetime.fromisoformat(start_time)
                end_dt = datetime.fromisoformat(end_time)

                if start_dt >= end_dt:
                    raise ValueError("start_time doit être antérieur à end_time")

                # Créer la signature via Celery
                celery_app.send_task(
                    "add_nilm_signature",
                    args=(appliance_name, start_time, end_time),
                    kwargs={"is_negative": is_negative},
                    queue="nilm_cnn",
                    routing_key="nilm.add_nilm_signature",
                )

                success_count += 1

                # Publish progress every 5 lines
                if processed_lines % 5 == 0:
                    progress_percent = int((processed_lines / total_lines_expected) * 100) if total_lines_expected > 0 else 0
                    publish_progress_sync(
                        "import_progress",
                        {
                            "total_lines": processed_lines,
                            "success_count": success_count,
                            "error_count": error_count,
                            "progress_percent": progress_percent,
                        },
                    )

            except ValueError as e:
                error_count += 1
                errors.append({"line": line_num, "error": str(e)})
            except Exception as e:
                error_count += 1
                errors.append({"line": line_num, "error": f"Erreur inattendue: {str(e)}"})

        # Publish import_complete event
        publish_progress_sync(
            "import_complete", {"status": "completed", "total_lines": processed_lines, "success_count": success_count, "error_count": error_count}
        )

        return {
            "status": "completed",
            "signatures_deleted": delete_result["signatures_deleted"],
            "total_lines": processed_lines,
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during l'import CSV: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur serveur lors de l'import: {str(e)}")
