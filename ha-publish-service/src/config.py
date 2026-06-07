import os


class Settings:
    def __init__(self):
        self.ha_url = os.getenv("HA_URL", "http://homeassistant.local:8123")
        self.ha_token = os.getenv("HA_TOKEN", "")

        self.ha_mqtt_host = os.getenv("HA_MQTT_HOST", "homeassistant.local")
        self.ha_mqtt_port = int(os.getenv("HA_MQTT_PORT", "1883"))
        self.ha_mqtt_user = os.getenv("HA_MQTT_USER", "homeassistant")
        self.ha_mqtt_password = os.getenv("HA_MQTT_PASSWORD", "")

        self.local_db_host = os.getenv("LOCAL_DB_HOST", "postgres")
        self.local_db_port = int(os.getenv("LOCAL_DB_PORT", "5432"))
        self.local_db_name = os.getenv("LOCAL_DB_NAME", "linkya_db")
        self.local_db_user = os.getenv("LOCAL_DB_USER", "postgres")
        self.local_db_password = os.getenv("LOCAL_DB_PASSWORD", "postgres")

        self.poll_interval = int(os.getenv("HA_PUBLISH_POLL_INTERVAL", "30"))

        # Buffer : une détection est "active" si end_time >= NOW() - buffer
        # Doit être >= NILM_DETECTION_INTERVAL_MINUTES pour ne pas rater les cycles récents
        self.active_buffer_minutes = int(os.getenv("NILM_DETECTION_INTERVAL_MINUTES", "5")) * 2

        # Path to HA SQLite DB mounted into this container (empty = feature disabled).
        self.ha_sqlite_path = os.getenv("HA_SQLITE_PATH", "")

    @property
    def local_db_url(self):
        return (
            f"postgresql+psycopg://{self.local_db_user}:{self.local_db_password}"
            f"@{self.local_db_host}:{self.local_db_port}/{self.local_db_name}"
        )


settings = Settings()
