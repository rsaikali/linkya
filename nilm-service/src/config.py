"""
Configuration pour nilm-service
"""

import os


class Settings:
    """Configuration du service NILM"""

    def __init__(self):
        # Base de données locale (TimescaleDB)
        self.local_db_host = os.getenv("LOCAL_DB_HOST", "timescaledb")
        self.local_db_port = int(os.getenv("LOCAL_DB_PORT", "5432"))
        self.local_db_name = os.getenv("LOCAL_DB_NAME", "linkya_db")
        self.local_db_user = os.getenv("LOCAL_DB_USER", "postgres")
        self.local_db_password = os.getenv("LOCAL_DB_PASSWORD", "postgres")

        # Redis/Celery
        self.celery_broker_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
        self.celery_result_backend = os.getenv(
            "CELERY_RESULT_BACKEND", "redis://redis:6379/0"
        )

        # Configuration NILM
        self.nilm_training_interval_hours = int(
            os.getenv("NILM_TRAINING_INTERVAL_HOURS", "24")
        )
        self.nilm_detection_interval_minutes = int(
            os.getenv("NILM_DETECTION_INTERVAL_MINUTES", "5")
        )
        # Période analysée (None=tout, ou nombre d'heures)
        period_hours = os.getenv("NILM_DETECTION_PERIOD_HOURS")
        self.nilm_detection_period_hours = int(period_hours) if period_hours else None
        # Fenêtre d'analyse en minutes (auto-converti en sequence_length)
        self.nilm_window_size_minutes = int(os.getenv("NILM_WINDOW_SIZE_MINUTES", "10"))
        # Seuil minimal de puissance (W) - réduit pour transitions douces
        self.nilm_min_power_threshold = int(os.getenv("NILM_MIN_POWER_THRESHOLD", "15"))
        self.nilm_min_duration_seconds = int(
            os.getenv("NILM_MIN_DURATION_SECONDS", "30")
        )

        # Configuration du modèle (S2P, LSTM, GRU)
        self.nilm_model_path = os.getenv("NILM_MODEL_PATH", "/app/models")
        # Override manuel de la longueur de séquence (si None, calculé auto)
        seq_length = os.getenv("NILM_SEQUENCE_LENGTH", "599")
        self.nilm_sequence_length = int(seq_length) if seq_length else 599
        self.nilm_batch_size = int(os.getenv("NILM_BATCH_SIZE", "32"))
        self.nilm_epochs = int(os.getenv("NILM_EPOCHS", "50"))
        self.nilm_learning_rate = float(os.getenv("NILM_LEARNING_RATE", "0.001"))
        self.nilm_validation_split = float(os.getenv("NILM_VALIDATION_SPLIT", "0.2"))

        # Device configuration (CPU/GPU)
        self.use_gpu = os.getenv("USE_GPU")  # "true", "false", "auto" (default)
        self.nilm_model_type = os.getenv("NILM_MODEL_TYPE", "gru")
        # Activer détection d'états/cycles
        detect_states = os.getenv("NILM_DETECT_STATES", "true")
        self.nilm_detect_states = detect_states.lower() in ("true", "1", "yes")

    @property
    def database_url(self):
        """URL de connexion à la base de données locale"""
        return (
            f"postgresql://{self.local_db_user}:{self.local_db_password}"
            f"@{self.local_db_host}:{self.local_db_port}/{self.local_db_name}"
        )

    @property
    def effective_sequence_length(self):
        """
        Calcule la longueur de séquence effective.

        Si nilm_sequence_length est défini, l'utilise.
        Sinon, calcule depuis nilm_window_size_minutes (1Hz = 60 points/min).

        Returns:
            Longueur de séquence en nombre de points
        """
        if self.nilm_sequence_length is not None:
            return self.nilm_sequence_length

        # Conversion: minutes -> secondes (1Hz = 1 point/seconde)
        return self.nilm_window_size_minutes * 60


# Instance globale de configuration
settings = Settings()
