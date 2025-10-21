"""Configuration du backend FastAPI."""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from celery import Celery


class Settings(BaseSettings):
    """Configuration du backend avec validation Pydantic."""

    # Configuration base de données locale (TimescaleDB)
    local_db_host: str = "timescaledb"
    local_db_port: int = 5432
    local_db_name: str = "local_data"
    local_db_user: str = "postgres"
    local_db_password: str = "postgres"

    # Configuration API
    api_title: str = "Nilmia API"
    api_version: str = "0.1.0"
    api_description: str = "API REST pour accéder aux données Linky et NILM"
    cors_origins: list[str] = ["http://localhost:3000", "http://frontend:3000"]

    # Configuration Celery
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def local_db_url(self) -> str:
        """URL de connexion à TimescaleDB."""
        return (
            f"postgresql://{self.local_db_user}:{self.local_db_password}"
            f"@{self.local_db_host}:{self.local_db_port}/{self.local_db_name}"
        )


settings = Settings()


# Instance Celery singleton - initialisée une seule fois
_celery_app: Celery | None = None


def get_celery_app() -> Celery:
    """Retourne l'instance Celery singleton."""
    global _celery_app
    
    if _celery_app is None:
        _celery_app = Celery(
            "nilmia-backend",
            broker=settings.celery_broker_url,
            backend=settings.celery_result_backend
        )
    
    return _celery_app
