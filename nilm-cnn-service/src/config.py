"""
Configuration pour nilm-cnn-service
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Configuration du service NILM CNN"""
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    # Base de données locale (TimescaleDB)
    local_db_host: str = "timescaledb"
    local_db_port: int = 5432
    local_db_name: str = "local_data"
    local_db_user: str = "postgres"
    local_db_password: str = "postgres"
    
    # Redis/Celery
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"
    
    # Configuration CNN NILM
    cnn_training_interval_hours: int = 24  # Entraînement toutes les 24h
    cnn_detection_interval_minutes: int = 5  # Détection toutes les 5min
    cnn_detection_period_hours: int = 24  # Période analysée (défaut: 24h)
    cnn_window_size_minutes: int = 60  # Fenêtre d'analyse de 60min
    cnn_min_power_threshold: int = 30  # Seuil minimal de puissance (W)
    cnn_min_duration_seconds: int = 30  # Durée minimale d'un événement (s)
    
    # Configuration du modèle CNN
    cnn_model_path: str = "/app/models/cnn"
    cnn_sequence_length: int = 600  # Longueur des séquences (10min à 1Hz)
    cnn_batch_size: int = 32
    cnn_epochs: int = 50
    cnn_learning_rate: float = 0.001
    cnn_validation_split: float = 0.2
    
    # Augmentation de données
    cnn_augmentation_enabled: bool = True
    cnn_noise_factor: float = 0.02
    cnn_shift_range: int = 30  # Décalage temporel max (secondes)
    
    # Feature engineering
    cnn_fft_enabled: bool = True  # Extraction de features FFT
    cnn_gradient_enabled: bool = True  # Calcul des gradients
    cnn_statistics_enabled: bool = True  # Stats fenêtres glissantes
    
    @property
    def database_url(self) -> str:
        """URL de connexion à la base de données locale"""
        return (
            f"postgresql://{self.local_db_user}:{self.local_db_password}"
            f"@{self.local_db_host}:{self.local_db_port}/{self.local_db_name}"
        )


# Instance globale de configuration
settings = Settings()
