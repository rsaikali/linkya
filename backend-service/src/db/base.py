"""Base database utilities and connection management."""

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..config import settings


logger = logging.getLogger(__name__)


def format_datetime(dt):
    """
    Formats a datetime to ISO string.

    Args:
        dt: Datetime to format (with timezone)

    Returns:
        ISO string with timezone or None
    """
    if dt is None:
        return None
    return dt.isoformat()


_shared_engine = None
_shared_session_factory = None


def _get_engine():
    global _shared_engine
    if _shared_engine is None:
        _shared_engine = create_engine(
            settings.local_db_url, pool_pre_ping=True, pool_size=10, max_overflow=20
        )
    return _shared_engine


def _get_session_factory():
    global _shared_session_factory
    if _shared_session_factory is None:
        _shared_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    return _shared_session_factory


class DatabaseBase:
    """Base class for database repositories."""

    def __init__(self):
        """Initializes the database connection."""
        self.engine = _get_engine()
        self.SessionLocal = _get_session_factory()
