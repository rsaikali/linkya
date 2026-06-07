"""Main database manager aggregating all repositories."""

from .appliances import ApplianceRepository
from .consumption import ConsumptionRepository
from .detections import DetectionRepository
from .models import ModelRepository
from .signatures import SignatureRepository


class DatabaseManager:
    """
    Main database manager that aggregates all repositories.

    This class delegates database operations to specialized repositories
    for better code organization and maintainability.
    """

    def __init__(self):
        """Initialize all repositories."""
        self.consumption = ConsumptionRepository()
        self.appliances = ApplianceRepository()
        self.signatures = SignatureRepository()
        self.detections = DetectionRepository()
        self.models = ModelRepository()

        # For backward compatibility, expose engine from one of the repos
        self.engine = self.consumption.engine
        self.SessionLocal = self.consumption.SessionLocal

    # Consumption methods
    def get_latest_consumption(self):
        """Get latest consumption data."""
        return self.consumption.get_latest_consumption()

    def get_consumption_time_range(self):
        """Get consumption time range."""
        return self.consumption.get_consumption_time_range()

    def get_consumption_history(self, start_time, end_time, interval="5 minutes"):
        """Get consumption history."""
        return self.consumption.get_consumption_history(start_time, end_time, interval)

    # Appliance methods
    def get_all_appliances(self):
        """Get all appliances."""
        return self.appliances.get_all_appliances()

    def update_appliance(self, appliance_id, name=None):
        """Update appliance."""
        return self.appliances.update_appliance(appliance_id, name)

    def delete_appliance(self, appliance_id):
        """Delete appliance."""
        return self.appliances.delete_appliance(appliance_id)

    def get_or_create_appliance(self, appliance_name):
        """Get or create appliance."""
        return self.appliances.get_or_create_appliance(appliance_name)

    def update_ha_publish(self, appliance_id: int, enabled: bool):
        """Toggle HA publishing for an appliance."""
        return self.appliances.update_ha_publish(appliance_id, enabled)

    def reset_energy(self, appliance_id: int):
        """Reset the HA energy sensor to 0 (keeps detections)."""
        return self.appliances.reset_energy(appliance_id)

    # Signature methods
    def get_appliance_signatures(self, appliance_id):
        """Get appliance signatures."""
        return self.signatures.get_appliance_signatures(appliance_id)

    def delete_all_signatures(self):
        """Delete all signatures."""
        return self.signatures.delete_all_signatures()

    def delete_signature(self, signature_id):
        """Delete specific signature."""
        return self.signatures.delete_signature(signature_id)

    def get_all_signatures_with_appliance(self):
        """Get all signatures with appliance info."""
        return self.signatures.get_all_signatures_with_appliance()

    # Detection methods
    def get_scorecard(self, appliance_name: str, window_days: int = 30):
        """Per-appliance NILM scorecard over the last N days."""
        return self.detections.get_scorecard(appliance_name, window_days)

    def get_history(self, appliance_name: str, days: int = 30):
        """Daily kWh series for the last N days."""
        return self.detections.get_history(appliance_name, days)

    def get_cycles(self, appliance_name: str, limit: int = 60):
        """Last N detection cycles with hour and duration, plus peak_hours."""
        return self.detections.get_cycles(appliance_name, limit)

    def get_detected_appliances(self, start_time=None, end_time=None, model_name=None):
        """Get detected appliances."""
        return self.detections.get_detected_appliances(start_time, end_time, model_name)

    def delete_detection(self, detection_id):
        """Delete specific detection."""
        return self.detections.delete_detection(detection_id)

    def delete_all_detections(self):
        """Delete all detections."""
        return self.detections.delete_all_detections()

    def validate_detection(self, detection_id, is_correct):
        """Validate detection."""
        return self.detections.validate_detection(detection_id, is_correct)

    def reassign_detection(self, detection_id, correct_appliance_name):
        """Reassign detection to correct appliance."""
        return self.detections.reassign_detection(detection_id, correct_appliance_name)

    def get_detections_for_backfill(self, appliance_id: int) -> list[dict]:
        """All detections for HA statistics backfill."""
        return self.detections.get_detections_for_backfill(appliance_id)

    # Model methods
    def get_latest_nilm_model(self):
        """Get latest NILM model."""
        return self.models.get_latest_nilm_model()

    def delete_all_models(self):
        """Delete all models."""
        return self.models.delete_all_models()


# Instance globale du gestionnaire de base de données
db_manager = DatabaseManager()
