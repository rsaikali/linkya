"""WebSocket manager for training logs."""

from .base import BaseWebSocketManager


class TrainingLogsManager(BaseWebSocketManager):
    """Manages WebSocket connections for real-time training logs."""

    def __init__(self):
        super().__init__(channel_name="training:logs", manager_name="Training")


training_logs_manager = TrainingLogsManager()
