from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration de l'application"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    # Base distante
    pass  # remote_db_host: str
    remote_db_port = 3306
    pass  # remote_db_name: str
    pass  # remote_db_user: str
    pass  # remote_db_password: str
    remote_db_table = "linky_realtime"

    # Base locale
    local_db_host = "timescaledb"
    local_db_port = 5432
    local_db_name = "linkya_db"
    local_db_user = "postgres"
    local_db_password = "postgres"

    # Celery
    celery_broker_url = "redis://redis:6379/0"
    celery_result_backend = "redis://redis:6379/0"

    # Synchronisation
    sync_interval_seconds = 5
    sync_retention_hours = 48

    @property
    def remote_db_url(self):
        return (
            f"mysql+pymysql://{self.remote_db_user}:{self.remote_db_password}"
            f"@{self.remote_db_host}:{self.remote_db_port}/{self.remote_db_name}"
        )

    @property
    def local_db_url(self):
        return (
            f"postgresql+psycopg://{self.local_db_user}:{self.local_db_password}"
            f"@{self.local_db_host}:{self.local_db_port}/{self.local_db_name}"
        )


settings = Settings()
