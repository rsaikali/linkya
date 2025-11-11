import logging
from datetime import datetime, timedelta

from celery import Celery

from .config import settings
from .database import db_manager


# Configuration du logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialisation de Celery
celery_app = Celery("linkya-sync", broker=settings.celery_broker_url, backend=settings.celery_result_backend)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="full_sync")
def full_sync():
    """Full synchronization of 48h of data"""
    logger.info("Starting full synchronization...")

    try:
        # Retrieve data from last 48 hours
        since = datetime.utcnow() - timedelta(hours=settings.sync_retention_hours)

        logger.info(f"Fetching data since {since}")
        data = db_manager.get_remote_data(since=since)

        logger.info(f"{len(data)} records retrieved")

        if data:
            inserted = db_manager.bulk_insert_data(data)
            logger.info(f"{inserted} records inserted")

            return {"status": "success", "fetched": len(data), "inserted": inserted, "timestamp": datetime.utcnow().isoformat()}
        else:
            logger.info("No data to synchronize")
            return {"status": "success", "fetched": 0, "inserted": 0, "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error(f"Error during full synchronization: {e}")
        return {"status": "error", "message": str(e)}


@celery_app.task(name="incremental_sync")
def incremental_sync():
    """Incremental synchronization of new data"""
    logger.info("Starting incremental synchronization...")

    try:
        # Retrieve last sync timestamp
        last_sync = db_manager.get_last_sync_timestamp()

        if last_sync:
            logger.info(f"Last synchronization: {last_sync}")
            data = db_manager.get_remote_data(since=last_sync)
        else:
            logger.warning("No previous synchronization, full synchronization required")
            return full_sync()

        if data:
            inserted = db_manager.bulk_insert_data(data)
            logger.info(f"{inserted} new records inserted")

            return {
                "status": "success",
                "fetched": len(data),
                "inserted": inserted,
                "last_sync": last_sync.isoformat() if last_sync else None,
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            logger.info("No new data")
            return {
                "status": "success",
                "fetched": 0,
                "inserted": 0,
                "last_sync": last_sync.isoformat() if last_sync else None,
                "timestamp": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        logger.error(f"Error during incremental synchronization: {e}")
        return {"status": "error", "message": str(e)}


# Configuration du Beat scheduler pour les tâches périodiques
celery_app.conf.beat_schedule = {"incremental-sync": {"task": "incremental_sync", "schedule": float(settings.sync_interval_seconds)}}
