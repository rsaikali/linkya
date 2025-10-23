"""
Modèle CNN pour détection de signatures complexes d'appareils électriques
"""
import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from pathlib import Path
import json

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, models, callbacks
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from scipy import signal
from scipy.fft import fft, fftfreq

from .config import settings
from .database import db_manager

logger = logging.getLogger(__name__)


class SignaturePreprocessor:
    """Préprocessing et extraction de features pour les signatures"""
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
    
    def extract_features(self, power_data: List[float]) -> Dict[str, Any]:
        """
        Extrait les features d'une séquence de consommation
        
        Args:
            power_data: Liste de valeurs de puissance
            
        Returns:
            Dictionnaire de features
        """
        power_array = np.array(power_data)
        features = {}
        
        # Statistiques de base
        features['mean'] = float(np.mean(power_array))
        features['std'] = float(np.std(power_array))
        features['min'] = float(np.min(power_array))
        features['max'] = float(np.max(power_array))
        features['range'] = features['max'] - features['min']
        
        # Statistiques avancées
        features['median'] = float(np.median(power_array))
        features['q25'] = float(np.percentile(power_array, 25))
        features['q75'] = float(np.percentile(power_array, 75))
        features['iqr'] = features['q75'] - features['q25']
        
        # Gradients et variations
        if settings.cnn_gradient_enabled:
            gradients = np.gradient(power_array)
            features['gradient_mean'] = float(np.mean(gradients))
            features['gradient_std'] = float(np.std(gradients))
            features['gradient_max'] = float(np.max(np.abs(gradients)))
            
            # Nombre de changements de direction
            sign_changes = np.diff(np.sign(gradients))
            features['direction_changes'] = int(np.sum(np.abs(sign_changes) > 0))
        
        # Analyse fréquentielle (FFT)
        if settings.cnn_fft_enabled and len(power_array) > 10:
            fft_vals = fft(power_array)
            fft_freqs = fftfreq(len(power_array), d=1.0)
            
            # Magnitude du spectre
            fft_magnitude = np.abs(fft_vals)[:len(fft_vals)//2]
            features['fft_peak'] = float(np.max(fft_magnitude))
            features['fft_mean'] = float(np.mean(fft_magnitude))
            
            # Fréquence dominante
            if len(fft_magnitude) > 0:
                peak_idx = np.argmax(fft_magnitude)
                features['dominant_frequency'] = float(fft_freqs[peak_idx])
        
        # Stabilité et cyclicité
        if settings.cnn_statistics_enabled:
            # Coefficient de variation
            if features['mean'] > 0:
                features['cv'] = features['std'] / features['mean']
            
            # Autocorrélation pour détecter les cycles
            if len(power_array) > 20:
                autocorr = np.correlate(power_array, power_array, mode='full')
                autocorr = autocorr[len(autocorr)//2:]
                autocorr = autocorr / autocorr[0]  # Normaliser
                
                # Trouver le premier pic après le décalage 0
                peaks, _ = signal.find_peaks(autocorr[1:], height=0.5)
                if len(peaks) > 0:
                    features['cycle_period'] = int(peaks[0] + 1)
                    features['cycle_strength'] = float(autocorr[peaks[0] + 1])
        
        return features
    
    def augment_sequence(
        self, 
        sequence: np.ndarray, 
        label: int
    ) -> List[Tuple[np.ndarray, int]]:
        """
        Augmente les données d'entraînement
        
        Args:
            sequence: Séquence de puissance
            label: Label de l'appareil
            
        Returns:
            Liste de séquences augmentées avec leurs labels
        """
        augmented = [(sequence, label)]
        
        if not settings.cnn_augmentation_enabled:
            return augmented
        
        # Ajout de bruit
        noise = np.random.normal(0, settings.cnn_noise_factor * np.std(sequence), sequence.shape)
        augmented.append((sequence + noise, label))
        
        # Décalage temporel
        if settings.cnn_shift_range > 0 and len(sequence) > settings.cnn_shift_range:
            shift = np.random.randint(-settings.cnn_shift_range, settings.cnn_shift_range)
            shifted = np.roll(sequence, shift)
            augmented.append((shifted, label))
        
        # Mise à l'échelle légère
        scale_factor = np.random.uniform(0.95, 1.05)
        augmented.append((sequence * scale_factor, label))
        
        return augmented
    
    def prepare_sequences(
        self, 
        signatures: List[Dict[str, Any]]
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Prépare les séquences pour l'entraînement du CNN
        
        Args:
            signatures: Liste de signatures avec raw_data
            
        Returns:
            (X, y, class_names) - Séquences, labels, noms des classes
        """
        sequences = []
        labels = []
        class_names = []
        
        # Grouper par appareil
        appliances = {}
        for sig in signatures:
            app_id = sig['appliance_id']
            if app_id not in appliances:
                appliances[app_id] = {
                    'name': sig['appliance_name'],
                    'signatures': []
                }
            appliances[app_id]['signatures'].append(sig)
        
        # Créer un mapping appliance_id -> classe
        class_names = [appliances[app_id]['name'] for app_id in sorted(appliances.keys())]
        app_id_to_class = {app_id: idx for idx, app_id in enumerate(sorted(appliances.keys()))}
        
        logger.info(f"Nombre d'appareils (classes): {len(class_names)}")
        
        # Extraire et normaliser les séquences
        for app_id, app_data in appliances.items():
            class_idx = app_id_to_class[app_id]
            
            for sig in app_data['signatures']:
                raw_data = sig['raw_data']
                if not raw_data:
                    continue
                
                # Extraire les valeurs de puissance
                power_values = [d['papp'] for d in raw_data]
                
                # Rééchantillonner ou padding pour avoir une longueur fixe
                # Padding ou troncature
                target_length = settings.effective_sequence_length
                
                if len(power_values) > target_length:
                    # Rééchantillonner
                    indices = np.linspace(0, len(power_values) - 1, target_length, dtype=int)
                    power_values = [power_values[i] for i in indices]
                elif len(power_values) < target_length:
                    # Padding avec la valeur moyenne
                    mean_val = np.mean(power_values)
                    power_values = power_values + [mean_val] * (target_length - len(power_values))
                
                sequence = np.array(power_values, dtype=np.float32)
                
                # Augmentation de données
                augmented = self.augment_sequence(sequence, class_idx)
                for aug_seq, aug_label in augmented:
                    sequences.append(aug_seq)
                    labels.append(aug_label)
        
        # Convertir en arrays
        X = np.array(sequences)
        y = np.array(labels)
        
        # Normaliser les séquences
        X_reshaped = X.reshape(-1, 1)
        X_normalized = self.scaler.fit_transform(X_reshaped)
        X = X_normalized.reshape(X.shape)
        
        # Ajouter une dimension pour le CNN (samples, timesteps, features)
        X = X.reshape(X.shape[0], X.shape[1], 1)
        
        logger.info(f"Préparé {len(X)} séquences pour {len(class_names)} classes")
        
        return X, y, class_names


class CNNNILMModel:
    """Modèle CNN pour détection et classification d'appareils"""
    
    def __init__(self):
        self.model: Optional[keras.Model] = None
        self.preprocessor = SignaturePreprocessor()
        self.class_names: List[str] = []
        self.history = None
        
        # Créer le répertoire des modèles
        Path(settings.cnn_model_path).mkdir(parents=True, exist_ok=True)
    
    def build_model(self, num_classes: int, sequence_length: int) -> keras.Model:
        """
        Construit l'architecture du modèle CNN 1D
        
        Args:
            num_classes: Nombre de classes (appareils)
            sequence_length: Longueur des séquences d'entrée
            
        Returns:
            Modèle Keras compilé
        """
        model = models.Sequential([
            # Première couche de convolution
            layers.Conv1D(
                filters=64,
                kernel_size=5,
                activation='relu',
                input_shape=(sequence_length, 1),
                padding='same'
            ),
            layers.BatchNormalization(),
            layers.MaxPooling1D(pool_size=2),
            layers.Dropout(0.3),
            
            # Deuxième couche de convolution
            layers.Conv1D(
                filters=128,
                kernel_size=5,
                activation='relu',
                padding='same'
            ),
            layers.BatchNormalization(),
            layers.MaxPooling1D(pool_size=2),
            layers.Dropout(0.3),
            
            # Troisième couche de convolution
            layers.Conv1D(
                filters=256,
                kernel_size=3,
                activation='relu',
                padding='same'
            ),
            layers.BatchNormalization(),
            layers.MaxPooling1D(pool_size=2),
            layers.Dropout(0.4),
            
            # Couches denses
            layers.Flatten(),
            layers.Dense(256, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.5),
            layers.Dense(128, activation='relu'),
            layers.Dropout(0.5),
            
            # Couche de sortie
            layers.Dense(num_classes, activation='softmax')
        ])
        
        # Compiler le modèle
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=settings.cnn_learning_rate),
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
        
        logger.info(f"Modèle CNN construit: {num_classes} classes, {sequence_length} timesteps")
        return model
    
    def train(
        self, 
        signatures: List[Dict[str, Any]],
        version: str
    ) -> Dict[str, Any]:
        """
        Entraîne le modèle CNN sur les signatures
        
        Args:
            signatures: Liste de signatures d'entraînement
            version: Version du modèle
            
        Returns:
            Dictionnaire de métriques de performance
        """
        if len(signatures) < 10:
            logger.error("Pas assez de signatures pour l'entraînement (minimum 10)")
            return {}
        
        # Préparer les données
        X, y, self.class_names = self.preprocessor.prepare_sequences(signatures)
        
        if len(X) == 0:
            logger.error("Aucune séquence valide pour l'entraînement")
            return {}
        
        # Split train/validation
        # Pour les petits datasets, ajuster la validation split
        num_classes = len(np.unique(y))
        min_samples_per_class = np.min(np.bincount(y))
        
        # Si trop peu d'échantillons par classe, désactiver stratify
        if min_samples_per_class < 2 or len(X) < num_classes * 5:
            logger.warning(f"Dataset trop petit ({len(X)} samples, {num_classes} classes), stratify désactivé")
            X_train, X_val, y_train, y_val = train_test_split(
                X, y,
                test_size=0.1,  # 10% pour validation
                random_state=42
            )
        else:
            X_train, X_val, y_train, y_val = train_test_split(
                X, y,
                test_size=settings.cnn_validation_split,
                stratify=y,
                random_state=42
            )
        
        logger.info(f"Train: {len(X_train)} samples, Validation: {len(X_val)} samples")
        
        # Construire le modèle
        self.model = self.build_model(
            num_classes=len(self.class_names),
            sequence_length=settings.effective_sequence_length
        )
        
        # Créer le répertoire TensorBoard logs
        log_dir = Path(settings.cnn_model_path) / "logs" / version
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Callbacks
        early_stopping = callbacks.EarlyStopping(
            monitor='val_loss',
            patience=10,
            restore_best_weights=True
        )
        
        reduce_lr = callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=5,
            min_lr=1e-6
        )
        
        tensorboard_callback = callbacks.TensorBoard(
            log_dir=str(log_dir),
            histogram_freq=1,
            write_graph=True,
            update_freq='epoch'
        )
        
        # Entraînement
        self.history = self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=settings.cnn_epochs,
            batch_size=settings.cnn_batch_size,
            callbacks=[early_stopping, reduce_lr, tensorboard_callback],
            verbose=1
        )
        
        # Évaluation
        val_loss, val_accuracy = self.model.evaluate(X_val, y_val, verbose=0)
        
        # Sauvegarder le modèle
        model_path = Path(settings.cnn_model_path) / f"model_{version}.keras"
        self.model.save(model_path)
        
        # Sauvegarder les métadonnées
        metadata = {
            'class_names': self.class_names,
            'scaler_mean': self.preprocessor.scaler.mean_.tolist(),
            'scaler_scale': self.preprocessor.scaler.scale_.tolist(),
            'sequence_length': settings.effective_sequence_length
        }
        
        metadata_path = Path(settings.cnn_model_path) / f"metadata_{version}.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)
        
        metrics = {
            'val_loss': float(val_loss),
            'val_accuracy': float(val_accuracy),
            'train_loss': float(self.history.history['loss'][-1]),
            'train_accuracy': float(self.history.history['accuracy'][-1]),
            'epochs_trained': len(self.history.history['loss'])
        }
        
        logger.info(f"Entraînement terminé: accuracy={val_accuracy:.3f}, loss={val_loss:.3f}")
        
        return metrics
    
    def load_model(self, version: str) -> bool:
        """
        Charge un modèle sauvegardé
        
        Args:
            version: Version du modèle à charger
            
        Returns:
            True si chargement réussi
        """
        try:
            model_path = Path(settings.cnn_model_path) / f"model_{version}.keras"
            metadata_path = Path(settings.cnn_model_path) / f"metadata_{version}.json"
            
            if not model_path.exists() or not metadata_path.exists():
                logger.error(f"Modèle {version} introuvable")
                return False
            
            # Charger le modèle
            self.model = keras.models.load_model(model_path)
            
            # Charger les métadonnées
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            self.class_names = metadata['class_names']
            self.preprocessor.scaler.mean_ = np.array(metadata['scaler_mean'])
            self.preprocessor.scaler.scale_ = np.array(metadata['scaler_scale'])
            
            logger.info(f"Modèle {version} chargé avec succès")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement du modèle: {e}")
            return False
    
    def predict_appliance(
        self,
        power_sequence: List[float]
    ) -> Tuple[Optional[str], float, List[float]]:
        """
        Prédit l'appareil à partir d'une séquence de puissance
        
        Args:
            power_sequence: Séquence de valeurs de puissance
            
        Returns:
            (nom_appareil, confidence, probabilités) ou (None, 0, []) si erreur
        """
        if self.model is None:
            logger.error("Modèle non chargé")
            return None, 0.0, []
        
        # Préparer la séquence
        target_length = settings.effective_sequence_length
        
        if len(power_sequence) > target_length:
            indices = np.linspace(0, len(power_sequence) - 1, target_length, dtype=int)
            power_sequence = [power_sequence[i] for i in indices]
        elif len(power_sequence) < target_length:
            mean_val = np.mean(power_sequence)
            power_sequence = power_sequence + [mean_val] * (target_length - len(power_sequence))
        
        sequence = np.array(power_sequence, dtype=np.float32)
        
        # Normaliser
        sequence_reshaped = sequence.reshape(-1, 1)
        sequence_normalized = self.preprocessor.scaler.transform(sequence_reshaped)
        sequence = sequence_normalized.reshape(sequence.shape)
        
        # Préparer pour le CNN
        X = sequence.reshape(1, sequence.shape[0], 1)
        
        # Prédiction
        predictions = self.model.predict(X, verbose=0)[0]
        
        # Classe prédite
        predicted_class = int(np.argmax(predictions))
        confidence = float(predictions[predicted_class])
        
        appliance_name = self.class_names[predicted_class] if predicted_class < len(self.class_names) else None
        
        return appliance_name, confidence, predictions.tolist()
    
    def detect_events(
        self,
        start_time: datetime,
        end_time: datetime,
        min_confidence: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        Détecte les événements d'appareils dans une période
        
        Args:
            start_time: Début de la période
            end_time: Fin de la période
            min_confidence: Seuil de confiance minimal
            
        Returns:
            Liste d'événements détectés
        """
        if self.model is None:
            logger.error("Modèle non chargé")
            return []
        
        # Récupérer les données de consommation
        consumption_data = db_manager.get_consumption_data(start_time, end_time, resample_seconds=1)
        
        if not consumption_data:
            logger.warning("Aucune donnée de consommation disponible")
            return []
        
        power_values = [d['papp'] for d in consumption_data]
        timestamps = [d['time'] for d in consumption_data]
        
        # Fenêtre glissante pour la détection
        window_size = settings.effective_sequence_length
        step_size = window_size // 2  # 50% de recouvrement
        
        events = []
        
        for i in range(0, len(power_values) - window_size, step_size):
            window = power_values[i:i + window_size]
            window_start = timestamps[i]
            window_end = timestamps[i + window_size - 1]
            
            # Vérifier le seuil de puissance
            avg_power = np.mean(window)
            if avg_power < settings.cnn_min_power_threshold:
                continue
            
            # Prédire l'appareil
            appliance_name, confidence, probs = self.predict_appliance(window)
            
            if confidence >= min_confidence and appliance_name:
                # Récupérer la classe prédite
                predicted_class = int(np.argmax(probs))
                
                # Calculer l'énergie
                duration_hours = (window_end - window_start).total_seconds() / 3600
                energy = avg_power * duration_hours
                
                events.append({
                    'appliance_name': appliance_name,
                    'start_time': window_start,
                    'end_time': window_end,
                    'avg_power': float(avg_power),
                    'energy_consumed': float(energy),
                    'confidence_score': float(confidence),
                    'probabilities': probs,
                    'prediction_class': predicted_class
                })
        
        # Fusionner les événements consécutifs du même appareil
        merged_events = self._merge_consecutive_events(events)
        
        logger.info(f"Détecté {len(merged_events)} événements")
        return merged_events
    
    def _merge_consecutive_events(
        self,
        events: List[Dict[str, Any]],
        max_gap_seconds: int = 120
    ) -> List[Dict[str, Any]]:
        """Fusionne les événements consécutifs du même appareil"""
        if not events:
            return []
        
        # Trier par temps
        events = sorted(events, key=lambda x: x['start_time'])
        
        merged = []
        current = events[0].copy()
        
        for i in range(1, len(events)):
            event = events[i]
            
            # Vérifier si c'est le même appareil et proche dans le temps
            gap = (event['start_time'] - current['end_time']).total_seconds()
            
            if event['appliance_name'] == current['appliance_name'] and gap <= max_gap_seconds:
                # Fusionner
                current['end_time'] = event['end_time']
                current['avg_power'] = (current['avg_power'] + event['avg_power']) / 2
                current['energy_consumed'] += event['energy_consumed']
                current['confidence_score'] = max(current['confidence_score'], event['confidence_score'])
            else:
                # Ajouter l'événement courant et commencer un nouveau
                merged.append(current)
                current = event.copy()
        
        # Ajouter le dernier
        merged.append(current)
        
        return merged


# Instance globale du modèle CNN
cnn_model = CNNNILMModel()
