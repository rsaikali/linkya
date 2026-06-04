from datetime import datetime

from loguru import logger
from sqlalchemy import create_engine, text

from .config import settings


class DatabaseManager:
    def __init__(self):
        self.engine = create_engine(settings.local_db_url, pool_pre_ping=True, pool_size=5)

    def init_db(self):
        """Create linky_realtime on plain PostgreSQL (no TimescaleDB)."""
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS linky_realtime (
                        time  TIMESTAMPTZ NOT NULL,
                        papp  INTEGER     NOT NULL,
                        PRIMARY KEY (time)
                    );
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_linky_realtime_time ON linky_realtime (time DESC);")
            )
        logger.info("linky_realtime table ready")

    def get_last_timestamp(self):
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT MAX(time) FROM linky_realtime")).fetchone()
            return result[0] if result and result[0] else None

    def bulk_insert(self, rows: list[dict]):
        """Upsert a list of {time, papp} rows."""
        if not rows:
            return 0
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO linky_realtime (time, papp)
                    VALUES (:time, :papp)
                    ON CONFLICT (time) DO UPDATE SET papp = EXCLUDED.papp
                    """
                ),
                rows,
            )
        return len(rows)

    def insert_point(self, ts: datetime, papp: int):
        """Upsert a single real-time point."""
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO linky_realtime (time, papp)
                    VALUES (:time, :papp)
                    ON CONFLICT (time) DO UPDATE SET papp = EXCLUDED.papp
                    """
                ),
                {"time": ts, "papp": papp},
            )


db_manager = DatabaseManager()
