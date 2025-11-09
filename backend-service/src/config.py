"""FastAPI backend configuration."""

import os

from celery import Celery


class Settings:
    """Backend configuration."""

    def __init__(self):
        # Local database configuration (TimescaleDB)
        self.local_db_host = os.getenv("LOCAL_DB_HOST", "timescaledb")
        self.local_db_port = int(os.getenv("LOCAL_DB_PORT", "5432"))
        self.local_db_name = os.getenv("LOCAL_DB_NAME", "linkya_db")
        self.local_db_user = os.getenv("LOCAL_DB_USER", "postgres")
        self.local_db_password = os.getenv("LOCAL_DB_PASSWORD", "postgres")

        # API Configuration
        self.api_title = os.getenv("API_TITLE", "Linkya API")
        self.api_version = os.getenv("API_VERSION", "0.1.0")
        self.api_description = os.getenv("API_DESCRIPTION", "API REST pour accéder aux données Linky et NILM")
        self.cors_origins = [
            "http://localhost:3000",
            "http://frontend:3000",
            "ws://localhost:3000",
            "ws://frontend:3000",
        ]

        # Celery Configuration
        self.celery_broker_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
        self.celery_result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

    @property
    def local_db_url(self):
        """TimescaleDB connection URL."""
        return f"postgresql://{self.local_db_user}:{self.local_db_password}" f"@{self.local_db_host}:{self.local_db_port}/{self.local_db_name}"


settings = Settings()


# Celery singleton instance - initialized once
_celery_app = None


def get_celery_app():
    """Returns the Celery singleton instance."""
    global _celery_app

    if _celery_app is None:
        _celery_app = Celery(
            "linkya-backend",
            broker=settings.celery_broker_url,
            backend=settings.celery_result_backend,
        )

    return _celery_app
