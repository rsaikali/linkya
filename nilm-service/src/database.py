from sqlalchemy import create_engine, text, Column, Integer, String, Float, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import logging
import os

from .config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()


class Appliance(Base):
    """Table des appareils électriques détectés"""
    __tablename__ = 'appliances'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    is_validated = Column(Boolean, default=False)  # Validé par l'utilisateur
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Caractéristiques de la signature
    avg_power = Column(Float)  # Puissance moyenne (VA)
    max_power = Column(Float)  # Puissance max
    min_power = Column(Float)  # Puissance min
    power_variance = Column(Float)  # Variance de puissance
    cycle_duration_avg = Column(Integer)  # Durée moyenne du cycle (secondes)
    
    # Métadonnées ML
    cluster_id = Column(Integer)  # ID du cluster associé
    signature_features = Column(JSON)  # Features extraites pour la signature


class ApplianceSignature(Base):
    """Table des signatures d'appareils (données d'entraînement)"""
    __tablename__ = 'appliance_signatures'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    appliance_id = Column(Integer, ForeignKey('appliances.id'), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    is_training_data = Column(Boolean, default=True)
    added_by_user = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class DetectionEvent(Base):
    """Table des événements de détection"""
    __tablename__ = 'detection_events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    appliance_id = Column(Integer, ForeignKey('appliances.id'))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    confidence_score = Column(Float)  # Score de confiance de la détection
    avg_power = Column(Float)
    energy_consumed = Column(Float)  # Énergie consommée (Wh estimée)
    is_validated = Column(Boolean)  # Validé par l'utilisateur (None = non vérifié)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ModelVersion(Base):
    """Table pour versionner les modèles ML"""
    __tablename__ = 'model_versions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50), nullable=False, unique=True)
    model_type = Column(String(50))  # 'clustering', 'anomaly_detection', etc.
    model_path = Column(String(500))
    training_date = Column(DateTime, default=datetime.utcnow)
    metrics = Column(JSON)  # Métriques de performance du modèle
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class DatabaseManager:
    """Gestionnaire de connexion à TimescaleDB pour NILM"""
    
    def __init__(self):
        self.engine = create_engine(
            settings.local_db_url,
            pool_pre_ping=True,
            echo=False
        )
        self.Session = sessionmaker(bind=self.engine)
    
    def init_nilm_db(self):
        """Initialise les tables NILM dans TimescaleDB"""
        logger.info("Initialisation des tables NILM...")
        
        # Création de toutes les tables
        Base.metadata.create_all(self.engine)
        
        with self.engine.connect() as conn:
            # Index pour optimiser les requêtes de détection
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_detection_events_time
                ON detection_events (start_time DESC, end_time DESC);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_detection_events_appliance
                ON detection_events (appliance_id, start_time DESC);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_signatures_appliance
                ON appliance_signatures (appliance_id, start_time);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_signatures_time
                ON appliance_signatures (start_time, end_time);
            """))
            
            conn.commit()
            logger.info("Tables NILM créées avec succès")
    
    def get_linky_data(self, start_time: datetime, end_time: datetime):
        """Récupère les données Linky pour l'analyse"""
        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT time, papp, temperature
                    FROM linky_realtime
                    WHERE time >= :start_time AND time <= :end_time
                    ORDER BY time ASC
                """),
                {"start_time": start_time, "end_time": end_time}
            )
            return result.fetchall()
    
    def get_training_signatures(self):
        """Récupère toutes les signatures validées pour l'entraînement"""
        session = self.Session()
        try:
            signatures = session.execute(
                text("""
                    SELECT s.*, a.name, a.cluster_id
                    FROM appliance_signatures s
                    JOIN appliances a ON s.appliance_id = a.id
                    WHERE s.is_training_data = true
                    ORDER BY s.start_time
                """)
            ).fetchall()
            return signatures
        finally:
            session.close()
    
    def save_model_version(self, version: str, model_type: str, model_path: str, metrics: dict):
        """Sauvegarde une nouvelle version de modèle"""
        session = self.Session()
        try:
            # Désactiver les anciens modèles du même type
            session.execute(
                text("""
                    UPDATE model_versions
                    SET is_active = false
                    WHERE model_type = :model_type AND is_active = true
                """),
                {"model_type": model_type}
            )
            
            # Créer la nouvelle version
            model = ModelVersion(
                version=version,
                model_type=model_type,
                model_path=model_path,
                metrics=metrics,
                is_active=True
            )
            session.add(model)
            session.commit()
            logger.info(f"Modèle {version} sauvegardé avec succès")
            return model.id
        finally:
            session.close()
    
    def get_active_model(self, model_type: str):
        """Récupère le modèle actif pour un type donné"""
        session = self.Session()
        try:
            result = session.execute(
                text("""
                    SELECT * FROM model_versions
                    WHERE model_type = :model_type AND is_active = true
                    ORDER BY training_date DESC
                    LIMIT 1
                """),
                {"model_type": model_type}
            ).fetchone()
            return result
        finally:
            session.close()
    
    def save_detection_event(self, appliance_id: int, start_time: datetime, 
                           end_time: datetime, confidence: float, avg_power: float, 
                           energy: float):
        """Sauvegarde un événement de détection"""
        session = self.Session()
        try:
            event = DetectionEvent(
                appliance_id=appliance_id,
                start_time=start_time,
                end_time=end_time,
                confidence_score=confidence,
                avg_power=avg_power,
                energy_consumed=energy
            )
            session.add(event)
            session.commit()
            return event.id
        finally:
            session.close()


# Instance globale
db_manager = DatabaseManager()
