"""FastAPI backend configuration."""

import os

from celery import Celery
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Backend configuration with Pydantic validation."""

    # Local database configuration (TimescaleDB)
    local_db_host = "timescaledb"
    local_db_port = 5432
    local_db_name = "linkya_db"
    local_db_user = "postgres"
    local_db_password = "postgres"

    # API Configuration
    api_title = "Linkya API"
    api_version = "0.1.0"
    api_description = "API REST pour accéder aux données Linky et NILM"
    cors_origins = [
        "http://localhost:3000",
        "http://frontend:3000",
        "ws://localhost:3000",
        "ws://frontend:3000",
    ]

    # Celery Configuration
    celery_broker_url = "redis://redis:6379/0"
    celery_result_backend = "redis://redis:6379/0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def local_db_url(self):
        """TimescaleDB connection URL."""
        return (
            f"postgresql://{self.local_db_user}:{self.local_db_password}"
            f"@{self.local_db_host}:{self.local_db_port}/{self.local_db_name}"
        )


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
