import numpy as np
import pandas as pd
import torch
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import logging
import os
import pickle
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
from pypots.clustering import CRLI
from pypots.imputation import SAITS

from .config import settings
from .database import db_manager

logger = logging.getLogger(__name__)

# Configuration CUDA sécurisée pour Celery
if torch.cuda.is_available():
    # Force la synchronisation CUDA dans les workers
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


class SignatureExtractor:
    """Extracteur de features pour les signatures d'appareils"""
    
    @staticmethod
    def extract_features(power_sequence: np.ndarray, timestamps: np.ndarray) -> Dict[str, float]:
        """
        Extrait les features caractéristiques d'une séquence de puissance
        
        Args:
            power_sequence: Séquence de puissance (VA)
            timestamps: Timestamps correspondants
            
        Returns:
            Dictionnaire de features
        """
        if len(power_sequence) == 0:
            return {}
        
        # Features statistiques basiques
        features = {
            'mean_power': float(np.mean(power_sequence)),
            'max_power': float(np.max(power_sequence)),
            'min_power': float(np.min(power_sequence)),
            'std_power': float(np.std(power_sequence)),
            'variance': float(np.var(power_sequence)),
            'range': float(np.ptp(power_sequence)),
        }
        
        # Features de variation
        if len(power_sequence) > 1:
            diffs = np.diff(power_sequence)
            features.update({
                'mean_diff': float(np.mean(diffs)),
                'std_diff': float(np.std(diffs)),
                'max_increase': float(np.max(diffs)),
                'max_decrease': float(np.min(diffs)),
            })
        
        # Features de forme
        if len(power_sequence) > 2:
            # Détection de cycles/périodicité
            from scipy.signal import find_peaks
            peaks, _ = find_peaks(power_sequence, distance=5)
            features['n_peaks'] = len(peaks)
            
            if len(peaks) > 1:
                peak_intervals = np.diff(peaks)
                features['cycle_regularity'] = float(np.std(peak_intervals))
                features['avg_cycle_length'] = float(np.mean(peak_intervals))
        
        # Features temporelles
        duration = (timestamps[-1] - timestamps[0]).total_seconds()
        features['duration_seconds'] = duration
        
        # Stabilité (ratio de temps où la puissance est stable)
        if len(power_sequence) > 10:
            stable_threshold = features['std_power'] * 0.5
            stable_points = np.sum(np.abs(power_sequence - features['mean_power']) < stable_threshold)
            features['stability_ratio'] = stable_points / len(power_sequence)
        
        return features


class NilmDetector:
    """Détecteur NILM utilisant PyPOTS pour l'analyse de séries temporelles"""
    
    def __init__(self):
        self.model_path = settings.model_path
        os.makedirs(self.model_path, exist_ok=True)
        
        self.scaler = StandardScaler()
        self.clustering_model = None
        self.imputation_model = None
        
        # Détection CUDA avec vérification mémoire
        self.device = self._select_device()
        logger.info(f"Utilisation du device: {self.device}")
        if self.device == 'cuda':
            gpu_props = torch.cuda.get_device_properties(0)
            logger.info(f"GPU disponible: {gpu_props.name}")
            logger.info(f"Mémoire GPU totale: {gpu_props.total_memory / 1e9:.1f} GB")
        
        # Tentative de chargement automatique d'un modèle existant
        self._try_load_existing_model()
    
    def _select_device(self) -> str:
        """
        Sélectionne le device optimal en fonction de la mémoire disponible
        """
        if not torch.cuda.is_available():
            return 'cpu'
        
        try:
            # Test de la mémoire GPU disponible
            torch.cuda.empty_cache()
            gpu_props = torch.cuda.get_device_properties(0)
            total_memory = gpu_props.total_memory
            
            # Seuil minimum de 2GB pour utiliser GPU
            if total_memory < 2e9:
                logger.warning(f"Mémoire GPU insuffisante ({total_memory/1e9:.1f} GB), utilisation CPU")
                return 'cpu'
            
            # Test d'allocation mémoire
            test_tensor = torch.randn(1000, 1000, device='cuda')
            del test_tensor
            torch.cuda.empty_cache()
            
            return 'cuda'
        except Exception as e:
            logger.warning(f"Erreur CUDA, fallback sur CPU: {e}")
            return 'cpu'
    
    def _try_load_existing_model(self):
        """
        Tente de charger automatiquement un modèle existant
        Priorité: modèle actif en DB > dernier modèle fichier local
        """
        try:
            # 1. Essayer de charger le modèle actif depuis la DB
            if self.load_model():
                logger.info("Modèle actif chargé depuis la base de données")
                return True
            
            # 2. Sinon, chercher le modèle le plus récent dans les fichiers locaux
            model_files = []
            if os.path.exists(self.model_path):
                for filename in os.listdir(self.model_path):
                    if filename.startswith('clustering_') and filename.endswith('.pkl'):
                        model_files.append(filename)
            
            if model_files:
                # Trier par nom (qui contient timestamp) pour avoir le plus récent
                latest_model = sorted(model_files)[-1]
                model_path = os.path.join(self.model_path, latest_model)
                
                logger.info(f"Tentative de chargement du modèle local: {latest_model}")
                with open(model_path, 'rb') as f:
                    data = pickle.load(f)
                    self.clustering_model = data['clustering_model']
                    self.imputation_model = data['imputation_model']
                    self.scaler = data['scaler']
                
                logger.info(f"Modèle local chargé avec succès: {latest_model}")
                return True
            
            logger.info("Aucun modèle existant trouvé, le service devra être entraîné")
            return False
            
        except Exception as e:
            logger.warning(f"Erreur lors du chargement automatique du modèle: {e}")
            return False
    
    def _check_gpu_memory(self) -> bool:
        """
        Vérifie si assez de mémoire GPU est disponible
        """
        if self.device != 'cuda':
            return True
        
        try:
            torch.cuda.empty_cache()
            memory_allocated = torch.cuda.memory_allocated(0)
            memory_cached = torch.cuda.memory_reserved(0)
            total_memory = torch.cuda.get_device_properties(0).total_memory
            
            available_memory = total_memory - memory_allocated - memory_cached
            required_memory = 1e9  # 1GB minimum requis
            
            if available_memory < required_memory:
                logger.warning(f"Mémoire GPU insuffisante: {available_memory/1e9:.1f} GB disponible")
                return False
            
            return True
        except Exception as e:
            logger.warning(f"Erreur vérification mémoire GPU: {e}")
            return False
    
    def prepare_time_series_data(self, data: List[Tuple], window_size: int = 60) -> np.ndarray:
        """
        Prépare les données pour PyPOTS (format time series)
        
        Args:
            data: Liste de tuples (timestamp, power, temperature)
            window_size: Taille de la fenêtre glissante en minutes
            
        Returns:
            Array 3D pour PyPOTS (n_samples, n_steps, n_features)
        """
        df = pd.DataFrame(data, columns=['time', 'papp', 'temperature'])
        df['time'] = pd.to_datetime(df['time'])
        df = df.set_index('time').sort_index()
        
        # Rééchantillonnage à la seconde
        df_resampled = df.resample('1s').mean().interpolate(method='linear')
        
        # Création de fenêtres glissantes
        window_samples = window_size * 60  # Conversion en secondes
        step_size = window_samples // 2  # 50% overlap
        
        windows = []
        for i in range(0, len(df_resampled) - window_samples, step_size):
            window = df_resampled.iloc[i:i+window_samples]
            if len(window) == window_samples:
                # Features: puissance, dérivée de puissance, température
                power = window['papp'].values
                power_diff = np.gradient(power)
                temp = window['temperature'].fillna(method='ffill').fillna(20).values
                
                features = np.stack([power, power_diff, temp], axis=1)
                windows.append(features)
        
        if len(windows) == 0:
            return np.array([])
        
        return np.array(windows)
    
    def train_clustering_model(self, training_data: List[Tuple]) -> Dict[str, float]:
        """
        Entraîne le modèle de clustering pour identifier les signatures
        
        Args:
            training_data: Données d'entraînement depuis linky_realtime
            
        Returns:
            Métriques de performance
        """
        logger.info("Préparation des données d'entraînement...")
        X = self.prepare_time_series_data(training_data, settings.window_size_minutes)
        
        if len(X) == 0:
            logger.error("Aucune donnée d'entraînement préparée")
            return {}
        
        # Limitation du nombre d'échantillons pour éviter OOM
        if len(X) > settings.max_samples_training:
            logger.info(f"Limitation des échantillons de {len(X)} à {settings.max_samples_training}")
            indices = np.random.choice(len(X), settings.max_samples_training, replace=False)
            X = X[indices]
        
        logger.info(f"Données préparées: {X.shape}")
        
        # Vérification mémoire GPU et fallback si nécessaire
        if not self._check_gpu_memory():
            logger.warning("Mémoire GPU insuffisante, fallback sur CPU")
            self.device = 'cpu'
        
        # Nettoyage de la mémoire GPU avant l'entraînement
        if self.device == 'cuda':
            torch.cuda.empty_cache()
            memory_info = torch.cuda.mem_get_info()
            logger.info(f"Mémoire GPU libre: {memory_info[0] / 1e9:.1f} GB / {memory_info[1] / 1e9:.1f} GB")
        
        # Imputation des valeurs manquantes avec SAITS (paramètres optimisés mémoire)
        logger.info("Imputation des valeurs manquantes...")
        self.imputation_model = SAITS(
            n_steps=X.shape[1],
            n_features=X.shape[2],
            n_layers=1,  # Réduction du nombre de couches
            d_model=128,  # Réduction de la taille du modèle
            d_ffn=256,  # Réduction FFN
            n_heads=2,  # Réduction du nombre de têtes d'attention
            d_k=32,  # Réduction dimension key
            d_v=32,  # Réduction dimension value
            dropout=0.1,
            epochs=settings.imputation_epochs,  # Configurable
            batch_size=settings.batch_size,  # Configurable
            device=self.device
        )
        
        # PyPOTS attend un format spécifique avec masques
        X_with_mask = {
            'X': X,
        }
        
        try:
            # Nettoyage mémoire avant imputation
            if self.device == 'cuda':
                torch.cuda.empty_cache()
            
            self.imputation_model.fit(X_with_mask)
            X_imputed = self.imputation_model.impute(X_with_mask)
            
            # Nettoyage après imputation
            if self.device == 'cuda':
                torch.cuda.empty_cache()
                
        except Exception as e:
            logger.warning(f"Erreur d'imputation, utilisation des données brutes: {e}")
            X_imputed = X
            # Nettoyage en cas d'erreur
            if self.device == 'cuda':
                torch.cuda.empty_cache()
        
        # Clustering avec CRLI (paramètres optimisés mémoire)
        logger.info("Entraînement du modèle de clustering...")
        self.clustering_model = CRLI(
            n_steps=X.shape[1],
            n_features=X.shape[2],
            n_clusters=settings.n_clusters,
            n_generator_layers=1,  # Réduction du nombre de couches
            rnn_hidden_size=settings.model_hidden_size,  # Configurable et réduit
            epochs=settings.clustering_epochs,  # Configurable
            batch_size=settings.batch_size,  # Configurable
            device=self.device
        )
        
        try:
            # Nettoyage mémoire avant clustering
            if self.device == 'cuda':
                torch.cuda.empty_cache()
                
            self.clustering_model.fit(X_with_mask)
            
            # Nettoyage après entraînement
            if self.device == 'cuda':
                torch.cuda.empty_cache()
            
        except Exception as e:
            logger.error(f"Erreur lors du clustering: {e}")
            # Nettoyage en cas d'erreur
            if self.device == 'cuda':
                torch.cuda.empty_cache()
            raise
        
        # Prédiction des clusters
        cluster_labels = self.clustering_model.predict(X_with_mask)['clustering']
        
        # Calcul des métriques
        from sklearn.metrics import silhouette_score, davies_bouldin_score
        
        # Flatten pour les métriques
        X_flat = X_imputed.reshape(X_imputed.shape[0], -1)
        
        metrics = {
            'n_samples': len(X),
            'n_clusters_found': len(np.unique(cluster_labels)),
            'silhouette_score': float(silhouette_score(X_flat, cluster_labels)),
            'davies_bouldin_score': float(davies_bouldin_score(X_flat, cluster_labels)),
        }
        
        logger.info(f"Clustering terminé: {metrics}")
        
        # Sauvegarde des modèles
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        version = f"v_{timestamp}"
        
        model_file = os.path.join(self.model_path, f"clustering_{version}.pkl")
        with open(model_file, 'wb') as f:
            pickle.dump({
                'clustering_model': self.clustering_model,
                'imputation_model': self.imputation_model,
                'scaler': self.scaler,
                'device': self.device
            }, f)
        
        db_manager.save_model_version(version, 'clustering', model_file, metrics)
        
        return metrics
    
    def load_model(self, version: Optional[str] = None):
        """Charge un modèle sauvegardé"""
        if version is None:
            model_info = db_manager.get_active_model('clustering')
            if model_info is None:
                logger.warning("Aucun modèle actif trouvé")
                return False
            model_path = model_info.model_path
        else:
            model_path = os.path.join(self.model_path, f"clustering_{version}.pkl")
        
        if not os.path.exists(model_path):
            logger.error(f"Modèle non trouvé: {model_path}")
            return False
        
        logger.info(f"Chargement du modèle: {model_path}")
        with open(model_path, 'rb') as f:
            data = pickle.load(f)
            self.clustering_model = data['clustering_model']
            self.imputation_model = data['imputation_model']
            self.scaler = data['scaler']
        
        return True
    
    def detect_appliances(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """
        Détecte les appareils en fonctionnement dans la période donnée
        
        Args:
            start_time: Début de la période
            end_time: Fin de la période
            
        Returns:
            Liste des détections avec timestamps et scores de confiance
        """
        if self.clustering_model is None:
            logger.error("Modèle non chargé")
            return []
        
        # Récupération des données
        data = db_manager.get_linky_data(start_time, end_time)
        if len(data) == 0:
            logger.warning("Aucune donnée à analyser")
            return []
        
        logger.info(f"Analyse de {len(data)} points de données")
        
        # Préparation
        X = self.prepare_time_series_data(data, settings.window_size_minutes)
        if len(X) == 0:
            return []
        
        # Prédiction
        X_with_mask = {'X': X}
        predictions = self.clustering_model.predict(X_with_mask)
        cluster_labels = predictions['clustering']
        
        # Analyse des transitions entre clusters (détection d'événements)
        detections = []
        current_cluster = cluster_labels[0]
        event_start_idx = 0
        
        for i in range(1, len(cluster_labels)):
            if cluster_labels[i] != current_cluster:
                # Transition détectée
                event_end_idx = i - 1
                
                # Extraction des features de cet événement
                event_windows = X[event_start_idx:event_end_idx+1]
                event_power = event_windows[:, :, 0].flatten()  # Feature 0 = puissance
                
                avg_power = float(np.mean(event_power))
                
                # Filtrage par seuil de puissance
                if avg_power >= settings.min_power_threshold:
                    # Calcul du timestamp
                    window_duration_sec = settings.window_size_minutes * 60
                    step_sec = window_duration_sec // 2
                    event_start_sec = event_start_idx * step_sec
                    event_end_sec = event_end_idx * step_sec + window_duration_sec
                    
                    event_start_time = start_time + timedelta(seconds=event_start_sec)
                    event_end_time = start_time + timedelta(seconds=event_end_sec)
                    
                    duration = (event_end_time - event_start_time).total_seconds()
                    
                    # Filtrage par durée minimale
                    if duration >= settings.min_duration_seconds:
                        # Calcul de l'énergie (approximation)
                        energy_wh = (avg_power * duration) / 3600
                        
                        detection = {
                            'cluster_id': int(current_cluster),
                            'start_time': event_start_time,
                            'end_time': event_end_time,
                            'avg_power': avg_power,
                            'energy_wh': energy_wh,
                            'confidence': 0.8,  # Score basique, à améliorer
                            'duration_seconds': duration
                        }
                        detections.append(detection)
                
                # Nouveau cluster
                current_cluster = cluster_labels[i]
                event_start_idx = i
        
        logger.info(f"{len(detections)} événements détectés")
        return detections


# Instance globale
nilm_detector = NilmDetector()
