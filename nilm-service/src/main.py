"""NILM service — FastAPI wrapper around the Seq2Point engine.

Endpoints (internal, Docker-network only):
  POST /train            → train a fresh model (background)
  POST /detect           → detect over full history (background)
  POST /signatures       → add a user signature (sync)
  POST /models/delete    → delete all models
  GET  /healthz

A built-in APScheduler runs detection every NILM_DETECTION_INTERVAL_MINUTES
over a rolling 2h window.
"""

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from pydantic import BaseModel

from . import jobs
from .config import settings
from .database import db_manager


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")


def _scheduled_detect():
    logger.info("Scheduled detection (rolling 2h)")
    jobs.request_detection(hours=2, min_confidence=0.25)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_manager.init_tables()
    logger.info("NILM tables ready")
    scheduler.add_job(
        _scheduled_detect,
        "interval",
        minutes=settings.nilm_detection_interval_minutes,
        id="detect",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Detection scheduler started (every %d min)", settings.nilm_detection_interval_minutes)
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Linkya NILM", lifespan=lifespan)


class SignatureIn(BaseModel):
    appliance_name: str
    start_time: str
    end_time: str
    is_negative: bool = False
    auto_train: bool = True   # False during bulk CSV import


@app.get("/healthz")
def healthz():
    return {"status": "healthy"}


@app.post("/train")
def train():
    queued = jobs.request_training()
    return {"status": "started" if queued else "already_pending", "message": "Entraînement lancé"}


@app.post("/detect")
def detect():
    queued = jobs.request_detection(None, 0.25)
    return {"status": "started" if queued else "already_pending", "message": "Détection lancée"}


@app.post("/signatures")
def add_signature(sig: SignatureIn):
    return jobs.add_signature(sig.appliance_name, sig.start_time, sig.end_time, sig.is_negative, sig.auto_train)


@app.post("/models/delete")
def delete_models():
    return jobs.delete_models()
