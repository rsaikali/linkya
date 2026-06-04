"""Consumption data repository (plain PostgreSQL, no TimescaleDB)."""

from sqlalchemy import text

from .base import DatabaseBase, format_datetime


# Map interval label → bucket size in seconds (epoch-floor bucketing).
_INTERVAL_SECONDS = {
    "1 minute": 60,
    "5 minutes": 300,
    "10 minutes": 600,
    "15 minutes": 900,
    "1 hour": 3600,
}


class ConsumptionRepository(DatabaseBase):
    def get_latest_consumption(self):
        query = text("SELECT time, papp FROM linky_realtime ORDER BY time DESC LIMIT 1")
        with self.engine.connect() as conn:
            row = conn.execute(query).fetchone()
            return {"time": format_datetime(row[0]), "papp": row[1]} if row else None

    def get_consumption_time_range(self):
        query = text("SELECT MIN(time) AS min_time, MAX(time) AS max_time FROM linky_realtime")
        with self.engine.connect() as conn:
            row = conn.execute(query).fetchone()
            if row and row[0] and row[1]:
                return {"min_time": row[0], "max_time": row[1]}
            return None

    def get_consumption_history(self, start_time, end_time, interval="5 minutes"):
        """Aggregate papp over a period. 'raw' returns every sample.

        Bucketing uses epoch-floor (works on vanilla PostgreSQL, no TimescaleDB).
        """
        if interval in ("raw", "none"):
            query = text(
                """
                SELECT time, papp AS avg_papp, papp AS max_papp, papp AS min_papp
                FROM linky_realtime
                WHERE time >= :start_time AND time <= :end_time
                ORDER BY time ASC
                """
            )
            params = {"start_time": start_time, "end_time": end_time}
        else:
            secs = _INTERVAL_SECONDS.get(interval, 300)
            query = text(
                """
                SELECT
                    to_timestamp(floor(extract(epoch FROM time) / :secs) * :secs) AS bucket,
                    AVG(papp) AS avg_papp,
                    MAX(papp) AS max_papp,
                    MIN(papp) AS min_papp
                FROM linky_realtime
                WHERE time >= :start_time AND time <= :end_time
                GROUP BY bucket
                ORDER BY bucket ASC
                """
            )
            params = {"secs": secs, "start_time": start_time, "end_time": end_time}

        with self.engine.connect() as conn:
            result = conn.execute(query, params)
            return [
                {
                    "time": format_datetime(row[0]),
                    "avg_papp": float(row[1]) if row[1] is not None else None,
                    "max_papp": float(row[2]) if row[2] is not None else None,
                    "min_papp": float(row[3]) if row[3] is not None else None,
                }
                for row in result
            ]
