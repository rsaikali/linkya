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

    def get_scorecard(self, appliance_name: str, window_days: int = 30) -> dict | None:
        """
        Per-appliance NILM scorecard over the last N days.
        Returns None if the appliance is unknown.
        """
        query = text(
            """
            WITH app AS (
                SELECT id, name FROM nilm_appliances WHERE name = :appliance_name
            ),
            det_stats AS (
                SELECT
                    COUNT(*)::int AS cycles,
                    COALESCE(SUM(d.energy_consumed) / 1000.0, 0.0) AS kwh,
                    AVG(d.confidence_score) AS confidence_avg
                FROM nilm_detections d
                WHERE d.appliance_id = (SELECT id FROM app)
                  AND d.start_time >= NOW() - make_interval(days => :window_days)
            ),
            total_consumption AS (
                SELECT COALESCE(SUM(papp) / 3600000.0, 0.0) AS total_kwh
                FROM linky_realtime
                WHERE time >= NOW() - make_interval(days => :window_days)
            ),
            sig_count AS (
                SELECT COUNT(*)::int AS cnt
                FROM nilm_signatures
                WHERE appliance_id = (SELECT id FROM app)
                  AND is_negative = FALSE
            )
            SELECT
                (SELECT name FROM app) AS appliance_name,
                (SELECT id FROM app) AS appliance_id,
                d.cycles,
                ROUND(d.kwh::numeric, 3) AS kwh,
                ROUND(d.confidence_avg::numeric, 3) AS confidence_avg,
                ROUND(t.total_kwh::numeric, 3) AS total_kwh,
                s.cnt AS signatures_count,
                (SELECT training_date FROM nilm_models ORDER BY training_date DESC LIMIT 1) AS trained_at
            FROM det_stats d, total_consumption t, sig_count s
            """
        )

        with self.engine.connect() as conn:
            row = conn.execute(
                query, {"appliance_name": appliance_name, "window_days": window_days}
            ).fetchone()

        if not row or row[1] is None:
            return None

        m = row._mapping
        kwh = float(m["kwh"]) if m["kwh"] is not None else 0.0
        total_kwh = float(m["total_kwh"]) if m["total_kwh"] is not None else 0.0
        recovered_share = round(kwh / total_kwh, 3) if total_kwh > 0 else None

        return {
            "appliance": m["appliance_name"],
            "window_days": window_days,
            "kwh": kwh,
            "total_kwh": total_kwh,
            "recovered_share": recovered_share,
            "cycles": int(m["cycles"]) if m["cycles"] is not None else 0,
            "confidence_avg": (float(m["confidence_avg"]) if m["confidence_avg"] is not None else None),
            "signatures_count": int(m["signatures_count"]) if m["signatures_count"] is not None else 0,
            "trained_at": format_datetime(m["trained_at"]),
        }

    def get_history(self, appliance_name: str, days: int = 30) -> dict | None:
        """Daily kWh per day for the last N days (zeros included for quiet days).

        Returns both NILM-detected kWh (days) and total meter kWh (total_days)
        so the caller can overlay them and compute a meaningful % share.
        """
        query = text(
            """
            WITH app AS (
                SELECT id FROM nilm_appliances WHERE name = :appliance_name
            ),
            date_series AS (
                SELECT generate_series(
                    (NOW() - make_interval(days => :days))::date,
                    (NOW())::date,
                    '1 day'::interval
                )::date AS day
            ),
            daily_kwh AS (
                SELECT
                    DATE(d.start_time) AS day,
                    COALESCE(SUM(d.energy_consumed) / 1000.0, 0.0) AS kwh
                FROM nilm_detections d
                WHERE d.appliance_id = (SELECT id FROM app)
                  AND d.start_time >= NOW() - make_interval(days => :days)
                  AND (d.user_validated IS NULL OR d.is_correct = TRUE)
                GROUP BY DATE(d.start_time)
            ),
            total_daily AS (
                SELECT
                    DATE(time) AS day,
                    COALESCE(SUM(papp) / 3600000.0, 0.0) AS kwh
                FROM linky_realtime
                WHERE time >= NOW() - make_interval(days => :days)
                GROUP BY DATE(time)
            )
            SELECT ds.day,
                COALESCE(dk.kwh, 0.0)  AS kwh,
                COALESCE(td.kwh, 0.0)  AS total_kwh
            FROM date_series ds
            LEFT JOIN daily_kwh dk    ON ds.day = dk.day
            LEFT JOIN total_daily td  ON ds.day = td.day
            ORDER BY ds.day
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(
                query, {"appliance_name": appliance_name, "days": days}
            ).fetchall()

        if not rows:
            return None

        return {
            "appliance": appliance_name,
            "days": [round(float(r._mapping["kwh"]), 3) for r in rows],
            "total_days": [round(float(r._mapping["total_kwh"]), 3) for r in rows],
        }

    def get_cycles(self, appliance_name: str, limit: int = 60) -> dict | None:
        """
        Last N detection cycles with decimal hour and duration_min.
        Also computes peak_hours: the 2 most frequent hour buckets (integer).
        """
        query = text(
            """
            SELECT
                EXTRACT(HOUR FROM d.start_time) +
                EXTRACT(MINUTE FROM d.start_time) / 60.0 AS hour,
                GREATEST(
                    EXTRACT(EPOCH FROM (d.end_time - d.start_time)) / 60.0,
                    1.0
                ) AS duration_min
            FROM nilm_detections d
            JOIN nilm_appliances a ON d.appliance_id = a.id
            WHERE a.name = :appliance_name
              AND (d.user_validated IS NULL OR d.is_correct = TRUE)
            ORDER BY d.start_time DESC
            LIMIT :limit
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(
                query, {"appliance_name": appliance_name, "limit": limit}
            ).fetchall()

        if not rows:
            return None

        cycles = [
            {
                "hour": round(float(r._mapping["hour"]), 2),
                "duration_min": round(float(r._mapping["duration_min"])),
            }
            for r in rows
        ]

        # Top-2 hour buckets by frequency (integer hour bins)
        from collections import Counter
        hour_counts = Counter(int(c["hour"]) for c in cycles)
        peak_hours = [h for h, _ in hour_counts.most_common(2)]
        peak_hours.sort()

        return {
            "appliance": appliance_name,
            "peak_hours": peak_hours,
            "cycles": cycles,
        }

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

            # Decide if a signature should be created (dedup check). The actual
            # creation is delegated to the API layer (calls nilm service).
            existing = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM nilm_signatures
                    WHERE appliance_id = :appliance_id
                      AND start_time = :start_time
                      AND end_time = :end_time
                      AND is_negative = :is_negative
                    """
                ),
                {"appliance_id": result[1], "start_time": start_time, "end_time": end_time, "is_negative": not is_correct},
            ).scalar()

            if existing == 0:
                detection_info["pending_signature"] = {
                    "appliance_name": appliance_name,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "is_negative": not is_correct,
                }

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

            pending_signature = None
            if existing_positive == 0:
                pending_signature = {
                    "appliance_name": correct_appliance_name,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "is_negative": False,
                }

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
                "pending_signature": pending_signature,
            }

    def get_detections_for_backfill(self, appliance_id: int) -> list[dict]:
        """All validated detections for HA statistics backfill, ordered chronologically."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT start_time, end_time, energy_consumed
                    FROM nilm_detections
                    WHERE appliance_id = :id
                      AND energy_consumed IS NOT NULL
                      AND energy_consumed > 0
                    ORDER BY start_time ASC
                    """
                ),
                {"id": appliance_id},
            ).fetchall()
        return [{"start_time": r[0], "end_time": r[1], "energy_wh": float(r[2])} for r in rows]
