import os


class Settings:
    """Configuration de l'application"""

    def __init__(self):
        # Base distante
        self.remote_db_host = os.getenv("REMOTE_DB_HOST")
        self.remote_db_port = int(os.getenv("REMOTE_DB_PORT", "3306"))
        self.remote_db_name = os.getenv("REMOTE_DB_NAME")
        self.remote_db_user = os.getenv("REMOTE_DB_USER")
        self.remote_db_password = os.getenv("REMOTE_DB_PASSWORD")
        self.remote_db_table = os.getenv("REMOTE_DB_TABLE", "linky_realtime")

        # Base locale
        self.local_db_host = os.getenv("LOCAL_DB_HOST", "timescaledb")
        self.local_db_port = int(os.getenv("LOCAL_DB_PORT", "5432"))
        self.local_db_name = os.getenv("LOCAL_DB_NAME", "linkya_db")
        self.local_db_user = os.getenv("LOCAL_DB_USER", "postgres")
        self.local_db_password = os.getenv("LOCAL_DB_PASSWORD", "postgres")

        # Celery
        self.celery_broker_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
        self.celery_result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

        # Synchronisation
        self.sync_interval_seconds = int(os.getenv("SYNC_INTERVAL_SECONDS", "5"))
        self.sync_retention_hours = int(os.getenv("SYNC_RETENTION_HOURS", "48"))

    @property
    def remote_db_url(self):
        return (
            f"mysql+pymysql://{self.remote_db_user}:{self.remote_db_password}" f"@{self.remote_db_host}:{self.remote_db_port}/{self.remote_db_name}"
        )

    @property
    def local_db_url(self):
        return (
            f"postgresql+psycopg://{self.local_db_user}:{self.local_db_password}" f"@{self.local_db_host}:{self.local_db_port}/{self.local_db_name}"
        )


settings = Settings()
