from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration de l'application"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Base distante
    remote_db_host: str
    remote_db_port: int = 3306
    remote_db_name: str
    remote_db_user: str
    remote_db_password: str
    remote_db_table: str = "linky_realtime"
    
    # Base locale
    local_db_host: str = "timescaledb"
    local_db_port: int = 5432
    local_db_name: str = "local_data"
    local_db_user: str = "postgres"
    local_db_password: str = "postgres"
    
    # Celery
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"
    
    # Synchronisation
    sync_interval_seconds: int = 5
    sync_retention_hours: int = 48
    
    @property
    def remote_db_url(self) -> str:
        return (
            f"mysql+pymysql://{self.remote_db_user}:{self.remote_db_password}"
            f"@{self.remote_db_host}:{self.remote_db_port}/{self.remote_db_name}"
        )
    
    @property
    def local_db_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.local_db_user}:{self.local_db_password}"
            f"@{self.local_db_host}:{self.local_db_port}/{self.local_db_name}"
        )


settings = Settings()
