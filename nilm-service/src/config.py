"""
Configuration for nilm-service
"""

import os


class Settings:
    """NILM service configuration"""

    def __init__(self):
        # Local database (plain PostgreSQL)
        self.local_db_host = os.getenv("LOCAL_DB_HOST", "postgres")
        self.local_db_port = int(os.getenv("LOCAL_DB_PORT", "5432"))
        self.local_db_name = os.getenv("LOCAL_DB_NAME", "linkya_db")
        self.local_db_user = os.getenv("LOCAL_DB_USER", "postgres")
        self.local_db_password = os.getenv("LOCAL_DB_PASSWORD", "postgres")

        # NILM configuration
        self.nilm_detection_interval_minutes = int(os.getenv("NILM_DETECTION_INTERVAL_MINUTES", "5"))
        # Analyzed period (None=all history, or number of hours)
        period_hours = os.getenv("NILM_DETECTION_PERIOD_HOURS")
        self.nilm_detection_period_hours = int(period_hours) if period_hours else None
        # Analysis window in minutes (auto-converted to sequence_length)
        self.nilm_window_size_minutes = int(os.getenv("NILM_WINDOW_SIZE_MINUTES", "10"))
        # Minimum power threshold (W) - lowered to catch soft transitions
        self.nilm_min_power_threshold = int(os.getenv("NILM_MIN_POWER_THRESHOLD", "15"))
        self.nilm_min_duration_seconds = int(os.getenv("NILM_MIN_DURATION_SECONDS", "30"))

        # Model configuration (S2P, LSTM, GRU)
        self.nilm_model_path = os.getenv("NILM_MODEL_PATH", "/app/models")
        # Manual sequence length override (if None, computed automatically)
        seq_length = os.getenv("NILM_SEQUENCE_LENGTH", "599")
        self.nilm_sequence_length = int(seq_length) if seq_length else 599
        self.nilm_batch_size = int(os.getenv("NILM_BATCH_SIZE", "32"))
        self.nilm_epochs = int(os.getenv("NILM_EPOCHS", "50"))
        self.nilm_learning_rate = float(os.getenv("NILM_LEARNING_RATE", "0.001"))
        self.nilm_validation_split = float(os.getenv("NILM_VALIDATION_SPLIT", "0.2"))

        # Device configuration (CPU/GPU)
        self.use_gpu = os.getenv("USE_GPU")  # "true", "false", "auto" (default)
        self.nilm_model_type = os.getenv("NILM_MODEL_TYPE", "gru")
        # Enable state/cycle detection
        detect_states = os.getenv("NILM_DETECT_STATES", "true")
        self.nilm_detect_states = detect_states.lower() in ("true", "1", "yes")

    @property
    def database_url(self):
        """Connection URL for the local database"""
        return f"postgresql://{self.local_db_user}:{self.local_db_password}" f"@{self.local_db_host}:{self.local_db_port}/{self.local_db_name}"

    @property
    def effective_sequence_length(self):
        """
        Compute the effective sequence length.

        Uses nilm_sequence_length if set.
        Otherwise, derives it from nilm_window_size_minutes (1Hz = 60 points/min).

        Returns:
            Sequence length in number of points
        """
        if self.nilm_sequence_length is not None:
            return self.nilm_sequence_length

        # Conversion: minutes -> seconds (1Hz = 1 point/second)
        return self.nilm_window_size_minutes * 60


# Global configuration instance
settings = Settings()
