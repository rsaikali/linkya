"""Read appliances, current state, cumulative energy, and lab stats."""

import json

from sqlalchemy import create_engine, text

from .config import settings


class PublishRepository:
    def __init__(self):
        self.engine = create_engine(settings.local_db_url, pool_pre_ping=True, pool_size=3)

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

    def is_publish_paused(self) -> bool:
        """True when experiment mode is active (ha_publish_paused=1 in nilm_meta)."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT value FROM nilm_meta WHERE key = 'ha_publish_paused'")
            ).fetchone()
        return row is not None and row[0] == "1"

    def get_cumulative_energy_kwh(self, appliance_id: int) -> float:
        """Total kWh from all detections (MQTT live state, total_increasing)."""
        with self.engine.connect() as conn:
            val = conn.execute(
                text(
                    """
                    SELECT COALESCE(SUM(energy_consumed), 0) / 1000.0
                    FROM nilm_detections
                    WHERE appliance_id = :id
                      AND energy_consumed IS NOT NULL AND energy_consumed > 0
                    """
                ),
                {"id": appliance_id},
            ).scalar()
        return round(float(val or 0.0), 4)

    def get_all_detections_ordered(self, appliance_id: int) -> list[dict]:
        """All detections with energy_consumed > 0, oldest first (for full resync)."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, start_time, end_time, energy_consumed
                    FROM nilm_detections
                    WHERE appliance_id = :id
                      AND energy_consumed IS NOT NULL AND energy_consumed > 0
                    ORDER BY start_time ASC
                    """
                ),
                {"id": appliance_id},
            ).fetchall()
        return [
            {"id": r[0], "start_time": r[1], "end_time": r[2], "energy_wh": float(r[3])}
            for r in rows
        ]

    def get_detections_since_id(self, appliance_id: int, min_id: int) -> list[dict]:
        """Detections with id > min_id, oldest first (for incremental updates)."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, start_time, end_time, energy_consumed
                    FROM nilm_detections
                    WHERE appliance_id = :id AND id > :min_id
                      AND energy_consumed IS NOT NULL AND energy_consumed > 0
                    ORDER BY start_time ASC
                    """
                ),
                {"id": appliance_id, "min_id": min_id},
            ).fetchall()
        return [
            {"id": r[0], "start_time": r[1], "end_time": r[2], "energy_wh": float(r[3])}
            for r in rows
        ]

    def get_cumulative_energy_before_id(self, appliance_id: int, det_id: int) -> float:
        """Sum of energy_consumed (Wh) for all detections with id < det_id."""
        with self.engine.connect() as conn:
            val = conn.execute(
                text(
                    """
                    SELECT COALESCE(SUM(energy_consumed), 0)
                    FROM nilm_detections
                    WHERE appliance_id = :id AND id < :det_id
                      AND energy_consumed IS NOT NULL AND energy_consumed > 0
                    """
                ),
                {"id": appliance_id, "det_id": det_id},
            ).scalar()
        return float(val or 0.0)

    def get_last_confidence(self, appliance_id: int) -> float | None:
        """Confidence score (0–100 %) of the most recent detection for this appliance."""
        with self.engine.connect() as conn:
            val = conn.execute(
                text(
                    """
                    SELECT ROUND(confidence_score::numeric * 100, 1)
                    FROM nilm_detections
                    WHERE appliance_id = :id
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"id": appliance_id},
            ).scalar()
        return float(val) if val is not None else None

    def get_nilm_stats(self) -> dict | None:
        """Lab diagnostics for HA: active model + detection aggregates.
        Returns None when no model has been trained yet."""
        with self.engine.connect() as conn:
            # Champion first, fallback to latest.
            m = conn.execute(
                text(
                    """
                    SELECT model_name, model_type, training_date, num_signatures,
                           num_classes, training_duration_seconds, metrics
                    FROM nilm_models
                    WHERE is_champion = TRUE
                    ORDER BY training_date DESC
                    LIMIT 1
                    """
                )
            ).fetchone()
            if not m:
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
            avg_conf = conn.execute(
                text(
                    """
                    SELECT ROUND(AVG(confidence_score)::numeric * 100, 1)
                    FROM nilm_detections
                    WHERE created_at >= NOW() - INTERVAL '30 days'
                    """
                )
            ).scalar()
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
            "avg_confidence_pct": float(avg_conf) if avg_conf is not None else None,
            "detections_total": det[0] if det else 0,
            "last_detection": _iso(det[1]) if det else None,
            "last_detect_run": last_run,
        }


def _round(v, n=4):
    return round(float(v), n) if v is not None else None


repo = PublishRepository()
