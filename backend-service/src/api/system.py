"""Health check + system-level controls."""

from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text

from ..db import db_manager
from ..events import bus


router = APIRouter(tags=["System"])

_META_KEY = "ha_publish_paused"


def _get_paused() -> bool:
    with db_manager.engine.connect() as conn:
        row = conn.execute(
            text("SELECT value FROM nilm_meta WHERE key = :k"),
            {"k": _META_KEY},
        ).fetchone()
    return row is not None and row[0] == "1"


def _set_paused(paused: bool) -> None:
    with db_manager.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO nilm_meta (key, value) VALUES (:k, :v)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """
            ),
            {"k": _META_KEY, "v": "1" if paused else "0"},
        )


@router.get("/healthz")
async def healthz():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@router.get("/api/ha/experiment-mode")
async def get_experiment_mode():
    return {"paused": _get_paused()}


@router.post("/api/ha/experiment-mode")
async def set_experiment_mode(body: dict):
    paused = bool(body.get("paused", False))
    _set_paused(paused)
    bus.publish("ha_experiment_mode", {"paused": paused})
    return {"paused": paused}
