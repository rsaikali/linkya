"""WebSocket manager for consumption updates."""

from .base import BaseWebSocketManager


class ConsumptionUpdatesManager(BaseWebSocketManager):
    """Manages WebSocket connections for real-time consumption data."""

    def __init__(self):
        super().__init__(channel_name="consumption:updates", manager_name="Consumption")


consumption_updates_manager = ConsumptionUpdatesManager()
