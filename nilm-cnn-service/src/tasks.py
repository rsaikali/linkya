"""
Tâches Celery pour nilm-cnn-service
"""
import json
import logging
import warnings
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo

# Filtrer les warnings Celery root avant les imports
os.environ['C_FORCE_ROOT'] = 'true'
warnings.filterwarnings('ignore', message='.*superuser privileges.*')

from celery import Celery
from celery.schedules import crontab

# Configuration du logger (doit être avant les imports locaux)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

LOCAL_TIMEZONE = ZoneInfo(os.environ.get('TZ', 'Europe/Paris'))

from .config import settings
from .database import db_manager

from .seq2point_nilm import Seq2PointNILMManager
logger.info("🚀 Mode Sequence-to-Point (S2P) activé")
nilm_manager = Seq2PointNILMManager()

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
def train_cnn_model(min_signatures: int = 2) -> Dict[str, Any]:
    """
    Entraîne le modèle NILM (S2P ou CNN legacy) sur les signatures
    
    Args:
        min_signatures: Nombre minimum de signatures par appareil
        
    Returns:
        Statut et métriques de l'entraînement
    """
    try:
        import time
        from sqlalchemy import text
        import json
        
        start_time = time.time()
        
        logger.info("🚀 Entraînement Sequence-to-Point (désagrégation multi-sorties)")
        # Créer une version basée sur le timestamp (timezone locale)
        version = datetime.now(LOCAL_TIMEZONE).strftime('%Y%m%d_%H%M%S')
        # Entraîner le modèle multi-sorties
        metrics = nilm_manager.train_all_appliances(version)
        if 'error' in metrics:
            return {
                'status': 'error',
                'message': metrics.get('error'),
                'details': metrics
            }
        # Préparer les infos pour la base
        num_appliances = metrics.get('num_appliances', 0)
        total_signatures = sum(
            app['num_signatures'] 
            for app in metrics.get('appliances', [])
        )
        architecture = {
            'type': f'S2P-MULTI-{nilm_manager.model_type.upper()}',
            'sequence_length': settings.effective_sequence_length,
            'num_appliances': num_appliances,
            'model_type': nilm_manager.model_type,
            'appliances': metrics.get('appliances', [])
        }
        model_type_str = f'S2P-MULTI-{nilm_manager.model_type.upper()}'
        
        # Calculer la durée
        training_duration = int(time.time() - start_time)
        
        # Sauvegarder en base
        completed_at = datetime.now(LOCAL_TIMEZONE)
        with db_manager.get_session() as session:
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
                    'model_type': model_type_str,
                    'architecture': json.dumps(architecture),
                    'training_date': completed_at,
                    'num_signatures': total_signatures,
                    'num_classes': num_appliances,
                    'metrics': json.dumps(metrics, default=str),
                    'model_path': metrics.get('model_path', f"{settings.cnn_model_path}/{version}"),
                    'is_active': True,
                    'training_duration_seconds': training_duration
                }
            )
            
            model_id = result.scalar()
            
            # Désactiver les anciens modèles
            session.execute(
                text("UPDATE cnn_models SET is_active = FALSE "
                     "WHERE id != :id"),
                {'id': model_id}
            )
        
        logger.info(
            f"✅ Modèle {version} entraîné en {training_duration}s - "
            f"{num_appliances} appareils, {total_signatures} signatures"
        )
        
        return {
            'status': 'success',
            'version': version,
            'model_type': model_type_str,
            'num_signatures': total_signatures,
            'num_appliances': num_appliances,
            'metrics': metrics,
            'training_duration_seconds': training_duration,
            'timestamp': completed_at.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur entraînement: {e}", exc_info=True)
        return {'status': 'error', 'message': str(e)}


@celery_app.task(name='detect_cnn_appliances')
def detect_cnn_appliances(
    hours: int = None,
    min_confidence: float = 0.3
) -> Dict[str, Any]:
    """
    Détecte et désagrège les appareils (S2P ou CNN legacy)
    
    Args:
        hours: Nombre d'heures à analyser (défaut: depuis config)
        min_confidence: Seuil de confiance minimal
        
    Returns:
        Statut et nombre de détections
    """
    try:
        from sqlalchemy import text
        import json
        
        # Utiliser la valeur de configuration par défaut si non spécifié
        if hours is None:
            hours = settings.cnn_detection_period_hours
        
        logger.info(f"Détection sur les {hours} dernières heures...")
        
        # Vérifier qu'un modèle est disponible
        with db_manager.engine.connect() as conn:
            result = conn.execute(
                text("SELECT version, model_type FROM cnn_models "
                     "WHERE is_active = TRUE "
                     "ORDER BY training_date DESC LIMIT 1")
            )
            row = result.first()
            
            if not row:
                message = "Aucun modèle actif disponible"
                logger.warning(message)
                return {'status': 'skipped', 'message': message}
            
            active_version = row.version
            model_type = row.model_type
        
        # Définir la période d'analyse
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        # Désagrégation S2P multi-sorties
        logger.info(f"🔍 Désagrégation S2P multi-sorties: {start_time} -> {end_time}")
        # Charger le modèle actif
        if not nilm_manager.models:
            if not nilm_manager.load_active_models():
                return {
                    'status': 'error',
                    'message': 'Échec chargement modèle S2P multi-sorties'
                }
        # Désagrégation
        events = nilm_manager.disaggregate(start_time, end_time)
        
        if not events:
            logger.info("Aucun événement détecté")
            return {
                'status': 'success',
                'num_detections': 0,
                'period': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                }
            }
        
        logger.info(f"📊 {len(events)} événements à traiter")
        
        # Sauvegarder les détections en base
        num_saved = 0
        num_updated = 0
        num_skipped = 0
        
        with db_manager.get_session() as session:
            for event in events:
                # Récupérer l'appliance_id (déjà présent en S2P)
                appliance_id = event.get('appliance_id')
                
                # Si pas d'appliance_id, chercher par nom (mode legacy)
                if not appliance_id:
                    result = session.execute(
                        text("SELECT id FROM cnn_appliances "
                             "WHERE name = :name LIMIT 1"),
                        {'name': event['appliance_name']}
                    )
                    row = result.first()
                    appliance_id = row.id if row else None
                
                if not appliance_id:
                    logger.warning(
                        f"Appareil inconnu: {event['appliance_name']}"
                    )
                    num_skipped += 1
                    continue
                
                # Vérifier chevauchements pour cet appareil
                check_overlap_query = text("""
                    SELECT id, confidence_score, start_time, end_time
                    FROM cnn_detections
                    WHERE appliance_id = :appliance_id
                    AND (
                        (:start_time <= end_time AND :end_time >= start_time)
                    )
                    ORDER BY confidence_score DESC
                    LIMIT 1
                """)
                
                overlap_result = session.execute(
                    check_overlap_query,
                    {
                        'appliance_id': appliance_id,
                        'start_time': event['start_time'],
                        'end_time': event['end_time']
                    }
                )
                existing = overlap_result.first()
                
                if existing:
                    # Une détection superposée existe
                    existing_id = existing.id
                    existing_confidence = float(existing.confidence_score)
                    new_confidence = float(event['confidence_score'])
                    
                    if new_confidence > existing_confidence:
                        # Mettre à jour la détection existante avec de meilleures données
                        update_query = text("""
                            UPDATE cnn_detections
                            SET start_time = :start_time,
                                end_time = :end_time,
                                avg_power = :avg_power,
                                energy_consumed = :energy_consumed,
                                confidence_score = :confidence_score,
                                prediction_class = :prediction_class,
                                signature_id = :signature_id,
                                features = :features,
                                created_at = NOW()
                            WHERE id = :detection_id
                        """)
                        
                        # Préparer features selon le mode
                        features_data = event.get('features', {})
                        if 'probabilities' in event:
                            features_data['probabilities'] = event['probabilities']
                        
                        session.execute(
                            update_query,
                            {
                                'detection_id': existing_id,
                                'start_time': event['start_time'],
                                'end_time': event['end_time'],
                                'avg_power': event['avg_power'],
                                'energy_consumed': event.get(
                                    'energy_consumed',
                                    event.get('energy_wh', 0)
                                ),
                                'confidence_score': event['confidence_score'],
                                'prediction_class': event.get('prediction_class'),
                                'signature_id': event.get('signature_id'),
                                'features': json.dumps(features_data)
                            }
                        )
                        num_updated += 1
                        logger.info(
                            f"Détection #{existing_id} mise à jour "
                            f"(confiance {existing_confidence:.2%} → {new_confidence:.2%})"
                        )
                    else:
                        # Ignorer la nouvelle détection (moins bonne confiance)
                        num_skipped += 1
                        logger.debug(
                            f"Détection ignorée pour {event['appliance_name']} "
                            f"(confiance {new_confidence:.2%} ≤ {existing_confidence:.2%})"
                        )
                else:
                    # Aucune détection superposée, insérer une nouvelle
                    # Préparer features
                    features_data = event.get('features', {})
                    if 'probabilities' in event:
                        features_data['probabilities'] = event['probabilities']
                    
                    insert_query = text("""
                        INSERT INTO cnn_detections
                        (appliance_id, signature_id, start_time, end_time,
                         avg_power, energy_consumed, confidence_score,
                         prediction_class, features, created_at)
                        VALUES
                        (:appliance_id, :signature_id, :start_time, :end_time,
                         :avg_power, :energy_consumed, :confidence_score,
                         :prediction_class, :features, NOW())
                    """)
                    
                    session.execute(
                        insert_query,
                        {
                            'appliance_id': appliance_id,
                            'signature_id': event.get('signature_id'),
                            'start_time': event['start_time'],
                            'end_time': event['end_time'],
                            'avg_power': event['avg_power'],
                            'energy_consumed': event.get(
                                'energy_consumed',
                                event.get('energy_wh', 0)
                            ),
                            'confidence_score': event['confidence_score'],
                            'prediction_class': event.get('prediction_class'),
                            'features': json.dumps(features_data)
                        }
                    )
                    num_saved += 1
                    logger.debug(
                        f"✅ Nouvelle détection: {event['appliance_name']} "
                        f"- {event.get('duration_seconds', 0)}s "
                        f"- {event['avg_power']:.1f}W"
                    )
        
        total_processed = num_saved + num_updated + num_skipped
        logger.info(
            f"Détections traitées: {total_processed} "
            f"(nouvelles: {num_saved}, mises à jour: {num_updated}, "
            f"ignorées: {num_skipped})"
        )
        
        return {
            'status': 'success',
            'num_detections': num_saved,
            'num_updated': num_updated,
            'num_skipped': num_skipped,
            'total_processed': total_processed,
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
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ajoute une signature manuelle soumise par l'utilisateur

    Args:
        appliance_name: Nom de l'appareil
        start_time_str: Timestamp de début (ISO format)
        end_time_str: Timestamp de fin (ISO format)
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
                end_time=end_time
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


@celery_app.task(name='enrich_cnn_signatures')
def enrich_cnn_signatures() -> Dict[str, Any]:
    """
    Enrichit toutes les signatures avec les cycles détectés par S2P
    
    Returns:
        Statut et nombre de signatures enrichies
    """
    try:
        logger.info("🔍 Enrichissement des signatures avec cycles...")
        
        if not USE_S2P:
            return {
                'status': 'skipped',
                'message': 'Mode S2P non disponible',
                'enriched_count': 0
            }
        
        # Charger les modèles actifs si pas déjà chargés
        if not nilm_manager.models:
            if not nilm_manager.load_active_models():
                return {
                    'status': 'error',
                    'message': 'Impossible de charger les modèles S2P',
                    'enriched_count': 0
                }
        
        # Enrichir toutes les signatures
        enriched_count = nilm_manager.enrich_all_signatures()
        
        logger.info(f"✅ {enriched_count} signatures enrichies avec cycles")
        
        return {
            'status': 'success',
            'enriched_count': enriched_count,
            'num_appliances': len(nilm_manager.models),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur enrichissement: {e}", exc_info=True)
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
        'kwargs': {'hours': 2, 'min_confidence': 0.6}  # Analyse 2h pour couvrir les cycles HC/HP
    },
    'get-cnn-stats': {
        'task': 'get_cnn_stats',
        'schedule': 300.0,  # Toutes les 5 minutes
    },
}
