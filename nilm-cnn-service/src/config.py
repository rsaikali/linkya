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
    
    # Configuration NILM
    cnn_training_interval_hours: int = 24  # Entraînement toutes les 24h
    cnn_detection_interval_minutes: int = 5  # Détection toutes les 5min
    cnn_detection_period_hours: Optional[int] = None  # Période analysée (None=tout, ou nombre d'heures)
    # Fenêtre d'analyse en minutes (auto-converti en sequence_length)
    cnn_window_size_minutes: int = 10  # 10 min = 600 points à 1Hz
    cnn_min_power_threshold: int = 30  # Seuil minimal de puissance (W)
    cnn_min_duration_seconds: int = 30  # Durée minimale d'un événement (s)
    
    # Configuration du modèle (S2P, LSTM, GRU)
    cnn_model_path: str = "/app/models"
    # Override manuel de la longueur de séquence (si None, calculé auto)
    cnn_sequence_length: Optional[int] = None
    cnn_batch_size: int = 32
    cnn_epochs: int = 50
    cnn_learning_rate: float = 0.001
    cnn_validation_split: float = 0.2
    
    # Device configuration (CPU/GPU)
    use_gpu: Optional[str] = None  # "true", "false", "auto" (default)
    nilm_model_type: str = "gru"  # Type de modèle: "gru" (défaut) ou "lstm"
    nilm_detect_states: bool = True  # Activer détection d'états/cycles
    
    @property
    def database_url(self) -> str:
        """URL de connexion à la base de données locale"""
        return (
            f"postgresql://{self.local_db_user}:{self.local_db_password}"
            f"@{self.local_db_host}:{self.local_db_port}/{self.local_db_name}"
        )
    
    @property
    def effective_sequence_length(self) -> int:
        """
        Calcule la longueur de séquence effective.
        
        Si cnn_sequence_length est défini, l'utilise.
        Sinon, calcule depuis cnn_window_size_minutes (1Hz = 60 points/min).
        
        Returns:
            Longueur de séquence en nombre de points
        """
        if self.cnn_sequence_length is not None:
            return self.cnn_sequence_length
        
        # Conversion: minutes -> secondes (1Hz = 1 point/seconde)
        return self.cnn_window_size_minutes * 60


# Instance globale de configuration
settings = Settings()
