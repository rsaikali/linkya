"""Consumption data repository."""

from sqlalchemy import text

from .base import DatabaseBase, format_datetime


class ConsumptionRepository(DatabaseBase):
    """Repository for consumption data operations."""

    def get_latest_consumption(self):
        """Retrieves the latest consumption value."""
        query = text(
            """
            SELECT time, papp, hchp, hchc, temperature, libelle_tarif
            FROM linky_realtime
            ORDER BY time DESC
            LIMIT 1
        """
        )

        with self.engine.connect() as conn:
            result = conn.execute(query).fetchone()
            if result:
                return {
                    "time": format_datetime(result[0]),
                    "papp": result[1],
                    "hchp": result[2],
                    "hchc": result[3],
                    "temperature": result[4],
                    "libelle_tarif": result[5],
                }
            return None

    def get_consumption_time_range(self):
        """
        Get the min and max timestamps from linky_realtime table.

        Returns:
            Dictionary with min_time and max_time, or None if no data
        """
        query = text(
            """
            SELECT MIN(time) as min_time, MAX(time) as max_time
            FROM linky_realtime
        """
        )

        with self.engine.connect() as conn:
            result = conn.execute(query).fetchone()
            if result and result[0] and result[1]:
                return {"min_time": result[0], "max_time": result[1]}
            return None

    def get_consumption_history(self, start_time, end_time, interval="5 minutes"):
        """
        Retrieves consumption history over a period.

        Args:
            start_time: Start date
            end_time: End date
            interval: Aggregation interval (e.g., '5 minutes', '1 hour', 'raw' for raw data)

        Returns:
            List of aggregated or raw consumption points
        """
        # If interval is "raw" or "none", return raw data without aggregation
        if interval in ("raw", "none"):
            query = text(
                """
                SELECT
                    time,
                    papp as avg_papp,
                    papp as max_papp,
                    papp as min_papp,
                    temperature as avg_temperature
                FROM linky_realtime
                WHERE time >= :start_time AND time <= :end_time
                ORDER BY time ASC
            """
            )
        else:
            query = text(
                """
                SELECT
                    time_bucket(:interval, time) AS bucket,
                    AVG(papp) as avg_papp,
                    MAX(papp) as max_papp,
                    MIN(papp) as min_papp,
                    AVG(temperature) as avg_temperature
                FROM linky_realtime
                WHERE time >= :start_time AND time <= :end_time
                GROUP BY bucket
                ORDER BY bucket ASC
            """
            )

        with self.engine.connect() as conn:
            if interval in ("raw", "none"):
                result = conn.execute(query, {"start_time": start_time, "end_time": end_time})
            else:
                result = conn.execute(
                    query,
                    {
                        "interval": interval,
                        "start_time": start_time,
                        "end_time": end_time,
                    },
                )
            return [
                {
                    "time": format_datetime(row[0]),
                    "avg_papp": float(row[1]) if row[1] is not None else None,
                    "max_papp": float(row[2]) if row[2] is not None else None,
                    "min_papp": float(row[3]) if row[3] is not None else None,
                    "avg_temperature": (float(row[4]) if row[4] is not None else None),
                }
                for row in result
            ]
