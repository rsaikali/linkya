"""Detections repository."""

import json
import logging

from sqlalchemy import text

from .base import DatabaseBase, format_datetime


logger = logging.getLogger(__name__)


class DetectionRepository(DatabaseBase):
    """Repository for detection operations."""

    def get_detected_appliances(self, start_time=None, end_time=None):
        """
        Retrieves appliances detected by NILM-CNN.

        Args:
            start_time: Optional start date filter
            end_time: Optional end date filter

        Returns:
            List of detections with appliance information
        """
        query = text(
            """
            SELECT
                cd.id AS detection_id,
                cd.appliance_id,
                ca.name AS appliance_name,
                cd.start_time AS detection_start,
                cd.end_time AS detection_end,
                (
                    SELECT AVG(papp)
                    FROM linky_realtime
                    WHERE time >= cd.start_time AND time <= cd.end_time
                ) as avg_power,
                (
                    SELECT SUM(papp) / 3600.0
                    FROM linky_realtime
                    WHERE time >= cd.start_time AND time <= cd.end_time
                ) as energy_consumed,
                cd.confidence_score,
                cd.prediction_class,
                cd.features,
                cd.created_at AS detection_created_at,
                cd.user_validated,
                cd.is_correct,
                cd.validated_at
            FROM nilm_detections cd
            JOIN nilm_appliances ca ON cd.appliance_id = ca.id
            WHERE (:start_time IS NULL OR cd.start_time >= :start_time)
              AND (:end_time IS NULL OR cd.end_time <= :end_time)
              AND (cd.user_validated IS NULL
                   OR cd.user_validated = FALSE
                   OR cd.is_correct = TRUE)
            ORDER BY cd.start_time DESC
        """
        )

        with self.engine.connect() as conn:
            result = conn.execute(query, {"start_time": start_time, "end_time": end_time})
            detections = []
            for row in result:
                m = row._mapping
                det = {
                    "id": m["detection_id"],
                    "appliance_id": m["appliance_id"],
                    "name": m["appliance_name"],
                    "start_time": format_datetime(m["detection_start"]),
                    "end_time": format_datetime(m["detection_end"]),
                    "avg_power": (float(m["avg_power"]) if m["avg_power"] is not None else None),
                    "energy_consumed": (float(m["energy_consumed"]) if m["energy_consumed"] is not None else None),
                    "confidence_score": (float(m["confidence_score"]) if m["confidence_score"] is not None else None),
                    "prediction_class": (int(m["prediction_class"]) if m["prediction_class"] is not None else None),
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

    def delete_detection(self, detection_id):
        """
        Deletes a specific detection from the database.

        Args:
            detection_id: ID of the detection to delete

        Returns:
            Dictionary with deleted detection information
            or None if the detection doesn't exist
        """
        # Check that the detection exists and retrieve its information
        check_query = text(
            """
            SELECT
                cd.id,
                cd.appliance_id,
                ca.name,
                cd.start_time,
                cd.end_time
            FROM nilm_detections cd
            JOIN nilm_appliances ca ON cd.appliance_id = ca.id
            WHERE cd.id = :detection_id
        """
        )

        with self.engine.connect() as conn:
            result = conn.execute(check_query, {"detection_id": detection_id}).fetchone()

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
            delete_query = text(
                """
                DELETE FROM nilm_detections
                WHERE id = :detection_id
            """
            )

            conn.execute(delete_query, {"detection_id": detection_id})
            conn.commit()

            return detection_info

    def delete_all_detections(self):
        """
        Deletes all detections from the database.

        Returns:
            Dictionary with the number of deleted detections
        """
        with self.engine.connect() as conn:
            # Compter d'abord le nombre de détections
            count_query = text(
                """
                SELECT COUNT(*) FROM nilm_detections
            """
            )
            count = conn.execute(count_query).scalar() or 0

            # Supprimer toutes les détections
            delete_query = text(
                """
                DELETE FROM nilm_detections
            """
            )
            conn.execute(delete_query)
            conn.commit()

            logger.info(f"Deleted {count} detection(s)")

            return {"deleted_count": count, "status": "success"}

    def validate_detection(self, detection_id, is_correct):
        """
        Marks a detection as validated by the user.
        Creates a signature (positive or negative) via Celery task.

        Args:
            detection_id: ID of the detection to validate
            is_correct: True if correct, False if incorrect

        Returns:
            Dictionary with validated detection information
            or None if the detection doesn't exist
        """
        # Check that the detection exists and retrieve its information
        check_query = text(
            """
            SELECT
                cd.id,
                cd.appliance_id,
                ca.name,
                cd.start_time,
                cd.end_time,
                cd.confidence_score
            FROM nilm_detections cd
            JOIN nilm_appliances ca ON cd.appliance_id = ca.id
            WHERE cd.id = :detection_id
        """
        )

        with self.engine.connect() as conn:
            result = conn.execute(check_query, {"detection_id": detection_id}).fetchone()

            if not result:
                return None

            detection_info = {
                "id": result[0],
                "appliance_id": result[1],
                "appliance_name": result[2],
                "start_time": format_datetime(result[3]),
                "end_time": format_datetime(result[4]),
                "confidence_score": (float(result[5]) if result[5] is not None else None),
                "user_validated": True,
                "is_correct": is_correct,
            }

            appliance_name = result[2]
            start_time = result[3]
            end_time = result[4]

            # Check if signature already exists (to avoid duplicates)
            check_signature_query = text(
                """
                SELECT COUNT(*) FROM nilm_signatures
                WHERE appliance_id = :appliance_id
                  AND start_time = :start_time
                  AND end_time = :end_time
                  AND is_negative = :is_negative
            """
            )

            existing = conn.execute(
                check_signature_query, {"appliance_id": result[1], "start_time": start_time, "end_time": end_time, "is_negative": not is_correct}
            ).scalar()

            if existing == 0:
                # Send Celery task to create signature via nilm-service
                from ..config import get_celery_app

                celery_app = get_celery_app()

                signature_type = "positive" if is_correct else "negative"
                logger.info(f"Sending task to create {signature_type} signature " f"for {appliance_name} (detection {detection_id})")

                try:
                    task = celery_app.send_task(
                        "add_nilm_signature",
                        args=[appliance_name, start_time.isoformat(), end_time.isoformat(), not is_correct],
                        queue="nilm",
                        routing_key="nilm.add_nilm_signature",  # is_negative
                    )
                    logger.info(f"Signature creation task sent: {task.id} " f"({signature_type} for {appliance_name})")
                except Exception as e:
                    logger.error(f"Failed to send signature creation task: {e}", exc_info=True)
            else:
                signature_type = "positive" if is_correct else "negative"
                logger.info(f"Signature already exists: {signature_type} " f"for {appliance_name} at {start_time} - {end_time}")

            # Update detection as validated
            update_query = text(
                """
                UPDATE nilm_detections
                SET user_validated = :user_validated,
                    is_correct = :is_correct,
                    validated_at = NOW()
                WHERE id = :detection_id
            """
            )

            conn.execute(update_query, {"detection_id": detection_id, "user_validated": True, "is_correct": is_correct})

            logger.info(f"Detection {detection_id} marked as " f"{'correct' if is_correct else 'incorrect'}")

            conn.commit()

            return detection_info

    def reassign_detection(self, detection_id, correct_appliance_name):
        """
        Reassigns a detection to the correct appliance.
        Creates a positive signature for the correct appliance
        and marks the detection as incorrect to hide it from the list.

        Args:
            detection_id: ID of the detection to reassign
            correct_appliance_name: Name of the correct appliance

        Returns:
            Dictionary with reassignment information
            or None if the detection doesn't exist
        """
        from .appliances import ApplianceRepository

        # Check that the detection exists and retrieve its information
        check_query = text(
            """
            SELECT
                cd.id,
                cd.appliance_id,
                ca.name,
                cd.start_time,
                cd.end_time
            FROM nilm_detections cd
            JOIN nilm_appliances ca ON cd.appliance_id = ca.id
            WHERE cd.id = :detection_id
        """
        )

        with self.engine.connect() as conn:
            result = conn.execute(check_query, {"detection_id": detection_id}).fetchone()

            if not result:
                return None

            incorrect_appliance_name = result[2]
            start_time = result[3]
            end_time = result[4]

            # Get or create the correct appliance
            appliance_repo = ApplianceRepository()
            correct_appliance_id = appliance_repo.get_or_create_appliance(correct_appliance_name)

            # Check if positive signature already exists
            check_positive_query = text(
                """
                SELECT COUNT(*) FROM nilm_signatures
                WHERE appliance_id = :appliance_id
                  AND start_time = :start_time
                  AND end_time = :end_time
                  AND is_negative = FALSE
            """
            )

            existing_positive = conn.execute(
                check_positive_query, {"appliance_id": correct_appliance_id, "start_time": start_time, "end_time": end_time}
            ).scalar()

            if existing_positive == 0:
                # Send Celery task to create positive signature via nilm-service
                from ..config import get_celery_app

                celery_app = get_celery_app()

                logger.info(f"Sending task to create positive signature " f"for {correct_appliance_name} (detection {detection_id})")

                try:
                    task = celery_app.send_task(
                        "add_nilm_signature",
                        args=[
                            correct_appliance_name,
                            start_time.isoformat(),
                            end_time.isoformat(),
                            False,
                        ],  # is_negative = False for positive signature
                        queue="nilm",
                        routing_key="nilm.add_nilm_signature",
                    )
                    logger.info(f"Positive signature creation task sent: {task.id} " f"for {correct_appliance_name}")
                except Exception as e:
                    logger.error(f"Failed to send signature creation task: {e}", exc_info=True)
            else:
                logger.info(f"Positive signature already exists for {correct_appliance_name} " f"at {start_time} - {end_time}")

            # Mark detection as incorrect to hide it from the list
            update_query = text(
                """
                UPDATE nilm_detections
                SET user_validated = :user_validated,
                    is_correct = :is_correct,
                    validated_at = NOW()
                WHERE id = :detection_id
            """
            )

            conn.execute(update_query, {"detection_id": detection_id, "user_validated": True, "is_correct": False})
            logger.info(f"Detection {detection_id} reassigned from " f"{incorrect_appliance_name} to {correct_appliance_name}")

            conn.commit()

            return {
                "detection_id": detection_id,
                "incorrect_appliance": incorrect_appliance_name,
                "correct_appliance": correct_appliance_name,
                "start_time": format_datetime(start_time),
                "end_time": format_datetime(end_time),
            }
