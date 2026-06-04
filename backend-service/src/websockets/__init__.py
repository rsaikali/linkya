"""WebSocket manager modules."""

from .consumption import consumption_updates_manager
from .detections import detection_updates_manager
from .import_progress import import_progress_manager
from .training import training_logs_manager


__all__ = [
    "training_logs_manager",
    "consumption_updates_manager",
    "detection_updates_manager",
    "import_progress_manager",
]
