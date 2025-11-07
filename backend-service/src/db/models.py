"""NILM models repository."""

import logging

from sqlalchemy import text

from .base import DatabaseBase, format_datetime

logger = logging.getLogger(__name__)


class ModelRepository(DatabaseBase):
    """Repository for NILM model operations."""

    def get_latest_nilm_model(self):
        """
        Retrieves the latest trained NILM model.

        Returns:
            Dictionary with model information or None if no model exists
        """
        query = text(
            """
            SELECT
                id,
                model_name,
                model_type,
                architecture,
                training_date,
                num_signatures,
                num_classes,
                metrics,
                model_path,
                training_duration_seconds
            FROM nilm_models
            ORDER BY training_date DESC
            LIMIT 1
        """
        )

        with self.engine.connect() as conn:
            result = conn.execute(query).fetchone()

            if not result:
                return None

            return {
                "id": result[0],
                "model_name": result[1],
                "model_type": result[2],
                "architecture": result[3],
                "training_date": format_datetime(result[4]),
                "num_signatures": result[5],
                "num_classes": result[6],
                "metrics": result[7],
                "model_path": result[8],
                "training_duration_seconds": result[9],
            }

    def delete_all_models(self):
        """
        Deletes all NILM models from the database.

        Returns:
            Number of deleted models
        """
        delete_query = text("DELETE FROM nilm_models")

        with self.engine.connect() as conn:
            result = conn.execute(delete_query)
            count = result.rowcount
            conn.commit()

            logger.info(f"Deleted {count} NILM model(s) from database")
            return count
