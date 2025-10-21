from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration du service NILM"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Base locale TimescaleDB
    local_db_host: str = "timescaledb"
    local_db_port: int = 5432
    local_db_name: str = "local_data"
    local_db_user: str = "postgres"
    local_db_password: str = "postgres"
    
    # Celery
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"
    
    # NILM Configuration
    training_interval_hours: int = 24  # Retraining toutes les 24h
    detection_interval_minutes: int = 5  # Détection toutes les 5 minutes
    window_size_minutes: int = 60  # Fenêtre d'analyse de 60 minutes
    min_power_threshold: int = 50  # Seuil minimum de puissance (VA)
    min_duration_seconds: int = 60  # Durée minimale d'un événement (secondes)
    
    # Modèle ML
    model_path: str = "/app/models"
    n_clusters: int = 10  # Nombre de clusters pour la détection
    
    # Paramètres mémoire CUDA
    batch_size: int = 2  # Batch size réduit pour éviter CUDA OOM
    max_samples_training: int = 1000  # Limite du nombre d'échantillons d'entraînement
    imputation_epochs: int = 5  # Réduction des epochs pour l'imputation
    clustering_epochs: int = 20  # Réduction des epochs pour le clustering
    model_hidden_size: int = 64  # Taille cachée réduite
    
    @property
    def local_db_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.local_db_user}:{self.local_db_password}"
            f"@{self.local_db_host}:{self.local_db_port}/{self.local_db_name}"
        )


settings = Settings()
