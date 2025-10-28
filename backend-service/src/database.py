"""TimescaleDB database management."""

from datetime import datetime
import json
import logging
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .config import settings

logger = logging.getLogger(__name__)


def format_datetime(dt: datetime | None) -> str | None:
    """
    Formats a datetime to ISO string.

    Args:
        dt: Datetime to format (with timezone)

    Returns:
        ISO string with timezone or None
    """
    if dt is None:
        return None
    return dt.isoformat()


class DatabaseManager:
    """TimescaleDB connection manager."""

    def __init__(self):
        """Initializes the TimescaleDB connection."""
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
        """Retrieves the latest consumption value."""
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
                    "time": format_datetime(result[0]),
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
            query = text("""
                SELECT
                    time,
                    papp as avg_papp,
                    papp as max_papp,
                    papp as min_papp,
                    temperature as avg_temperature
                FROM linky_realtime
                WHERE time >= :start_time AND time <= :end_time
                ORDER BY time ASC
            """)
        else:
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
            if interval in ("raw", "none"):
                result = conn.execute(
                    query,
                    {
                        "start_time": start_time,
                        "end_time": end_time,
                    },
                )
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
                    "avg_temperature": float(row[4]) if row[4] is not None else None,
                }
                for row in result
            ]

    def get_detected_appliances(
        self, start_time: datetime | None = None, end_time: datetime | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieves appliances detected by NILM-CNN.

        Args:
            start_time: Optional start date filter
            end_time: Optional end date filter

        Returns:
            List of detections with appliance information
        """
        query = text("""
            SELECT
                cd.id AS detection_id,
                cd.appliance_id,
                ca.name AS appliance_name,
                ca.description AS appliance_description,
                cd.start_time AS detection_start,
                cd.end_time AS detection_end,
                cd.avg_power,
                cd.energy_consumed,
                cd.confidence_score,
                cd.prediction_class,
                cd.features,
                cd.created_at AS detection_created_at,
                cd.user_validated,
                cd.is_correct,
                cd.validated_at
            FROM cnn_detections cd
            JOIN cnn_appliances ca ON cd.appliance_id = ca.id
            WHERE (:start_time IS NULL OR cd.start_time >= :start_time)
              AND (:end_time IS NULL OR cd.end_time <= :end_time)
            ORDER BY cd.start_time DESC
        """)

        with self.engine.connect() as conn:
            result = conn.execute(
                query, {"start_time": start_time, "end_time": end_time}
            )
            detections = []
            for row in result:
                m = row._mapping
                det = {
                    "id": m["detection_id"],
                    "appliance_id": m["appliance_id"],
                    "name": m["appliance_name"],
                    "description": m["appliance_description"],
                    "start_time": format_datetime(m["detection_start"]),
                    "end_time": format_datetime(m["detection_end"]),
                    "avg_power": float(m["avg_power"]) if m["avg_power"] is not None else None,
                    "energy_consumed": float(m["energy_consumed"]) if m["energy_consumed"] is not None else None,
                    "confidence_score": float(m["confidence_score"]) if m["confidence_score"] is not None else None,
                    "prediction_class": int(m["prediction_class"]) if m["prediction_class"] is not None else None,
                    "created_at": format_datetime(m["detection_created_at"]),
                    "user_validated": m["user_validated"],
                    "is_correct": m["is_correct"],
                    "validated_at": format_datetime(m["validated_at"]),
                }
                # Exposer les features JSON
                if "features" in m and m["features"] is not None:
                    feat = m["features"]
                    if isinstance(feat, str):
                        try:
                            feat = json.loads(feat)
                        except Exception:
                            pass
                    det["features"] = feat
                detections.append(det)

            return detections

    def get_all_appliances(self) -> list[dict[str, Any]]:
        """Retrieves the list of all known appliances with CNN stats computed on-the-fly."""
        query = text("""
            SELECT
                ca.id,
                ca.name,
                ca.description,
                ca.created_at,
                ca.updated_at,
                -- Statistiques calculées depuis les signatures
                AVG(cs.avg_power) as avg_power,
                STDDEV(cs.avg_power) as power_std,
                AVG(EXTRACT(EPOCH FROM (cs.end_time - cs.start_time))) as avg_duration,
                COUNT(DISTINCT cs.id) as num_signatures,
                MAX(cs.start_time) as last_signature_start,
                MAX(cs.end_time) as last_signature_end,
                COUNT(DISTINCT cd.id) as detection_count
            FROM cnn_appliances ca
            LEFT JOIN cnn_signatures cs ON ca.id = cs.appliance_id
            LEFT JOIN cnn_detections cd ON ca.id = cd.appliance_id
            GROUP BY ca.id, ca.name, ca.description, ca.created_at, ca.updated_at
            ORDER BY ca.name ASC
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query)
            appliances_list = []
            for row in result:
                appliance = {
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "created_at": format_datetime(row[3]),
                    "updated_at": format_datetime(row[4]),
                    "avg_power": float(row[5]) if row[5] is not None else None,
                    "power_std": float(row[6]) if row[6] is not None else None,
                    "avg_duration": float(row[7]) if row[7] is not None else None,
                    "num_signatures": int(row[8]) if row[8] is not None else 0,
                    "last_signature_start": format_datetime(row[9]),
                    "last_signature_end": format_datetime(row[10]),
                    "signature_count": int(row[8]) if row[8] is not None else 0,  # Même que num_signatures
                    "detection_count": int(row[11]) if row[11] is not None else 0,
                }
                
                appliances_list.append(appliance)
            
            return appliances_list

    def get_appliance_signatures(
        self, appliance_id: int
    ) -> list[dict[str, Any]]:
        """
        Retrieves all signatures for a specific appliance.

        Args:
            appliance_id: Appliance ID

        Returns:
            List of signatures with their details
        """
        query = text("""
            SELECT
                cs.id,
                cs.appliance_id,
                cs.start_time,
                cs.end_time,
                cs.avg_power,
                cs.power_std,
                cs.energy_consumed,
                cs.created_at,
                EXTRACT(EPOCH FROM (cs.end_time - cs.start_time))
                    as duration_seconds
            FROM cnn_signatures cs
            WHERE cs.appliance_id = :appliance_id
            ORDER BY cs.start_time DESC
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query, {"appliance_id": appliance_id})
            signatures_list = []
            for row in result:
                signature = {
                    "id": row[0],
                    "appliance_id": row[1],
                    "start_time": format_datetime(row[2]),
                    "end_time": format_datetime(row[3]),
                    "avg_power": (
                        float(row[4]) if row[4] is not None else None
                    ),
                    "power_std": (
                        float(row[5]) if row[5] is not None else None
                    ),
                    "energy_consumed": (
                        float(row[6]) if row[6] is not None else None
                    ),
                    "created_at": format_datetime(row[7]),
                    "duration_seconds": (
                        float(row[8]) if row[8] is not None else None
                    ),
                }
                signatures_list.append(signature)
            
            return signatures_list

    def update_appliance(
        self,
        appliance_id: int,
        name: str | None = None,
        description: str | None = None
    ) -> dict[str, Any] | None:
        """
        Updates the name and/or description of an appliance.

        Args:
            appliance_id: Appliance ID
            name: New name (optional)
            description: New description (optional)

        Returns:
            Updated appliance or None if not found
        """
        # Dynamically build the UPDATE query
        set_clauses = []
        params = {"appliance_id": appliance_id}
        
        if name is not None:
            set_clauses.append("name = :name")
            params["name"] = name
        
        if description is not None:
            set_clauses.append("description = :description")
            params["description"] = description
        
        if not set_clauses:
            # Rien à mettre à jour, récupérer l'appareil actuel
            select_query = text("""
                SELECT id, name, description, created_at, updated_at
                FROM cnn_appliances
                WHERE id = :appliance_id
            """)
            with self.engine.connect() as conn:
                result = conn.execute(select_query, params).fetchone()
                if result:
                    return {
                        "id": result[0],
                        "name": result[1],
                        "description": result[2],
                        "created_at": format_datetime(result[3]),
                        "updated_at": format_datetime(result[4]),
                    }
                return None
        
        set_clauses.append("updated_at = NOW()")
        update_query = text(f"""
            UPDATE cnn_appliances
            SET {", ".join(set_clauses)}
            WHERE id = :appliance_id
            RETURNING id, name, description, created_at, updated_at
        """)

        with self.engine.connect() as conn:
            result = conn.execute(update_query, params).fetchone()
            
            if result:
                conn.commit()
                return {
                    "id": result[0],
                    "name": result[1],
                    "description": result[2],
                    "created_at": format_datetime(result[3]),
                    "updated_at": format_datetime(result[4]),
                }
            return None

    def delete_appliance(self, appliance_id: int) -> dict[str, int] | None:
        """
        Deletes an appliance and all its associated data.

        Args:
            appliance_id: ID of the appliance to delete

        Returns:
            Dictionary with the number of deleted signatures and detections
        """
        # First check that the appliance exists
        check_query = text("""
            SELECT id FROM cnn_appliances WHERE id = :appliance_id
        """)

        with self.engine.connect() as conn:
            exists = conn.execute(
                check_query,
                {"appliance_id": appliance_id}
            ).fetchone()
            
            if not exists:
                return None

            # Compter les éléments à supprimer
            count_signatures_query = text("""
                SELECT COUNT(*) FROM cnn_signatures WHERE appliance_id = :appliance_id
            """)
            count_detections_query = text("""
                SELECT COUNT(*) FROM cnn_detections WHERE appliance_id = :appliance_id
            """)

            signatures_count = conn.execute(
                count_signatures_query,
                {"appliance_id": appliance_id}
            ).scalar()
            
            detections_count = conn.execute(
                count_detections_query,
                {"appliance_id": appliance_id}
            ).scalar()

            # Supprimer dans l'ordre (FK constraints)
            delete_detections_query = text("""
                DELETE FROM cnn_detections WHERE appliance_id = :appliance_id
            """)
            delete_signatures_query = text("""
                DELETE FROM cnn_signatures WHERE appliance_id = :appliance_id
            """)
            delete_appliance_query = text("""
                DELETE FROM cnn_appliances WHERE id = :appliance_id
            """)

            conn.execute(delete_detections_query, {"appliance_id": appliance_id})
            conn.execute(delete_signatures_query, {"appliance_id": appliance_id})
            conn.execute(delete_appliance_query, {"appliance_id": appliance_id})
            
            conn.commit()

            return {
                "signatures_deleted": signatures_count or 0,
                "detections_deleted": detections_count or 0,
            }

    def _get_average_consumption(self) -> float | None:
        """Récupère la puissance moyenne des dernières 48h."""
        query = text("""
            SELECT AVG(papp)
            FROM linky_realtime
            WHERE time >= NOW() - INTERVAL '48 hours'
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query).fetchone()
            if result and result[0] is not None:
                return float(result[0])
            return None

    def get_cnn_models_paginated(
        self, page: int = 1, per_page: int = 10
    ) -> dict[str, Any]:
        """
        Retrieves CNN models with pagination.

        Args:
            page: Page number (starts at 1)
            per_page: Number of models per page

        Returns:
            Dictionary with total, total_pages and list of models
        """
        # Calculate the offset
        offset = (page - 1) * per_page

        # Requête pour le total
        count_query = text("""
            SELECT COUNT(*) FROM cnn_models
        """)

        # Requête pour les modèles paginés
        query = text("""
            SELECT
                id,
                version,
                model_type,
                architecture,
                training_date,
                num_signatures,
                num_classes,
                metrics,
                model_path,
                model_status,
                training_duration_seconds
            FROM cnn_models
            ORDER BY 
                CASE model_status 
                    WHEN 'current' THEN 1 
                    WHEN 'backup' THEN 2 
                    ELSE 3 
                END,
                training_date DESC
            LIMIT :limit OFFSET :offset
        """)

        with self.engine.connect() as conn:
            # Récupérer le total
            total = conn.execute(count_query).scalar() or 0
            
            # Calculer le nombre total de pages
            total_pages = (
                (total + per_page - 1) // per_page if total > 0 else 0
            )

            # Récupérer les modèles
            result = conn.execute(
                query,
                {"limit": per_page, "offset": offset}
            ).fetchall()

            models = []
            for row in result:
                models.append({
                    "id": row[0],
                    "version": row[1],
                    "model_type": row[2],
                    "architecture": row[3],
                    "training_date": format_datetime(row[4]),
                    "num_signatures": row[5],
                    "num_classes": row[6],
                    "metrics": row[7],
                    "model_path": row[8],
                    "model_status": row[9],
                    "training_duration_seconds": row[10],
                })

            return {
                "total": total,
                "total_pages": total_pages,
                "models": models,
            }

    def delete_cnn_model(self, model_id: int) -> dict[str, Any]:
        """
        Deletes a CNN model from the database and filesystem.

        If the 'current' model is deleted, the 'backup' model is automatically
        promoted to 'current' to ensure there's always an active model.

        Args:
            model_id: ID of the model to delete

        Returns:
            Dictionary with deletion status

        Raises:
            ValueError: If the model doesn't exist
        """
        # Check that the model exists
        check_query = text("""
            SELECT id, version, model_status, model_path
            FROM cnn_models
            WHERE id = :model_id
        """)

        with self.engine.connect() as conn:
            result = conn.execute(
                check_query, {"model_id": model_id}
            ).fetchone()

            if not result:
                raise ValueError(f"Modèle {model_id} non trouvé")

            model_id_db, version, model_status, model_path = result

            # Supprimer d'abord le modèle de la base de données
            delete_query = text("""
                DELETE FROM cnn_models
                WHERE id = :model_id
            """)

            conn.execute(delete_query, {"model_id": model_id})

            # Si on vient de supprimer le modèle 'current', promouvoir 'backup' → 'current'
            if model_status == 'current':
                # Vérifier s'il existe un backup
                backup_query = text("""
                    SELECT id FROM cnn_models
                    WHERE model_status = 'backup'
                    LIMIT 1
                """)
                backup_result = conn.execute(backup_query).fetchone()

                if backup_result:
                    # Promouvoir backup → current
                    promote_query = text("""
                        UPDATE cnn_models
                        SET model_status = 'current'
                        WHERE model_status = 'backup'
                    """)
                    conn.execute(promote_query)
                    logger.info(
                        "✅ Modèle backup promu en current après "
                        "suppression du modèle actif"
                    )

            conn.commit()

            return {
                "id": model_id_db,
                "version": version,
                "model_status": model_status,
                "model_path": model_path,
                "deleted": True,
            }

    def delete_detection(self, detection_id: int) -> dict[str, Any] | None:
        """
        Deletes a specific detection from the database.

        Args:
            detection_id: ID of the detection to delete

        Returns:
            Dictionary with deleted detection information
            or None if the detection doesn't exist
        """
        # Check that the detection exists and retrieve its information
        check_query = text("""
            SELECT
                cd.id,
                cd.appliance_id,
                ca.name,
                cd.start_time,
                cd.end_time
            FROM cnn_detections cd
            JOIN cnn_appliances ca ON cd.appliance_id = ca.id
            WHERE cd.id = :detection_id
        """)

        with self.engine.connect() as conn:
            result = conn.execute(
                check_query,
                {"detection_id": detection_id}
            ).fetchone()

            if not result:
                return None

            detection_info = {
                "id": result[0],
                "appliance_id": result[1],
                "appliance_name": result[2],
                "start_time": format_datetime(result[3]),
                "end_time": format_datetime(result[4]),
            }

            # Supprimer la détection
            delete_query = text("""
                DELETE FROM cnn_detections
                WHERE id = :detection_id
            """)

            conn.execute(delete_query, {"detection_id": detection_id})
            conn.commit()

            return detection_info

    def delete_all_detections(self) -> dict[str, Any]:
        """
        Deletes all detections from the database.

        Returns:
            Dictionary with the number of deleted detections
        """
        with self.engine.connect() as conn:
            # Compter d'abord le nombre de détections
            count_query = text("""
                SELECT COUNT(*) FROM cnn_detections
            """)
            count = conn.execute(count_query).scalar() or 0

            # Supprimer toutes les détections
            delete_query = text("""
                DELETE FROM cnn_detections
            """)
            conn.execute(delete_query)
            conn.commit()

            logger.info(f"🗑️  {count} détection(s) supprimée(s)")

            return {
                "deleted_count": count,
                "status": "success",
            }

    def validate_detection(
        self, detection_id: int, is_correct: bool
    ) -> dict[str, Any] | None:
        """
        Marks a detection as validated by the user.

        Args:
            detection_id: ID of the detection to validate
            is_correct: True if correct, False if incorrect

        Returns:
            Dictionary with validated detection information
            or None if the detection doesn't exist
        """
        # Check that the detection exists and retrieve its information
        check_query = text("""
            SELECT
                cd.id,
                cd.appliance_id,
                ca.name,
                cd.start_time,
                cd.end_time,
                cd.confidence_score,
                cd.avg_power,
                cd.energy_consumed
            FROM cnn_detections cd
            JOIN cnn_appliances ca ON cd.appliance_id = ca.id
            WHERE cd.id = :detection_id
        """)

        with self.engine.connect() as conn:
            result = conn.execute(
                check_query,
                {"detection_id": detection_id}
            ).fetchone()

            if not result:
                return None

            detection_info = {
                "id": result[0],
                "appliance_id": result[1],
                "appliance_name": result[2],
                "start_time": format_datetime(result[3]),
                "end_time": format_datetime(result[4]),
                "confidence_score": (
                    float(result[5]) if result[5] is not None else None
                ),
                "avg_power": float(result[6]) if result[6] is not None else None,
                "energy_consumed": (
                    float(result[7]) if result[7] is not None else None
                ),
                "user_validated": True,
                "is_correct": is_correct,
            }

            # Si la détection est correcte, la marquer comme validée
            if is_correct:
                # Créer une signature positive à partir de la détection validée
                # Vérifier qu'une signature similaire n'existe pas déjà
                check_signature_query = text("""
                    SELECT COUNT(*) FROM cnn_signatures
                    WHERE appliance_id = :appliance_id
                      AND start_time = :start_time
                      AND end_time = :end_time
                      AND is_negative = FALSE
                """)

                existing = conn.execute(
                    check_signature_query,
                    {
                        "appliance_id": result[1],
                        "start_time": result[3],
                        "end_time": result[4]
                    }
                ).scalar()

                if existing == 0:
                    # Créer la signature positive avec les données de la détection
                    create_signature_query = text("""
                        INSERT INTO cnn_signatures
                        (appliance_id, start_time, end_time, is_negative,
                         avg_power, energy_consumed, created_at)
                        VALUES
                        (:appliance_id, :start_time, :end_time, FALSE,
                         :avg_power, :energy_consumed, NOW())
                    """)

                    conn.execute(
                        create_signature_query,
                        {
                            "appliance_id": result[1],
                            "start_time": result[3],
                            "end_time": result[4],
                            "avg_power": result[6],
                            "energy_consumed": result[7]
                        }
                    )
                    logger.info(
                        f"Signature positive créée pour {result[2]} "
                        f"(détection {detection_id})"
                    )

                # Mettre à jour la détection avec les champs de validation
                update_query = text("""
                    UPDATE cnn_detections
                    SET user_validated = :user_validated,
                        is_correct = :is_correct,
                        validated_at = NOW()
                    WHERE id = :detection_id
                """)

                conn.execute(
                    update_query,
                    {
                        "detection_id": detection_id,
                        "user_validated": True,
                        "is_correct": True,
                    }
                )
            else:
                # Si la détection est incorrecte, créer une signature négative
                # puis supprimer la détection
                if result[5] is not None and result[5] >= 0.6:
                    # Vérifier qu'une signature négative similaire n'existe pas déjà
                    check_negative_query = text("""
                        SELECT COUNT(*) FROM cnn_signatures
                        WHERE appliance_id = :appliance_id
                          AND is_negative = TRUE
                          AND start_time = :start_time
                          AND end_time = :end_time
                    """)

                    existing = conn.execute(
                        check_negative_query,
                        {
                            "appliance_id": result[1],
                            "start_time": result[3],
                            "end_time": result[4]
                        }
                    ).scalar()

                    if existing == 0:
                        # Créer la signature négative avec les données de la détection
                        create_negative_query = text("""
                            INSERT INTO cnn_signatures
                            (appliance_id, start_time, end_time, is_negative,
                             avg_power, energy_consumed, created_at)
                            VALUES
                            (:appliance_id, :start_time, :end_time, TRUE,
                             :avg_power, :energy_consumed, NOW())
                        """)

                        conn.execute(
                            create_negative_query,
                            {
                                "appliance_id": result[1],
                                "start_time": result[3],
                                "end_time": result[4],
                                "avg_power": result[6],
                                "energy_consumed": result[7]
                            }
                        )
                        logger.info(
                            f"Signature négative créée pour {result[2]} "
                            f"(détection {detection_id})"
                        )

                # Supprimer la détection incorrecte
                delete_query = text("""
                    DELETE FROM cnn_detections
                    WHERE id = :detection_id
                """)
                conn.execute(delete_query, {"detection_id": detection_id})
                logger.info(f"Détection incorrecte supprimée: {detection_id}")

                detection_info["deleted"] = True

            conn.commit()

            return detection_info

    def delete_all_signatures(self) -> dict[str, int]:
        """
        Deletes all signatures from all appliances.

        Returns:
            Dictionary with the number of deleted signatures
        """
        count_query = text("""
            SELECT COUNT(*) FROM cnn_signatures
        """)

        delete_query = text("""
            DELETE FROM cnn_signatures
        """)

        with self.engine.connect() as conn:
            # Compter les signatures à supprimer
            signatures_count = conn.execute(count_query).scalar() or 0

            # Supprimer toutes les signatures
            conn.execute(delete_query)
            conn.commit()

            return {
                "signatures_deleted": signatures_count
            }

    def delete_signature(self, signature_id: int) -> dict[str, Any] | None:
        """
        Deletes a specific signature.

        Args:
            signature_id: ID of the signature to delete

        Returns:
            Deleted signature information or None if not found
        """
        # Retrieve information before deletion
        get_query = text("""
            SELECT
                s.id,
                s.appliance_id,
                a.name as appliance_name,
                s.start_time,
                s.end_time,
                s.avg_power,
                s.is_negative,
                s.created_at
            FROM cnn_signatures s
            JOIN cnn_appliances a ON s.appliance_id = a.id
            WHERE s.id = :signature_id
        """)

        delete_query = text("""
            DELETE FROM cnn_signatures
            WHERE id = :signature_id
        """)

        with self.engine.connect() as conn:
            # Récupérer les infos de la signature
            result = conn.execute(
                get_query,
                {"signature_id": signature_id}
            ).fetchone()

            if not result:
                return None

            # Convertir en dict
            signature_info = {
                "id": result[0],
                "appliance_id": result[1],
                "appliance_name": result[2],
                "start_time": format_datetime(result[3]),
                "end_time": format_datetime(result[4]),
                "avg_power": float(result[5]) if result[5] else None,
                "is_negative": result[6],
                "created_at": format_datetime(result[7]),
            }

            # Supprimer la signature
            conn.execute(delete_query, {"signature_id": signature_id})
            conn.commit()

            return signature_info

    def get_all_signatures_with_appliance(self) -> list[dict[str, Any]]:
        """
        Retrieves all signatures with associated appliance information.

        Returns:
            List of signatures with appliance_name, appliance_description,
            start_time, end_time, is_negative
        """
        query = text("""
            SELECT
                cs.id,
                ca.id as appliance_id,
                ca.name as appliance_name,
                ca.description as appliance_description,
                cs.start_time,
                cs.end_time,
                cs.avg_power,
                cs.energy_consumed,
                EXTRACT(EPOCH FROM (cs.end_time - cs.start_time)) as duration_seconds,
                cs.is_negative
            FROM cnn_signatures cs
            JOIN cnn_appliances ca ON cs.appliance_id = ca.id
            ORDER BY cs.start_time DESC
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query)
            return [
                {
                    "id": row[0],
                    "appliance_id": row[1],
                    "appliance_name": row[2],
                    "appliance_description": row[3] if row[3] else "",
                    "start_time": format_datetime(row[4]),
                    "end_time": format_datetime(row[5]),
                    "avg_power": float(row[6]) if row[6] is not None else None,
                    "energy_consumed": float(row[7]) if row[7] is not None else None,
                    "duration_seconds": float(row[8]) if row[8] is not None else None,
                    "is_negative": row[9] if row[9] is not None else False,
                }
                for row in result
            ]


# Instance globale du gestionnaire de base de données
db_manager = DatabaseManager()
