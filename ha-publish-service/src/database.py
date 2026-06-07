"""Read appliances, current state, cumulative energy, and lab stats."""

import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from .config import settings


class PublishRepository:
    def __init__(self):
        self.engine = create_engine(settings.local_db_url, pool_pre_ping=True, pool_size=3)
        self._init_hwm()

    def _init_hwm(self):
        """Per-appliance energy state for the HA total_increasing sensor:
        - baseline: SUM(detections) at the last reset (sensor = SUM - baseline)
        - kwh: high-water-mark → published value never decreases.
        """
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS ha_energy_hwm (
                        appliance_id INTEGER PRIMARY KEY,
                        baseline DOUBLE PRECISION NOT NULL DEFAULT 0,
                        kwh DOUBLE PRECISION NOT NULL DEFAULT 0
                    );
                    """
                )
            )
            # Upgrade older tables that lack the baseline column.
            conn.execute(
                text("ALTER TABLE ha_energy_hwm ADD COLUMN IF NOT EXISTS baseline DOUBLE PRECISION NOT NULL DEFAULT 0")
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

    def is_publish_paused(self) -> bool:
        """True when experiment mode is active (ha_publish_paused=1 in nilm_meta)."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT value FROM nilm_meta WHERE key = 'ha_publish_paused'")
            ).fetchone()
        return row is not None and row[0] == "1"

    def get_frozen_energy_kwh(self, appliance_id: int) -> float:
        """Return the current HWM without updating it (safe to call during experiment mode)."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT kwh FROM ha_energy_hwm WHERE appliance_id = :id"),
                {"id": appliance_id},
            ).fetchone()
        return round(float(row[0]), 3) if row else 0.0

    def get_monotonic_energy_kwh(self, appliance_id: int) -> float:
        """Energy since last reset (kWh) = SUM(detections) - baseline, clamped to a
        persisted high-water-mark so it never decreases (re-detection / restart
        safe → no false meter reset/jump in HA total_increasing)."""
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
            row = conn.execute(
                text("SELECT baseline, kwh FROM ha_energy_hwm WHERE appliance_id = :id"),
                {"id": appliance_id},
            ).fetchone()
            cur_f = float(cur)
            if row is None:
                # First time: anchor baseline to current sum so MQTT starts at 0.
                # Historical data must be injected via ha-backfill.
                baseline = cur_f
                prev = 0.0
            else:
                baseline = float(row[0])
                prev = float(row[1])
            if cur_f < baseline:
                # Total shrank (re-detection with different values, or deleted detections).
                # Re-anchor so future detections accumulate correctly.
                baseline = cur_f
            value = max(cur_f - baseline, prev, 0.0)
            conn.execute(
                text(
                    """
                    INSERT INTO ha_energy_hwm (appliance_id, baseline, kwh)
                    VALUES (:id, :baseline, :kwh)
                    ON CONFLICT (appliance_id) DO UPDATE SET baseline = EXCLUDED.baseline, kwh = EXCLUDED.kwh
                    """
                ),
                {"id": appliance_id, "baseline": baseline, "kwh": value},
            )
        return round(value, 3)

    def reset_energy(self, appliance_id: int):
        """Reset the energy sensor to 0: baseline := current SUM(detections),
        high-water-mark := 0. Detections are kept untouched."""
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
            conn.execute(
                text(
                    """
                    INSERT INTO ha_energy_hwm (appliance_id, baseline, kwh)
                    VALUES (:id, :baseline, 0)
                    ON CONFLICT (appliance_id) DO UPDATE SET baseline = EXCLUDED.baseline, kwh = 0
                    """
                ),
                {"id": appliance_id, "baseline": float(cur)},
            )
        return float(cur)

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

    def get_new_detections(self, appliance_id: int, since_id: int) -> list[dict]:
        """Detections with id > since_id, ordered chronologically."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, start_time, end_time FROM nilm_detections
                    WHERE appliance_id = :id AND id > :since_id
                    ORDER BY id
                    """
                ),
                {"id": appliance_id, "since_id": since_id},
            ).fetchall()

        def _utc(dt):
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

        return [{"id": r[0], "start": _utc(r[1]), "end": _utc(r[2])} for r in rows]

    def get_detections_in_hour(
        self, appliance_id: int, h_start: datetime, h_end: datetime
    ) -> list[tuple[datetime, datetime]]:
        """All detections overlapping [h_start, h_end) for computing hourly fraction."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT start_time, end_time FROM nilm_detections
                    WHERE appliance_id = :id
                      AND start_time < :h_end
                      AND end_time   > :h_start
                    """
                ),
                {"id": appliance_id, "h_start": h_start, "h_end": h_end},
            ).fetchall()

        def _utc(dt):
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

        return [(_utc(r[0]), _utc(r[1])) for r in rows]

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
