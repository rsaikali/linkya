"""
Gestion de la base de données TimescaleDB pour nilm-service
"""

import logging
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from .config import settings


logger = logging.getLogger(__name__)


class DatabaseManager:
    """Gestionnaire de connexion à la base de données TimescaleDB"""

    def __init__(self):
        """Initialise le gestionnaire de base de données"""
        self.engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=10)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.metadata = MetaData()

        # Définition des tables
        self._define_tables()

    def _define_tables(self):
        """Définit les tables pour le service NILM"""

        # Table des appliances
        self.nilm_appliances = Table(
            "nilm_appliances",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("name", String(255), nullable=False),
            Column("created_at", DateTime(timezone=True), default=datetime.utcnow),
            Column(
                "updated_at",
                DateTime(timezone=True),
                default=datetime.utcnow,
                onupdate=datetime.utcnow,
            ),
            Index("idx_nilm_appliances_name", "name"),
        )

        # Table des signatures de courbes (soumises par utilisateur)
        self.nilm_signatures = Table(
            "nilm_signatures",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column(
                "appliance_id",
                Integer,
                ForeignKey("nilm_appliances.id", ondelete="CASCADE"),
            ),
            Column("start_time", DateTime(timezone=True), nullable=False),
            Column("end_time", DateTime(timezone=True), nullable=False),
            # Power data points (stored as JSON)
            Column("power_data", JSON, nullable=True),
            # Format: {"start": "ISO8601", "rate_hz": 1.0, "values": [float, ...], "num_points": int}
            # Basic statistics (computed for fast queries)
            Column("avg_power", Float),
            Column("power_std", Float),
            Column("energy_consumed", Float),
            Column("num_points", Integer),
            # Morphological analysis (computed once, stored as JSON)
            Column("morphology_analysis", JSON, nullable=True),
            # Format: see MorphologyAnalyzer output structure
            Column("is_negative", Boolean, default=False, nullable=False),
            Column("created_at", DateTime(timezone=True), default=datetime.utcnow),
            Index("idx_nilm_signatures_appliance", "appliance_id"),
            Index("idx_nilm_signatures_time", "start_time", "end_time"),
        )

        # Table des détections d'appliances
        self.nilm_detections = Table(
            "nilm_detections",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column(
                "appliance_id",
                Integer,
                ForeignKey("nilm_appliances.id", ondelete="SET NULL"),
                nullable=True,
            ),
            Column(
                "signature_id",
                Integer,
                ForeignKey("nilm_signatures.id", ondelete="SET NULL"),
                nullable=True,
            ),
            Column("start_time", DateTime(timezone=True), nullable=False),
            Column("end_time", DateTime(timezone=True), nullable=False),
            Column("avg_power", Float),
            Column("energy_consumed", Float),  # Énergie désagrégée (Wh)
            Column("confidence_score", Float),  # Score de confiance [0-1]
            Column("prediction_class", Integer),  # Classe prédite
            Column("features", JSON),  # Features de la détection
            Column("created_at", DateTime(timezone=True), default=datetime.utcnow),
            # Champs de validation utilisateur pour apprentissage par feedback
            Column("user_validated", Boolean, default=None, nullable=True),  # NULL = pas encore validée
            Column("is_correct", Boolean, default=None, nullable=True),  # True = correcte, False = incorrecte
            Column("validated_at", DateTime(timezone=True), nullable=True),  # Timestamp de validation
            Index("idx_nilm_detections_appliance", "appliance_id"),
            Index("idx_nilm_detections_time", "start_time", "end_time"),
            Index("idx_nilm_detections_validation", "user_validated", "is_correct"),
        )

        # Table des modèles NILM (un seul modèle actif à la fois)
        self.nilm_models = Table(
            "nilm_models",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("model_name", String(255), unique=True, nullable=False),  # Format: linkya_model_<timestamp>
            Column("model_type", String(100), default="CNN1D"),
            Column("architecture", JSON),  # Architecture du modèle
            Column("training_date", DateTime(timezone=True), default=datetime.utcnow),
            Column("num_signatures", Integer),  # Nombre de signatures d'entraînement
            Column("num_classes", Integer),  # Nombre de classes
            Column("metrics", JSON),  # Métriques de performance (accuracy, loss, etc.)
            Column("model_path", String(500)),
            Column("training_duration_seconds", Integer),  # Durée d'entraînement (secondes)
            Index("idx_nilm_models_name", "model_name"),
        )

    @contextmanager
    def get_session(self):
        """Context manager pour obtenir une session de base de données"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Erreur de session: {e}")
            raise
        finally:
            session.close()

    def test_connection(self):
        """Teste la connexion à la base de données"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Connexion à TimescaleDB: OK")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Erreur de connexion à TimescaleDB: {e}")
            return False

    def init_tables(self):
        """Initialise les tables NILM dans TimescaleDB"""
        try:
            with self.engine.connect() as conn:
                # Créer les tables si elles n'existent pas
                self.metadata.create_all(self.engine)
                logger.info("Tables NILM créées avec succès")

                # Vérifier si les tables existent
                for table_name in [
                    "nilm_appliances",
                    "nilm_signatures",
                    "nilm_detections",
                    "nilm_models",
                ]:
                    result = conn.execute(text(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}')"))
                    exists = result.scalar()
                    status = "existe" if exists else "n'existe pas"
                    logger.info(f"Table {table_name}: {status}")

                conn.commit()

        except SQLAlchemyError as e:
            logger.error(f"Erreur lors de l'initialisation des tables: {e}")
            raise

    def get_consumption_data(self, start_time, end_time, resample_seconds=1):
        """
        Récupère les données de consommation depuis linky_realtime

        Args:
            start_time: Début de la période
            end_time: Fin de la période
            resample_seconds: Intervalle de rééchantillonnage (secondes)

        Returns:
            Liste de dictionnaires avec time et papp
        """
        try:
            with self.engine.connect() as conn:
                query = text(
                    """
                    SELECT
                        time_bucket(:interval, time) as bucket_time,
                        AVG(papp) as avg_papp
                    FROM linky_realtime
                    WHERE time >= :start_time AND time <= :end_time
                    GROUP BY bucket_time
                    ORDER BY bucket_time ASC
                """
                )

                result = conn.execute(
                    query,
                    {
                        "interval": f"{resample_seconds} seconds",
                        "start_time": start_time,
                        "end_time": end_time,
                    },
                )

                data = [{"time": row.bucket_time, "papp": float(row.avg_papp)} for row in result]

                logger.info(f"Récupéré {len(data)} points de consommation")
                return data

        except SQLAlchemyError as e:
            logger.error(f"Erreur lors de la récupération des données: {e}")
            return []

    def add_signature(self, appliance_id, start_time, end_time, is_negative=False):
        """
        Ajoute une signature de courbe soumise par l'utilisateur.
        Capture les data points et calcule l'analyse morphologique.

        Args:
            appliance_id: ID de l'appareil
            start_time: Début de la signature
            end_time: Fin de la signature
            is_negative: True si signature négative (faux positif)

        Returns:
            ID de la signature créée ou None si erreur
        """
        try:
            # Vérifier les chevauchements
            with self.engine.connect() as conn:
                overlap_query = text(
                    """
                    SELECT id, start_time, end_time
                    FROM nilm_signatures
                    WHERE appliance_id = :appliance_id
                    AND (
                        (start_time <= :start_time AND end_time > :start_time)
                        OR (start_time < :end_time AND end_time >= :end_time)
                        OR (start_time >= :start_time
                            AND end_time <= :end_time)
                    )
                    LIMIT 1
                """
                )

                result = conn.execute(
                    overlap_query,
                    {
                        "appliance_id": appliance_id,
                        "start_time": start_time,
                        "end_time": end_time,
                    },
                )

                overlap = result.first()
                if overlap:
                    logger.error(f"Chevauchement détecté avec signature {overlap.id}")
                    raise ValueError(
                        f"Cette période chevauche une signature existante "
                        f"({overlap.start_time.strftime('%Y-%m-%d %H:%M')} - "
                        f"{overlap.end_time.strftime('%Y-%m-%d %H:%M')})"
                    )

            # Récupérer les données de consommation
            consumption_data = self.get_consumption_data(start_time, end_time)

            if not consumption_data:
                logger.error("Aucune donnée trouvée pour cette période")
                return None

            # Extract power values and compute stats
            import json

            import numpy as np

            from .nilm.morphology import MorphologyAnalyzer

            power_values = np.array([d["papp"] for d in consumption_data])

            # Build compact power_data JSON
            power_data = {
                "start": start_time.isoformat(),
                "rate_hz": 1.0,
                "values": power_values.tolist(),
                "num_points": len(power_values),
            }

            # Compute basic statistics
            avg_power = float(np.mean(power_values))
            power_std = float(np.std(power_values))
            energy_consumed = float(np.sum(power_values) / 3600.0)
            num_points = len(power_values)

            # Compute morphological analysis for all signatures
            # For negative signatures, this helps the model learn what patterns to avoid
            morphology_analysis = None
            if len(power_values) >= 10:
                analyzer = MorphologyAnalyzer(sampling_rate_hz=1.0)
                morphology_analysis = analyzer.analyze(power_values, start_time)

            with self.get_session() as session:
                query = text(
                    """
                    INSERT INTO nilm_signatures
                    (appliance_id, start_time, end_time, power_data,
                     avg_power, power_std, energy_consumed, num_points,
                     morphology_analysis, is_negative, created_at)
                    VALUES (
                        :appliance_id, :start_time, :end_time, :power_data,
                        :avg_power, :power_std, :energy_consumed, :num_points,
                        :morphology_analysis, :is_negative, NOW()
                    )
                    RETURNING id
                """
                )

                result = session.execute(
                    query,
                    {
                        "appliance_id": appliance_id,
                        "start_time": start_time,
                        "end_time": end_time,
                        "power_data": json.dumps(power_data),
                        "avg_power": avg_power,
                        "power_std": power_std,
                        "energy_consumed": energy_consumed,
                        "num_points": num_points,
                        "morphology_analysis": (json.dumps(morphology_analysis) if morphology_analysis else None),
                        "is_negative": is_negative,
                    },
                )

                signature_id = result.scalar()

                logger.info(
                    f"Signature {signature_id} créée: "
                    f"{num_points} points, {avg_power:.1f}W avg, "
                    f"morphology={'computed' if morphology_analysis else 'skipped'}"
                )
                return signature_id

        except SQLAlchemyError as e:
            logger.error(f"Erreur lors de l'ajout de la signature: {e}")
            return None

    def get_all_signatures(self):
        """
        Récupère toutes les signatures pour l'entraînement
        Note: raw_data est récupéré à la volée depuis linky_realtime

        Returns:
            Liste de signatures avec leurs données (raw_data récupéré dynamiquement)
        """
        try:
            with self.engine.connect() as conn:
                query_text = """
                    SELECT
                        s.id, s.appliance_id, s.start_time, s.end_time,
                        a.name as appliance_name
                    FROM nilm_signatures s
                    JOIN nilm_appliances a ON s.appliance_id = a.id
                    ORDER BY s.created_at DESC
                """

                result = conn.execute(text(query_text))

                signatures = []
                for row in result:
                    # Récupérer les données brutes depuis linky_realtime
                    raw_data = self.get_consumption_data(row.start_time, row.end_time)

                    # Calculer les statistiques à la volée
                    avg_power = None
                    power_std = None
                    energy_consumed = None
                    if raw_data:
                        power_values = [d["papp"] for d in raw_data]
                        if power_values:
                            avg_power = sum(power_values) / len(power_values)
                            power_std = (sum((p - avg_power) ** 2 for p in power_values) / len(power_values)) ** 0.5
                            duration_hours = (row.end_time - row.start_time).total_seconds() / 3600
                            energy_consumed = avg_power * duration_hours

                    sig = {
                        "id": row.id,
                        "appliance_id": row.appliance_id,
                        "appliance_name": row.appliance_name,
                        "start_time": row.start_time,
                        "end_time": row.end_time,
                        "avg_power": avg_power,
                        "power_std": power_std,
                        "energy_consumed": energy_consumed,
                        "raw_data": raw_data,
                    }

                    signatures.append(sig)

                logger.info(f"Récupéré {len(signatures)} signatures")
                return signatures

        except SQLAlchemyError as e:
            logger.error(f"Erreur lors de la récupération des signatures: {e}")
            return []


# Instance globale du gestionnaire de base de données
db_manager = DatabaseManager()
