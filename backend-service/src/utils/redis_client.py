"""Redis client initialization and management."""

import logging

import redis

from ..config import settings


logger = logging.getLogger(__name__)

# Redis client for publishing real-time events
_redis_client = None


def get_redis_client():
    """Get or create Redis client instance."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.celery_broker_url, decode_responses=True
            )
            logger.info("Redis client initialized for real-time events")
        except Exception as e:
            logger.warning(f"Redis client init failed: {e}")
            _redis_client = None
    return _redis_client
