import json
import logging
from datetime import datetime

import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .config import settings


logger = logging.getLogger(__name__)


class DatabaseManager:
    """Gestionnaire de connexions aux bases de données"""

    def __init__(self):
        # Connexion à la base distante (lecture seule)
        self.remote_engine = create_engine(
            settings.remote_db_url, pool_pre_ping=True, echo=False
        )

        # Connexion à la base locale (TimescaleDB)
        self.local_engine = create_engine(
            settings.local_db_url, pool_pre_ping=True, echo=False
        )

        self.LocalSession = sessionmaker(bind=self.local_engine)
        self.RemoteSession = sessionmaker(bind=self.remote_engine)

        # Redis client pour WebSocket real-time updates
        try:
            redis_url = settings.celery_broker_url
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            logger.info("✅ Redis client initialized for consumption updates")
        except Exception as e:
            logger.warning(f"⚠️ Redis client init failed: {e}")
            self.redis_client = None

    def init_local_db(self):
        """Initialise la base locale avec TimescaleDB"""
        with self.local_engine.connect() as conn:
            # Activation de l'extension TimescaleDB
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
            conn.commit()

            # Création de la table linky_realtime dans TimescaleDB
            conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS linky_realtime (
                    time TIMESTAMPTZ NOT NULL,
                    papp SMALLINT NOT NULL,
                    hchp INTEGER NOT NULL,
                    hchc INTEGER NOT NULL,
                    temperature DOUBLE PRECISION,
                    libelle_tarif VARCHAR(16),
                    PRIMARY KEY (time)
                );
            """
                )
            )
            conn.commit()

            # Conversion en hypertable TimescaleDB
            try:
                conn.execute(
                    text(
                        """
                    SELECT create_hypertable('linky_realtime', 'time',
                        if_not_exists => TRUE,
                        chunk_time_interval => INTERVAL '6 hours'
                    );
                """
                    )
                )
                conn.commit()
                logger.info("Hypertable créée avec succès")
            except Exception as e:
                logger.warning(f"L'hypertable existe déjà ou erreur: {e}")

            # Index pour optimiser les requêtes
            conn.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_linky_realtime_time
                ON linky_realtime (time DESC);
            """
                )
            )
            conn.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_linky_realtime_tarif
                ON linky_realtime (libelle_tarif, time DESC);
            """
                )
            )
            conn.commit()

    def get_remote_data(self, since=None, limit=None):
        """Récupère les données depuis la base distante MySQL"""
        with self.remote_engine.connect() as conn:
            query = f"SELECT * FROM {settings.remote_db_table}"

            if since:
                # Formatage de la date pour MySQL
                since_str = since.strftime("%Y-%m-%d %H:%M:%S")
                query += f" WHERE time > '{since_str}'"

            query += " ORDER BY time ASC"

            if limit:
                query += f" LIMIT {limit}"

            result = conn.execute(text(query))
            rows = []
            for row in result:
                # Conversion des noms de colonnes en minuscules pour PostgreSQL
                rows.append(
                    {
                        "time": row.time,
                        "papp": row.PAPP,
                        "hchp": row.HCHP,
                        "hchc": row.HCHC,
                        "temperature": row.temperature,
                        "libelle_tarif": row.libelle_tarif,
                    }
                )
            return rows

    def get_last_sync_timestamp(self):
        """Récupère le timestamp de la dernière synchronisation"""
        with self.local_engine.connect() as conn:
            result = conn.execute(
                text("SELECT MAX(time) as last_ts FROM linky_realtime")
            )
            row = result.fetchone()
            return row[0] if row and row[0] else None

    def bulk_insert_data(self, data):
        """Insère des données en masse dans la base locale"""
        if not data:
            return 0

        with self.local_engine.begin() as conn:
            inserted = 0
            latest_row = None
            for row in data:
                try:
                    conn.execute(
                        text(
                            """
                        INSERT INTO linky_realtime (time, papp, hchp, hchc, temperature, libelle_tarif)
                        VALUES (:time, :papp, :hchp, :hchc, :temperature, :libelle_tarif)
                        ON CONFLICT (time) DO UPDATE SET
                            papp = EXCLUDED.papp,
                            hchp = EXCLUDED.hchp,
                            hchc = EXCLUDED.hchc,
                            temperature = EXCLUDED.temperature,
                            libelle_tarif = EXCLUDED.libelle_tarif
                    """
                        ),
                        row,
                    )
                    inserted += 1
                    latest_row = row
                except Exception as e:
                    logger.error(f"Erreur insertion: {e}")

            # Publish latest consumption to Redis for WebSocket streaming
            if inserted > 0 and latest_row and self.redis_client:
                try:
                    message = json.dumps(
                        {
                            "event": "new_consumption",
                            "data": {
                                "time": latest_row["time"].isoformat(),
                                "papp": latest_row["papp"],
                                "hchp": latest_row["hchp"],
                                "hchc": latest_row["hchc"],
                                "temperature": latest_row["temperature"],
                                "libelle_tarif": latest_row["libelle_tarif"],
                            },
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )
                    self.redis_client.publish("consumption:updates", message)
                    logger.debug("Published consumption update to Redis")
                except Exception as e:
                    logger.error(f"Failed to publish to Redis: {e}")

            return inserted

    def get_data_stats(self):
        """Récupère des statistiques sur les données locales"""
        with self.local_engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT
                    COUNT(*) as total_rows,
                    MIN(time) as oldest,
                    MAX(time) as newest,
                    AVG(papp) as avg_power,
                    MAX(papp) as max_power,
                    MIN(papp) as min_power,
                    AVG(temperature) as avg_temp
                FROM linky_realtime
            """
                )
            )
            row = result.fetchone()

            if row:
                return {
                    "total_rows": row[0],
                    "oldest": row[1],
                    "newest": row[2],
                    "avg_power": round(row[3], 2) if row[3] else None,
                    "max_power": row[4],
                    "min_power": row[5],
                    "avg_temperature": round(row[6], 2) if row[6] else None,
                }
            return {}


# Instance globale
db_manager = DatabaseManager()
