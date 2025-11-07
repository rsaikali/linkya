"""WebSocket manager for import progress."""

from .base import BaseWebSocketManager


class ImportProgressManager(BaseWebSocketManager):
    """Manages WebSocket connections for real-time import progress."""

    def __init__(self):
        super().__init__(channel_name="import:progress", manager_name="Import")


import_progress_manager = ImportProgressManager()
