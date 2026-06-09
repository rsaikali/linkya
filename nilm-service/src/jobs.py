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

# Name of the model currently loaded in nilm_manager (for champion-change detection).
_loaded_model_name: str | None = None

# Keep at most this many models in DB/disk.
_MAX_MODELS = 5

# Serialize train/detect — TF is not safe to run concurrently in one process.
_lock = threading.Lock()

# Coalescing: at most one training and one detection may be pending at a time.
# Bursts (e.g. CSV import crossing several auto-train thresholds, or rapid UI
# clicks) collapse to a single queued run instead of piling up on the Pi.
_pending = {"train": False, "detect": False}
_pending_lock = threading.Lock()


def request_training(min_signatures: int = 2) -> bool:
    """Queue a training run unless one is already pending. Returns True if queued."""
    with _pending_lock:
        if _pending["train"]:
            logger.info("Training already pending — request coalesced")
            return False
        _pending["train"] = True

    def _worker():
        try:
            run_training(min_signatures)
        finally:
            with _pending_lock:
                _pending["train"] = False

    threading.Thread(target=_worker, daemon=True).start()
    return True


def request_detection(hours=None, min_confidence: float = 0.25) -> bool:
    """Queue a detection run unless one is already pending. Returns True if queued."""
    with _pending_lock:
        if _pending["detect"]:
            logger.info("Detection already pending — request coalesced")
            return False
        _pending["detect"] = True

    def _worker():
        try:
            run_detection(hours, min_confidence)
        finally:
            with _pending_lock:
                _pending["detect"] = False

    threading.Thread(target=_worker, daemon=True).start()
    return True


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

            with db_manager.get_session() as session:
                # Insert new model as challenger (is_champion=False).
                session.execute(
                    text(
                        """
                        INSERT INTO nilm_models
                        (model_name, model_type, architecture, training_date,
                         num_signatures, num_classes, metrics, model_path,
                         training_duration_seconds, is_champion)
                        VALUES
                        (:model_name, :model_type, cast(:architecture as jsonb),
                         :training_date, :num_signatures, :num_classes,
                         cast(:metrics as jsonb), :model_path, :duration, FALSE)
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
                # Auto-promote when no champion exists yet (first model).
                has_champion = session.execute(
                    text("SELECT COUNT(*) FROM nilm_models WHERE is_champion=TRUE")
                ).scalar() or 0
                if not has_champion:
                    session.execute(
                        text("UPDATE nilm_models SET is_champion=TRUE WHERE model_name=:name"),
                        {"name": model_name},
                    )
                    logger.info("Auto-promoted %s as champion (no previous champion)", model_name)
                # Trim oldest non-champion models beyond _MAX_MODELS.
                _trim_old_models(session)
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
        # Heartbeat: marks each detection run (distinct from last detected cycle).
        db_manager.set_meta("last_detect_run", datetime.now(timezone.utc).isoformat())
        try:
            global _loaded_model_name
            with db_manager.engine.connect() as conn:
                # Champion first, fallback to latest.
                row = conn.execute(
                    text("SELECT model_name FROM nilm_models WHERE is_champion=TRUE LIMIT 1")
                ).first()
                if not row:
                    row = conn.execute(
                        text("SELECT model_name FROM nilm_models ORDER BY training_date DESC LIMIT 1")
                    ).first()
                if not row:
                    return {"status": "skipped", "message": "Aucun modèle disponible"}
                active_model = row.model_name

            model_path = os.path.join(settings.nilm_model_path, f"{active_model}.keras")
            if nilm_manager.multioutput_model is None or _loaded_model_name != active_model:
                if os.path.exists(model_path):
                    nilm_manager.load_model(model_path)
                    _loaded_model_name = active_model
                else:
                    return {"status": "error", "message": f"Fichier modèle introuvable: {model_path}"}

            end_time = datetime.now(timezone.utc)
            if hours is None:
                with db_manager.engine.connect() as conn:
                    row = conn.execute(text("SELECT MIN(time) AS min_date FROM linky_realtime")).first()
                start_time = row.min_date if row and row.min_date else end_time - timedelta(hours=240)
            else:
                start_time = end_time - timedelta(hours=hours)

            full_detect = hours is None

            events.emit("detection_start", {"model_name": active_model})
            events_list = nilm_manager.disaggregate(start_time, end_time)

            num_saved = num_skipped = 0
            with db_manager.get_session() as session:
                # Wipe existing detections for the window, then insert fresh ones.
                # Full detect: wipe ALL detections + reset energy HWM (fresh slate).
                # Cron: wipe only the time window (don't touch older history).
                if full_detect:
                    session.execute(text("DELETE FROM nilm_detections"))
                    logger.info("Full detect: wiped all detections")
                else:
                    session.execute(
                        text("""
                            DELETE FROM nilm_detections
                            WHERE start_time >= :start AND start_time < :end
                        """),
                        {"start": start_time, "end": end_time},
                    )
                    logger.info("Cron detect: wiped detections in window [%s, %s]", start_time, end_time)

                for ev in events_list:
                    appliance_id = ev.get("appliance_id")
                    if not appliance_id:
                        r = session.execute(
                            text("SELECT id FROM nilm_appliances WHERE name = :n LIMIT 1"),
                            {"n": ev["appliance_name"]},
                        ).first()
                        appliance_id = r.id if r else None
                    if not appliance_id:
                        num_skipped += 1
                        continue

                    det_id = session.execute(
                        text("""
                            INSERT INTO nilm_detections
                            (appliance_id, start_time, end_time, avg_power, energy_consumed,
                             confidence_score, prediction_class, features, model_name, created_at)
                            VALUES (:aid, :start, :end, :avg, :energy, :conf, :cls, :feat, :model, NOW())
                            RETURNING id
                        """),
                        {
                            "aid": appliance_id,
                            "start": ev["start_time"],
                            "end": ev["end_time"],
                            "avg": ev.get("avg_power"),
                            "energy": ev.get("energy_wh", ev.get("energy_consumed")),
                            "conf": ev["confidence_score"],
                            "cls": ev.get("prediction_class"),
                            "feat": json.dumps(ev.get("features", {})),
                            "model": active_model,
                        },
                    ).scalar()
                    num_saved += 1
                    events.emit("detection_new", {
                        "id": det_id,
                        "name": ev["appliance_name"],
                        "avg_power": ev.get("avg_power"),
                        "confidence_score": ev["confidence_score"],
                    })

            result = {
                "status": "success",
                "num_detections": num_saved,
                "num_skipped": num_skipped,
                "model_name": active_model,
                "full_detect": full_detect,
            }
            events.emit("detection_complete", result)
            logger.info("Detection: %d saved, %d skipped (full=%s)", num_saved, num_skipped, full_detect)
            return result

        except Exception as e:
            logger.error("detection error: %s", e, exc_info=True)
            return {"status": "error", "message": str(e)}


def add_signature(appliance_name: str, start_time_str: str, end_time_str: str, is_negative: bool = False, auto_train: bool = True) -> dict:
    """Store a user signature (computes power_data + morphology).

    auto_train=False during bulk CSV import — the caller triggers a single
    training afterwards instead of one per row.
    """
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
        # Coalesced — bursts collapse to one queued run.
        if auto_train and not is_negative:
            n = db_manager.count_positive_signatures()
            if n >= 2 and (n - 2) % 5 == 0:
                if request_training():
                    logger.info("Auto-train queued (%d positive signatures)", n)

        return {"status": "success", "signature_id": signature_id, "appliance_id": appliance_id, "appliance_name": appliance_name}

    except Exception as e:
        logger.error("add_signature error: %s", e, exc_info=True)
        return {"status": "error", "message": str(e)}


def _trim_old_models(session) -> None:
    """Delete oldest non-champion models when total exceeds _MAX_MODELS."""
    total = session.execute(text("SELECT COUNT(*) FROM nilm_models")).scalar() or 0
    excess = total - _MAX_MODELS
    if excess <= 0:
        return
    rows = session.execute(
        text("SELECT id, model_path FROM nilm_models WHERE is_champion=FALSE ORDER BY training_date ASC LIMIT :n"),
        {"n": excess},
    ).fetchall()
    for row in rows:
        if row.model_path:
            for p in (Path(row.model_path), Path(str(row.model_path).replace(".keras", ".metadata.json"))):
                if p.exists():
                    try:
                        p.unlink()
                    except Exception as e:
                        logger.warning("cannot delete %s: %s", p, e)
        session.execute(text("DELETE FROM nilm_models WHERE id=:id"), {"id": row.id})
    logger.info("Trimmed %d old non-champion model(s)", len(rows))


def promote_model(model_id: int) -> dict:
    """Promote a model to champion. Reloads it immediately for detection."""
    global _loaded_model_name
    with _lock:
        with db_manager.engine.begin() as conn:
            row = conn.execute(
                text("SELECT model_name, model_path FROM nilm_models WHERE id=:id"),
                {"id": model_id},
            ).first()
            if not row:
                return {"status": "error", "message": f"Modèle {model_id} introuvable"}
            conn.execute(text("UPDATE nilm_models SET is_champion=FALSE"))
            conn.execute(
                text("UPDATE nilm_models SET is_champion=TRUE WHERE id=:id"),
                {"id": model_id},
            )
        model_path = os.path.join(settings.nilm_model_path, f"{row.model_name}.keras")
        if not os.path.exists(model_path):
            return {"status": "error", "message": f"Fichier modèle introuvable: {model_path}"}
        nilm_manager.load_model(model_path)
        _loaded_model_name = row.model_name
        logger.info("Champion promoted: %s", row.model_name)
        return {"status": "ok", "champion": row.model_name}


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
