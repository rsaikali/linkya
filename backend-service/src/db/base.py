"""Base database utilities and connection management."""

from datetime import datetime
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..config import settings

logger = logging.getLogger(__name__)


def format_datetime(dt: datetime | None) -> str | None:
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


class DatabaseBase:
    """Base class for database repositories."""

    def __init__(self):
        """Initializes the database connection."""
        self.engine = create_engine(
            settings.local_db_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
