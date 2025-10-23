"""
Tâches Celery pour nilm-cnn-service
"""
import json
import logging
import warnings
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Filtrer les warnings Celery root avant les imports
os.environ['C_FORCE_ROOT'] = 'true'
warnings.filterwarnings('ignore', message='.*superuser privileges.*')

from celery import Celery
from celery.schedules import crontab

from .config import settings
from .database import db_manager
from .cnn_nilm import cnn_model

# Configuration du logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Vérifier la disponibilité du GPU (sauf si CUDA_VISIBLE_DEVICES est vide)
if os.environ.get('CUDA_VISIBLE_DEVICES', '0') != '':
    try:
        import tensorflow as tf
        gpus = tf.config.list_physical_devices('GPU')
        if gpus:
            logger.info(f"🎮 GPU disponibles: {len(gpus)}")
            for gpu in gpus:
                logger.info(f"   - {gpu.name}")
            # Activer la croissance mémoire dynamique
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
        else:
            logger.warning("⚠️  Aucun GPU détecté, utilisation du CPU")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la vérification GPU: {e}")
else:
    # Beat n'a pas besoin de GPU, importer TensorFlow sans init GPU
    logger.info("ℹ️  Mode CPU uniquement (planificateur)")
    import tensorflow as tf

# Initialisation de Celery
celery_app = Celery(
    'nilm_cnn_tasks',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend
)

# Configuration Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 heure max par tâche
    worker_pool='solo',  # Pour éviter les conflits avec TensorFlow
)


@celery_app.task(name='init_cnn_database')
def init_cnn_database() -> Dict[str, Any]:
    """
    Initialise les tables CNN NILM dans TimescaleDB
    
    Returns:
        Statut de l'initialisation
    """
    try:
        logger.info("Initialisation des tables CNN NILM...")
        
        # Tester la connexion
        if not db_manager.test_connection():
            return {'status': 'error', 'message': 'Connexion à la base de données échouée'}
        
        # Créer les tables
        db_manager.init_tables()
        
        logger.info("Tables CNN NILM initialisées avec succès")
        
        return {
            'status': 'success',
            'message': 'Tables CNN NILM créées',
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation: {e}")
        return {'status': 'error', 'message': str(e)}


@celery_app.task(name='train_cnn_model')
def train_cnn_model(min_signatures: int = 10) -> Dict[str, Any]:
    """
    Entraîne le modèle CNN sur les signatures disponibles
    
    Args:
        min_signatures: Nombre minimum de signatures requises
        
    Returns:
        Statut et métriques de l'entraînement
    """
    try:
        import time
        start_time = time.time()
        
        logger.info("Démarrage de l'entraînement du modèle CNN...")
        
        # Récupérer toutes les signatures
        signatures = db_manager.get_all_signatures()
        
        if len(signatures) < min_signatures:
            message = f"Pas assez de signatures ({len(signatures)}/{min_signatures})"
            logger.warning(message)
            return {
                'status': 'skipped',
                'message': message,
                'num_signatures': len(signatures)
            }
        
        # Créer une version basée sur le timestamp
        version = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        
        # Entraîner le modèle
        metrics = cnn_model.train(signatures, version)
        
        if not metrics:
            return {
                'status': 'error',
                'message': 'Entraînement échoué',
                'num_signatures': len(signatures)
            }
        
        # Calculer la durée d'entraînement
        training_duration = int(time.time() - start_time)
        
        # Sauvegarder les informations du modèle en base
        from sqlalchemy import text
        import json
        with db_manager.get_session() as session:
            # Obtenir l'architecture du modèle
            architecture = {
                'type': 'CNN1D',
                'sequence_length': settings.cnn_sequence_length,
                'num_classes': len(cnn_model.class_names),
                'class_names': cnn_model.class_names
            }
            
            query = text("""
                INSERT INTO cnn_models 
                (version, model_type, architecture, training_date, 
                 num_signatures, num_classes, metrics, model_path, 
                 is_active, training_duration_seconds)
                VALUES 
                (:version, :model_type, cast(:architecture as jsonb), 
                 :training_date, :num_signatures, :num_classes,
                 cast(:metrics as jsonb), :model_path, :is_active,
                 :training_duration_seconds)
                RETURNING id
            """)
            
            result = session.execute(
                query,
                {
                    'version': version,
                    'model_type': 'CNN1D',
                    'architecture': json.dumps(architecture),
                    'training_date': datetime.utcnow(),
                    'num_signatures': len(signatures),
                    'num_classes': len(cnn_model.class_names),
                    'metrics': json.dumps(metrics, default=str),
                    'model_path': f"{settings.cnn_model_path}/model_{version}.keras",
                    'is_active': True,
                    'training_duration_seconds': training_duration
                }
            )
            
            model_id = result.scalar()
            
            # Désactiver les anciens modèles
            session.execute(
                text("UPDATE cnn_models SET is_active = FALSE WHERE id != :id"),
                {'id': model_id}
            )
        
        logger.info(f"Modèle {version} entraîné avec succès en {training_duration}s: accuracy={metrics.get('val_accuracy', 0):.3f}")
        
        return {
            'status': 'success',
            'version': version,
            'num_signatures': len(signatures),
            'num_classes': len(cnn_model.class_names),
            'metrics': metrics,
            'training_duration_seconds': training_duration,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de l'entraînement: {e}", exc_info=True)
        return {'status': 'error', 'message': str(e)}


@celery_app.task(name='detect_cnn_appliances')
def detect_cnn_appliances(
    hours: int = None,
    min_confidence: float = 0.6
) -> Dict[str, Any]:
    """
    Détecte les appareils dans la période récente
    
    Args:
        hours: Nombre d'heures à analyser (défaut: depuis config)
        min_confidence: Seuil de confiance minimal
        
    Returns:
        Statut et nombre de détections
    """
    try:
        # Utiliser la valeur de configuration par défaut si non spécifié
        if hours is None:
            hours = settings.cnn_detection_period_hours
        
        logger.info(f"Détection d'appareils sur les {hours} dernières heures...")
        
        # Vérifier qu'un modèle est disponible
        from sqlalchemy import text
        with db_manager.engine.connect() as conn:
            result = conn.execute(
                text("SELECT version FROM cnn_models WHERE is_active = TRUE ORDER BY training_date DESC LIMIT 1")
            )
            row = result.first()
            
            if not row:
                message = "Aucun modèle actif disponible"
                logger.warning(message)
                return {'status': 'skipped', 'message': message}
            
            active_version = row.version
        
        # Charger le modèle
        if not cnn_model.load_model(active_version):
            return {'status': 'error', 'message': 'Échec du chargement du modèle'}
        
        # Définir la période d'analyse
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        # Détecter les événements
        events = cnn_model.detect_events(start_time, end_time, min_confidence)
        
        if not events:
            logger.info("Aucun événement détecté")
            return {
                'status': 'success',
                'num_detections': 0,
                'period': {'start': start_time.isoformat(), 'end': end_time.isoformat()}
            }
        
        # Sauvegarder les détections en base
        num_saved = 0
        with db_manager.get_session() as session:
            for event in events:
                # Trouver l'ID de l'appareil par son nom
                result = session.execute(
                    text("SELECT id FROM cnn_appliances WHERE name = :name LIMIT 1"),
                    {'name': event['appliance_name']}
                )
                row = result.first()
                appliance_id = row.id if row else None
                
                # Insérer la détection
                query = text("""
                    INSERT INTO cnn_detections
                    (appliance_id, start_time, end_time, avg_power, energy_consumed,
                     confidence_score, prediction_class, features, created_at)
                    VALUES
                    (:appliance_id, :start_time, :end_time, :avg_power, :energy_consumed,
                     :confidence_score, :prediction_class, :features, NOW())
                """)
                
                session.execute(
                    query,
                    {
                        'appliance_id': appliance_id,
                        'start_time': event['start_time'],
                        'end_time': event['end_time'],
                        'avg_power': event['avg_power'],
                        'energy_consumed': event['energy_consumed'],
                        'confidence_score': event['confidence_score'],
                        'prediction_class': event.get('prediction_class'),
                        'features': json.dumps({
                            'probabilities': event['probabilities']
                        })
                    }
                )
                num_saved += 1
        
        logger.info(f"{num_saved} détections sauvegardées")
        
        return {
            'status': 'success',
            'num_detections': num_saved,
            'model_version': active_version,
            'period': {'start': start_time.isoformat(), 'end': end_time.isoformat()},
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la détection: {e}", exc_info=True)
        return {'status': 'error', 'message': str(e)}


@celery_app.task(name='add_cnn_signature')
def add_cnn_signature(
    appliance_name: str,
    start_time_str: str,
    end_time_str: str,
    mode: Optional[str] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ajoute une signature manuelle soumise par l'utilisateur
    
    Args:
        appliance_name: Nom de l'appareil
        start_time_str: Timestamp de début (ISO format)
        end_time_str: Timestamp de fin (ISO format)
        mode: Mode de fonctionnement (optionnel)
        description: Description (optionnel)
        
    Returns:
        Statut et ID de la signature créée
    """
    try:
        logger.info(f"Ajout de signature pour {appliance_name}...")
        
        # Parser les dates
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
        
        # Vérifier la durée
        duration = (end_time - start_time).total_seconds()
        if duration < settings.cnn_min_duration_seconds:
            return {
                'status': 'error',
                'message': f'Durée trop courte (minimum {settings.cnn_min_duration_seconds}s)'
            }
        
        from sqlalchemy import text
        
        # Trouver ou créer l'appareil
        with db_manager.get_session() as session:
            result = session.execute(
                text("SELECT id FROM cnn_appliances WHERE name = :name LIMIT 1"),
                {'name': appliance_name}
            )
            row = result.first()
            
            if row:
                appliance_id = row.id
            else:
                # Créer un nouvel appareil
                result = session.execute(
                    text("""
                        INSERT INTO cnn_appliances
                        (name, description, created_at, updated_at)
                        VALUES (:name, :description, NOW(), NOW())
                        RETURNING id
                    """),
                    {'name': appliance_name, 'description': description}
                )
                appliance_id = result.scalar()
                logger.info(
                    f"Appareil créé: {appliance_name} (ID: {appliance_id})"
                )
        
        # Ajouter la signature
        try:
            signature_id = db_manager.add_signature(
                appliance_id=appliance_id,
                start_time=start_time,
                end_time=end_time,
                mode=mode
            )
        except ValueError as ve:
            # Erreur de validation (chevauchement, etc.)
            logger.warning(f"Validation échouée: {ve}")
            return {
                'status': 'error',
                'error_type': 'validation',
                'message': str(ve)
            }
        
        if not signature_id:
            return {
                'status': 'error',
                'message': 'Échec de l\'ajout de la signature'
            }
        
        logger.info(f"Signature {signature_id} ajoutée avec succès")
        
        # Déclencher un réentraînement si assez de signatures
        signatures = db_manager.get_all_signatures()
        if len(signatures) >= 10 and len(signatures) % 5 == 0:
            train_cnn_model.delay()
            logger.info("Réentraînement du modèle déclenché")
        
        return {
            'status': 'success',
            'signature_id': signature_id,
            'appliance_id': appliance_id,
            'appliance_name': appliance_name,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            f"Erreur lors de l'ajout de signature: {e}",
            exc_info=True
        )
        return {'status': 'error', 'message': str(e)}


@celery_app.task(name='get_cnn_stats')
def get_cnn_stats() -> Dict[str, Any]:
    """
    Récupère les statistiques du service CNN NILM
    
    Returns:
        Statistiques complètes
    """
    try:
        from sqlalchemy import text
        
        stats = {}
        
        with db_manager.engine.connect() as conn:
            # Nombre d'appareils
            result = conn.execute(text("SELECT COUNT(*) FROM cnn_appliances"))
            stats['num_appliances'] = result.scalar()
            
            # Nombre de signatures
            result = conn.execute(text("SELECT COUNT(*) FROM cnn_signatures"))
            stats['num_signatures'] = result.scalar()
            
            # Nombre de détections
            result = conn.execute(text("SELECT COUNT(*) FROM cnn_detections"))
            stats['num_detections'] = result.scalar()
            
            # Nombre de modèles
            result = conn.execute(text("SELECT COUNT(*) FROM cnn_models"))
            stats['num_models'] = result.scalar()
            
            # Modèle actif
            result = conn.execute(
                text("SELECT version, num_classes, metrics FROM cnn_models WHERE is_active = TRUE LIMIT 1")
            )
            row = result.first()
            if row:
                stats['active_model'] = {
                    'version': row.version,
                    'num_classes': row.num_classes,
                    'metrics': row.metrics
                }
            
            # Statistiques par appareil
            result = conn.execute(text("""
                SELECT 
                    a.name,
                    COUNT(DISTINCT s.id) as num_signatures,
                    COUNT(DISTINCT d.id) as num_detections
                FROM cnn_appliances a
                LEFT JOIN cnn_signatures s ON a.id = s.appliance_id
                LEFT JOIN cnn_detections d ON a.id = d.appliance_id
                GROUP BY a.id, a.name
                ORDER BY a.name
            """))
            
            stats['appliances'] = [
                {
                    'name': row.name,
                    'num_signatures': row.num_signatures,
                    'num_detections': row.num_detections
                }
                for row in result
            ]
        
        stats['timestamp'] = datetime.utcnow().isoformat()
        
        logger.info(f"Statistiques CNN: {stats['num_appliances']} appareils, {stats['num_signatures']} signatures")
        
        return stats
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats: {e}")
        return {'status': 'error', 'message': str(e)}


# Configuration des tâches périodiques
celery_app.conf.beat_schedule = {
    'train-cnn-model': {
        'task': 'train_cnn_model',
        'schedule': crontab(hour=f'*/{settings.cnn_training_interval_hours}', minute=0),
    },
    'detect-cnn-appliances': {
        'task': 'detect_cnn_appliances',
        'schedule': settings.cnn_detection_interval_minutes * 60.0,
        'kwargs': {'hours': 1, 'min_confidence': 0.6}
    },
    'get-cnn-stats': {
        'task': 'get_cnn_stats',
        'schedule': 300.0,  # Toutes les 5 minutes
    },
}
