"""Base WebSocket manager class."""

import asyncio
import logging

import redis.asyncio as aioredis

from ..config import settings


logger = logging.getLogger(__name__)


class BaseWebSocketManager:
    """Base class for WebSocket connection management with Redis Pub/Sub."""

    def __init__(self, channel_name: str, manager_name: str):
        """
        Initialize WebSocket manager.

        Args:
            channel_name: Redis Pub/Sub channel to subscribe to
            manager_name: Name for logging purposes
        """
        self.channel_name = channel_name
        self.manager_name = manager_name
        self.active_connections = set()
        self.redis_client = None
        self.pubsub = None
        self.listener_task = None

    async def connect(self, websocket):
        """Accept new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"{self.manager_name} WS connected. Total: {len(self.active_connections)}")

        if not self.listener_task:
            await self.start_redis_listener()

    def disconnect(self, websocket):
        """Remove WebSocket connection."""
        self.active_connections.discard(websocket)
        logger.info(f"{self.manager_name} WS disconnected. Total: {len(self.active_connections)}")

    async def start_redis_listener(self):
        """Start listening to Redis Pub/Sub channel."""
        try:
            redis_url = settings.celery_broker_url.replace("redis://", "")
            host_port = redis_url.split("/")[0]

            self.redis_client = await aioredis.from_url(f"redis://{host_port}", decode_responses=True)
            self.pubsub = self.redis_client.pubsub()
            await self.pubsub.subscribe(self.channel_name)

            logger.info(f"Started Redis listener for {self.channel_name}")
            self.listener_task = asyncio.create_task(self._listen_redis())

        except Exception as e:
            logger.error(f"Failed to start {self.manager_name} Redis listener: {e}")

    async def _listen_redis(self):
        """Background task that listens to Redis and broadcasts to WebSockets."""
        logger.info(f"{self.manager_name} Redis listener task started")
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    logger.debug(f"Broadcasting {self.manager_name} to {len(self.active_connections)} clients")
                    await self.broadcast(data)
        except Exception as e:
            logger.error(f"Error in {self.manager_name} Redis listener: {e}", exc_info=True)
        finally:
            logger.info(f"{self.manager_name} Redis listener task ending")
            if self.pubsub:
                await self.pubsub.unsubscribe(self.channel_name)
                await self.pubsub.close()
            if self.redis_client:
                await self.redis_client.close()

    async def broadcast(self, message):
        """Broadcast message to all connected WebSocket clients."""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to {self.manager_name} WebSocket: {e}")
                disconnected.add(connection)

        for conn in disconnected:
            self.disconnect(conn)
