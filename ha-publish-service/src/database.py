"""Read appliances, current state, and cumulative energy from TimescaleDB."""


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

    def get_cumulative_energy_kwh(self, appliance_id: int) -> float:
        """
        Total energy detected for this appliance since first detection.
        Cumulative, never-decreasing — suitable for HA total_increasing.
        """
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT COALESCE(SUM(energy_consumed), 0)
                    FROM nilm_detections
                    WHERE appliance_id = :id
                      AND energy_consumed IS NOT NULL
                    """
                ),
                {"id": appliance_id},
            ).fetchone()
        return round(float(row[0]) / 1000.0, 3) if row and row[0] else 0.0

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


repo = PublishRepository()
