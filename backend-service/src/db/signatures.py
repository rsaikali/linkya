"""Signatures repository."""

from sqlalchemy import text

from .base import DatabaseBase, format_datetime


class SignatureRepository(DatabaseBase):
    """Repository for signature operations."""

    def get_appliance_signatures(self, appliance_id):
        """
        Retrieves all signatures for a specific appliance.

        Args:
            appliance_id: Appliance ID

        Returns:
            List of signatures with their details
        """
        query = text(
            """
            SELECT
                cs.id,
                cs.appliance_id,
                cs.start_time,
                cs.end_time,
                (
                    SELECT AVG(papp)
                    FROM linky_realtime
                    WHERE time >= cs.start_time AND time <= cs.end_time
                ) as avg_power,
                (
                    SELECT STDDEV(papp)
                    FROM linky_realtime
                    WHERE time >= cs.start_time AND time <= cs.end_time
                ) as power_std,
                (
                    SELECT SUM(papp) / 3600.0
                    FROM linky_realtime
                    WHERE time >= cs.start_time AND time <= cs.end_time
                ) as energy_consumed,
                cs.created_at,
                EXTRACT(EPOCH FROM (cs.end_time - cs.start_time))
                    as duration_seconds
            FROM nilm_signatures cs
            WHERE cs.appliance_id = :appliance_id
            ORDER BY cs.start_time DESC
        """
        )

        with self.engine.connect() as conn:
            result = conn.execute(query, {"appliance_id": appliance_id})
            signatures_list = []
            for row in result:
                signature = {
                    "id": row[0],
                    "appliance_id": row[1],
                    "start_time": format_datetime(row[2]),
                    "end_time": format_datetime(row[3]),
                    "avg_power": (float(row[4]) if row[4] is not None else None),
                    "power_std": (float(row[5]) if row[5] is not None else None),
                    "energy_consumed": (float(row[6]) if row[6] is not None else None),
                    "created_at": format_datetime(row[7]),
                    "duration_seconds": (float(row[8]) if row[8] is not None else None),
                }
                signatures_list.append(signature)

            return signatures_list

    def delete_all_signatures(self):
        """
        Deletes all signatures from all appliances.

        Returns:
            Dictionary with the number of deleted signatures
        """
        count_query = text(
            """
            SELECT COUNT(*) FROM nilm_signatures
        """
        )

        delete_query = text(
            """
            DELETE FROM nilm_signatures
        """
        )

        with self.engine.connect() as conn:
            # Compter les signatures à supprimer
            signatures_count = conn.execute(count_query).scalar() or 0

            # Supprimer toutes les signatures
            conn.execute(delete_query)
            conn.commit()

            return {"signatures_deleted": signatures_count}

    def delete_signature(self, signature_id):
        """
        Deletes a specific signature.

        Args:
            signature_id: ID of the signature to delete

        Returns:
            Deleted signature information or None if not found
        """
        # Retrieve information before deletion
        get_query = text(
            """
            SELECT
                s.id,
                s.appliance_id,
                a.name as appliance_name,
                s.start_time,
                s.end_time,
                s.is_negative,
                s.created_at
            FROM nilm_signatures s
            JOIN nilm_appliances a ON s.appliance_id = a.id
            WHERE s.id = :signature_id
        """
        )

        delete_query = text(
            """
            DELETE FROM nilm_signatures
            WHERE id = :signature_id
        """
        )

        with self.engine.connect() as conn:
            # Récupérer les infos de la signature
            result = conn.execute(get_query, {"signature_id": signature_id}).fetchone()

            if not result:
                return None

            # Convertir en dict
            signature_info = {
                "id": result[0],
                "appliance_id": result[1],
                "appliance_name": result[2],
                "start_time": format_datetime(result[3]),
                "end_time": format_datetime(result[4]),
                "is_negative": result[5],
                "created_at": format_datetime(result[6]),
            }

            # Supprimer la signature
            conn.execute(delete_query, {"signature_id": signature_id})
            conn.commit()

            return signature_info

    def get_all_signatures_with_appliance(self):
        """
        Retrieves all signatures with associated appliance information.

        Returns:
            List of signatures with appliance_name,
            start_time, end_time, is_negative
        """
        query = text(
            """
            SELECT
                cs.id,
                ca.id as appliance_id,
                ca.name as appliance_name,
                cs.start_time,
                cs.end_time,
                (
                    SELECT AVG(papp)
                    FROM linky_realtime
                    WHERE time >= cs.start_time AND time <= cs.end_time
                ) as avg_power,
                (
                    SELECT SUM(papp) / 3600.0
                    FROM linky_realtime
                    WHERE time >= cs.start_time AND time <= cs.end_time
                ) as energy_consumed,
                EXTRACT(EPOCH FROM (cs.end_time - cs.start_time))
                    as duration_seconds,
                cs.is_negative
            FROM nilm_signatures cs
            JOIN nilm_appliances ca ON cs.appliance_id = ca.id
            ORDER BY cs.start_time DESC
        """
        )

        with self.engine.connect() as conn:
            result = conn.execute(query)
            return [
                {
                    "id": row[0],
                    "appliance_id": row[1],
                    "appliance_name": row[2],
                    "start_time": format_datetime(row[3]),
                    "end_time": format_datetime(row[4]),
                    "avg_power": float(row[5]) if row[5] is not None else None,
                    "energy_consumed": (float(row[6]) if row[6] is not None else None),
                    "duration_seconds": (float(row[7]) if row[7] is not None else None),
                    "is_negative": row[8] if row[8] is not None else False,
                }
                for row in result
            ]
