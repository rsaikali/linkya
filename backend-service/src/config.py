"""FastAPI backend configuration."""

import os


class Settings:
    def __init__(self):
        self.local_db_host = os.getenv("LOCAL_DB_HOST", "postgres")
        self.local_db_port = int(os.getenv("LOCAL_DB_PORT", "5432"))
        self.local_db_name = os.getenv("LOCAL_DB_NAME", "linkya_db")
        self.local_db_user = os.getenv("LOCAL_DB_USER", "postgres")
        self.local_db_password = os.getenv("LOCAL_DB_PASSWORD", "postgres")

        self.api_title = "Linkya API"
        self.api_version = "1.0.0"
        self.api_description = "NILM for Home Assistant — REST API + SSE"

        # Home Assistant
        self.ha_url = os.getenv("HA_URL", "http://homeassistant.local:8123")
        self.ha_token = os.getenv("HA_TOKEN", "")

        # Internal nilm service (train / detect / signature processing)
        self.nilm_url = os.getenv("NILM_URL", "http://nilm:8001")

        # Static React build dir (production image). Absent in dev.
        self.static_dir = os.getenv("STATIC_DIR", "/app/static")

    @property
    def local_db_url(self):
        return (
            f"postgresql://{self.local_db_user}:{self.local_db_password}"
            f"@{self.local_db_host}:{self.local_db_port}/{self.local_db_name}"
        )


settings = Settings()
