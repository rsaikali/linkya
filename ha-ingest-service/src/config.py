import os


class Settings:
    def __init__(self):
        self.ha_url = os.getenv("HA_URL", "http://homeassistant.local:8123")
        self.ha_token = os.getenv("HA_TOKEN", "")
        self.ha_entity_papp = os.getenv("HA_ENTITY_PAPP", "sensor.linky_sinsts")
        self.ha_backfill_days = int(os.getenv("HA_BACKFILL_DAYS", "30"))

        self.ha_mqtt_host = os.getenv("HA_MQTT_HOST", "homeassistant.local")
        self.ha_mqtt_port = int(os.getenv("HA_MQTT_PORT", "1883"))
        self.ha_mqtt_user = os.getenv("HA_MQTT_USER", "homeassistant")
        self.ha_mqtt_password = os.getenv("HA_MQTT_PASSWORD", "")

        self.local_db_host = os.getenv("LOCAL_DB_HOST", "timescaledb")
        self.local_db_port = int(os.getenv("LOCAL_DB_PORT", "5432"))
        self.local_db_name = os.getenv("LOCAL_DB_NAME", "linkya_db")
        self.local_db_user = os.getenv("LOCAL_DB_USER", "postgres")
        self.local_db_password = os.getenv("LOCAL_DB_PASSWORD", "postgres")

        self.redis_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")

    @property
    def local_db_url(self):
        return (
            f"postgresql+psycopg://{self.local_db_user}:{self.local_db_password}"
            f"@{self.local_db_host}:{self.local_db_port}/{self.local_db_name}"
        )

    @property
    def mqtt_topic_papp(self):
        # statestream/{domain}/{object_id}/state
        # sensor.linky_sinsts -> statestream/sensor/linky_sinsts/state
        parts = self.ha_entity_papp.split(".", 1)
        domain, object_id = (parts[0], parts[1]) if len(parts) == 2 else ("sensor", parts[0])
        return f"statestream/{domain}/{object_id}/state"


settings = Settings()
