"""WebSocket manager for detection updates."""

from .base import BaseWebSocketManager


class DetectionUpdatesManager(BaseWebSocketManager):
    """Manages WebSocket connections for real-time detection updates."""

    def __init__(self):
        super().__init__(channel_name="detections:updates", manager_name="Detection")


detection_updates_manager = DetectionUpdatesManager()
