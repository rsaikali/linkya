"""Gestion de la base de données TimescaleDB."""

from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .config import settings


class DatabaseManager:
    """Gestionnaire de connexion à TimescaleDB."""

    def __init__(self):
        """Initialise la connexion à TimescaleDB."""
        self.engine = create_engine(
            settings.local_db_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def get_latest_consumption(self) -> dict[str, Any] | None:
        """Récupère la dernière valeur de consommation."""
        query = text("""
            SELECT time, papp, hchp, hchc, temperature, libelle_tarif
            FROM linky_realtime
            ORDER BY time DESC
            LIMIT 1
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query).fetchone()
            if result:
                return {
                    "time": result[0].isoformat() if result[0] else None,
                    "papp": result[1],
                    "hchp": result[2],
                    "hchc": result[3],
                    "temperature": result[4],
                    "libelle_tarif": result[5],
                }
            return None

    def get_consumption_history(
        self, start_time: datetime, end_time: datetime, interval: str = "5 minutes"
    ) -> list[dict[str, Any]]:
        """
        Récupère l'historique de consommation sur une période.

        Args:
            start_time: Date de début
            end_time: Date de fin
            interval: Intervalle d'agrégation (ex: '5 minutes', '1 hour')

        Returns:
            Liste des points de consommation agrégés
        """
        query = text("""
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
        """)

        with self.engine.connect() as conn:
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
                    "time": row[0].isoformat() if row[0] else None,
                    "avg_papp": float(row[1]) if row[1] is not None else None,
                    "max_papp": float(row[2]) if row[2] is not None else None,
                    "min_papp": float(row[3]) if row[3] is not None else None,
                    "avg_temperature": float(row[4]) if row[4] is not None else None,
                }
                for row in result
            ]

    def get_detected_appliances(
        self, start_time: datetime | None = None, end_time: datetime | None = None
    ) -> list[dict[str, Any]]:
        """
        Récupère les appareils détectés par le NILM.

        Args:
            start_time: Filtre optionnel sur date de début
            end_time: Filtre optionnel sur date de fin

        Returns:
            Liste des détections avec informations sur les appareils
        """
        query = text("""
            SELECT
                de.id,
                de.appliance_id,
                a.name,
                a.description,
                de.start_time,
                de.end_time,
                de.avg_power,
                de.energy_consumed,
                de.confidence_score
            FROM detection_events de
            JOIN appliances a ON de.appliance_id = a.id
            WHERE (:start_time IS NULL OR de.start_time >= :start_time)
              AND (:end_time IS NULL OR de.end_time <= :end_time)
            ORDER BY de.start_time DESC
        """)

        with self.engine.connect() as conn:
            result = conn.execute(
                query, {"start_time": start_time, "end_time": end_time}
            )
            return [
                {
                    "id": row[0],
                    "appliance_id": row[1],
                    "name": row[2],
                    "description": row[3],
                    "start_time": row[4].isoformat() if row[4] else None,
                    "end_time": row[5].isoformat() if row[5] else None,
                    "avg_power": float(row[6]) if row[6] is not None else None,
                    "energy_consumed": float(row[7]) if row[7] is not None else None,
                    "confidence_score": float(row[8]) if row[8] is not None else None,
                }
                for row in result
            ]

    def get_all_appliances(self) -> list[dict[str, Any]]:
        """Récupère la liste de tous les appareils connus."""
        query = text("""
            SELECT
                id,
                name,
                description,
                is_validated,
                created_at,
                updated_at
            FROM appliances
            ORDER BY name ASC
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query)
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "is_validated": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                    "updated_at": row[5].isoformat() if row[5] else None,
                }
                for row in result
            ]


# Instance globale du gestionnaire de base de données
db_manager = DatabaseManager()
