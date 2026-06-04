"""NILM jobs: train, detect, add signature, delete models.

Converted from the old Celery tasks. No broker: called directly (FastAPI
BackgroundTasks) or by the APScheduler detect cron. Live progress is pushed
to the backend SSE bus via events.emit().
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text

from . import events
from .config import settings
from .database import db_manager
from .seq2point_nilm import Seq2PointNILMManager


logger = logging.getLogger(__name__)

LOCAL_TZ = timezone.utc

# Single shared manager (holds the loaded Keras model in memory).
nilm_manager = Seq2PointNILMManager()

# Serialize train/detect — TF is not safe to run concurrently in one process.
_lock = threading.Lock()


def run_training(min_signatures: int = 2) -> dict:
    """Train a fresh model from all signatures. Replaces the previous model."""
    with _lock:
        try:
            events.emit("training_progress", {"phase": "start"})
            start = time.time()
            timestamp = datetime.now(LOCAL_TZ).strftime("%Y%m%d_%H%M%S")
            model_name = f"linkya_model_{timestamp}"
            logger.info("Training %s ...", model_name)

            metrics = nilm_manager.train_all_appliances(model_name, fine_tune=False)
            if "error" in metrics:
                events.emit("training_error", {"error": metrics.get("error")})
                return {"status": "error", "message": metrics.get("error"), "details": metrics}

            num_appliances = metrics.get("num_appliances", 0)
            total_signatures = sum(a["num_signatures"] for a in metrics.get("appliances", []))
            architecture = {
                "type": f"S2P-MULTI-{nilm_manager.model_type.upper()}",
                "sequence_length": settings.effective_sequence_length,
                "num_appliances": num_appliances,
                "model_type": nilm_manager.model_type,
                "appliances": metrics.get("appliances", []),
            }
            model_type_str = f"S2P-MULTI-{nilm_manager.model_type.upper()}"
            duration = int(time.time() - start)
            completed_at = datetime.now(LOCAL_TZ)

            # Drop the previous model (single active model policy).
            with db_manager.get_session() as session:
                for old_id, old_path in session.execute(text("SELECT id, model_path FROM nilm_models")).fetchall():
                    if old_path and Path(old_path).exists():
                        try:
                            Path(old_path).unlink()
                        except Exception as e:
                            logger.warning("cannot delete %s: %s", old_path, e)
                    meta = Path(str(old_path).replace(".keras", ".metadata.json"))
                    if meta.exists():
                        try:
                            meta.unlink()
                        except Exception:
                            pass
                session.execute(text("DELETE FROM nilm_models"))
                session.commit()

            with db_manager.get_session() as session:
                session.execute(
                    text(
                        """
                        INSERT INTO nilm_models
                        (model_name, model_type, architecture, training_date,
                         num_signatures, num_classes, metrics, model_path,
                         training_duration_seconds)
                        VALUES
                        (:model_name, :model_type, cast(:architecture as jsonb),
                         :training_date, :num_signatures, :num_classes,
                         cast(:metrics as jsonb), :model_path, :duration)
                        """
                    ),
                    {
                        "model_name": model_name,
                        "model_type": model_type_str,
                        "architecture": json.dumps(architecture),
                        "training_date": completed_at,
                        "num_signatures": total_signatures,
                        "num_classes": num_appliances,
                        "metrics": json.dumps(metrics, default=str),
                        "model_path": metrics.get("model_path", f"{settings.nilm_model_path}/{model_name}.keras"),
                        "duration": duration,
                    },
                )
                session.commit()

            logger.info("Model %s trained in %ds (%d appliances, %d sigs)", model_name, duration, num_appliances, total_signatures)
            result = {
                "status": "success",
                "model_name": model_name,
                "model_type": model_type_str,
                "num_signatures": total_signatures,
                "num_appliances": num_appliances,
                "training_duration_seconds": duration,
                "timestamp": completed_at.isoformat(),
            }
            events.emit("training_complete", result)
            return result

        except Exception as e:
            logger.error("training error: %s", e, exc_info=True)
            events.emit("training_error", {"error": str(e)})
            return {"status": "error", "message": str(e)}


def run_detection(hours=None, min_confidence: float = 0.25) -> dict:
    """Run disaggregation over a window (hours=None → full history)."""
    with _lock:
        try:
            with db_manager.engine.connect() as conn:
                row = conn.execute(text("SELECT model_name FROM nilm_models ORDER BY training_date DESC LIMIT 1")).first()
                if not row:
                    return {"status": "skipped", "message": "Aucun modèle disponible"}
                active_model = row.model_name

            model_path = os.path.join(settings.nilm_model_path, f"{active_model}.keras")
            if nilm_manager.multioutput_model is None:
                if os.path.exists(model_path):
                    nilm_manager.load_model(model_path)
                else:
                    return {"status": "error", "message": f"Fichier modèle introuvable: {model_path}"}

            end_time = datetime.now(timezone.utc)
            if hours is None:
                with db_manager.engine.connect() as conn:
                    row = conn.execute(text("SELECT MIN(time) AS min_date FROM linky_realtime")).first()
                start_time = row.min_date if row and row.min_date else end_time - timedelta(hours=240)
            else:
                start_time = end_time - timedelta(hours=hours)

            events.emit("detection_start", {"model_name": active_model})
            events_list = nilm_manager.disaggregate(start_time, end_time)
            if not events_list:
                events.emit("detection_complete", {"num_detections": 0})
                return {"status": "success", "num_detections": 0}

            num_saved = num_updated = num_skipped = 0
            with db_manager.get_session() as session:
                for ev in events_list:
                    appliance_id = ev.get("appliance_id")
                    if not appliance_id:
                        r = session.execute(text("SELECT id FROM nilm_appliances WHERE name = :n LIMIT 1"), {"n": ev["appliance_name"]}).first()
                        appliance_id = r.id if r else None
                    if not appliance_id:
                        num_skipped += 1
                        continue

                    existing = session.execute(
                        text(
                            """
                            SELECT id, confidence_score FROM nilm_detections
                            WHERE appliance_id = :aid
                              AND (:start <= end_time AND :end >= start_time)
                            ORDER BY confidence_score DESC LIMIT 1
                            """
                        ),
                        {"aid": appliance_id, "start": ev["start_time"], "end": ev["end_time"]},
                    ).first()

                    features = ev.get("features", {})
                    if existing:
                        if float(ev["confidence_score"]) > float(existing.confidence_score):
                            session.execute(
                                text(
                                    """
                                    UPDATE nilm_detections
                                    SET start_time=:start, end_time=:end, avg_power=:avg,
                                        energy_consumed=:energy, confidence_score=:conf,
                                        prediction_class=:cls, features=:feat, created_at=NOW()
                                    WHERE id=:id
                                    """
                                ),
                                {
                                    "id": existing.id, "start": ev["start_time"], "end": ev["end_time"],
                                    "avg": ev.get("avg_power"), "energy": ev.get("energy_wh", ev.get("energy_consumed")),
                                    "conf": ev["confidence_score"], "cls": ev.get("prediction_class"),
                                    "feat": json.dumps(features),
                                },
                            )
                            num_updated += 1
                        else:
                            num_skipped += 1
                    else:
                        det_id = session.execute(
                            text(
                                """
                                INSERT INTO nilm_detections
                                (appliance_id, start_time, end_time, avg_power, energy_consumed,
                                 confidence_score, prediction_class, features, created_at)
                                VALUES (:aid, :start, :end, :avg, :energy, :conf, :cls, :feat, NOW())
                                RETURNING id
                                """
                            ),
                            {
                                "aid": appliance_id, "start": ev["start_time"], "end": ev["end_time"],
                                "avg": ev.get("avg_power"), "energy": ev.get("energy_wh", ev.get("energy_consumed")),
                                "conf": ev["confidence_score"], "cls": ev.get("prediction_class"),
                                "feat": json.dumps(features),
                            },
                        ).scalar()
                        num_saved += 1
                        events.emit("detection_new", {
                            "id": det_id, "name": ev["appliance_name"],
                            "avg_power": ev.get("avg_power"), "confidence_score": ev["confidence_score"],
                        })

            result = {
                "status": "success", "num_detections": num_saved, "num_updated": num_updated,
                "num_skipped": num_skipped, "model_name": active_model,
            }
            events.emit("detection_complete", result)
            logger.info("Detection: %d new, %d updated, %d skipped", num_saved, num_updated, num_skipped)
            return result

        except Exception as e:
            logger.error("detection error: %s", e, exc_info=True)
            return {"status": "error", "message": str(e)}


def add_signature(appliance_name: str, start_time_str: str, end_time_str: str, is_negative: bool = False) -> dict:
    """Store a user signature (computes power_data + morphology). May auto-train."""
    try:
        start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
        if (end_time - start_time).total_seconds() < settings.nilm_min_duration_seconds:
            return {"status": "error", "message": f"Durée trop courte (min {settings.nilm_min_duration_seconds}s)"}

        with db_manager.get_session() as session:
            r = session.execute(text("SELECT id FROM nilm_appliances WHERE name = :n LIMIT 1"), {"n": appliance_name}).first()
            if r:
                appliance_id = r.id
            else:
                appliance_id = session.execute(
                    text("INSERT INTO nilm_appliances (name, created_at, updated_at) VALUES (:n, NOW(), NOW()) RETURNING id"),
                    {"n": appliance_name},
                ).scalar()

        try:
            signature_id = db_manager.add_signature(
                appliance_id=appliance_id, start_time=start_time, end_time=end_time, is_negative=is_negative
            )
        except ValueError as ve:
            return {"status": "error", "error_type": "validation", "message": str(ve)}
        if not signature_id:
            return {"status": "error", "message": "Échec de l'ajout de la signature"}

        # Auto-train on positive signatures: at 2, then every 5th (Pi-friendly).
        if not is_negative:
            n = db_manager.count_positive_signatures()
            if n >= 2 and (n - 2) % 5 == 0:
                threading.Thread(target=run_training, daemon=True).start()
                logger.info("Auto-train triggered (%d positive signatures)", n)

        return {"status": "success", "signature_id": signature_id, "appliance_id": appliance_id, "appliance_name": appliance_name}

    except Exception as e:
        logger.error("add_signature error: %s", e, exc_info=True)
        return {"status": "error", "message": str(e)}


def delete_models() -> dict:
    """Delete all models from DB + .keras/.metadata files on disk."""
    import glob

    deleted_count = 0
    with db_manager.get_session() as session:
        deleted_count = session.execute(text("SELECT COUNT(*) FROM nilm_models")).scalar() or 0
        session.execute(text("DELETE FROM nilm_models"))
        session.commit()

    deleted_files = []
    for pattern in ("*.keras", "*.metadata.json"):
        for fp in glob.glob(os.path.join(settings.nilm_model_path, pattern)):
            try:
                os.remove(fp)
                deleted_files.append(fp)
            except OSError as e:
                logger.warning("cannot delete %s: %s", fp, e)

    nilm_manager.multioutput_model = None
    return {"status": "success", "deleted_count": deleted_count, "deleted_files": len(deleted_files)}
