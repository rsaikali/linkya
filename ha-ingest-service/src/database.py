import json
from datetime import datetime, timezone

import redis
from loguru import logger
from sqlalchemy import create_engine, text

from .config import settings


class DatabaseManager:
    def __init__(self):
        self.engine = create_engine(settings.local_db_url, pool_pre_ping=True, pool_size=5)
        try:
            self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        except Exception as e:
            logger.warning(f"Redis init failed: {e}")
            self.redis_client = None

    def init_db(self):
        with self.engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
            conn.commit()

            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS linky_realtime (
                        time  TIMESTAMPTZ NOT NULL,
                        papp  SMALLINT    NOT NULL,
                        PRIMARY KEY (time)
                    );
                    """
                )
            )
            conn.commit()

            try:
                conn.execute(
                    text(
                        """
                        SELECT create_hypertable(
                            'linky_realtime', 'time',
                            if_not_exists => TRUE,
                            chunk_time_interval => INTERVAL '6 hours'
                        );
                        """
                    )
                )
                conn.commit()
            except Exception as e:
                logger.warning(f"Hypertable already exists: {e}")

            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_linky_realtime_time ON linky_realtime (time DESC);"
                )
            )
            conn.commit()
            logger.info("linky_realtime table ready")

    def get_last_timestamp(self):
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT MAX(time) FROM linky_realtime")).fetchone()
            return result[0] if result and result[0] else None

    def bulk_insert(self, rows: list[dict]):
        """Insert list of {time: datetime, papp: int} rows, upsert on conflict."""
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
        """Insert a single real-time point and publish to Redis for WebSocket."""
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

        if self.redis_client:
            try:
                self.redis_client.publish(
                    "consumption:updates",
                    json.dumps(
                        {
                            "event": "new_consumption",
                            "data": {"time": ts.isoformat(), "papp": papp},
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    ),
                )
            except Exception as e:
                logger.warning(f"Redis publish failed: {e}")


db_manager = DatabaseManager()
