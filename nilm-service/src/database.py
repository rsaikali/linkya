"""
Database access for nilm-service (plain PostgreSQL)
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
    """Database connection manager"""

    def __init__(self):
        """Initialize the database manager"""
        self.engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=10)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.metadata = MetaData()

        # Define tables
        self._define_tables()

    def _define_tables(self):
        """Define the tables for the NILM service"""

        # Appliances table
        self.nilm_appliances = Table(
            "nilm_appliances",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("name", String(255), nullable=False),
            Column("ha_publish", Boolean, nullable=False, server_default="false"),
            Column("ha_entity_id", String(255), nullable=True),
            Column("created_at", DateTime(timezone=True), default=datetime.utcnow),
            Column("updated_at", DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow),
            Index("idx_nilm_appliances_name", "name"),
        )

        # Curve signatures table (user-submitted)
        self.nilm_signatures = Table(
            "nilm_signatures",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("appliance_id", Integer, ForeignKey("nilm_appliances.id", ondelete="CASCADE")),
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

        # Appliance detections table
        self.nilm_detections = Table(
            "nilm_detections",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("appliance_id", Integer, ForeignKey("nilm_appliances.id", ondelete="SET NULL"), nullable=True),
            Column("signature_id", Integer, ForeignKey("nilm_signatures.id", ondelete="SET NULL"), nullable=True),
            Column("start_time", DateTime(timezone=True), nullable=False),
            Column("end_time", DateTime(timezone=True), nullable=False),
            Column("avg_power", Float),
            Column("energy_consumed", Float),
            Column("confidence_score", Float),
            Column("prediction_class", Integer),
            Column("features", JSON),
            Column("model_name", String(255), nullable=True),  # model that produced this detection
            Column("created_at", DateTime(timezone=True), default=datetime.utcnow),
            Column("user_validated", Boolean, default=None, nullable=True),
            Column("is_correct", Boolean, default=None, nullable=True),
            Column("validated_at", DateTime(timezone=True), nullable=True),
            Index("idx_nilm_detections_appliance", "appliance_id"),
            Index("idx_nilm_detections_time", "start_time", "end_time"),
            Index("idx_nilm_detections_validation", "user_validated", "is_correct"),
        )

        self.nilm_models = Table(
            "nilm_models",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("model_name", String(255), unique=True, nullable=False),
            Column("model_type", String(100), default="CNN1D"),
            Column("architecture", JSON),
            Column("training_date", DateTime(timezone=True), default=datetime.utcnow),
            Column("num_signatures", Integer),
            Column("num_classes", Integer),
            Column("metrics", JSON),
            Column("model_path", String(500)),
            Column("training_duration_seconds", Integer),
            Column("is_champion", Boolean, nullable=False, server_default="false"),
            Index("idx_nilm_models_name", "model_name"),
        )

    @contextmanager
    def get_session(self):
        """Context manager to obtain a database session"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session error: {e}")
            raise
        finally:
            session.close()

    def test_connection(self):
        """Test the database connection"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connection: OK")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Database connection error: {e}")
            return False

    def init_tables(self):
        """Initialize the NILM tables"""
        try:
            with self.engine.connect() as conn:
                # Create tables if they don't exist
                self.metadata.create_all(self.engine)
                # Key/value meta (e.g. last_detect_run heartbeat)
                conn.execute(
                    text("CREATE TABLE IF NOT EXISTS nilm_meta (key TEXT PRIMARY KEY, value TEXT)")
                )
                conn.execute(
                    text("ALTER TABLE nilm_models ADD COLUMN IF NOT EXISTS is_champion BOOLEAN NOT NULL DEFAULT FALSE")
                )
                conn.execute(
                    text("ALTER TABLE nilm_detections ADD COLUMN IF NOT EXISTS model_name TEXT")
                )
                # Energy HWM removed: energy now goes to HA as external statistics.
                conn.execute(
                    text("ALTER TABLE nilm_appliances DROP COLUMN IF EXISTS energy_hwm_kwh")
                )
                conn.commit()
                logger.info("NILM tables created successfully")

                # Check that the tables exist
                for table_name in ["nilm_appliances", "nilm_signatures", "nilm_detections", "nilm_models"]:
                    result = conn.execute(text(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}')"))
                    exists = result.scalar()
                    status = "exists" if exists else "does not exist"
                    logger.info(f"Table {table_name}: {status}")

                conn.commit()

        except SQLAlchemyError as e:
            logger.error(f"Error initializing tables: {e}")
            raise

    def get_consumption_data(self, start_time, end_time, resample_seconds=1):
        """
        Fetch consumption data from linky_realtime

        Args:
            start_time: Period start
            end_time: Period end
            resample_seconds: Resampling interval (seconds)

        Returns:
            List of dicts with time and papp
        """
        try:
            with self.engine.connect() as conn:
                # Epoch-floor bucketing — plain PostgreSQL (no TimescaleDB).
                query = text(
                    """
                    SELECT
                        to_timestamp(floor(extract(epoch FROM time) / :secs) * :secs) AS bucket_time,
                        AVG(papp) AS avg_papp
                    FROM linky_realtime
                    WHERE time >= :start_time AND time <= :end_time
                    GROUP BY bucket_time
                    ORDER BY bucket_time ASC
                    """
                )

                result = conn.execute(query, {"secs": int(resample_seconds), "start_time": start_time, "end_time": end_time})

                data = [{"time": row.bucket_time, "papp": float(row.avg_papp)} for row in result]

                logger.info(f"Fetched {len(data)} consumption points")
                return data

        except SQLAlchemyError as e:
            logger.error(f"Error fetching data: {e}")
            return []

    def add_signature(self, appliance_id, start_time, end_time, is_negative=False):
        """
        Add a user-submitted curve signature.
        Captures the data points and computes the morphological analysis.

        Args:
            appliance_id: Appliance ID
            start_time: Signature start
            end_time: Signature end
            is_negative: True if a negative signature (false positive)

        Returns:
            ID of the created signature, or None on error
        """
        try:
            # Check for overlaps
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

                result = conn.execute(overlap_query, {"appliance_id": appliance_id, "start_time": start_time, "end_time": end_time})

                overlap = result.first()
                if overlap:
                    logger.error(f"Overlap detected with signature {overlap.id}")
                    raise ValueError(
                        f"This period overlaps an existing signature "
                        f"({overlap.start_time.strftime('%Y-%m-%d %H:%M')} - "
                        f"{overlap.end_time.strftime('%Y-%m-%d %H:%M')})"
                    )

            # Fetch consumption data
            consumption_data = self.get_consumption_data(start_time, end_time)

            if not consumption_data:
                logger.error("No data found for this period")
                return None

            # Extract power values and compute stats
            import json

            import numpy as np

            from .nilm.morphology import MorphologyAnalyzer

            power_values = np.array([d["papp"] for d in consumption_data])

            # Build compact power_data JSON
            power_data = {"start": start_time.isoformat(), "rate_hz": 1.0, "values": power_values.tolist(), "num_points": len(power_values)}

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
                    f"Signature {signature_id} created: "
                    f"{num_points} points, {avg_power:.1f}W avg, "
                    f"morphology={'computed' if morphology_analysis else 'skipped'}"
                )
                return signature_id

        except SQLAlchemyError as e:
            logger.error(f"Error adding signature: {e}")
            return None

    def get_all_signatures(self):
        """
        Fetch all signatures for training.
        Optimized to avoid the N+1 problem:
        1. Uses power_data (JSON) if available
        2. Batch-loads missing data if needed

        Returns:
            List of signatures with their data
        """
        try:
            with self.engine.connect() as conn:
                # Fetch all signatures
                query_text = """
                    SELECT
                        s.id, s.appliance_id, s.start_time, s.end_time,
                        s.power_data, s.avg_power, s.power_std, s.energy_consumed,
                        s.is_negative,
                        a.name as appliance_name
                    FROM nilm_signatures s
                    JOIN nilm_appliances a ON s.appliance_id = a.id
                    ORDER BY s.created_at DESC
                """

                result = conn.execute(text(query_text))
                signatures = []
                missing_data_sigs = []

                import json

                for row in result:
                    sig = {
                        "id": row.id,
                        "appliance_id": row.appliance_id,
                        "appliance_name": row.appliance_name,
                        "start_time": row.start_time,
                        "end_time": row.end_time,
                        "avg_power": row.avg_power,
                        "power_std": row.power_std,
                        "energy_consumed": row.energy_consumed,
                        "is_negative": row.is_negative,
                        "raw_data": None,
                    }

                    # Strategy 1: use stored power_data (fast)
                    if row.power_data:
                        try:
                            p_data = row.power_data if isinstance(row.power_data, dict) else json.loads(row.power_data)
                            values = p_data.get("values", [])
                            # Rebuild the format expected by the model [{"papp": x}, ...]
                            sig["raw_data"] = [{"papp": v} for v in values]
                        except Exception as e:
                            logger.warning(f"Error reading power_data for sig {row.id}: {e}")

                    if not sig["raw_data"]:
                        missing_data_sigs.append(sig)

                    signatures.append(sig)

                # Strategy 2: batch-load missing data (slow but optimized)
                if missing_data_sigs:
                    logger.info(f"Loading raw data for {len(missing_data_sigs)} signatures...")
                    # To avoid one giant query, we loop per-signature (N+1) —
                    # acceptable since it only affects old signatures without power_data
                    for sig in missing_data_sigs:
                        sig["raw_data"] = self.get_consumption_data(sig["start_time"], sig["end_time"])

                        # Auto-repair: save power_data for next time
                        if sig["raw_data"]:
                            try:
                                power_values = [d["papp"] for d in sig["raw_data"]]
                                power_data = {
                                    "start": sig["start_time"].isoformat(),
                                    "rate_hz": 1.0,
                                    "values": power_values,
                                    "num_points": len(power_values),
                                }
                                # Update DB (in a new transaction)
                                with self.get_session() as session:
                                    session.execute(
                                        text("UPDATE nilm_signatures SET power_data = :pd WHERE id = :id"),
                                        {"pd": json.dumps(power_data), "id": sig["id"]},
                                    )
                            except Exception as e:
                                logger.warning(f"Auto-repair failed for sig {sig['id']}: {e}")

                logger.info(f"Fetched {len(signatures)} signatures ({len(missing_data_sigs)} reloaded)")
                return signatures

        except SQLAlchemyError as e:
            logger.error(f"Error fetching signatures: {e}")
            return []

    def set_meta(self, key, value):
        """Upsert a key/value into nilm_meta (heartbeats, markers)."""
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO nilm_meta (key, value) VALUES (:k, :v)
                        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                        """
                    ),
                    {"k": key, "v": str(value)},
                )
        except SQLAlchemyError as e:
            logger.error(f"set_meta {key} failed: {e}")

    def count_positive_signatures(self):
        """Count of positive (non-negative) signatures across all appliances."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("SELECT COUNT(*) FROM nilm_signatures WHERE is_negative = FALSE")
                )
                return result.scalar() or 0
        except SQLAlchemyError as e:
            logger.error(f"Error in count_positive_signatures: {e}")
            return 0


# Global database manager instance
db_manager = DatabaseManager()
