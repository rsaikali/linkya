"""Configuration du backend FastAPI."""

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def local_db_url(self) -> str:
        """URL de connexion à TimescaleDB."""
        return (
            f"postgresql://{self.local_db_user}:{self.local_db_password}"
            f"@{self.local_db_host}:{self.local_db_port}/{self.local_db_name}"
        )


settings = Settings()
