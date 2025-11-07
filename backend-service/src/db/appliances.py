"""Appliances repository."""

import logging

from sqlalchemy import text

from .base import DatabaseBase, format_datetime


logger = logging.getLogger(__name__)


class ApplianceRepository(DatabaseBase):
    """Repository for appliance operations."""

    def get_all_appliances(self):
        """Retrieves all appliances with stats from linky_realtime."""
        query = text(
            """
            SELECT
                ca.id,
                ca.name,
                ca.created_at,
                ca.updated_at,
                -- Calculer avg_power depuis linky_realtime
                (
                    SELECT AVG(
                        (SELECT AVG(papp)
                         FROM linky_realtime
                         WHERE time >= cs.start_time
                           AND time <= cs.end_time)
                    )
                    FROM nilm_signatures cs
                    WHERE cs.appliance_id = ca.id
                      AND cs.is_negative = false
                ) as avg_power,
                -- Calculer power_std depuis linky_realtime
                (
                    SELECT STDDEV(
                        (SELECT AVG(papp)
                         FROM linky_realtime
                         WHERE time >= cs.start_time
                           AND time <= cs.end_time)
                    )
                    FROM nilm_signatures cs
                    WHERE cs.appliance_id = ca.id
                      AND cs.is_negative = false
                ) as power_std,
                (
                    SELECT AVG(
                        EXTRACT(EPOCH FROM (cs.end_time - cs.start_time))
                    )
                    FROM nilm_signatures cs
                    WHERE cs.appliance_id = ca.id
                      AND cs.is_negative = false
                ) as avg_duration,
                (
                    SELECT COUNT(*)
                    FROM nilm_signatures cs
                    WHERE cs.appliance_id = ca.id
                ) as num_signatures,
                (
                    SELECT MAX(start_time)
                    FROM nilm_signatures cs
                    WHERE cs.appliance_id = ca.id
                ) as last_signature_start,
                (
                    SELECT MAX(end_time)
                    FROM nilm_signatures cs
                    WHERE cs.appliance_id = ca.id
                ) as last_signature_end,
                (
                    SELECT COUNT(*)
                    FROM nilm_detections cd
                    WHERE cd.appliance_id = ca.id
                ) as detection_count
            FROM nilm_appliances ca
            ORDER BY ca.name ASC
        """
        )

        with self.engine.connect() as conn:
            result = conn.execute(query)
            appliances_list = []
            for row in result:
                appliance = {
                    "id": row[0],
                    "name": row[1],
                    "created_at": format_datetime(row[2]),
                    "updated_at": format_datetime(row[3]),
                    "avg_power": float(row[4]) if row[4] is not None else None,
                    "power_std": float(row[5]) if row[5] is not None else None,
                    "avg_duration": (float(row[6]) if row[6] is not None else None),
                    "num_signatures": int(row[7]) if row[7] is not None else 0,
                    "last_signature_start": format_datetime(row[8]),
                    "last_signature_end": format_datetime(row[9]),
                    "signature_count": int(row[7]) if row[7] is not None else 0,
                    "detection_count": int(row[10]) if row[10] is not None else 0,
                }

                appliances_list.append(appliance)

            return appliances_list

    def update_appliance(self, appliance_id, name=None):
        """
        Updates the name of an appliance.

        Args:
            appliance_id: Appliance ID
            name: New name (optional)

        Returns:
            Updated appliance or None if not found
        """
        # Dynamically build the UPDATE query
        set_clauses = []
        params = {"appliance_id": appliance_id}

        if name is not None:
            set_clauses.append("name = :name")
            params["name"] = name

        if not set_clauses:
            # Rien à mettre à jour, récupérer l'appareil actuel
            select_query = text(
                """
                SELECT id, name, created_at, updated_at
                FROM nilm_appliances
                WHERE id = :appliance_id
            """
            )
            with self.engine.connect() as conn:
                result = conn.execute(select_query, params).fetchone()
                if result:
                    return {
                        "id": result[0],
                        "name": result[1],
                        "created_at": format_datetime(result[2]),
                        "updated_at": format_datetime(result[3]),
                    }
                return None

        set_clauses.append("updated_at = NOW()")
        update_query = text(
            f"""
            UPDATE nilm_appliances
            SET {", ".join(set_clauses)}
            WHERE id = :appliance_id
            RETURNING id, name, created_at, updated_at
        """
        )

        with self.engine.connect() as conn:
            result = conn.execute(update_query, params).fetchone()

            if result:
                conn.commit()
                return {
                    "id": result[0],
                    "name": result[1],
                    "created_at": format_datetime(result[2]),
                    "updated_at": format_datetime(result[3]),
                }
            return None

    def delete_appliance(self, appliance_id):
        """
        Deletes an appliance and all its associated data.

        Args:
            appliance_id: ID of the appliance to delete

        Returns:
            Dictionary with the number of deleted signatures and detections
        """
        # First check that the appliance exists
        check_query = text(
            """
            SELECT id FROM nilm_appliances WHERE id = :appliance_id
        """
        )

        with self.engine.connect() as conn:
            exists = conn.execute(
                check_query, {"appliance_id": appliance_id}
            ).fetchone()

            if not exists:
                return None

            # Compter les éléments à supprimer
            count_signatures_query = text(
                """
                SELECT COUNT(*)
                FROM nilm_signatures
                WHERE appliance_id = :appliance_id
            """
            )
            count_detections_query = text(
                """
                SELECT COUNT(*)
                FROM nilm_detections
                WHERE appliance_id = :appliance_id
            """
            )

            signatures_count = conn.execute(
                count_signatures_query, {"appliance_id": appliance_id}
            ).scalar()

            detections_count = conn.execute(
                count_detections_query, {"appliance_id": appliance_id}
            ).scalar()

            # Supprimer dans l'ordre (FK constraints)
            delete_detections_query = text(
                """
                DELETE FROM nilm_detections
                WHERE appliance_id = :appliance_id
            """
            )
            delete_signatures_query = text(
                """
                DELETE FROM nilm_signatures
                WHERE appliance_id = :appliance_id
            """
            )
            delete_appliance_query = text(
                """
                DELETE FROM nilm_appliances WHERE id = :appliance_id
            """
            )

            conn.execute(delete_detections_query, {"appliance_id": appliance_id})
            conn.execute(delete_signatures_query, {"appliance_id": appliance_id})
            conn.execute(delete_appliance_query, {"appliance_id": appliance_id})

            conn.commit()

            return {
                "signatures_deleted": signatures_count or 0,
                "detections_deleted": detections_count or 0,
            }

    def get_or_create_appliance(self, appliance_name):
        """
        Gets or creates an appliance by name.

        Args:
            appliance_name: Name of the appliance

        Returns:
            Appliance ID
        """
        with self.engine.connect() as conn:
            # Try to find the appliance
            select_query = text(
                """
                SELECT id FROM nilm_appliances
                WHERE name = :name
                LIMIT 1
            """
            )

            result = conn.execute(select_query, {"name": appliance_name}).fetchone()

            if result:
                return result[0]

            # Create a new appliance if it doesn't exist
            insert_query = text(
                """
                INSERT INTO nilm_appliances
                (name, created_at, updated_at)
                VALUES (:name, NOW(), NOW())
                RETURNING id
            """
            )

            result = conn.execute(insert_query, {"name": appliance_name})
            appliance_id = result.scalar()
            conn.commit()

            logger.info(f"Appliance created: {appliance_name} (ID: {appliance_id})")

            return appliance_id
