from celery import Celery
from celery.schedules import crontab
from datetime import datetime, timedelta
import logging
import multiprocessing
import torch

from .config import settings
from .database import db_manager, Appliance
from .nilm import nilm_detector

# Configuration du multiprocessing pour CUDA
multiprocessing.set_start_method('spawn', force=True)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialisation de Celery (réutilisation du broker Redis existant)
celery_app = Celery(
    'nilmia-nilm',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 heure max pour le training
    worker_prefetch_multiplier=1,
    # Configuration pour CUDA
    worker_pool='solo',  # Force single process pour éviter les pb CUDA
)

# Configuration du beat schedule
celery_app.conf.beat_schedule = {
    'train-nilm-model': {
        'task': 'train_nilm_model',
        'schedule': crontab(hour=f'*/{settings.training_interval_hours}', minute=0),
    },
    'detect-appliances': {
        'task': 'detect_appliances_task',
        'schedule': crontab(minute=f'*/{settings.detection_interval_minutes}'),
    },
}


@celery_app.task(name='init_nilm_database')
def init_nilm_database():
    """Initialise la base de données NILM"""
    logger.info("Initialisation de la base de données NILM...")
    try:
        db_manager.init_nilm_db()
        logger.info("Base de données NILM initialisée avec succès")
        return {"status": "success", "message": "NILM database initialized"}
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation NILM: {e}")
        return {"status": "error", "message": str(e)}


@celery_app.task(name='train_nilm_model', bind=True)
def train_nilm_model(self):
    """
    Entraîne le modèle NILM sur les données historiques
    Tâche périodique (toutes les 24h par défaut)
    """
    logger.info("=== Démarrage de l'entraînement du modèle NILM ===")
    
    try:
        # Récupération des données des dernières 48h pour l'entraînement
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=48)
        
        logger.info(f"Récupération des données de {start_time} à {end_time}")
        training_data = db_manager.get_linky_data(start_time, end_time)
        
        if len(training_data) < 1000:
            logger.warning(f"Pas assez de données pour l'entraînement: {len(training_data)} points")
            return {
                "status": "skipped",
                "message": "Not enough data for training",
                "data_points": len(training_data)
            }
        
        logger.info(f"{len(training_data)} points de données récupérés")
        
        # Entraînement du modèle
        metrics = nilm_detector.train_clustering_model(training_data)
        
        logger.info("=== Entraînement terminé avec succès ===")
        logger.info(f"Métriques: {metrics}")
        
        return {
            "status": "success",
            "data_points": len(training_data),
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de l'entraînement du modèle: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@celery_app.task(name='detect_appliances_task', bind=True)
def detect_appliances_task(self):
    """
    Détecte les appareils en fonctionnement
    Tâche périodique (toutes les 5 minutes par défaut)
    """
    logger.info("=== Démarrage de la détection d'appareils ===")
    
    try:
        # Chargement du modèle actif
        if not nilm_detector.load_model():
            logger.warning("Aucun modèle chargé, entraînement nécessaire")
            return {
                "status": "skipped",
                "message": "No trained model available"
            }
        
        # Analyse de la dernière fenêtre
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=settings.window_size_minutes)
        
        logger.info(f"Analyse de la période {start_time} à {end_time}")
        
        # Détection
        detections = nilm_detector.detect_appliances(start_time, end_time)
        
        # Sauvegarde des détections
        saved_count = 0
        for detection in detections:
            # Vérification si un appareil existe pour ce cluster
            session = db_manager.Session()
            try:
                appliance = session.query(Appliance).filter_by(
                    cluster_id=detection['cluster_id']
                ).first()
                
                if appliance is None:
                    # Création d'un nouvel appareil non identifié
                    appliance = Appliance(
                        name=f"Appareil inconnu #{detection['cluster_id']}",
                        description="Détecté automatiquement, identification requise",
                        is_validated=False,
                        cluster_id=detection['cluster_id'],
                        avg_power=detection['avg_power']
                    )
                    session.add(appliance)
                    session.commit()
                    logger.info(f"Nouvel appareil créé: {appliance.name}")
                
                # Sauvegarde de l'événement de détection
                db_manager.save_detection_event(
                    appliance_id=appliance.id,
                    start_time=detection['start_time'],
                    end_time=detection['end_time'],
                    confidence=detection['confidence'],
                    avg_power=detection['avg_power'],
                    energy=detection['energy_wh']
                )
                saved_count += 1
                
            finally:
                session.close()
        
        logger.info(f"=== {saved_count} événements sauvegardés ===")
        
        return {
            "status": "success",
            "detections_count": len(detections),
            "saved_count": saved_count,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Erreur lors de la détection: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@celery_app.task(name='add_manual_signature')
def add_manual_signature(appliance_name: str, start_time: str, end_time: str, 
                        description: str = None):
    """
    Permet à l'utilisateur d'ajouter manuellement une signature d'appareil
    
    Args:
        appliance_name: Nom de l'appareil
        start_time: Timestamp de début (ISO format)
        end_time: Timestamp de fin (ISO format)
        description: Description optionnelle
    """
    logger.info(f"Ajout manuel de signature pour: {appliance_name}")
    
    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
        
        # Récupération des données pour cette période
        data = db_manager.get_linky_data(start_dt, end_dt)
        
        if len(data) == 0:
            return {
                "status": "error",
                "message": "No data found for this time period"
            }
        
        # Extraction des features
        from .nilm import SignatureExtractor
        import numpy as np
        power_values = np.array([d[1] for d in data])  # d[1] = papp
        timestamps = np.array([d[0] for d in data])
        
        features = SignatureExtractor.extract_features(power_values, timestamps)
        
        # Création ou récupération de l'appareil
        session = db_manager.Session()
        try:
            appliance = session.query(Appliance).filter_by(name=appliance_name).first()
            
            if appliance is None:
                appliance = Appliance(
                    name=appliance_name,
                    description=description,
                    is_validated=True,
                    avg_power=features.get('mean_power'),
                    max_power=features.get('max_power'),
                    min_power=features.get('min_power'),
                    power_variance=features.get('variance'),
                    signature_features=features
                )
                session.add(appliance)
                session.commit()
                logger.info(f"Nouvel appareil créé: {appliance_name}")
            
            # Ajout de la signature
            from .database import ApplianceSignature
            signature = ApplianceSignature(
                appliance_id=appliance.id,
                start_time=start_dt,
                end_time=end_dt,
                is_training_data=True,
                added_by_user=True
            )
            session.add(signature)
            session.commit()
            
            logger.info(f"Signature ajoutée pour {appliance_name}")
            
            return {
                "status": "success",
                "appliance_id": appliance.id,
                "signature_id": signature.id,
                "features": features
            }
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout de signature: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@celery_app.task(name='validate_detection')
def validate_detection(detection_id: int, is_correct: bool, correct_appliance_id: int = None):
    """
    Valide ou corrige une détection
    
    Args:
        detection_id: ID de l'événement de détection
        is_correct: True si la détection est correcte
        correct_appliance_id: ID du bon appareil si la détection était incorrecte
    """
    logger.info(f"Validation de la détection #{detection_id}")
    
    try:
        session = db_manager.Session()
        try:
            from .database import DetectionEvent
            detection = session.query(DetectionEvent).filter_by(id=detection_id).first()
            
            if detection is None:
                return {"status": "error", "message": "Detection not found"}
            
            if is_correct:
                detection.is_validated = True
                logger.info("Détection validée comme correcte")
            else:
                if correct_appliance_id:
                    detection.appliance_id = correct_appliance_id
                    detection.is_validated = True
                    logger.info(f"Détection corrigée -> appareil #{correct_appliance_id}")
                else:
                    detection.is_validated = False
                    logger.info("Détection marquée comme incorrecte")
            
            session.commit()
            
            return {
                "status": "success",
                "detection_id": detection_id,
                "is_validated": detection.is_validated
            }
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Erreur lors de la validation: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@celery_app.task(name='get_detection_stats')
def get_detection_stats(hours: int = 24):
    """
    Récupère les statistiques de détection
    
    Args:
        hours: Nombre d'heures à analyser
    """
    try:
        session = db_manager.Session()
        try:
            from sqlalchemy import text
            
            since = datetime.utcnow() - timedelta(hours=hours)
            
            result = session.execute(
                text("""
                    SELECT 
                        a.name,
                        COUNT(*) as detection_count,
                        SUM(d.energy_consumed) as total_energy_wh,
                        AVG(d.avg_power) as avg_power,
                        AVG(d.confidence_score) as avg_confidence
                    FROM detection_events d
                    JOIN appliances a ON d.appliance_id = a.id
                    WHERE d.start_time >= :since
                    GROUP BY a.id, a.name
                    ORDER BY total_energy_wh DESC
                """),
                {"since": since}
            ).fetchall()
            
            stats = []
            for row in result:
                stats.append({
                    "appliance": row[0],
                    "detection_count": row[1],
                    "total_energy_wh": float(row[2]) if row[2] else 0,
                    "avg_power": float(row[3]) if row[3] else 0,
                    "avg_confidence": float(row[4]) if row[4] else 0
                })
            
            return {
                "status": "success",
                "period_hours": hours,
                "stats": stats
            }
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
