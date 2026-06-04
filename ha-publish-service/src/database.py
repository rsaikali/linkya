"""Read appliances, current state, cumulative energy, and lab stats."""

import json

from sqlalchemy import create_engine, text

from .config import settings


class PublishRepository:
    def __init__(self):
        self.engine = create_engine(settings.local_db_url, pool_pre_ping=True, pool_size=3)
        self._init_hwm()

    def _init_hwm(self):
        """High-water-mark table: persisted monotonic energy per appliance so the
        HA total_increasing sensor never decreases (re-detection / restart safe)."""
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS ha_energy_hwm (
                        appliance_id INTEGER PRIMARY KEY,
                        kwh DOUBLE PRECISION NOT NULL DEFAULT 0
                    );
                    """
                )
            )

    def get_active_appliances(self) -> list[dict]:
        """Return all appliances with ha_publish=True."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, name, ha_entity_id
                    FROM nilm_appliances
                    WHERE ha_publish = TRUE
                    ORDER BY name
                    """
                )
            ).fetchall()
        return [{"id": r[0], "name": r[1], "ha_entity_id": r[2]} for r in rows]

    def get_all_appliance_names(self) -> list[str]:
        """All appliance names (for legacy MQTT topic cleanup)."""
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT name FROM nilm_appliances")).fetchall()
        return [r[0] for r in rows]

    def is_currently_active(self, appliance_id: int) -> bool:
        """
        True if the appliance has a detection cycle currently in progress
        or that ended within the active_buffer (detection lag tolerance).

        A cycle is "active" if:
          start_time <= NOW()  AND  end_time >= NOW() - buffer
        """
        buffer = int(settings.active_buffer_minutes)
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    f"""
                    SELECT id FROM nilm_detections
                    WHERE appliance_id = :id
                      AND start_time <= NOW()
                      AND end_time >= NOW() - INTERVAL '{buffer} minutes'
                    ORDER BY end_time DESC
                    LIMIT 1
                    """
                ),
                {"id": appliance_id},
            ).fetchone()
        return row is not None

    def get_monotonic_energy_kwh(self, appliance_id: int) -> float:
        """Cumulative detected energy (kWh), clamped to a persisted high-water-mark
        so it never decreases — safe for HA total_increasing (no false reset/jump
        when a re-detection shrinks the raw sum)."""
        with self.engine.begin() as conn:
            cur = conn.execute(
                text(
                    """
                    SELECT COALESCE(SUM(energy_consumed), 0) / 1000.0
                    FROM nilm_detections
                    WHERE appliance_id = :id AND energy_consumed IS NOT NULL
                    """
                ),
                {"id": appliance_id},
            ).scalar() or 0.0
            prev = conn.execute(
                text("SELECT kwh FROM ha_energy_hwm WHERE appliance_id = :id"),
                {"id": appliance_id},
            ).scalar() or 0.0
            value = max(float(cur), float(prev))
            conn.execute(
                text(
                    """
                    INSERT INTO ha_energy_hwm (appliance_id, kwh) VALUES (:id, :kwh)
                    ON CONFLICT (appliance_id) DO UPDATE SET kwh = EXCLUDED.kwh
                    """
                ),
                {"id": appliance_id, "kwh": value},
            )
        return round(value, 3)

    def get_detections_for_backfill(self, appliance_id: int) -> list[dict]:
        """
        All validated detections for this appliance, ordered chronologically.
        Used to build hourly statistics for HA historical import.
        """
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT start_time, end_time, energy_consumed
                    FROM nilm_detections
                    WHERE appliance_id = :id
                      AND energy_consumed IS NOT NULL
                      AND energy_consumed > 0
                    ORDER BY start_time ASC
                    """
                ),
                {"id": appliance_id},
            ).fetchall()
        return [
            {
                "start_time": r[0],
                "end_time": r[1],
                "energy_wh": float(r[2]),
            }
            for r in rows
        ]

    def get_nilm_stats(self) -> dict | None:
        """Lab diagnostics for HA: active model + detection aggregates.
        Returns None when no model has been trained yet."""
        with self.engine.connect() as conn:
            m = conn.execute(
                text(
                    """
                    SELECT model_name, model_type, training_date, num_signatures,
                           num_classes, training_duration_seconds, metrics
                    FROM nilm_models
                    ORDER BY training_date DESC
                    LIMIT 1
                    """
                )
            ).fetchone()
            if not m:
                return None

            det = conn.execute(
                text("SELECT COUNT(*), MAX(created_at) FROM nilm_detections")
            ).fetchone()
            last_run = conn.execute(
                text("SELECT value FROM nilm_meta WHERE key = 'last_detect_run'")
            ).scalar()

        metrics = m[6] if isinstance(m[6], dict) else json.loads(m[6] or "{}")
        apps = metrics.get("appliances") or []
        first = apps[0].get("metrics", {}) if apps else {}

        def _iso(dt):
            return dt.isoformat() if dt else None

        return {
            "model_version": m[0],
            "model_type": m[1],
            "trained_at": _iso(m[2]),
            "num_signatures": m[3],
            "num_appliances": m[4],
            "train_duration_s": m[5],
            "train_loss": _round(first.get("train_loss")),
            "val_loss": _round(first.get("val_loss")),
            "epochs": first.get("epochs_trained"),
            "detections_total": det[0] if det else 0,
            "last_detection": _iso(det[1]) if det else None,
            "last_detect_run": last_run,
        }


def _round(v, n=4):
    return round(float(v), n) if v is not None else None


repo = PublishRepository()
