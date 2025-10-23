"""
Gestion de la base de données TimescaleDB pour nilm-cnn-service
"""
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager

from sqlalchemy import create_engine, text, Table, Column, Integer, String, Float, DateTime, Boolean, JSON, ForeignKey, MetaData, Index
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from .config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Gestionnaire de connexion à la base de données TimescaleDB"""
    
    def __init__(self):
        """Initialise le gestionnaire de base de données"""
        self.engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.metadata = MetaData()
        
        # Définition des tables
        self._define_tables()
    
    def _define_tables(self):
        """Définit les tables pour le service NILM CNN"""
        
        # Table des appareils
        self.cnn_appliances = Table(
            'cnn_appliances',
            self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('name', String(255), nullable=False),
            Column('description', String(1000)),
            Column('created_at', DateTime, default=datetime.utcnow),
            Column('updated_at', DateTime, default=datetime.utcnow, onupdate=datetime.utcnow),
            Index('idx_cnn_appliances_name', 'name')
        )
        
        # Table des signatures de courbes (soumises par utilisateur)
        # Note: raw_data supprimé - les données sont récupérées depuis linky_realtime via start_time/end_time
        self.cnn_signatures = Table(
            'cnn_signatures',
            self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('appliance_id', Integer, ForeignKey('cnn_appliances.id', ondelete='CASCADE')),
            Column('start_time', DateTime, nullable=False),
            Column('end_time', DateTime, nullable=False),
            Column('avg_power', Float),
            Column('power_std', Float),
            Column('energy_consumed', Float),  # Énergie totale (Wh)
            Column('features', JSON),  # Features extraites (FFT, gradients, etc.)
            Column('created_at', DateTime, default=datetime.utcnow),
            Index('idx_cnn_signatures_appliance', 'appliance_id'),
            Index('idx_cnn_signatures_time', 'start_time', 'end_time')
        )
        
        # Table des détections d'appareils
        self.cnn_detections = Table(
            'cnn_detections',
            self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('appliance_id', Integer, ForeignKey('cnn_appliances.id', ondelete='SET NULL'), nullable=True),
            Column('signature_id', Integer, ForeignKey('cnn_signatures.id', ondelete='SET NULL'), nullable=True),
            Column('start_time', DateTime, nullable=False),
            Column('end_time', DateTime, nullable=False),
            Column('avg_power', Float),
            Column('energy_consumed', Float),  # Énergie désagrégée (Wh)
            Column('confidence_score', Float),  # Score de confiance [0-1]
            Column('prediction_class', Integer),  # Classe prédite par CNN
            Column('features', JSON),  # Features de la détection
            Column('created_at', DateTime, default=datetime.utcnow),
            Index('idx_cnn_detections_appliance', 'appliance_id'),
            Index('idx_cnn_detections_time', 'start_time', 'end_time')
        )
        
        # Table des modèles CNN versionnés
        self.cnn_models = Table(
            'cnn_models',
            self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('version', String(50), unique=True, nullable=False),
            Column('model_type', String(100), default='CNN1D'),
            Column('architecture', JSON),  # Architecture du modèle
            Column('training_date', DateTime, default=datetime.utcnow),
            Column('num_signatures', Integer),  # Nombre de signatures d'entraînement
            Column('num_classes', Integer),  # Nombre de classes
            Column('metrics', JSON),  # Métriques de performance (accuracy, loss, etc.)
            Column('model_path', String(500)),
            Column('is_active', Boolean, default=False),
            Column('training_duration_seconds', Integer),  # Durée d'entraînement (secondes)
            Index('idx_cnn_models_version', 'version'),
            Index('idx_cnn_models_active', 'is_active')
        )
    
    @contextmanager
    def get_session(self):
        """Context manager pour obtenir une session de base de données"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Erreur de session: {e}")
            raise
        finally:
            session.close()
    
    def test_connection(self) -> bool:
        """Teste la connexion à la base de données"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Connexion à TimescaleDB: OK")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Erreur de connexion à TimescaleDB: {e}")
            return False
    
    def init_tables(self):
        """Initialise les tables CNN NILM dans TimescaleDB"""
        try:
            with self.engine.connect() as conn:
                # Créer les tables si elles n'existent pas
                self.metadata.create_all(self.engine)
                logger.info("Tables CNN NILM créées avec succès")
                
                # Vérifier si les tables existent
                for table_name in ['cnn_appliances', 'cnn_signatures', 'cnn_detections', 'cnn_models']:
                    result = conn.execute(text(
                        f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}')"
                    ))
                    exists = result.scalar()
                    status = 'existe' if exists else "n'existe pas"
                    logger.info(f"Table {table_name}: {status}")
                
                conn.commit()
                
        except SQLAlchemyError as e:
            logger.error(f"Erreur lors de l'initialisation des tables: {e}")
            raise
    
    def get_consumption_data(
        self, 
        start_time: datetime, 
        end_time: datetime,
        resample_seconds: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Récupère les données de consommation depuis linky_realtime
        
        Args:
            start_time: Début de la période
            end_time: Fin de la période
            resample_seconds: Intervalle de rééchantillonnage (secondes)
            
        Returns:
            Liste de dictionnaires avec time et papp
        """
        try:
            with self.engine.connect() as conn:
                query = text("""
                    SELECT 
                        time_bucket(:interval, time) as bucket_time,
                        AVG(papp) as avg_papp
                    FROM linky_realtime
                    WHERE time >= :start_time AND time <= :end_time
                    GROUP BY bucket_time
                    ORDER BY bucket_time ASC
                """)
                
                result = conn.execute(
                    query,
                    {
                        'interval': f"{resample_seconds} seconds",
                        'start_time': start_time,
                        'end_time': end_time
                    }
                )
                
                data = [
                    {'time': row.bucket_time, 'papp': float(row.avg_papp)}
                    for row in result
                ]
                
                logger.info(f"Récupéré {len(data)} points de consommation")
                return data
                
        except SQLAlchemyError as e:
            logger.error(f"Erreur lors de la récupération des données: {e}")
            return []
    
    def add_signature(
        self,
        appliance_id: int,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[int]:
        """
        Ajoute une signature de courbe soumise par l'utilisateur
        
        Args:
            appliance_id: ID de l'appareil
            start_time: Début de la signature
            end_time: Fin de la signature
            
        Returns:
            ID de la signature créée ou None si erreur
        """
        try:
            # Vérifier les chevauchements avec d'autres signatures du même appareil
            with self.engine.connect() as conn:
                overlap_query = text("""
                    SELECT id, start_time, end_time
                    FROM cnn_signatures
                    WHERE appliance_id = :appliance_id
                    AND (
                        (start_time <= :start_time AND end_time > :start_time)
                        OR (start_time < :end_time AND end_time >= :end_time)
                        OR (start_time >= :start_time
                            AND end_time <= :end_time)
                    )
                    LIMIT 1
                """)
                
                result = conn.execute(
                    overlap_query,
                    {
                        'appliance_id': appliance_id,
                        'start_time': start_time,
                        'end_time': end_time
                    }
                )
                
                overlap = result.first()
                if overlap:
                    logger.error(
                        f"Chevauchement détecté avec signature {overlap.id} "
                        f"({overlap.start_time} - {overlap.end_time})"
                    )
                    raise ValueError(
                        f"Cette période chevauche une signature existante "
                        f"({overlap.start_time.strftime('%Y-%m-%d %H:%M')} - "
                        f"{overlap.end_time.strftime('%Y-%m-%d %H:%M')})"
                    )
            
            # Récupérer les données de consommation pour validation et statistiques
            consumption_data = self.get_consumption_data(start_time, end_time)
            
            if not consumption_data:
                logger.error("Aucune donnée de consommation trouvée pour cette période")
                return None
            
            # Calculer les statistiques
            power_values = [d['papp'] for d in consumption_data]
            avg_power = sum(power_values) / len(power_values)
            power_std = (sum((p - avg_power) ** 2 for p in power_values) / len(power_values)) ** 0.5
            
            # Calculer l'énergie consommée (Wh)
            duration_hours = (end_time - start_time).total_seconds() / 3600
            energy_consumed = avg_power * duration_hours
            
            # Extraire les features (pour optimiser l'entraînement)
            features = self._extract_basic_features(power_values)
            
            with self.get_session() as session:
                # Note: raw_data supprimé - les données sont récupérées
                # depuis linky_realtime
                query = text("""
                    INSERT INTO cnn_signatures
                    (appliance_id, start_time, end_time, avg_power,
                     power_std, energy_consumed, features, created_at)
                    VALUES (:appliance_id, :start_time, :end_time,
                            :avg_power, :power_std, :energy_consumed,
                            cast(:features as jsonb), NOW())
                    RETURNING id
                """)

                result = session.execute(
                    query,
                    {
                        'appliance_id': appliance_id,
                        'start_time': start_time,
                        'end_time': end_time,
                        'avg_power': avg_power,
                        'power_std': power_std,
                        'energy_consumed': energy_consumed,
                        'features': json.dumps(features) if features else '{}'
                    }
                )
                
                signature_id = result.scalar()
                
                logger.info(f"Signature {signature_id} ajoutée pour l'appareil {appliance_id}")
                return signature_id
                
        except SQLAlchemyError as e:
            logger.error(f"Erreur lors de l'ajout de la signature: {e}")
            return None
    
    def _extract_basic_features(self, power_values: List[float]) -> Dict[str, Any]:
        """
        Extrait les features basiques d'une signature
        
        Args:
            power_values: Liste de valeurs de puissance
            
        Returns:
            Dictionnaire de features
        """
        import numpy as np
        
        power_array = np.array(power_values)
        features = {
            'mean': float(np.mean(power_array)),
            'std': float(np.std(power_array)),
            'min': float(np.min(power_array)),
            'max': float(np.max(power_array)),
            'median': float(np.median(power_array)),
            'q25': float(np.percentile(power_array, 25)),
            'q75': float(np.percentile(power_array, 75)),
        }
        
        # Gradients si suffisamment de données
        if len(power_array) > 1:
            gradients = np.gradient(power_array)
            features['gradient_mean'] = float(np.mean(gradients))
            features['gradient_std'] = float(np.std(gradients))
        
        return features
    
    def get_all_signatures(self) -> List[Dict[str, Any]]:
        """
        Récupère toutes les signatures pour l'entraînement
        Note: raw_data est récupéré à la volée depuis linky_realtime
        
        Returns:
            Liste de signatures avec leurs données (raw_data récupéré dynamiquement)
        """
        try:
            with self.engine.connect() as conn:
                query_text = """
                    SELECT
                        s.id, s.appliance_id, s.start_time, s.end_time,
                        s.avg_power, s.power_std, s.energy_consumed,
                        s.features,
                        a.name as appliance_name
                    FROM cnn_signatures s
                    JOIN cnn_appliances a ON s.appliance_id = a.id
                    ORDER BY s.created_at DESC
                """

                result = conn.execute(text(query_text))

                signatures = []
                for row in result:
                    sig = {
                        'id': row.id,
                        'appliance_id': row.appliance_id,
                        'appliance_name': row.appliance_name,
                        'start_time': row.start_time,
                        'end_time': row.end_time,
                        'avg_power': row.avg_power,
                        'power_std': row.power_std,
                        'energy_consumed': row.energy_consumed,
                        'features': row.features
                    }

                    # Récupérer les données brutes depuis linky_realtime
                    raw_data = self.get_consumption_data(
                        row.start_time,
                        row.end_time
                    )
                    sig['raw_data'] = raw_data

                    signatures.append(sig)

                logger.info(f"Récupéré {len(signatures)} signatures")
                return signatures
                
        except SQLAlchemyError as e:
            logger.error(f"Erreur lors de la récupération des signatures: {e}")
            return []


# Instance globale du gestionnaire de base de données
db_manager = DatabaseManager()
