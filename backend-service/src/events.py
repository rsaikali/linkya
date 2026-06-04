"""In-memory SSE event bus.

Replaces the old Redis pub/sub + WebSocket stack. A single process holds the
fan-out: any code path (CRUD, detection cron callback, training progress from
the nilm service) calls `bus.publish(type, data)`, and every connected SSE
client receives it. No broker, no external dependency.
"""

import asyncio
import json
import logging


logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._clients: set[asyncio.Queue] = set()

    def publish(self, event_type: str, data: dict) -> None:
        """Fan-out an event to all connected SSE clients (non-blocking)."""
        payload = {"event": event_type, "data": data}
        dead = []
        for q in self._clients:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._clients.discard(q)
        logger.debug("SSE publish %s → %d clients", event_type, len(self._clients))

    async def subscribe(self):
        """Register a client queue; yields SSE-formatted strings."""
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._clients.add(q)
        logger.info("SSE client connected (total=%d)", len(self._clients))
        try:
            # Initial comment so the browser marks the stream as open.
            yield ": connected\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=20.0)
                    yield f"event: {payload['event']}\ndata: {json.dumps(payload['data'])}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat keeps proxies from closing the idle connection.
                    yield ": ping\n\n"
        finally:
            self._clients.discard(q)
            logger.info("SSE client disconnected (total=%d)", len(self._clients))


bus = EventBus()
