"""
Modèle Sequence-to-Point NILM pour désagrégation d'appareils concurrents
et détection de cycles complexes.

Architecture basée sur LSTM/GRU avec mécanisme d'attention pour :
- Désagrégation : prédit la consommation individuelle de chaque appareil
- Détection d'états : identifie les différentes phases/cycles (chauffage, lavage, etc.)
- Appareils concurrents : gère plusieurs appareils fonctionnant simultanément
"""
from __future__ import annotations
import logging
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json
import os

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, models, callbacks
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.cluster import KMeans
from scipy import signal
from scipy.stats import zscore
from sqlalchemy import text

from .config import settings
from .database import db_manager

logger = logging.getLogger(__name__)


# --- Custom Loss Functions ---
@tf.keras.utils.register_keras_serializable(package='custom_losses')
def focal_loss_fixed(y_true=None, y_pred=None, gamma=2.0, alpha=0.25):
    """
    Focal Loss pour se concentrer sur les exemples difficiles.
    
    Réduit la perte pour les exemples bien classifiés et augmente
    pour les difficiles. Utile pour rejeter les faux positifs.
    
    Args:
        y_true: Valeurs réelles (None si utilisé comme constructeur)
        y_pred: Valeurs prédites (None si utilisé comme constructeur)
        gamma: Facteur de modulation (2.0 par défaut).
               Plus élevé = focus sur difficiles
        alpha: Facteur de balance (0.25 par défaut).
               Poids relatif des classes
        
    Returns:
        Perte calculée si y_true et y_pred fournis, sinon fonction de perte
    """
    # Si y_true et y_pred sont fournis, calculer la perte directement
    if y_true is not None and y_pred is not None:
        # MAE de base
        mae = tf.abs(y_true - y_pred)
        
        # Normaliser les erreurs pour focal
        # Pour les prédictions proches de la vérité, p_t sera proche de 1
        # Pour les erreurs importantes, p_t sera proche de 0
        max_error = tf.reduce_max(mae) + 1e-7
        p_t = 1.0 - (mae / max_error)
        
        # Focal term: (1 - p_t)^gamma
        # Quand p_t proche de 1 (bonne prédiction): focal_weight ~0
        # Quand p_t proche de 0 (mauvaise prédiction): focal_weight ~1
        focal_weight = tf.pow(1.0 - p_t, gamma)
        
        # Pénaliser plus les faux positifs (y_true=0 mais y_pred>0)
        false_positive_mask = tf.cast(y_true < 0.1, tf.float32)
        alpha_weight = 1.0 + alpha * false_positive_mask
        
        # Loss finale
        loss = alpha_weight * focal_weight * mae
        
        return tf.reduce_mean(loss)
    
    # Sinon retourner une fonction de perte paramétrée
    def loss_fn(y_true, y_pred):
        # MAE de base
        mae = tf.abs(y_true - y_pred)
        
        # Normaliser les erreurs pour focal
        # Pour les prédictions proches de la vérité, p_t sera proche de 1
        # Pour les erreurs importantes, p_t sera proche de 0
        max_error = tf.reduce_max(mae) + 1e-7
        p_t = 1.0 - (mae / max_error)
        
        # Focal term: (1 - p_t)^gamma
        # Quand p_t proche de 1 (bonne prédiction): focal_weight ~0
        # Quand p_t proche de 0 (mauvaise prédiction): focal_weight ~1
        focal_weight = tf.pow(1.0 - p_t, gamma)
        
        # Pénaliser plus les faux positifs (y_true=0 mais y_pred>0)
        false_positive_mask = tf.cast(y_true < 0.1, tf.float32)
        alpha_weight = 1.0 + alpha * false_positive_mask
        
        # Loss finale
        loss = alpha_weight * focal_weight * mae
        
        return tf.reduce_mean(loss)
    
    return loss_fn


@tf.keras.utils.register_keras_serializable(package='custom_losses')
def asymmetric_loss(y_true=None, y_pred=None, false_positive_penalty=2.5):
    """
    Loss asymétrique qui pénalise plus les faux positifs.
    
    Quand y_true=0 (appareil éteint ou signature négative),
    les erreurs de prédiction sont pénalisées davantage.
    
    Args:
        y_true: Valeurs réelles (None si utilisé comme constructeur)
        y_pred: Valeurs prédites (None si utilisé comme constructeur)
        false_positive_penalty: Multiplicateur pour les faux positifs
                                (défaut: 2.5)
        
    Returns:
        Perte calculée si y_true et y_pred fournis, sinon fonction de perte
    """
    # Si y_true et y_pred sont fournis, calculer la perte directement
    if y_true is not None and y_pred is not None:
        mae = tf.abs(y_true - y_pred)
        
        # Détecter où y_true est proche de 0 (OFF ou négatif)
        is_negative = tf.cast(y_true < 0.1, tf.float32)
        
        # Pénaliser plus les erreurs quand l'appareil devrait être OFF
        weight = 1.0 + (false_positive_penalty - 1.0) * is_negative
        
        weighted_mae = weight * mae
        
        return tf.reduce_mean(weighted_mae)
    
    # Sinon retourner une fonction de perte paramétrée
    def loss_fn(y_true, y_pred):
        mae = tf.abs(y_true - y_pred)
        
        # Détecter où y_true est proche de 0 (OFF ou négatif)
        is_negative = tf.cast(y_true < 0.1, tf.float32)
        
        # Pénaliser plus les erreurs quand l'appareil devrait être OFF
        weight = 1.0 + (false_positive_penalty - 1.0) * is_negative
        
        weighted_mae = weight * mae
        
        return tf.reduce_mean(weighted_mae)
    
    return loss_fn


# --- FiLM Layer pour conditioning multi-target ---
@tf.keras.utils.register_keras_serializable(package='custom_layers')
class FiLMLayer(layers.Layer):
    """
    Feature-wise Linear Modulation (FiLM) layer.
    
    Applique une transformation affine conditionnée sur l'appareil cible:
    FiLM(x, gamma, beta) = x * gamma + beta
    
    Cette technique permet à un seul modèle d'apprendre à désagréger
    plusieurs appareils en modulant les features intermédiaires selon
    l'appareil demandé.
    
    Référence: "FiLM: Visual Reasoning with a General Conditioning Layer"
    """
    def __init__(self, **kwargs):
        super(FiLMLayer, self).__init__(**kwargs)
    
    def call(self, inputs):
        """
        Args:
            inputs: [features, gamma, beta]
                - features: (batch, features_dim) - Features à moduler
                - gamma: (batch, features_dim) - Scaling factors
                - beta: (batch, features_dim) - Shift factors
        
        Returns:
            Tensor modulé de même shape que features
        """
        features, gamma, beta = inputs
        return features * gamma + beta
    
    def get_config(self):
        return super(FiLMLayer, self).get_config()


# --- S2P FiLM : un seul modèle multi-target avec conditioning ---
class Seq2PointFiLMModel:
    """
    Modèle Sequence-to-Point avec FiLM conditioning pour multi-target.
    
    Architecture:
    1. Input aggregate power (séquence temporelle)
    2. Input appliance_id (one-hot encoding)
    3. Feature extraction (GRU/LSTM)
    4. FiLM conditioning: gamma/beta générés depuis appliance_id
    5. Feature modulation: features * gamma + beta
    6. Prediction head: une seule sortie
    
    Avantages vs. Multi-Output:
    - 1 seul modèle pour N appareils (vs N modèles)
    - Partage de features entre appareils similaires
    - Meilleure généralisation avec transfer learning
    - Ajout nouveau appareil = fine-tuning (pas nouveau modèle)
    """
    
    def __init__(
        self,
        appliance_ids: List[int],
        appliance_names: List[str],
        sequence_length: int = 299,
        model_type: str = "gru"
    ):
        self.appliance_ids = appliance_ids
        self.appliance_names = appliance_names
        self.sequence_length = sequence_length if sequence_length % 2 == 1 else sequence_length - 1
        self.model_type = model_type
        self.num_appliances = len(appliance_ids)
        self.model: Optional[keras.Model] = None
        self.preprocessor = Seq2PointPreprocessor(self.sequence_length)
        self.state_detectors: Dict[int, ApplianceStateDetector] = {}
        self.history = None
        self.use_gpu = self._configure_device()
        
        # Mapping appareil ID -> index pour one-hot encoding
        self.appliance_id_to_idx = {
            app_id: idx for idx, app_id in enumerate(appliance_ids)
        }
        self.appliance_idx_to_id = {
            idx: app_id for app_id, idx in self.appliance_id_to_idx.items()
        }
    
    def _configure_device(self) -> bool:
        gpus = tf.config.list_physical_devices('GPU')
        if gpus:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            logger.info(f"🎮 Device: GPU ({len(gpus)} disponible(s))")
            return True
        logger.info("💻 Device: CPU")
        return False
    
    def encode_appliance_id(self, appliance_id: int) -> np.ndarray:
        """
        Encode l'appliance_id en one-hot vector.
        
        Args:
            appliance_id: ID de l'appareil
        
        Returns:
            One-hot vector de taille num_appliances
        """
        idx = self.appliance_id_to_idx.get(appliance_id)
        if idx is None:
            raise ValueError(f"Appareil ID {appliance_id} inconnu")
        
        one_hot = np.zeros(self.num_appliances, dtype=np.float32)
        one_hot[idx] = 1.0
        return one_hot
    
    def build_model(self) -> keras.Model:
        """
        Construit le modèle FiLM avec conditioning.
        
        Architecture:
        - Input 1: aggregate_power (window_size, 1)
        - Input 2: appliance_id (num_appliances,) one-hot
        - Feature extraction: GRU/LSTM layers
        - FiLM generator: Dense layers pour gamma/beta
        - FiLM modulation: features * gamma + beta
        - Output: power prediction (1,)
        """
        # Input 1: Aggregate power sequence
        aggregate_input = layers.Input(
            shape=(self.sequence_length, 1),
            name='aggregate_power'
        )
        
        # Input 2: Appliance ID (one-hot)
        appliance_input = layers.Input(
            shape=(self.num_appliances,),
            name='appliance_id'
        )
        
        # Feature extraction from aggregate power
        if self.model_type == "gru":
            x = layers.GRU(128, return_sequences=True, name='gru_1')(aggregate_input)
            x = layers.Dropout(0.2)(x)
            x = layers.GRU(64, return_sequences=False, name='gru_2')(x)
            x = layers.Dropout(0.2)(x)
        elif self.model_type == "lstm":
            x = layers.LSTM(128, return_sequences=True, name='lstm_1')(aggregate_input)
            x = layers.Dropout(0.2)(x)
            x = layers.LSTM(64, return_sequences=False, name='lstm_2')(x)
            x = layers.Dropout(0.2)(x)
        else:
            raise ValueError(f"Type de modèle inconnu: {self.model_type}")
        
        # Dense feature layer
        features = layers.Dense(128, activation='relu', name='features')(x)
        features = layers.Dropout(0.1)(features)
        
        # FiLM Generator: génère gamma et beta depuis appliance_id
        # Architecture du générateur: 3 couches denses
        film_gen = layers.Dense(64, activation='relu', name='film_gen_1')(appliance_input)
        film_gen = layers.Dense(64, activation='relu', name='film_gen_2')(film_gen)
        
        # Générer gamma (scaling) et beta (shift)
        gamma = layers.Dense(128, activation='linear', name='film_gamma')(film_gen)
        beta = layers.Dense(128, activation='linear', name='film_beta')(film_gen)
        
        # FiLM modulation: features * gamma + beta
        modulated_features = FiLMLayer(name='film_modulation')([features, gamma, beta])
        
        # Prediction head
        x = layers.Dense(64, activation='relu', name='dense_1')(modulated_features)
        x = layers.Dropout(0.1)(x)
        x = layers.Dense(32, activation='relu', name='dense_2')(x)
        
        # Output: power prediction
        output = layers.Dense(1, activation='linear', name='power_output')(x)
        
        # Build model
        model = models.Model(
            inputs=[aggregate_input, appliance_input],
            outputs=output,
            name=f's2p_film_{self.model_type}'
        )
        
        # Compile avec loss asymétrique
        loss_fn = asymmetric_loss(false_positive_penalty=2.5)
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss=loss_fn,
            metrics=['mae', 'mse']
        )
        
        logger.info(
            f"🎬 Modèle S2P-FiLM {self.model_type.upper()} construit:\n"
            f"   - {self.num_appliances} appareils: {self.appliance_names}\n"
            f"   - Séquence: {self.sequence_length}\n"
            f"   - Architecture: FiLM conditioning\n"
            f"   - Loss: asymmetric (FP penalty=2.5)"
        )
        
        return model
    
    def train(
        self,
        all_signatures: Dict[int, List[Dict[str, Any]]],
        version: str,
        epochs: int = 30,
        batch_size: int = 32,
        validation_split: float = 0.15,
        use_feedback: bool = True,
        fine_tune: bool = False
    ) -> Dict[str, Any]:
        """
        Entraîne le modèle FiLM avec conditioning.
        
        Args:
            all_signatures: Dict[appliance_id, List[signature]]
            version: Version du modèle
            use_feedback: Utiliser détections invalidées comme négatifs
            fine_tune: Continue entraînement modèle existant
        
        Returns:
            Dictionnaire de métriques
        """
        is_fine_tuning = fine_tune and self.model is not None
        if is_fine_tuning:
            logger.info("🔄 Fine-tuning du modèle FiLM existant")
            learning_rate = 0.0001
            epochs = min(epochs, 15)
        else:
            logger.info("🆕 Entraînement from-scratch du modèle FiLM")
            learning_rate = 0.001
        
        # Préparer les données
        X_aggregate = []
        X_appliance_ids = []
        y_power = []
        
        for appliance_id, signatures in all_signatures.items():
            if appliance_id not in self.appliance_id_to_idx:
                logger.warning(f"Appareil {appliance_id} inconnu, ignoré")
                continue
            
            # One-hot encoding pour cet appareil
            appliance_one_hot = self.encode_appliance_id(appliance_id)
            
            for sig in signatures:
                aggregate, power = self._load_signature_data_static(sig)
                if aggregate is None or len(aggregate) < self.sequence_length:
                    continue
                
                # Créer les séquences
                X, y = self.preprocessor.create_sequences(
                    aggregate, power, stride=30
                )
                
                if len(X) > 0:
                    X_aggregate.append(X)
                    y_power.append(y)
                    # Répéter le one-hot pour chaque séquence
                    X_appliance_ids.append(
                        np.tile(appliance_one_hot, (len(X), 1))
                    )
        
        # Ajouter exemples négatifs si demandé
        if use_feedback:
            negative_count = self._add_negative_examples_film(
                X_aggregate, X_appliance_ids, y_power
            )
            if negative_count > 0:
                logger.info(
                    f"✅ {negative_count} exemples négatifs ajoutés (FiLM)"
                )
        
        # Concaténer
        if not X_aggregate:
            logger.error("Aucune donnée pour entraînement FiLM")
            return {}
        
        X_agg = np.concatenate(X_aggregate, axis=0)
        X_app_ids = np.concatenate(X_appliance_ids, axis=0)
        y = np.concatenate(y_power, axis=0)
        
        # Ajuster scalers (from-scratch seulement)
        if not is_fine_tuning:
            logger.info("Ajustement scalers (from-scratch)")
            self.preprocessor.input_scaler.fit(X_agg.reshape(-1, 1))
            self.preprocessor.target_scaler.fit(y.reshape(-1, 1))
            self.preprocessor.fitted = True
        else:
            logger.info("Réutilisation scalers existants (fine-tuning)")
        
        # Normaliser
        X_scaled, _ = self.preprocessor.transform(X_agg)
        X_scaled = X_scaled.reshape(X_scaled.shape[0], X_scaled.shape[1], 1)
        y_scaled = self.preprocessor.target_scaler.transform(
            y.reshape(-1, 1)
        ).flatten()
        
        # Split train/val
        indices = np.arange(len(X_scaled))
        idx_train, idx_val = train_test_split(
            indices, test_size=validation_split, random_state=42
        )
        
        X_agg_train = X_scaled[idx_train]
        X_agg_val = X_scaled[idx_val]
        X_app_train = X_app_ids[idx_train]
        X_app_val = X_app_ids[idx_val]
        y_train = y_scaled[idx_train]
        y_val = y_scaled[idx_val]
        
        # Construire ou ajuster modèle
        if not is_fine_tuning:
            self.model = self.build_model()
        else:
            logger.info(f"Ajustement learning rate: {learning_rate}")
            self.model.optimizer.learning_rate.assign(learning_rate)
        
        # Callbacks
        callbacks_list = [
            callbacks.EarlyStopping(
                monitor='val_loss',
                patience=10,
                restore_best_weights=True,
                verbose=1
            ),
            callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=5,
                min_lr=1e-6,
                verbose=1
            )
        ]
        
        # TensorBoard
        tensorboard_root = Path(settings.cnn_model_path) / "tensorboard"
        run_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        log_dir = tensorboard_root / f"film_{self.model_type}" / version / run_id
        log_dir.mkdir(parents=True, exist_ok=True)
        callbacks_list.append(
            callbacks.TensorBoard(
                log_dir=str(log_dir),
                histogram_freq=0,
                write_graph=False,
                profile_batch=0
            )
        )
        logger.info(f"📊 TensorBoard → {log_dir}")
        
        # Entraînement
        self.history = self.model.fit(
            [X_agg_train, X_app_train],
            y_train,
            validation_data=([X_agg_val, X_app_val], y_val),
            epochs=epochs,
            batch_size=batch_size,
            callbacks=callbacks_list,
            verbose=1
        )
        
        logger.info("✅ Entraînement FiLM terminé")
        
        # Métriques
        metrics = {
            'epochs_trained': len(self.history.history['loss']),
            'train_loss': float(self.history.history['loss'][-1]),
            'val_loss': float(self.history.history['val_loss'][-1]),
            'train_mae': float(self.history.history['mae'][-1]),
            'val_mae': float(self.history.history['val_mae'][-1]),
            'appliances': self.appliance_names,
            'architecture': 'FiLM'
        }
        
        return metrics
    
    def predict(
        self,
        aggregate_power: np.ndarray,
        appliance_id: int,
        stride: int = 1
    ) -> np.ndarray:
        """
        Prédit la consommation pour UN appareil spécifique.
        
        Args:
            aggregate_power: Série agrégée
            appliance_id: ID de l'appareil à désagréger
            stride: Pas de fenêtre glissante
        
        Returns:
            Prédictions de puissance
        """
        if self.model is None:
            raise ValueError("Modèle FiLM non entraîné/chargé")
        
        if appliance_id not in self.appliance_id_to_idx:
            raise ValueError(f"Appareil {appliance_id} inconnu")
        
        # Créer fenêtres glissantes
        X = self.preprocessor.create_prediction_windows(
            aggregate_power, stride=stride
        )
        
        if len(X) == 0:
            return np.zeros_like(aggregate_power)
        
        # Normaliser
        X_scaled, _ = self.preprocessor.transform(X)
        X_scaled = X_scaled.reshape(X_scaled.shape[0], X_scaled.shape[1], 1)
        
        # Encoder appliance_id
        appliance_one_hot = self.encode_appliance_id(appliance_id)
        X_app_ids = np.tile(appliance_one_hot, (len(X_scaled), 1))
        
        # Prédiction
        predictions_scaled = self.model.predict(
            [X_scaled, X_app_ids],
            batch_size=32,
            verbose=0
        )
        
        # Dénormaliser
        predictions = self.preprocessor.target_scaler.inverse_transform(
            predictions_scaled
        ).flatten()
        
        # Post-traitement
        predictions = np.maximum(predictions, 0)
        
        # Reconstruction signal complet
        result = np.zeros(len(aggregate_power))
        half_window = self.sequence_length // 2
        
        for i, pred in enumerate(predictions):
            idx = i * stride + half_window
            if idx < len(result):
                result[idx] = pred
        
        # Interpolation
        if stride > 1:
            from scipy.interpolate import interp1d
            indices = np.arange(0, len(result), stride)
            indices = np.minimum(indices, len(result) - 1)
            values = result[indices]
            f = interp1d(
                indices, values,
                kind='linear',
                fill_value='extrapolate'
            )
            result = f(np.arange(len(result)))
        
        return result
    
    def _add_negative_examples_film(
        self,
        X_aggregate: List,
        X_appliance_ids: List,
        y_power: List
    ) -> int:
        """
        Ajoute exemples négatifs pour FiLM.
        Similaire à la version multi-output mais adapté pour FiLM.
        """
        negative_count = 0
        negative_sigs = self._load_negative_signatures()
        
        for appliance_id, signatures in negative_sigs.items():
            if appliance_id not in self.appliance_id_to_idx:
                continue
            
            appliance_one_hot = self.encode_appliance_id(appliance_id)
            
            for sig in signatures:
                aggregate = self._load_aggregate_data(
                    sig['start_time'],
                    sig['end_time']
                )
                
                if aggregate is None or len(aggregate) < self.sequence_length:
                    continue
                
                # Target = 0 (négatif)
                zero_target = np.zeros(len(aggregate), dtype=np.float32)
                
                X, y = self.preprocessor.create_sequences(
                    aggregate, zero_target, stride=50
                )
                
                if len(X) > 0:
                    # Répéter 2x pour augmenter poids négatifs
                    for _ in range(2):
                        X_aggregate.append(X)
                        X_appliance_ids.append(
                            np.tile(appliance_one_hot, (len(X), 1))
                        )
                        y_power.append(y)
                    negative_count += len(X) * 2
        
        return negative_count
    
    def _load_negative_signatures(self) -> Dict[int, List[Dict[str, Any]]]:
        """Charge les signatures négatives depuis la base."""
        try:
            with db_manager.engine.connect() as conn:
                query = text("""
                    SELECT id, appliance_id, start_time, end_time
                    FROM cnn_signatures
                    WHERE is_negative = TRUE
                    ORDER BY created_at DESC
                """)
                result = conn.execute(query)
                
                signatures_by_appliance = {}
                for row in result:
                    signature = {
                        'id': row[0],
                        'appliance_id': row[1],
                        'start_time': row[2],
                        'end_time': row[3]
                    }
                    
                    app_id = signature['appliance_id']
                    if app_id not in signatures_by_appliance:
                        signatures_by_appliance[app_id] = []
                    signatures_by_appliance[app_id].append(signature)
                
                total = sum(len(s) for s in signatures_by_appliance.values())
                logger.info(f"📋 {total} signatures négatives chargées")
                
                return signatures_by_appliance
        except Exception as e:
            logger.error(f"Erreur chargement signatures négatives: {e}")
            return {}
    
    def _load_aggregate_data(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[np.ndarray]:
        """Charge données agrégées pour une période."""
        try:
            with db_manager.engine.connect() as conn:
                query = text("""
                    SELECT papp
                    FROM linky_realtime
                    WHERE time >= :start_time
                      AND time <= :end_time
                    ORDER BY time
                """)
                result = conn.execute(
                    query,
                    {'start_time': start_time, 'end_time': end_time}
                )
                power_values = [row[0] for row in result if row[0] is not None]
                
                if not power_values:
                    return None
                
                return np.array(power_values, dtype=np.float32)
        except Exception as e:
            logger.error(f"Erreur chargement données agrégées: {e}")
            return None
    
    @staticmethod
    def _load_signature_data_static(signature: Dict[str, Any]) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Charge les données d'une signature (aggregate + appliance)."""
        try:
            with db_manager.engine.connect() as conn:
                query = text("""
                    SELECT time, papp
                    FROM linky_realtime
                    WHERE time >= :start_time
                      AND time <= :end_time
                    ORDER BY time
                """)
                result = conn.execute(
                    query,
                    {
                        'start_time': signature['start_time'],
                        'end_time': signature['end_time']
                    }
                )
                
                aggregate_power = [row[1] for row in result if row[1] is not None]
                
                if not aggregate_power:
                    return None, None
                
                aggregate_power = np.array(aggregate_power, dtype=np.float32)
                
                # For appliance power: use aggregate as proxy
                # Negative signatures: appliance is OFF (zero power)
                # Positive signatures: appliance is ON (use aggregate)
                if signature.get('is_negative', False):
                    # Negative signature: appliance is off
                    appliance_power = np.zeros(
                        len(aggregate_power), dtype=np.float32
                    )
                else:
                    # Positive signature: appliance consumes the aggregate
                    # (assuming single appliance activation)
                    appliance_power = aggregate_power.copy()
                
                return aggregate_power, appliance_power
        except Exception as e:
            logger.error(f"Erreur chargement données signature: {e}")
            return None, None
    
    def save(self, filepath: str, metadata: Optional[Dict[str, Any]] = None):
        """Sauvegarde le modèle FiLM."""
        if self.model is None:
            raise ValueError("Aucun modèle à sauvegarder")
        
        # Sauvegarder le modèle Keras
        self.model.save(filepath)
        logger.info(f"💾 Modèle FiLM sauvegardé: {filepath}")
        
        # Sauvegarder les métadonnées
        meta = {
            'architecture': 'FiLM',
            'model_type': self.model_type,
            'sequence_length': self.sequence_length,
            'num_appliances': self.num_appliances,
            'appliance_ids': self.appliance_ids,
            'appliance_names': self.appliance_names,
            'appliance_id_to_idx': self.appliance_id_to_idx
        }
        if metadata:
            meta.update(metadata)
        
        meta_path = filepath.replace('.keras', '.metadata.json')
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=2)
        logger.info(f"📝 Métadonnées sauvegardées: {meta_path}")
    
    def load(self, filepath: str):
        """Charge le modèle FiLM."""
        # Charger le modèle Keras
        custom_objects = {
            'FiLMLayer': FiLMLayer,
            'asymmetric_loss': asymmetric_loss,
            'focal_loss_fixed': focal_loss_fixed
        }
        self.model = keras.models.load_model(
            filepath,
            custom_objects=custom_objects
        )
        logger.info(f"📂 Modèle FiLM chargé: {filepath}")
        
        # Charger métadonnées
        meta_path = filepath.replace('.keras', '.metadata.json')
        if Path(meta_path).exists():
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            
            self.appliance_ids = meta['appliance_ids']
            self.appliance_names = meta['appliance_names']
            self.num_appliances = meta['num_appliances']
            self.appliance_id_to_idx = {
                int(k): v for k, v in meta['appliance_id_to_idx'].items()
            }
            self.appliance_idx_to_id = {
                v: int(k) for k, v in self.appliance_id_to_idx.items()
            }
            logger.info(f"📋 Métadonnées chargées: {self.num_appliances} appareils")


# --- S2P Multi-sorties : un seul modèle pour tous les appareils ---
class Seq2PointMultiModel:
    """Modèle Sequence-to-Point multi-sorties pour tous les appareils"""
    def __init__(self, appliance_ids: List[int], appliance_names: List[str], sequence_length: int = 299, model_type: str = "gru"):
        self.appliance_ids = appliance_ids
        self.appliance_names = appliance_names
        self.sequence_length = sequence_length if sequence_length % 2 == 1 else sequence_length - 1
        self.model_type = model_type
        self.num_appliances = len(appliance_ids)
        self.model: Optional[keras.Model] = None
        self.preprocessor = Seq2PointPreprocessor(self.sequence_length)
        self.state_detectors: Dict[int, ApplianceStateDetector] = {}
        self.history = None
        self.use_gpu = self._configure_device()

    def _configure_device(self) -> bool:
        gpus = tf.config.list_physical_devices('GPU')
        if gpus:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            logger.info(f"Device: GPU ({len(gpus)} disponible(s))")
            return True
        logger.info("Device: CPU")
        return False

    def build_model(self) -> keras.Model:
        inputs = layers.Input(shape=(self.sequence_length, 1), name='aggregate_input')
        if self.model_type == "gru":
            x = layers.GRU(128, return_sequences=True, name='gru_1')(inputs)
            x = layers.Dropout(0.2)(x)
            x = layers.GRU(64, return_sequences=False, name='gru_2')(x)
            x = layers.Dropout(0.2)(x)
        elif self.model_type == "lstm":
            x = layers.LSTM(128, return_sequences=True, name='lstm_1')(inputs)
            x = layers.Dropout(0.2)(x)
            x = layers.LSTM(64, return_sequences=False, name='lstm_2')(x)
            x = layers.Dropout(0.2)(x)
        else:
            raise ValueError(f"Type de modèle inconnu: {self.model_type}")
        x = layers.Dense(64, activation='relu', name='dense_1')(x)
        x = layers.Dropout(0.1)(x)
        x = layers.Dense(32, activation='relu', name='dense_2')(x)
        # Multi-sorties : une sortie par appareil
        outputs = [
            layers.Dense(1, activation='linear', name=f'power_{i}')(x)
            for i in range(self.num_appliances)
        ]
        model = models.Model(
            inputs=inputs,
            outputs=outputs,
            name=f's2p_multi_{self.model_type}'
        )
        
        # Utiliser la loss asymétrique qui pénalise les faux positifs
        loss_fn = asymmetric_loss(false_positive_penalty=2.5)
        
        metrics = {
            f'power_{i}': ['mae', 'mse']
            for i in range(self.num_appliances)
        }
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss=loss_fn,  # Loss asymétrique au lieu de 'mae'
            metrics=metrics
        )
        logger.info(
            f"Modèle S2P-MULTI {self.model_type.upper()} construit "
            f"({self.num_appliances} appareils, "
            f"séquence={self.sequence_length}, loss=asymmetric)"
        )
        return model

    def _load_negative_signatures(self) -> Dict[int, List[Dict[str, Any]]]:
        """
        Charge les signatures négatives (exemples de ce qu'il ne faut PAS détecter).

        Ces signatures sont créées automatiquement quand l'utilisateur invalide une détection.
        Elles persistent dans la base et permettent de vider les détections sans perdre l'apprentissage.

        Returns:
            Dict[appliance_id, List[negative_signature]] des signatures négatives
        """
        try:
            with db_manager.engine.connect() as conn:
                query = text("""
                    SELECT
                        id,
                        appliance_id,
                        start_time,
                        end_time
                    FROM cnn_signatures
                    WHERE is_negative = TRUE
                    ORDER BY created_at DESC
                """)

                result = conn.execute(query)

                signatures_by_appliance = {}
                for row in result:
                    signature = {
                        'id': row[0],
                        'appliance_id': row[1],
                        'start_time': row[2],
                        'end_time': row[3]
                    }

                    appliance_id = signature['appliance_id']
                    if appliance_id not in signatures_by_appliance:
                        signatures_by_appliance[appliance_id] = []
                    signatures_by_appliance[appliance_id].append(signature)

                total = sum(len(sigs) for sigs in signatures_by_appliance.values())
                logger.info(f"Récupéré {total} signatures négatives (exemples à ne PAS détecter)")

                return signatures_by_appliance

        except Exception as e:
            logger.error(f"Erreur lors du chargement des signatures négatives: {e}")
            return {}

    def _add_negative_examples(
        self,
        X_all: List,
        y_all: List[List]
    ) -> int:
        """
        Ajoute des exemples négatifs avec augmentation de données.

        Les signatures négatives sont créées automatiquement quand
        l'utilisateur invalide une détection. Elles persistent dans
        la base et peuvent être réutilisées même après avoir vidé
        la table des détections.
        
        Amélioration: Génère des variations des signatures négatives
        pour augmenter la robustesse du modèle.

        Args:
            X_all: Liste des séquences d'input (agrégat)
            y_all: Liste par appareil des targets

        Returns:
            Nombre d'exemples négatifs ajoutés
        """
        negative_signatures = self._load_negative_signatures()
        negative_count = 0

        for idx, appliance_id in enumerate(self.appliance_ids):
            signatures = negative_signatures.get(appliance_id, [])

            for signature in signatures:
                # Charger la consommation agrégée pour cette période
                aggregate_power = self._load_aggregate_data(
                    signature['start_time'],
                    signature['end_time']
                )

                if (aggregate_power is None or
                        len(aggregate_power) < self.sequence_length):
                    continue

                # Générer des variations pour augmentation de données
                # Cela rend le modèle plus robuste aux faux positifs
                augmented_powers = [aggregate_power]
                
                # Variation 1: Ajouter du bruit gaussien (±5%)
                noise_level = np.std(aggregate_power) * 0.05
                noisy = aggregate_power + np.random.normal(
                    0, noise_level, len(aggregate_power)
                )
                augmented_powers.append(noisy.astype(np.float32))
                
                # Variation 2: Scaling (±10%)
                for scale in [0.9, 1.1]:
                    scaled = aggregate_power * scale
                    augmented_powers.append(scaled.astype(np.float32))

                # Créer des séquences pour chaque variation
                for aug_power in augmented_powers:
                    # Target = 0 (appareil non actif / faux positif)
                    zero_target = np.zeros(len(aug_power), dtype=np.float32)
                    X, y = self.preprocessor.create_sequences(
                        aug_power,
                        zero_target,
                        stride=50
                    )

                    if len(X) > 0:
                        # Ajouter avec répétition pour augmenter le poids
                        # (2x plus d'exemples négatifs dans le dataset)
                        for _ in range(2):
                            X_all.append(X)
                            y_all[idx].append(y)
                        negative_count += len(X) * 2

        logger.info(
            f"Ajout de {negative_count} exemples négatifs "
            f"(avec augmentation de données)"
        )
        return negative_count

    @staticmethod
    def _load_aggregate_data(start_time: datetime, end_time: datetime) -> Optional[np.ndarray]:
        """
        Charge les données de consommation agrégée pour une période donnée.

        Args:
            start_time: Début de la période
            end_time: Fin de la période

        Returns:
            Array numpy de la puissance agrégée ou None si erreur
        """
        try:
            data = db_manager.get_consumption_data(
                start_time=start_time,
                end_time=end_time,
                resample_seconds=1
            )

            if not data:
                return None

            values = np.array([row['papp'] for row in data], dtype=np.float32)
            return values

        except Exception as e:
            logger.error(f"Erreur lors du chargement des données agrégées: {e}")
            return None

    def train(self, all_signatures: Dict[int, List[Dict[str, Any]]], version: str, epochs: int = 30, batch_size: int = 32, validation_split: float = 0.15, use_feedback: bool = True, fine_tune: bool = False) -> Dict[str, Any]:
        """
        Entraîne le modèle multi-sorties sur toutes les signatures + feedbacks utilisateur
        Args:
            all_signatures: Dict[appliance_id, List[signature]]
            version: Version du modèle
            use_feedback: Si True, utilise les détections invalidées comme exemples négatifs
            fine_tune: Si True, continue l'entraînement du modèle existant au lieu de from-scratch
        Returns:
            Dictionnaire de métriques
        """
        is_fine_tuning = fine_tune and self.model is not None
        if is_fine_tuning:
            logger.info("🔄 Mode FINE-TUNING activé - Amélioration du modèle existant")
            # Paramètres adaptés au fine-tuning
            learning_rate = 0.0001  # 10x plus faible que from-scratch
            epochs = min(epochs, 15)  # Maximum 15 epochs pour le fine-tuning
        else:
            logger.info("🆕 Mode FROM-SCRATCH - Création d'un nouveau modèle")
            learning_rate = 0.001

        # Préparer les données pour chaque appareil (exemples positifs)
        X_all, y_all = [], [[] for _ in range(self.num_appliances)]
        for idx, appliance_id in enumerate(self.appliance_ids):
            signatures = all_signatures.get(appliance_id, [])
            for sig in signatures:
                aggregate_power, appliance_power = self._load_signature_data_static(sig)
                if aggregate_power is None or len(aggregate_power) < self.sequence_length:
                    continue
                X, y = self.preprocessor.create_sequences(aggregate_power, appliance_power, stride=30)
                if len(X) > 0:
                    X_all.append(X)
                    y_all[idx].append(y)

        # Ajouter les exemples négatifs (hard negative mining)
        if use_feedback:
            negative_count = self._add_negative_examples(X_all, y_all)
            if negative_count > 0:
                logger.info(f"Ajout de {negative_count} exemples négatifs (hard negative mining)")

        # Concaténer toutes les séquences
        if not X_all or not any(y_list for y_list in y_all):
            logger.error("Aucune donnée valide pour l'entraînement multi-sorties")
            return {}
        X = np.concatenate(X_all, axis=0)
        y_targets = [np.concatenate(y_all[i], axis=0) if y_all[i] else np.zeros((len(X),)) for i in range(self.num_appliances)]

        # Ajuster les scalers UNIQUEMENT si pas de fine-tuning (from-scratch)
        if not is_fine_tuning:
            logger.info("Ajustement des scalers (from-scratch)")
            self.preprocessor.input_scaler.fit(X.reshape(-1, 1))
            flat_targets_for_scaler = [
                np.concatenate(y_list, axis=0) for y_list in y_all if y_list
            ]
            if flat_targets_for_scaler:
                concatenated_targets = np.concatenate(flat_targets_for_scaler, axis=0)
                self.preprocessor.target_scaler.fit(concatenated_targets.reshape(-1, 1))
            self.preprocessor.fitted = True
        else:
            logger.info("Réutilisation des scalers existants (fine-tuning)")
        # Préparer les détecteurs d'états pour chaque appareil
        for idx, appliance_id in enumerate(self.appliance_ids):
            if not y_all[idx]:
                continue
            try:
                power_values = np.concatenate(y_all[idx], axis=0)
                # Utiliser 2 états (ON/OFF) pour éviter la sur-fragmentation
                detector = ApplianceStateDetector(n_states=2)
                detector.fit(power_values)
                self.state_detectors[appliance_id] = detector
            except Exception as e:
                logger.warning(f"Impossible de calibrer le détecteur d'états pour l'appareil {appliance_id}: {e}")
        # Normaliser X
        X_scaled, _ = self.preprocessor.transform(X)
        X_scaled = X_scaled.reshape(X_scaled.shape[0], X_scaled.shape[1], 1)
        # Normaliser y
        y_scaled = [
            self.preprocessor.target_scaler.transform(y_targets[i].reshape(-1, 1)).flatten()
            for i in range(self.num_appliances)
        ]
        # Split train/val
        X_train, X_val = train_test_split(X_scaled, test_size=validation_split, random_state=42)
        y_train = [train_test_split(y_scaled[i], test_size=validation_split, random_state=42)[0] for i in range(self.num_appliances)]
        y_val = [train_test_split(y_scaled[i], test_size=validation_split, random_state=42)[1] for i in range(self.num_appliances)]

        # Construire ou réutiliser le modèle
        if not is_fine_tuning:
            # From-scratch: construire un nouveau modèle
            self.model = self.build_model()
        else:
            # Fine-tuning: ajuster le learning rate du modèle existant
            logger.info(f"Ajustement du learning rate: {learning_rate}")
            self.model.optimizer.learning_rate.assign(learning_rate)

        # Callbacks
        callbacks_list = [
            callbacks.EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True, verbose=1),
            callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=1e-6, verbose=1)
        ]
        tensorboard_root = Path(settings.cnn_model_path) / "tensorboard"
        run_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        log_dir = tensorboard_root / f"multi_{self.model_type}" / version / run_id
        log_dir.mkdir(parents=True, exist_ok=True)
        callbacks_list.append(
            callbacks.TensorBoard(
                log_dir=str(log_dir),
                histogram_freq=0,
                write_graph=False,
                profile_batch=0
            )
        )
        logger.info(f"TensorBoard (multi) → {log_dir}")
        # Entraînement
        self.history = self.model.fit(
            X_train,
            [y_train[i] for i in range(self.num_appliances)],
            validation_data=(X_val, [y_val[i] for i in range(self.num_appliances)]),
            epochs=epochs,
            batch_size=batch_size,
            callbacks=callbacks_list,
            verbose=1
        )
        logger.info(f"Entraînement multi-sorties terminé")

        # Afficher les clés disponibles pour debug
        logger.info(f"Clés disponibles dans l'historique: {list(self.history.history.keys())}")

        # Métriques
        metrics = {}
        for i, name in enumerate(self.appliance_names):
            # Construire les métriques pour cet appareil
            appliance_metrics = {
                'epochs_trained': len(self.history.history['loss'])
            }

            # Chercher les métriques avec différents formats de noms possibles
            # Keras peut nommer les métriques différemment selon le nombre de sorties:
            # - Si une seule sortie: 'mae', 'val_mae', 'mse', 'val_mse'
            # - Si plusieurs sorties: 'power_0_mae', 'val_power_0_mae', etc.
            if self.num_appliances == 1:
                # Cas spécial: une seule sortie, pas de préfixe
                possible_mae_keys = ['mae']
                possible_val_mae_keys = ['val_mae']
                possible_mse_keys = ['mse']
                possible_val_mse_keys = ['val_mse']
            else:
                # Plusieurs sorties: préfixe avec le nom de la sortie
                possible_mae_keys = [
                    f'power_{i}_mae',
                    f'power_{i}_mean_absolute_error',
                ]
                possible_val_mae_keys = [
                    f'val_power_{i}_mae',
                    f'val_power_{i}_mean_absolute_error',
                ]
                possible_mse_keys = [
                    f'power_{i}_mse',
                    f'power_{i}_mean_squared_error',
                ]
                possible_val_mse_keys = [
                    f'val_power_{i}_mse',
                    f'val_power_{i}_mean_squared_error',
                ]

            # Trouver train_mae
            for key in possible_mae_keys:
                if key in self.history.history:
                    appliance_metrics['train_mae'] = float(self.history.history[key][-1])
                    break

            # Trouver val_mae
            for key in possible_val_mae_keys:
                if key in self.history.history:
                    appliance_metrics['val_mae'] = float(self.history.history[key][-1])
                    break

            # Trouver train_mse
            for key in possible_mse_keys:
                if key in self.history.history:
                    appliance_metrics['train_mse'] = float(self.history.history[key][-1])
                    break

            # Trouver val_mse
            for key in possible_val_mse_keys:
                if key in self.history.history:
                    appliance_metrics['val_mse'] = float(self.history.history[key][-1])
                    break

            # Log si des métriques sont manquantes
            if 'train_mae' not in appliance_metrics or 'val_mae' not in appliance_metrics:
                logger.warning(f"Métriques partiellement manquantes pour '{name}' (sortie {i})")
            else:
                logger.info(f"Métriques '{name}': train_mae={appliance_metrics['train_mae']:.2f}W, val_mae={appliance_metrics['val_mae']:.2f}W")

            metrics[name] = appliance_metrics

        return metrics

    def predict_all(
        self,
        aggregate_power: np.ndarray,
        stride: int = 1
    ) -> Tuple[Dict[int, np.ndarray], Dict[int, Dict[str, Any]]]:
        """
        Prédit la consommation pour tous les appareils simultanément.

        Args:
            aggregate_power: Série de puissance agrégée (1Hz).
            stride: Pas de déplacement de la fenêtre (par défaut 1 pour couvrir toute la série).

        Returns:
            Tuple contenant:
                - Dictionnaire {appliance_id: prédictions}
                - Dictionnaire {appliance_id: métadonnées}
        """
        if self.model is None:
            raise ValueError("Le modèle multi-sorties doit être entraîné/chargé avant prédiction")
        if not self.preprocessor.fitted:
            raise ValueError("Le préprocesseur multi-sorties n'est pas initialisé (fit manquant)")

        dummy_target = np.zeros_like(aggregate_power)
        X, _ = self.preprocessor.create_sequences(
            aggregate_power,
            dummy_target,
            stride=stride
        )
        if len(X) == 0:
            logger.warning("Aucune séquence générée pour la prédiction multi-sorties")
            return {}, {}

        X_scaled, _ = self.preprocessor.transform(X)
        X_scaled = X_scaled.reshape(X_scaled.shape[0], X_scaled.shape[1], 1)

        with tf.device('/GPU:0' if self.use_gpu else '/CPU:0'):
            predictions_scaled = self.model.predict(X_scaled, batch_size=64, verbose=0)

        if not isinstance(predictions_scaled, list):
            predictions_scaled = [predictions_scaled]

        predictions_dict: Dict[int, np.ndarray] = {}
        metadata_dict: Dict[int, Dict[str, Any]] = {}

        for idx, appliance_id in enumerate(self.appliance_ids):
            if idx >= len(predictions_scaled):
                logger.warning(f"Pas de prédiction pour l'appareil index {idx} (ID={appliance_id})")
                continue
            scaled_output = predictions_scaled[idx].flatten()
            y_pred = self.preprocessor.inverse_transform_target(scaled_output)
            y_pred = np.maximum(y_pred, 0)

            predictions_dict[appliance_id] = y_pred

            appliance_name = self.appliance_names[idx] if idx < len(self.appliance_names) else f"appliance_{appliance_id}"
            metadata: Dict[str, Any] = {
                'appliance_id': appliance_id,
                'appliance_name': appliance_name,
                'num_predictions': int(len(y_pred)),
                'avg_power': float(np.mean(y_pred)) if len(y_pred) > 0 else 0.0,
                'max_power': float(np.max(y_pred)) if len(y_pred) > 0 else 0.0,
                'energy_wh': float(np.sum(y_pred) / 3600) if len(y_pred) > 0 else 0.0,
            }

            detector = self.state_detectors.get(appliance_id)
            if detector is not None and getattr(detector, 'kmeans', None) is not None and len(y_pred) > 0:
                try:
                    # Assurer que y_pred est en float32 (type TensorFlow natif)
                    y_pred_float32 = y_pred.astype(np.float32)
                    # Log des stats de prédiction pour diagnostic
                    logger.info(f"Prédictions {appliance_name}: min={np.min(y_pred_float32):.1f}W, "
                               f"max={np.max(y_pred_float32):.1f}W, "
                               f"mean={np.mean(y_pred_float32):.1f}W, "
                               f">500W: {np.sum(y_pred_float32 > 500)}/{len(y_pred_float32)} points")
                    states, cycles = detector.predict_states(y_pred_float32)
                    metadata['states'] = states.tolist()
                    metadata['cycles'] = cycles
                    metadata['num_cycles'] = len(cycles)
                except Exception as e:
                    logger.warning(f"Erreur détection d'états pour l'appareil {appliance_id}: {e}")

            metadata_dict[appliance_id] = metadata

        return predictions_dict, metadata_dict

    def save(self, filepath: str):
        """Sauvegarde le modèle multi-sorties et ses métadonnées associées."""
        if self.model is None:
            raise ValueError("Aucun modèle à sauvegarder (multi-sorties)")

        self.model.save(filepath)

        metadata = {
            'appliance_ids': self.appliance_ids,
            'appliance_names': self.appliance_names,
            'sequence_length': self.sequence_length,
            'model_type': self.model_type,
            'use_gpu': self.use_gpu,
            'input_scaler_mean': self.preprocessor.input_scaler.mean_.tolist() if self.preprocessor.fitted else None,
            'input_scaler_scale': self.preprocessor.input_scaler.scale_.tolist() if self.preprocessor.fitted else None,
            'target_scaler_min': self.preprocessor.target_scaler.data_min_.tolist() if self.preprocessor.fitted else None,
            'target_scaler_max': self.preprocessor.target_scaler.data_max_.tolist() if self.preprocessor.fitted else None,
            'target_scaler_range': self.preprocessor.target_scaler.data_range_.tolist() if self.preprocessor.fitted else None,
            'target_scaler_scale': self.preprocessor.target_scaler.scale_.tolist() if self.preprocessor.fitted else None,
        }

        if self.state_detectors:
            metadata['state_detectors'] = {
                str(app_id): {
                    'n_states': detector.n_states,
                    'has_kmeans': detector.kmeans is not None,
                    'state_thresholds': [
                        float(x) for x in detector.state_thresholds
                    ] if detector.state_thresholds is not None else None
                }
                for app_id, detector in self.state_detectors.items()
            }

        metadata_path = Path(filepath).with_suffix('.metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Modèle multi-sorties sauvegardé: {filepath}")

    def load(self, filepath: str):
        """Charge le modèle multi-sorties avec les custom losses."""
        # Charger le modèle avec les custom objects
        custom_objects = {
            'asymmetric_loss': asymmetric_loss,
            'focal_loss_fixed': focal_loss_fixed,
            'loss_fn': asymmetric_loss,  # Pour les anciens modèles
        }
        try:
            self.model = keras.models.load_model(
                filepath,
                custom_objects=custom_objects
            )
        except Exception as e:
            logger.warning(f"Erreur chargement avec custom_objects: {e}")
            # Essayer sans compile si problème avec loss
            self.model = keras.models.load_model(
                filepath,
                compile=False
            )
            # Recompiler avec la nouvelle loss
            self.model.compile(
                optimizer=keras.optimizers.Adam(learning_rate=0.001),
                loss=asymmetric_loss(false_positive_penalty=2.5),
                metrics=['mae', 'mse']
            )
            logger.info("Modèle rechargé et recompilé avec nouvelle loss")

        metadata_path = Path(filepath).with_suffix('.metadata.json')
        if not metadata_path.exists():
            logger.warning(f"Métadonnées multi-sorties introuvables pour {filepath}")
            return

        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        self.appliance_ids = metadata.get('appliance_ids', self.appliance_ids)
        self.appliance_names = metadata.get('appliance_names', self.appliance_names)
        self.sequence_length = metadata.get('sequence_length', self.sequence_length)
        self.model_type = metadata.get('model_type', self.model_type)
        self.use_gpu = metadata.get('use_gpu', self.use_gpu)

        input_mean = metadata.get('input_scaler_mean')
        input_scale = metadata.get('input_scaler_scale')
        target_min = metadata.get('target_scaler_min')
        target_max = metadata.get('target_scaler_max')
        target_range = metadata.get('target_scaler_range')
        target_scale = metadata.get('target_scaler_scale')

        if all(v is not None for v in (input_mean, input_scale, target_min, target_max, target_range, target_scale)):
            self.preprocessor.input_scaler.mean_ = np.array(input_mean)
            self.preprocessor.input_scaler.scale_ = np.array(input_scale)
            self.preprocessor.target_scaler.data_min_ = np.array(target_min)
            self.preprocessor.target_scaler.data_max_ = np.array(target_max)
            self.preprocessor.target_scaler.data_range_ = np.array(target_range)
            self.preprocessor.target_scaler.scale_ = np.array(target_scale)
            # Restaurer min_ requis pour inverse_transform (pour feature_range=(0, 1))
            self.preprocessor.target_scaler.min_ = -self.preprocessor.target_scaler.data_min_ / self.preprocessor.target_scaler.data_range_
            # Marquer n_features_in_ pour sklearn
            self.preprocessor.target_scaler.n_features_in_ = 1
            self.preprocessor.fitted = True
            logger.info("Scalers multi-sorties restaurés depuis les métadonnées")
        else:
            logger.warning("Scalers multi-sorties non trouvés dans les métadonnées; préprocesseur à réinitialiser si nécessaire")

        state_detectors_meta = metadata.get('state_detectors', {})
        self.state_detectors = {}
        if state_detectors_meta:
            for app_id_str, detector_meta in state_detectors_meta.items():
                try:
                    app_id = int(app_id_str)
                except ValueError:
                    continue
                detector = ApplianceStateDetector(n_states=detector_meta.get('n_states', 5))
                state_thresholds = detector_meta.get('state_thresholds')
                detector.state_thresholds = state_thresholds

                # Reconstruire un KMeans factice depuis les seuils sauvegardés
                if state_thresholds:
                    detector.kmeans = KMeans(n_clusters=detector.n_states, random_state=42, n_init=10)
                    # Créer des cluster_centers_ factices (float32 pour correspondre aux prédictions TensorFlow)
                    detector.kmeans.cluster_centers_ = np.array(state_thresholds, dtype=np.float32).reshape(-1, 1)
                    # Marquer comme "fit"
                    detector.kmeans._n_threads = 1
                    logger.info(f"KMeans restauré avec {len(state_thresholds)} centres pour appareil {app_id}")

                self.state_detectors[app_id] = detector

        logger.info(f"Métadonnées multi-sorties chargées depuis {metadata_path}")

    @staticmethod
    def _load_signature_data_static(signature: Dict[str, Any]) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Charge les données de consommation pour une signature et les ré-échantillonne à 1Hz.
        """
        try:
            data = db_manager.get_consumption_data(
                start_time=signature['start_time'],
                end_time=signature['end_time'],
                resample_seconds=1
            )

            if not data:
                logger.warning(
                    f"Signature {signature.get('id')} sans données dans linky_realtime "
                    f"({signature['start_time']} - {signature['end_time']})"
                )
                return None, None

            timestamps = np.array(
                [row['time'].timestamp() for row in data],
                dtype=np.float64
            )
            values = np.array(
                [row['papp'] for row in data],
                dtype=np.float32
            )

            if len(timestamps) < 2:
                logger.warning(
                    f"Signature {signature.get('id')} trop courte ({len(timestamps)} points)"
                )
                return None, None

            start_ts = signature['start_time'].timestamp()
            end_ts = signature['end_time'].timestamp()

            full_timestamps = np.arange(
                start_ts,
                end_ts + 1,
                1.0,
                dtype=np.float64
            )

            unique_ts, unique_indices = np.unique(timestamps, return_index=True)
            unique_values = values[unique_indices]

            interpolated_values = np.interp(
                full_timestamps,
                unique_ts,
                unique_values
            ).astype(np.float32)

            aggregate_power = interpolated_values
            appliance_power = aggregate_power.copy()
            return aggregate_power, appliance_power
        except Exception as e:
            logger.error(f"Erreur chargement signature {signature.get('id')}: {e}")
            return None, None



def normalize_name_for_tensorflow(name: str) -> str:
    """
    Normalise un nom pour être compatible avec TensorFlow/Keras.
    Les noms de scope TensorFlow doivent correspondre au pattern: ^[A-Za-z0-9.][A-Za-z0-9_.\\/>-]*$
    
    Args:
        name: Nom à normaliser
        
    Returns:
        Nom normalisé (espaces → underscores, caractères spéciaux supprimés)
    """
    import re
    # Remplacer les espaces par des underscores
    normalized = name.replace(' ', '_')
    # Remplacer les apostrophes par rien
    normalized = normalized.replace("'", '')
    # Garder uniquement les caractères alphanumériques, points, underscores, slashes, tirets
    normalized = re.sub(r'[^A-Za-z0-9._/\->]', '', normalized)
    # S'assurer que le nom commence par une lettre, chiffre ou point
    if normalized and not re.match(r'^[A-Za-z0-9.]', normalized):
        normalized = 'appliance_' + normalized
    return normalized if normalized else 'unknown_appliance'


class ChangePointPatternDetector:
    """
    Détecteur hybride combinant change point detection et pattern matching.

    Approche :
    1. Détecte les change points (sauts significatifs) dans l'agrégé
    2. Extrait les patterns entre les baselines
    3. Compare avec les profils de signatures connus
    4. Reconstruit des cycles complets
    """

    def __init__(self, min_power_change: float = 500, min_duration: int = 300):
        """
        Args:
            min_power_change: Seuil minimal pour détecter un change point (W)
            min_duration: Durée minimale d'un pattern (secondes)
        """
        self.min_power_change = min_power_change
        self.min_duration = min_duration
        self.signature_profiles = {}  # {appliance_id: [profils]}

    def add_signature_profile(self, appliance_id: int, appliance_name: str,
                             power_sequence: np.ndarray, duration: int,
                             signature_id: Optional[int] = None):
        """
        Ajoute un profil de signature depuis les données d'entraînement.

        Args:
            appliance_id: ID de l'appareil
            appliance_name: Nom de l'appareil
            power_sequence: Séquence de puissance normalisée (0-1)
            duration: Durée en secondes
        """
        if appliance_id not in self.signature_profiles:
            self.signature_profiles[appliance_id] = {
                'name': appliance_name,
                'profiles': []
            }

        # Normaliser le profil (0-1)
        if len(power_sequence) > 0:
            profile_max = np.max(power_sequence)
            if profile_max > 0:
                normalized = power_sequence / profile_max
                self.signature_profiles[appliance_id]['profiles'].append({
                    'signature_id': signature_id,
                    'pattern': normalized,
                    'duration': duration,
                    'avg_power': float(np.mean(power_sequence)),
                    'max_power': float(profile_max)
                })

    def detect_change_points(self, aggregate_power: np.ndarray) -> List[Dict[str, Any]]:
        """
        Détecte les change points dans la consommation agrégée.

        Utilise un algorithme basé sur le gradient et la variance locale.

        Args:
            aggregate_power: Consommation agrégée

        Returns:
            Liste de change points avec indices et amplitudes
        """
        if len(aggregate_power) < 10:
            return []

        # Calculer le gradient (dérivée discrète)
        gradient = np.diff(aggregate_power)

        # Lisser pour éviter le bruit (moyenne mobile sur 5 points)
        window_size = 5
        if len(gradient) >= window_size:
            gradient_smooth = np.convolve(gradient, np.ones(window_size)/window_size, mode='valid')
        else:
            gradient_smooth = gradient

        # Détecter les sauts significatifs
        change_points = []
        threshold = self.min_power_change

        i = 0
        while i < len(gradient_smooth):
            # Chercher un saut significatif
            if abs(gradient_smooth[i]) > threshold / 10:  # Détection initiale sensible
                # Vérifier si c'est un vrai saut (somme sur fenêtre)
                window_end = min(i + 30, len(gradient_smooth))  # Fenêtre de 30s
                cumsum = np.sum(gradient_smooth[i:window_end])

                if abs(cumsum) > threshold:
                    # Change point détecté
                    change_points.append({
                        'index': i + window_size // 2,  # Ajuster pour le lissage
                        'amplitude': float(cumsum),
                        'direction': 'up' if cumsum > 0 else 'down'
                    })
                    # Sauter la fenêtre pour éviter les doublons
                    i = window_end
                    continue
            i += 1

        logger.info(f"Change points détectés: {len(change_points)}")
        return change_points

    def extract_patterns(
        self,
        aggregate_power: np.ndarray,
        change_points: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extrait les patterns entre les change points.

        Args:
            aggregate_power: Consommation agrégée
            change_points: Change points détectés

        Returns:
            Liste de patterns avec séquences et métadonnées
        """
        if len(change_points) < 2:
            return []

        patterns = []

        # Regrouper les change points en segments
        i = 0
        while i < len(change_points):
            cp = change_points[i]

            if cp['direction'] == 'up':
                # Chercher le change point DOWN correspondant
                end_idx = None
                for j in range(i + 1, len(change_points)):
                    if change_points[j]['direction'] == 'down':
                        end_idx = j
                        break

                if end_idx is not None:
                    start = cp['index']
                    end = change_points[end_idx]['index']
                    duration = end - start

                    if duration >= self.min_duration:
                        # Extraire la séquence
                        pattern = aggregate_power[start:end]

                        # Note: On ne soustrait PAS la baseline car les profils de signature
                        # sont stockés avec les valeurs originales (incluant la baseline).
                        # Le change point detection isole déjà les périodes d'activation.

                        if len(pattern) > 0 and np.max(pattern) > self.min_power_change:
                            patterns.append({
                                'start_idx': start,
                                'end_idx': end,
                                'duration': duration,
                                'pattern': pattern,
                                'avg_power': float(np.mean(pattern)),
                                'max_power': float(np.max(pattern)),
                                'energy_wh': float(np.sum(pattern) / 3600)
                            })

                    i = end_idx + 1
                else:
                    i += 1
            else:
                i += 1

        logger.info(f"Patterns extraits: {len(patterns)}")
        return patterns

    def match_pattern(
        self,
        pattern_data: Dict[str, Any]
    ) -> Optional[Tuple[int, str, Optional[int], float]]:
        """
        Compare un pattern avec les profils de signatures connus.

        Utilise DTW (Dynamic Time Warping) simplifié pour comparer les formes.

        Args:
            pattern_data: Données du pattern à matcher

        Returns:
            (appliance_id, appliance_name, signature_id, confidence) ou None
        """
        if not self.signature_profiles:
            return None

        pattern = pattern_data['pattern']
        pattern_duration = pattern_data['duration']
        pattern_power = pattern_data['avg_power']

        # Normaliser le pattern (0-1)
        pattern_max = np.max(pattern)
        if pattern_max == 0:
            return None
        pattern_normalized = pattern / pattern_max

        best_match: Optional[Tuple[int, str, Optional[int], float]] = None
        best_score: float = 0.0

        for appliance_id, data in self.signature_profiles.items():
            appliance_name = data['name']
            logger.info(f"Comparaison pattern ({pattern_duration}s, {pattern_power:.0f}W) avec {len(data['profiles'])} profils de {appliance_name}")

            for i, profile in enumerate(data['profiles']):
                # Vérifier la cohérence de durée (±50%)
                duration_ratio = pattern_duration / profile['duration']
                if duration_ratio < 0.5 or duration_ratio > 2.0:
                    logger.info(f"  Profil#{i}: ✗ durée (pattern={pattern_duration}s, prof={profile['duration']}s, ratio={duration_ratio:.2f})")
                    continue
                logger.info(f"  Profil#{i}: ✓ durée OK (ratio={duration_ratio:.2f})")

                # Vérifier la cohérence de puissance (±30%)
                power_ratio = pattern_power / profile['avg_power']
                if power_ratio < 0.7 or power_ratio > 1.3:
                    logger.info(f"  Profil#{i}: ✗ puissance (pattern={pattern_power:.0f}W, prof={profile['avg_power']:.0f}W, ratio={power_ratio:.2f})")
                    continue
                logger.info(f"  Profil#{i}: ✓ puissance OK (ratio={power_ratio:.2f})")

                # Comparer les formes avec corrélation
                # Redimensionner pour avoir même longueur
                target_len = min(len(pattern_normalized), len(profile['pattern']))

                if target_len < 10:
                    logger.info(f"  Profil#{i}: ✗ trop court (pattern_len={len(pattern_normalized)}, profile_len={len(profile['pattern'])}, target_len={target_len})")
                    continue
                logger.info(f"  Profil#{i}: ✓ longueur OK (target_len={target_len})")

                # Sous-échantillonner
                pattern_resampled = np.interp(
                    np.linspace(0, len(pattern_normalized)-1, target_len),
                    np.arange(len(pattern_normalized)),
                    pattern_normalized
                )
                profile_resampled = np.interp(
                    np.linspace(0, len(profile['pattern'])-1, target_len),
                    np.arange(len(profile['pattern'])),
                    profile['pattern']
                )

                # Calculer la corrélation (absolue pour gérer les inversions de phase)
                correlation = np.corrcoef(pattern_resampled, profile_resampled)[0, 1]
                abs_correlation = abs(correlation)

                # Score combiné : moins de poids sur corrélation, plus sur durée/puissance
                # Car durée et puissance sont très fiables pour identifier le ballon d'eau chaude
                duration_score = 1.0 - abs(1.0 - duration_ratio)
                power_score = 1.0 - abs(1.0 - power_ratio)

                combined_score = (abs_correlation * 0.2 + duration_score * 0.4 + power_score * 0.4)

                logger.info(f"  Profil#{i}: corr={correlation:.3f} (abs={abs_correlation:.3f}), dur_score={duration_score:.3f}, pow_score={power_score:.3f}, combined={combined_score:.3f}")

                if combined_score > best_score:
                    best_score = combined_score
                    best_match = (
                        appliance_id,
                        appliance_name,
                        profile.get('signature_id'),
                        combined_score,
                    )
                    logger.info(f"  Profil#{i}: ✓ nouveau meilleur score! ({combined_score:.3f})")

        # Seuil de confiance minimum (abaissé à 0.35 car durée/puissance sont très fiables)
        logger.info(f"Fin matching: best_score={best_score:.3f}, seuil=0.35")
        if best_match and best_match[3] > 0.35:
            logger.info(
                f"✓ Match trouvé: {best_match[1]} (sig_id={best_match[2]}, confiance={best_match[3]:.3f})"
            )
            return best_match
        else:
            logger.info(f"✗ Aucun match suffisant (best={best_score:.3f} < 0.35)")
            
            return None


class ApplianceStateDetector:
    """Détecteur d'états/cycles pour un appareil"""
    
    def __init__(self, n_states: int = 5):
        """
        Args:
            n_states: Nombre d'états à détecter (par défaut 5: off, low, medium, high, peak)
        """
        self.n_states = n_states
        self.kmeans = None
        self.state_thresholds = None
    
    def fit(self, power_values: np.ndarray) -> 'ApplianceStateDetector':
        """
        Entraîne le détecteur d'états sur des données de consommation
        
        Args:
            power_values: Array de valeurs de puissance
            
        Returns:
            Self pour chaînage
        """
        if len(power_values) < self.n_states:
            logger.warning(f"Pas assez de données pour {self.n_states} états, réduction automatique")
            self.n_states = max(2, len(power_values) // 10)
        
        # Reshape pour KMeans
        power_reshaped = power_values.reshape(-1, 1)
        
        # Clustering pour identifier les états
        self.kmeans = KMeans(n_clusters=self.n_states, random_state=42, n_init=10)
        self.kmeans.fit(power_reshaped)
        
        # Calculer les seuils entre états (centres triés)
        centers = sorted(self.kmeans.cluster_centers_.flatten())
        self.state_thresholds = centers
        
        logger.info(f"États détectés: {len(centers)} niveaux = {[f'{c:.1f}W' for c in centers]}")
        return self
    
    def predict_states(self, power_values: np.ndarray) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """
        Prédit les états pour une séquence de consommation
        
        Args:
            power_values: Array de valeurs de puissance
            
        Returns:
            Tuple (états prédits, cycles détectés)
        """
        if self.kmeans is None:
            raise ValueError("Le détecteur doit être entraîné avant prédiction (fit)")
        
        # Prédire les états
        power_reshaped = power_values.reshape(-1, 1)
        states = self.kmeans.predict(power_reshaped)
        
        # Détecter les cycles (transitions d'états)
        cycles = self._detect_cycles(states, power_values)
        
        return states, cycles
    
    def _detect_cycles(self, states: np.ndarray, power_values: np.ndarray) -> List[Dict[str, Any]]:
        """
        Détecte les cycles/phases dans les transitions d'états
        
        Args:
            states: Array d'états prédits
            power_values: Valeurs de puissance correspondantes
            
        Returns:
            Liste de cycles détectés avec métadonnées
        """
        cycles = []
        current_state = states[0]
        start_idx = 0
        
        for i in range(1, len(states)):
            # Transition d'état détectée
            if states[i] != current_state:
                # Enregistrer le cycle précédent
                if i - start_idx >= 10:  # Minimum 10 points (10 secondes)
                    cycle_power = power_values[start_idx:i]
                    cycles.append({
                        'state': int(current_state),
                        'start_idx': int(start_idx),
                        'end_idx': int(i),
                        'duration_seconds': int(i - start_idx),
                        'avg_power': float(np.mean(cycle_power)),
                        'max_power': float(np.max(cycle_power)),
                        'energy_wh': float(np.sum(cycle_power) / 3600)  # Wh (1Hz = 1s)
                    })
                
                # Nouveau cycle
                current_state = states[i]
                start_idx = i
        
        # Dernier cycle
        if len(states) - start_idx >= 10:
            cycle_power = power_values[start_idx:]
            cycles.append({
                'state': int(current_state),
                'start_idx': int(start_idx),
                'end_idx': int(len(states)),
                'duration_seconds': int(len(states) - start_idx),
                'avg_power': float(np.mean(cycle_power)),
                'max_power': float(np.max(cycle_power)),
                'energy_wh': float(np.sum(cycle_power) / 3600)
            })
        
        return cycles


class Seq2PointPreprocessor:
    """Preprocessing pour modèle Sequence-to-Point"""
    
    def __init__(self, sequence_length: int = 599):
        """
        Args:
            sequence_length: Longueur de la fenêtre d'entrée (impair pour point central)
        """
        # Forcer impair pour avoir un point central
        self.sequence_length = sequence_length if sequence_length % 2 == 1 else sequence_length - 1
        self.input_scaler = StandardScaler()
        self.target_scaler = MinMaxScaler(feature_range=(0, 1))
        self.fitted = False
    
    def create_sequences(
        self,
        aggregate_power: np.ndarray,
        appliance_power: np.ndarray,
        stride: int = 1
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Crée des séquences pour l'entraînement Sequence-to-Point
        
        Args:
            aggregate_power: Consommation totale (agrégée)
            appliance_power: Consommation de l'appareil cible
            stride: Pas de déplacement de la fenêtre
            
        Returns:
            Tuple (X: séquences d'entrée, y: valeurs cibles au point central)
        """
        if len(aggregate_power) != len(appliance_power):
            raise ValueError("aggregate_power et appliance_power doivent avoir la même longueur")
        
        if len(aggregate_power) < self.sequence_length:
            logger.warning(f"Séquence trop courte ({len(aggregate_power)} < {self.sequence_length})")
            return np.array([]), np.array([])
        
        X, y = [], []
        half_window = self.sequence_length // 2
        
        for i in range(half_window, len(aggregate_power) - half_window, stride):
            # Fenêtre d'entrée centrée sur i
            window = aggregate_power[i - half_window : i + half_window + 1]
            
            # Cible : consommation de l'appareil au point central
            target = appliance_power[i]
            
            X.append(window)
            y.append(target)
        
        X = np.array(X, dtype=np.float32)
        y = np.array(y, dtype=np.float32)
        
        return X, y
    
    def fit(self, aggregate_power: np.ndarray, appliance_power: np.ndarray):
        """
        Ajuste les scalers sur les données d'entraînement
        
        Args:
            aggregate_power: Consommation totale
            appliance_power: Consommation de l'appareil
        """
        # Fit scaler pour l'entrée (agrégat)
        self.input_scaler.fit(aggregate_power.reshape(-1, 1))
        
        # Fit scaler pour la cible (appareil)
        self.target_scaler.fit(appliance_power.reshape(-1, 1))
        
        self.fitted = True
        logger.info(f"Scalers ajustés: input=[{aggregate_power.min():.1f}, {aggregate_power.max():.1f}], "
                   f"target=[{appliance_power.min():.1f}, {appliance_power.max():.1f}]")
    
    def transform(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        Transforme les données avec les scalers
        
        Args:
            X: Séquences d'entrée
            y: Valeurs cibles (optionnel)
            
        Returns:
            Tuple (X transformé, y transformé ou None)
        """
        if not self.fitted:
            raise ValueError("Le preprocessor doit être ajusté avant transformation (fit)")
        
        # Normaliser X (chaque séquence indépendamment)
        X_scaled = np.zeros_like(X)
        for i in range(len(X)):
            X_scaled[i] = self.input_scaler.transform(X[i].reshape(-1, 1)).flatten()
        
        # Normaliser y si fourni
        y_scaled = None
        if y is not None:
            y_scaled = self.target_scaler.transform(y.reshape(-1, 1)).flatten()
        
        return X_scaled, y_scaled
    
    def inverse_transform_target(self, y_scaled: np.ndarray) -> np.ndarray:
        """
        Inverse la transformation pour les prédictions
        
        Args:
            y_scaled: Valeurs normalisées
            
        Returns:
            Valeurs originales
        """
        return self.target_scaler.inverse_transform(y_scaled.reshape(-1, 1)).flatten()


class Seq2PointModel:
    """Modèle Sequence-to-Point pour un appareil"""
    
    def __init__(
        self,
        appliance_id: int,
        appliance_name: str,
        sequence_length: int = 599,
        model_type: str = "lstm"  # "lstm", "gru", "attention"
    ):
        """
        Args:
            appliance_id: ID de l'appareil dans la base
            appliance_name: Nom de l'appareil
            sequence_length: Longueur de la fenêtre d'entrée
            model_type: Type de modèle ("lstm", "gru", "attention")
        """
        self.appliance_id = appliance_id
        self.appliance_name = appliance_name
        self.sequence_length = sequence_length if sequence_length % 2 == 1 else sequence_length - 1
        self.model_type = model_type
        
        # Normaliser le nom pour TensorFlow
        self.normalized_name = normalize_name_for_tensorflow(appliance_name)
        
        self.model: Optional[keras.Model] = None
        self.preprocessor = Seq2PointPreprocessor(self.sequence_length)
        self.state_detector: Optional[ApplianceStateDetector] = None
        self.history = None
        
        # Déterminer le device (CPU/GPU)
        self.use_gpu = self._configure_device()
    
    def _configure_device(self) -> bool:
        """
        Configure le device (CPU/GPU) selon la variable d'environnement
        
        Returns:
            True si GPU est utilisé, False sinon
        """
        use_gpu_env = os.getenv('USE_GPU', 'auto').lower()
        
        if use_gpu_env == 'false':
            # Forcer CPU
            tf.config.set_visible_devices([], 'GPU')
            logger.info("Device forcé: CPU")
            return False
        
        # Vérifier disponibilité GPU
        gpus = tf.config.list_physical_devices('GPU')
        
        if use_gpu_env == 'true' and not gpus:
            logger.warning("GPU demandé mais non disponible, utilisation du CPU")
            return False
        
        if gpus:
            try:
                # Configuration GPU
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
                logger.info(f"Device: GPU ({len(gpus)} disponible(s))")
                return True
            except RuntimeError as e:
                logger.warning(f"Erreur config GPU: {e}, utilisation du CPU")
                return False
        
        logger.info("Device: CPU")
        return False
    
    def build_model(self) -> keras.Model:
        """
        Construit l'architecture Sequence-to-Point
        
        Returns:
            Modèle Keras compilé
        """
        inputs = layers.Input(shape=(self.sequence_length, 1), name='aggregate_input')
        
        if self.model_type == "lstm":
            # Architecture LSTM
            x = layers.LSTM(128, return_sequences=True, name='lstm_1')(inputs)
            x = layers.Dropout(0.2)(x)
            x = layers.LSTM(64, return_sequences=False, name='lstm_2')(x)
            x = layers.Dropout(0.2)(x)
            
        elif self.model_type == "gru":
            # Architecture GRU (plus rapide que LSTM)
            x = layers.GRU(128, return_sequences=True, name='gru_1')(inputs)
            x = layers.Dropout(0.2)(x)
            x = layers.GRU(64, return_sequences=False, name='gru_2')(x)
            x = layers.Dropout(0.2)(x)
            
        elif self.model_type == "attention":
            # Architecture avec attention
            x = layers.LSTM(128, return_sequences=True, name='lstm_encoder')(inputs)
            x = layers.Dropout(0.2)(x)
            
            # Mécanisme d'attention simple
            attention = layers.Dense(1, activation='tanh')(x)
            attention = layers.Flatten()(attention)
            attention = layers.Activation('softmax')(attention)
            attention = layers.RepeatVector(128)(attention)
            attention = layers.Permute([2, 1])(attention)
            
            x = layers.Multiply()([x, attention])
            x = layers.Lambda(lambda xin: tf.reduce_sum(xin, axis=1))(x)
            
        else:
            raise ValueError(f"Type de modèle inconnu: {self.model_type}")
        
        # Couches denses finales
        x = layers.Dense(64, activation='relu', name='dense_1')(x)
        x = layers.Dropout(0.1)(x)
        x = layers.Dense(32, activation='relu', name='dense_2')(x)
        
        # Sortie : prédiction de la consommation au point central
        outputs = layers.Dense(1, activation='linear', name='power_output')(x)
        
        model = models.Model(
            inputs=inputs,
            outputs=outputs,
            name=f's2p_{self.normalized_name}'
        )
        
        # Compiler avec MAE (Mean Absolute Error) adapté à la régression
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='mae',
            metrics=['mae', 'mse']
        )
        
        logger.info(f"Modèle {self.model_type.upper()} construit pour '{self.appliance_name}' "
                   f"(séquence={self.sequence_length}, params={model.count_params():,})")
        return model
    
    def train(
        self,
        signatures: List[Dict[str, Any]],
        version: str,
        epochs: int = 30,
        batch_size: int = 32,
        validation_split: float = 0.15
    ) -> Dict[str, Any]:
        """
        Entraîne le modèle Sequence-to-Point
        
        Args:
            signatures: Signatures d'entraînement pour cet appareil
            version: Version du modèle
            epochs: Nombre d'époques max
            batch_size: Taille des batchs
            validation_split: Proportion de validation
            
        Returns:
            Dictionnaire de métriques
        """
        if len(signatures) < 2:
            logger.error(f"Pas assez de signatures pour '{self.appliance_name}' (minimum 2)")
            return {}
        
        logger.info(f"Entraînement de '{self.appliance_name}' avec {len(signatures)} signatures")
        
        # Préparer les données d'entraînement
        all_X, all_y = [], []
        all_appliance_power = []  # Pour fit state detector
        
        # Durée minimale requise (en minutes)
        min_duration_minutes = self.sequence_length / 60
        logger.info(f"⏱️  Durée minimale requise par signature: {min_duration_minutes:.1f} min ({self.sequence_length} points à 1Hz)")
        
        # Compteurs pour diagnostics
        valid_signatures = 0
        ignored_signatures = 0
        
        for sig in signatures:
            # Récupérer les données depuis linky_realtime
            aggregate_power, appliance_power = self._load_signature_data(sig)
            
            if aggregate_power is None:
                logger.warning(f"⚠️  Signature {sig['id']} : aucune donnée disponible")
                ignored_signatures += 1
                continue
            
            actual_duration_minutes = len(aggregate_power) / 60
            
            if len(aggregate_power) < self.sequence_length:
                logger.warning(
                    f"⚠️  Signature {sig['id']} ignorée : "
                    f"durée {actual_duration_minutes:.1f} min < {min_duration_minutes:.1f} min requises "
                    f"({len(aggregate_power)} points < {self.sequence_length} points)"
                )
                ignored_signatures += 1
                continue
            
            # Créer les séquences S2P
            X, y = self.preprocessor.create_sequences(
                aggregate_power,
                appliance_power,
                stride=30  # Stride de 30s pour réduire la redondance
            )
            
            if len(X) > 0:
                all_X.append(X)
                all_y.append(y)
                all_appliance_power.append(appliance_power)
                valid_signatures += 1
                logger.info(f"✅ Signature {sig['id']} : {actual_duration_minutes:.1f} min, {len(X)} séquences créées")
        
        # Vérifier qu'on a au moins une signature valide
        if len(all_X) == 0:
            error_msg = (
                f"❌ Aucune séquence valide pour '{self.appliance_name}' : "
                f"{ignored_signatures} signature(s) ignorée(s), 0 valide(s). "
                f"Créez des signatures d'au moins {min_duration_minutes:.1f} minutes "
                f"(actuellement configuré: CNN_WINDOW_SIZE_MINUTES={settings.cnn_window_size_minutes})."
            )
            logger.error(error_msg)
            return {}
        
        logger.info(f"📊 Bilan : {valid_signatures} signature(s) valide(s), {ignored_signatures} ignorée(s)")
        
        # Concaténer toutes les séquences
        X = np.concatenate(all_X, axis=0)
        y = np.concatenate(all_y, axis=0)
        
        logger.info(f"Séquences créées: {len(X)} échantillons")
        
        # Ajuster les scalers
        all_aggregate = np.concatenate([self._load_signature_data(sig)[0] for sig in signatures 
                                       if self._load_signature_data(sig)[0] is not None])
        all_appliance = np.concatenate(all_appliance_power)
        self.preprocessor.fit(all_aggregate, all_appliance)
        
        # Entraîner le détecteur d'états avec 2 états (ON/OFF)
        self.state_detector = ApplianceStateDetector(n_states=2)
        self.state_detector.fit(all_appliance)
        
        # Normaliser les données
        X_scaled, y_scaled = self.preprocessor.transform(X, y)
        
        # Reshape X pour le modèle (ajouter dimension features)
        X_scaled = X_scaled.reshape(X_scaled.shape[0], X_scaled.shape[1], 1)
        
        # Split train/validation
        X_train, X_val, y_train, y_val = train_test_split(
            X_scaled, y_scaled,
            test_size=validation_split,
            random_state=42
        )
        
        logger.info(f"Split: {len(X_train)} train, {len(X_val)} validation")
        
        # Construire le modèle
        self.model = self.build_model()
        
        # Callbacks (utiliser le nom normalisé pour le fichier)
        model_path = Path(settings.cnn_model_path) / f's2p_{self.normalized_name}_{version}.keras'
        model_path.parent.mkdir(parents=True, exist_ok=True)
        
        callbacks_list = [
            callbacks.EarlyStopping(
                monitor='val_loss',
                patience=10,
                restore_best_weights=True,
                verbose=1
            ),
            callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=5,
                min_lr=1e-6,
                verbose=1
            ),
            callbacks.ModelCheckpoint(
                filepath=str(model_path),
                monitor='val_loss',
                save_best_only=True,
                verbose=1
            )
        ]
        tensorboard_root = Path(settings.cnn_model_path) / "tensorboard"
        run_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        log_dir = tensorboard_root / self.normalized_name / version / run_id
        log_dir.mkdir(parents=True, exist_ok=True)
        callbacks_list.append(
            callbacks.TensorBoard(
                log_dir=str(log_dir),
                histogram_freq=0,
                write_graph=False,
                profile_batch=0
            )
        )
        logger.info(f"TensorBoard ({self.appliance_name}) → {log_dir}")
        
        # Entraînement
        start_time = datetime.now()
        
        with tf.device('/GPU:0' if self.use_gpu else '/CPU:0'):
            self.history = self.model.fit(
                X_train, y_train,
                validation_data=(X_val, y_val),
                epochs=epochs,
                batch_size=batch_size,
                callbacks=callbacks_list,
                verbose=1
            )
        
        training_duration = (datetime.now() - start_time).total_seconds()
        
        # Métriques finales
        final_metrics = {
            'train_mae': float(self.history.history['mae'][-1]),
            'train_mse': float(self.history.history['mse'][-1]),
            'val_mae': float(self.history.history['val_mae'][-1]),
            'val_mse': float(self.history.history['val_mse'][-1]),
            'epochs_trained': len(self.history.history['loss']),
            'training_duration_seconds': int(training_duration),
            'num_sequences': int(len(X)),
            'model_type': self.model_type,
            'device': 'GPU' if self.use_gpu else 'CPU'
        }
        
        logger.info(f"Entraînement terminé en {training_duration:.1f}s - "
                   f"Val MAE: {final_metrics['val_mae']:.2f}W")
        
        return final_metrics
    
    def _load_signature_data(self, signature: Dict[str, Any]) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Charge les données d'une signature depuis linky_realtime
        
        Args:
            signature: Dictionnaire de signature
            
        Returns:
            Tuple (aggregate_power, appliance_power) ou (None, None) si erreur
        """
        try:
            with db_manager.get_session() as session:
                query = """
                    SELECT time, papp
                    FROM linky_realtime
                    WHERE time >= :start_time AND time <= :end_time
                    ORDER BY time
                """
                
                result = session.execute(
                    text(query),
                    {
                        'start_time': signature['start_time'],
                        'end_time': signature['end_time']
                    }
                )
                
                data = result.fetchall()
                
                if not data:
                    return None, None
                
                # Consommation totale (agrégat)
                aggregate_power = np.array([row[1] for row in data], dtype=np.float32)
                
                # Consommation de l'appareil (pour l'entraînement, on l'isole)
                # Ici on suppose que pendant la signature, seul cet appareil consomme
                # ou on a une baseline pour soustraire
                # Pour simplifier : appliance_power = aggregate_power pendant la signature
                # (à affiner selon le contexte)
                appliance_power = aggregate_power.copy()
                
                return aggregate_power, appliance_power
                
        except Exception as e:
            logger.error(f"Erreur chargement signature {signature['id']}: {e}")
            return None, None
    
    def predict(self, aggregate_power: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Prédit la consommation de l'appareil sur une période
        
        Args:
            aggregate_power: Consommation totale
            
        Returns:
            Tuple (prédictions de puissance, métadonnées incluant les états)
        """
        if self.model is None:
            raise ValueError("Le modèle doit être entraîné avant prédiction")
        
        # Créer les séquences
        X, _ = self.preprocessor.create_sequences(
            aggregate_power,
            np.zeros_like(aggregate_power),  # Dummy target
            stride=1  # Stride de 1 pour prédiction complète
        )
        
        if len(X) == 0:
            return np.array([]), {}
        
        # Normaliser
        X_scaled, _ = self.preprocessor.transform(X)
        X_scaled = X_scaled.reshape(X_scaled.shape[0], X_scaled.shape[1], 1)
        
        # Prédire
        with tf.device('/GPU:0' if self.use_gpu else '/CPU:0'):
            y_pred_scaled = self.model.predict(X_scaled, batch_size=64, verbose=0)
        
        # Dénormaliser
        y_pred = self.preprocessor.inverse_transform_target(y_pred_scaled.flatten())
        
        # Assurer que les prédictions sont positives
        y_pred = np.maximum(y_pred, 0)
        
        # Détecter les états si state_detector disponible
        metadata = {
            'appliance_id': self.appliance_id,
            'appliance_name': self.appliance_name,
            'num_predictions': int(len(y_pred)),
            'avg_power': float(np.mean(y_pred)),
            'max_power': float(np.max(y_pred)),
            'energy_wh': float(np.sum(y_pred) / 3600),  # Wh (1Hz)
        }
        
        if self.state_detector is not None and len(y_pred) > 0:
            try:
                states, cycles = self.state_detector.predict_states(y_pred)
                metadata['states'] = states.tolist()
                metadata['cycles'] = cycles
                metadata['num_cycles'] = len(cycles)
            except Exception as e:
                logger.warning(f"Erreur détection d'états: {e}")
        
        return y_pred, metadata
    
    def save(self, filepath: str):
        """Sauvegarde le modèle et ses métadonnées"""
        if self.model is None:
            raise ValueError("Aucun modèle à sauvegarder")
        
        # Sauvegarder le modèle Keras
        self.model.save(filepath)
        
        # Sauvegarder les métadonnées (preprocessor, state_detector)
        metadata_path = Path(filepath).with_suffix('.metadata.json')
        
        # Convertir state_thresholds en liste Python si présent
        state_thresholds = None
        if self.state_detector and self.state_detector.state_thresholds is not None:
            state_thresholds = [float(x) for x in self.state_detector.state_thresholds]
        
        metadata = {
            'appliance_id': self.appliance_id,
            'appliance_name': self.appliance_name,
            'sequence_length': self.sequence_length,
            'model_type': self.model_type,
            'use_gpu': self.use_gpu,
            'input_scaler_mean': self.preprocessor.input_scaler.mean_.tolist() if self.preprocessor.fitted else None,
            'input_scaler_scale': self.preprocessor.input_scaler.scale_.tolist() if self.preprocessor.fitted else None,
            'target_scaler_min': self.preprocessor.target_scaler.data_min_.tolist() if self.preprocessor.fitted else None,
            'target_scaler_scale': self.preprocessor.target_scaler.scale_.tolist() if self.preprocessor.fitted else None,
            'state_thresholds': state_thresholds
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Modèle sauvegardé: {filepath}")
    
    def load(self, filepath: str):
        """Charge le modèle et ses métadonnées"""
        # Charger le modèle Keras
        self.model = keras.models.load_model(filepath)
        
        # Charger les métadonnées
        metadata_path = Path(filepath).with_suffix('.metadata.json')
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            self.appliance_id = metadata['appliance_id']
            self.appliance_name = metadata['appliance_name']
            self.sequence_length = metadata['sequence_length']
            self.model_type = metadata['model_type']
            
            # Normaliser le nom pour TensorFlow
            self.normalized_name = normalize_name_for_tensorflow(self.appliance_name)
            
            # Restaurer les scalers
            if metadata.get('input_scaler_mean'):
                self.preprocessor.input_scaler.mean_ = np.array(metadata['input_scaler_mean'])
                self.preprocessor.input_scaler.scale_ = np.array(metadata['input_scaler_scale'])
                self.preprocessor.target_scaler.data_min_ = np.array(metadata['target_scaler_min'])
                self.preprocessor.target_scaler.scale_ = np.array(metadata['target_scaler_scale'])
                self.preprocessor.fitted = True
            
            # Restaurer state detector
            if metadata.get('state_thresholds'):
                self.state_detector = ApplianceStateDetector()
                self.state_detector.state_thresholds = metadata['state_thresholds']
        
        logger.info(f"Modèle chargé: {filepath}")
    
    def enrich_signature_with_cycles(self, signature_id: int) -> Optional[Dict[str, Any]]:
        """
        Enrichit une signature avec les cycles détectés
        
        Args:
            signature_id: ID de la signature à enrichir
            
        Returns:
            Dictionnaire des cycles détectés ou None si erreur
        """
        if self.state_detector is None:
            logger.warning("Aucun state detector disponible pour enrichissement")
            return None
        
        try:
            # Charger la signature depuis la base
            with db_manager.get_session() as session:
                query = """
                    SELECT id, appliance_id, start_time, end_time
                    FROM cnn_signatures
                    WHERE id = :signature_id AND appliance_id = :appliance_id
                """
                
                result = session.execute(
                    text(query),
                    {
                        'signature_id': signature_id,
                        'appliance_id': self.appliance_id
                    }
                )
                
                sig_data = result.fetchone()
                
                if not sig_data:
                    logger.warning(f"Signature {signature_id} non trouvée pour appareil {self.appliance_id}")
                    return None
                
                # Charger les données de consommation
                signature = {
                    'id': sig_data[0],
                    'appliance_id': sig_data[1],
                    'start_time': sig_data[2],
                    'end_time': sig_data[3]
                }
                
                aggregate_power, appliance_power = self._load_signature_data(signature)
                
                if appliance_power is None or len(appliance_power) < 10:
                    logger.warning(f"Données insuffisantes pour signature {signature_id}")
                    return None
                
                # Détecter les cycles
                states, cycles = self.state_detector.predict_states(appliance_power)
                
                # Préparer les données de cycles (non persistées : colonne supprimée)
                enriched_features = {
                    'model_type': self.model_type,
                    'model_version': 's2p',
                    'num_cycles': len(cycles),
                    'cycles': cycles,
                    'num_states': len(np.unique(states)),
                    'enriched_at': datetime.utcnow().isoformat()
                }
                
                logger.info(
                    f"✅ Cycles analysés pour signature {signature_id} "
                    f"({len(cycles)} cycles détectés)"
                )
                return enriched_features
                
        except Exception as e:
            logger.error(f"Erreur enrichissement signature {signature_id}: {e}")
            return None


class Seq2PointNILMManager:
    """Gestionnaire de modèles S2P pour tous les appareils"""
    
    def __init__(self):
        self.models: Dict[int, Seq2PointModel] = {}  # appliance_id -> model
        self.model_type = os.getenv('NILM_MODEL_TYPE', 'gru').lower()
        
        # Choix architecture: 'film' (défaut) ou 'multi' ou 'single'
        self.architecture = os.getenv('NILM_ARCHITECTURE', 'film').lower()

        # Créer le répertoire des modèles
        Path(settings.cnn_model_path).mkdir(parents=True, exist_ok=True)

        # Détecteur hybride change point + pattern matching
        self.change_point_detector = ChangePointPatternDetector(
            min_power_change=settings.cnn_min_power_threshold,
            min_duration=settings.cnn_min_duration_seconds
        )
        logger.info("Change Point Pattern Detector initialisé")

        # Attribut pour le modèle (FiLM ou Multi-Output)
        self.multi_model: Optional[Seq2PointMultiModel] = None
        self.film_model: Optional[Seq2PointFiLMModel] = None
        
        logger.info(
            f"🎯 Architecture: {self.architecture.upper()}, "
            f"Type: {self.model_type.upper()}"
        )

    def load_model(self, model_path: str):
        """
        Charge un modèle S2P existant pour fine-tuning
        Détecte automatiquement si c'est FiLM ou Multi-Output

        Args:
            model_path: Chemin vers le modèle .keras à charger
        """
        try:
            # Charger les métadonnées
            metadata_path = Path(model_path).with_suffix('.metadata.json')
            if not metadata_path.exists():
                raise ValueError(f"Métadonnées introuvables: {metadata_path}")

            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            appliance_ids = metadata.get('appliance_ids', [])
            appliance_names = metadata.get('appliance_names', [])
            sequence_length = metadata.get(
                'sequence_length',
                settings.effective_sequence_length
            )
            architecture = metadata.get('architecture', 'multi')

            # Charger selon l'architecture
            if architecture.lower() == 'film':
                logger.info("📂 Chargement modèle FiLM...")
                self.film_model = Seq2PointFiLMModel(
                    appliance_ids=appliance_ids,
                    appliance_names=appliance_names,
                    sequence_length=sequence_length,
                    model_type=self.model_type
                )
                self.film_model.load(model_path)
                self.architecture = 'film'
                logger.info(f"✅ Modèle FiLM chargé: {model_path}")
            else:
                logger.info("📂 Chargement modèle Multi-Output...")
                self.multi_model = Seq2PointMultiModel(
                    appliance_ids=appliance_ids,
                    appliance_names=appliance_names,
                    sequence_length=sequence_length,
                    model_type=self.model_type
                )
                self.multi_model.load(model_path)
                self.architecture = 'multi'
                logger.info(f"✅ Modèle Multi-Output chargé: {model_path}")

        except Exception as e:
            logger.error(f"❌ Erreur chargement modèle: {e}")
            raise

    def train_all_appliances(self, version: str, fine_tune: bool = False) -> Dict[str, Any]:
        """
        Entraîne les modèles S2P (multi-sorties ou unitaire selon configuration)

        Args:
            version: Version du modèle
            fine_tune: Si True, continue l'entraînement du modèle existant

        Returns:
            Dictionnaire global de métriques
        """
        try:
            with db_manager.get_session() as session:
                query = """
                    SELECT DISTINCT a.id, a.name, COUNT(s.id) as num_signatures
                    FROM cnn_appliances a
                    JOIN cnn_signatures s ON s.appliance_id = a.id
                    GROUP BY a.id, a.name
                    HAVING COUNT(s.id) >= 2
                    ORDER BY a.name
                """
                appliances = session.execute(text(query)).fetchall()
            
            if len(appliances) < 1:
                logger.error(
                    "Aucun appareil avec assez de signatures (minimum 2)"
                )
                return {'error': 'insufficient_data', 'min_appliances': 1}
            
            appliance_ids = [row[0] for row in appliances]
            appliance_names = [row[1] for row in appliances]
            
            # Charger les signatures
            all_signatures: Dict[int, List[Dict[str, Any]]] = {}
            with db_manager.get_session() as session:
                for appliance_id in appliance_ids:
                    query = """
                        SELECT id, appliance_id, start_time, end_time
                        FROM cnn_signatures
                        WHERE appliance_id = :appliance_id
                        ORDER BY created_at
                    """
                    result = session.execute(
                        text(query),
                        {'appliance_id': appliance_id}
                    )
                    all_signatures[appliance_id] = [
                        dict(row._mapping) for row in result
                    ]

            # Charger les profils pour change point detector
            logger.info("📊 Chargement profils signatures...")
            for appliance_id, signatures in all_signatures.items():
                app_idx = appliance_ids.index(appliance_id)
                appliance_name = appliance_names[app_idx]
                for sig in signatures:
                    agg, app_pwr = Seq2PointFiLMModel._load_signature_data_static(sig)
                    if app_pwr is None or len(app_pwr) == 0:
                        continue

                    duration = int(
                        (sig['end_time'] - sig['start_time']).total_seconds()
                    )

                    self.change_point_detector.add_signature_profile(
                        appliance_id=appliance_id,
                        appliance_name=appliance_name,
                        power_sequence=app_pwr,
                        duration=duration,
                        signature_id=sig['id']
                    )

            total_profiles = sum(
                len(data['profiles'])
                for data in self.change_point_detector.signature_profiles.values()
            )
            logger.info(
                f"✅ {len(self.change_point_detector.signature_profiles)} "
                f"appareils, {total_profiles} profils"
            )

            # Entraîner selon l'architecture choisie
            if self.architecture == 'film':
                logger.info("🎬 Architecture FiLM (multi-target conditioning)")
                
                # Créer ou réutiliser modèle FiLM
                if fine_tune and self.film_model is not None:
                    logger.info("♻️ Réutilisation modèle FiLM pour fine-tuning")
                else:
                    self.film_model = Seq2PointFiLMModel(
                        appliance_ids,
                        appliance_names,
                        sequence_length=settings.effective_sequence_length,
                        model_type=self.model_type
                    )

                metrics = self.film_model.train(
                    all_signatures,
                    version,
                    epochs=30,
                    batch_size=32,
                    use_feedback=True,
                    fine_tune=fine_tune
                )
                
                if not metrics:
                    logger.error("Entraînement FiLM impossible (données insuffisantes)")
                    return {'error': 'insufficient_training_data'}
                
                model_path = Path(settings.cnn_model_path) / \
                    f's2p_film_{self.model_type}_{version}.keras'
                self.film_model.save(str(model_path), metadata=metrics)
                
                # Formater la réponse pour compatibilité frontend
                # Le frontend attend: model.metrics.appliances[0].metrics
                return {
                    'version': version,
                    'model_type': f'FiLM-{self.model_type}',
                    'architecture': 'FiLM',
                    'num_appliances': len(appliance_ids),
                    'model_path': str(model_path),
                    'appliances': [
                        {
                            'id': appliance_ids[i],
                            'name': appliance_names[i],
                            'num_signatures': len(all_signatures[appliance_ids[i]]),
                            # Les métriques globales pour cet appareil
                            'metrics': {
                                'train_mae': metrics.get('train_mae'),
                                'val_mae': metrics.get('val_mae'),
                                'train_mse': metrics.get('train_mae', 0) ** 2,  # Approximation
                                'val_mse': metrics.get('val_mae', 0) ** 2,
                                'train_loss': metrics.get('train_loss'),
                                'val_loss': metrics.get('val_loss'),
                                'epochs_trained': metrics.get('epochs_trained'),
                            }
                        }
                        for i in range(len(appliance_ids))
                    ]
                }
            
            elif self.architecture == 'multi':
                logger.info("🔀 Architecture Multi-Output (legacy)")
                
                # Si fine-tuning et multi_model déjà chargé
                if fine_tune and self.multi_model is not None:
                    logger.info("♻️ Réutilisation modèle multi pour fine-tuning")
                else:
                    self.multi_model = Seq2PointMultiModel(
                        appliance_ids,
                        appliance_names,
                        sequence_length=settings.effective_sequence_length,
                        model_type=self.model_type
                    )

                metrics = self.multi_model.train(
                    all_signatures,
                    version,
                    epochs=30,
                    batch_size=32,
                    use_feedback=True,
                    fine_tune=fine_tune
                )
                
                if not metrics:
                    logger.error("Entraînement multi impossible")
                    return {'error': 'insufficient_training_data'}
                
                model_path = Path(settings.cnn_model_path) / \
                    f's2p_multi_{self.model_type}_{version}.keras'
                self.multi_model.save(str(model_path))
                
                return {
                    'version': version,
                    'model_type': f'multi-{self.model_type}',
                    'architecture': 'multi',
                    'num_appliances': len(appliance_ids),
                    'model_path': str(model_path),
                    'appliances': [
                        {
                            'id': appliance_ids[i],
                            'name': appliance_names[i],
                            'num_signatures': len(all_signatures[appliance_ids[i]]),
                            'metrics': metrics.get(appliance_names[i], {})
                        }
                        for i in range(len(appliance_ids))
                    ]
                }
            
            # Fallback: un modèle par appareil
            min_duration_minutes = settings.effective_sequence_length / 60
            logger.info("=" * 60)
            logger.info("🚀 Entraînement NILM Sequence-to-Point (S2P) par appareil")
            logger.info("=" * 60)
            logger.info("📊 Configuration:")
            logger.info(f"   - Modèle: {self.model_type.upper()}")
            logger.info(f"   - Fenêtre: {settings.cnn_window_size_minutes} min = {settings.effective_sequence_length} points")
            logger.info(f"   - Durée minimale requise par signature: {min_duration_minutes:.1f} min")
            logger.info(f"   - Appareils à entraîner: {len(appliances)}")
            logger.info("=" * 60)
            
            global_metrics = {
                'version': version,
                'model_type': self.model_type,
                'num_appliances': len(appliances),
                'appliances': []
            }
            
            for appliance_id, appliance_name, num_sigs in appliances:
                logger.info(f"Entraînement de '{appliance_name}' ({num_sigs} signatures)")
                
                with db_manager.get_session() as session:
                    query = """
                        SELECT id, appliance_id, start_time, end_time
                        FROM cnn_signatures
                        WHERE appliance_id = :appliance_id
                        ORDER BY created_at
                    """
                    result = session.execute(text(query), {'appliance_id': appliance_id})
                    signatures = [dict(row._mapping) for row in result]
                
                model = Seq2PointModel(
                    appliance_id=appliance_id,
                    appliance_name=appliance_name,
                    sequence_length=settings.effective_sequence_length,
                    model_type=self.model_type
                )
                metrics = model.train(
                    signatures=signatures,
                    version=version,
                    epochs=30,
                    batch_size=32
                )
                
                if not metrics:
                    logger.warning(f"⚠️  Entraînement ignoré pour '{appliance_name}' (données insuffisantes)")
                    continue
                
                normalized_name = model.normalized_name
                filename = f's2p_{normalized_name}_{version}.keras'
                model_path = Path(settings.cnn_model_path) / filename
                model.save(str(model_path))
                
                self.models[appliance_id] = model
                global_metrics['appliances'].append({
                    'id': appliance_id,
                    'name': appliance_name,
                    'num_signatures': num_sigs,
                    'metrics': metrics,
                    'model_path': str(model_path)
                })
            
            if os.getenv('NILM_DETECT_STATES', 'true').lower() == 'true':
                logger.info("🔍 Enrichissement des signatures avec cycles...")
                enriched_count = self.enrich_all_signatures()
                global_metrics['enriched_signatures'] = enriched_count
            
            return global_metrics
        
        except Exception as e:
            logger.error(f"Erreur entraînement global: {e}", exc_info=True)
            return {'error': str(e)}
    
    def enrich_all_signatures(self) -> int:
        """
        Enrichit toutes les signatures avec les cycles détectés
        
        Returns:
            Nombre de signatures enrichies
        """
        enriched_count = 0
        
        try:
            for appliance_id, model in self.models.items():
                if model.state_detector is None:
                    logger.warning(
                        f"Pas de state detector pour '{model.appliance_name}'"
                    )
                    continue
                
                # Récupérer toutes les signatures de cet appareil
                with db_manager.get_session() as session:
                    query = """
                        SELECT id
                        FROM cnn_signatures
                        WHERE appliance_id = :appliance_id
                        ORDER BY created_at
                    """
                    
                    result = session.execute(
                        text(query),
                        {'appliance_id': appliance_id}
                    )
                    
                    signature_ids = [row[0] for row in result.fetchall()]
                
                # Enrichir chaque signature
                for sig_id in signature_ids:
                    enriched = model.enrich_signature_with_cycles(sig_id)
                    if enriched:
                        enriched_count += 1
                
                logger.info(
                    f"✅ {len(signature_ids)} signatures enrichies "
                    f"pour '{model.appliance_name}'"
                )
        
        except Exception as e:
            logger.error(f"Erreur enrichissement signatures: {e}")
        
        return enriched_count
    
    def load_active_models(self) -> bool:
        """
        Charge les modèles actifs depuis la base
        
        Returns:
            True si succès
        """
        try:
            with db_manager.get_session() as session:
                query = (
                    "SELECT version, model_path, architecture "
                    "FROM cnn_models "
                    "WHERE model_status = 'current' AND model_type LIKE 'S2P%' "
                    "ORDER BY training_date DESC "
                    "LIMIT 1"
                )
                result = session.execute(text(query))
                active_model = result.fetchone()
                if not active_model:
                    logger.warning("Aucun modèle S2P multi-sorties actif trouvé")
                    return False
                version, model_path, architecture_json = active_model
                # architecture_json est déjà un dict Python (PostgreSQL jsonb)
                architecture = architecture_json if architecture_json else {}
                if not Path(model_path).exists():
                    logger.error(f"Modèle multi-sorties introuvable: {model_path}")
                    return False
                # Charger le modèle multi-sorties
                self.multi_model = Seq2PointMultiModel(
                    appliance_ids=[app['id'] for app in architecture.get('appliances', [])],
                    appliance_names=[app['name'] for app in architecture.get('appliances', [])],
                    sequence_length=settings.effective_sequence_length,
                    model_type=self.model_type
                )
                self.multi_model.load(model_path)
                logger.info(f"Modèle multi-sorties '{version}' chargé depuis {model_path}")
                return True
        except Exception as e:
            logger.error(f"Erreur chargement modèle multi-sorties: {e}")
            return False

    def _load_signature_profiles(self):
        """Charge les profils de signatures depuis la base de données."""
        from sqlalchemy import text

        with db_manager.get_session() as session:
            # Récupérer les appareils actifs
            appliances_query = """
                SELECT DISTINCT appliance_id, ca.name
                FROM cnn_signatures cs
                JOIN cnn_appliances ca ON cs.appliance_id = ca.id
            """
            appliances = session.execute(text(appliances_query)).fetchall()

            for appliance_id, appliance_name in appliances:
                sig_query = """
                    SELECT id, start_time, end_time
                    FROM cnn_signatures
                    WHERE appliance_id = :appliance_id
                    ORDER BY created_at
                """
                signatures = session.execute(text(sig_query), {'appliance_id': appliance_id}).fetchall()

                for sig_id, start_time, end_time in signatures:
                    signature = {
                        'id': sig_id,
                        'appliance_id': appliance_id,
                        'start_time': start_time,
                        'end_time': end_time
                    }
                    aggregate_power, appliance_power = Seq2PointMultiModel._load_signature_data_static(signature)
                    if appliance_power is None or len(appliance_power) == 0:
                        continue

                    duration = int((end_time - start_time).total_seconds())

                    self.change_point_detector.add_signature_profile(
                        appliance_id=appliance_id,
                        appliance_name=appliance_name,
                        power_sequence=appliance_power,
                        duration=duration,
                        signature_id=sig_id
                    )

        total_profiles = sum(len(data['profiles']) for data in self.change_point_detector.signature_profiles.values())
        logger.info(f"Profils chargés: {len(self.change_point_detector.signature_profiles)} appareils, {total_profiles} profils")

    def _filter_against_negative_signatures(
        self,
        detections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filtre les détections qui ressemblent aux signatures négatives.
        
        Une signature négative est créée quand l'utilisateur invalide
        une détection. On compare durée, puissance moyenne et énergie
        pour rejeter les faux positifs similaires.
        
        Args:
            detections: Liste de détections à filtrer
            
        Returns:
            Liste de détections filtrées (sans les faux positifs)
        """
        if not detections:
            return []
        
        # Charger les signatures négatives depuis la base
        negative_sigs = {}
        try:
            with db_manager.engine.connect() as conn:
                query = text("""
                    SELECT
                        id,
                        appliance_id,
                        start_time,
                        end_time,
                        avg_power,
                        energy_consumed
                    FROM cnn_signatures
                    WHERE is_negative = TRUE
                    ORDER BY created_at DESC
                """)
                
                result = conn.execute(query)
                
                for row in result:
                    sig_id, app_id, start_t, end_t, avg_pwr, energy = row
                    duration = int((end_t - start_t).total_seconds())
                    
                    if app_id not in negative_sigs:
                        negative_sigs[app_id] = []
                    
                    negative_sigs[app_id].append({
                        'id': sig_id,
                        'duration_seconds': duration,
                        'avg_power': float(avg_pwr) if avg_pwr else 0.0,
                        'energy_wh': float(energy) if energy else 0.0
                    })
                
                total_negs = sum(len(s) for s in negative_sigs.values())
                if total_negs > 0:
                    logger.info(
                        f"Filtrage contre {total_negs} signatures négatives"
                    )
        except Exception as e:
            logger.error(f"Erreur chargement signatures négatives: {e}")
            return detections  # Retourner sans filtrer si erreur
        
        # Filtrer les détections
        filtered = []
        rejected_count = 0
        
        for det in detections:
            app_id = det['appliance_id']
            negs = negative_sigs.get(app_id, [])
            
            if not negs:
                # Pas de signatures négatives pour cet appareil
                filtered.append(det)
                continue
            
            is_false_positive = False
            
            # DEBUG: Log de la détection à analyser
            logger.info(
                f"🔍 Analyse détection: {det['duration_seconds']}s, "
                f"{det['avg_power']:.1f}W, {det.get('energy_wh', 0):.1f}Wh"
            )
            
            for neg in negs:
                # Critère 1: Durée similaire (±50% car change points)
                duration_ratio = (
                    det['duration_seconds'] / neg['duration_seconds']
                    if neg['duration_seconds'] > 0 else 0
                )
                
                # DEBUG: Log détaillé de la comparaison
                logger.info(
                    f"  vs signature négative #{neg['id']}: "
                    f"{neg['duration_seconds']:.0f}s, "
                    f"{neg['avg_power']:.1f}W, {neg['energy_wh']:.1f}Wh"
                )
                logger.info(
                    f"    Ratios: durée={duration_ratio:.2f}, "
                    f"seuils=[0.50, 1.50]"
                )
                
                if not (0.50 <= duration_ratio <= 1.50):
                    logger.info(f"    ✗ Durée hors limite")
                    continue
                
                logger.info(f"    ✓ Durée OK")
                
                # Critère 2: Puissance moyenne similaire (±5% strict!)
                if neg['avg_power'] > 0:
                    power_ratio = det['avg_power'] / neg['avg_power']
                    logger.info(
                        f"    Puissance: ratio={power_ratio:.2f}, "
                        f"seuils=[0.95, 1.05]"
                    )
                    if not (0.95 <= power_ratio <= 1.05):
                        logger.info(f"    ✗ Puissance hors limite")
                        continue
                    logger.info(f"    ✓ Puissance OK")
                
                # Critère 3: Énergie similaire (±10%)
                det_energy = det.get('energy_wh', 0)
                if neg['energy_wh'] > 0 and det_energy > 0:
                    energy_ratio = det_energy / neg['energy_wh']
                    logger.info(
                        f"    Énergie: ratio={energy_ratio:.2f}, "
                        f"seuils=[0.90, 1.10]"
                    )
                    if not (0.90 <= energy_ratio <= 1.10):
                        logger.info(f"    ✗ Énergie hors limite")
                        continue
                    logger.info(f"    ✓ Énergie OK")
                
                # Tous les critères correspondent → faux positif
                is_false_positive = True
                logger.info(
                    f"❌ Détection rejetée (similaire à signature "
                    f"négative #{neg['id']}): {det.get('appliance_name')} - "
                    f"{det['duration_seconds']}s, "
                    f"{det['avg_power']:.1f}W"
                )
                break
            
            if not is_false_positive:
                filtered.append(det)
            else:
                rejected_count += 1
        
        if rejected_count > 0:
            logger.info(
                f"✅ Filtrage terminé: {rejected_count} faux positifs "
                f"rejetés, {len(filtered)} détections conservées"
            )
        
        return filtered

    def disaggregate(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Désagrège la consommation totale pour tous les appareils
        
        Args:
            start_time: Début de la période
            end_time: Fin de la période
            
        Returns:
            Liste de détections par appareil
        """
        if not hasattr(self, 'multi_model') or self.multi_model is None:
            logger.error("Aucun modèle multi-sorties chargé pour la désagrégation")
            return []

        # Charger les profils de signatures si nécessaire
        if not self.change_point_detector.signature_profiles:
            logger.info("Chargement des profils de signatures pour détection...")
            self._load_signature_profiles()

        try:
            # Charger la consommation totale
            with db_manager.get_session() as session:
                query = """
                    SELECT time, papp
                    FROM linky_realtime
                    WHERE time >= :start_time AND time <= :end_time
                    ORDER BY time
                """
                result = session.execute(
                    text(query),
                    {'start_time': start_time, 'end_time': end_time}
                )
                data = result.fetchall()
                if not data:
                    logger.warning("Aucune donnée pour désagrégation")
                    return []
                timestamps = [row[0] for row in data]
                aggregate_power = np.array([row[1] for row in data], dtype=np.float32)
            logger.info(f"Désagrégation sur {len(aggregate_power)} points")

            #############################################################
            # APPROCHE HYBRIDE : Change Point Detection + Pattern Matching
            #############################################################

            logger.info("=== Détection Hybride (Change Point + Pattern Matching) ===")

            # Étape 1 : Détecter les change points dans l'agrégé
            change_points = self.change_point_detector.detect_change_points(aggregate_power)

            if not change_points:
                logger.warning("Aucun change point détecté")
                return []

            # Étape 2 : Extraire les patterns entre les change points
            patterns = self.change_point_detector.extract_patterns(aggregate_power, change_points)

            if not patterns:
                logger.warning("Aucun pattern extrait")
                return []

            # Étape 3 : Matcher chaque pattern avec les profils de signatures
            detections = []
            for pattern_data in patterns:
                match_result = self.change_point_detector.match_pattern(pattern_data)

                if match_result:
                    appliance_id, appliance_name, matched_signature_id, confidence = match_result

                    # Mapper les indices vers les timestamps
                    start_idx = pattern_data['start_idx']
                    end_idx = pattern_data['end_idx']

                    if start_idx < len(timestamps) and end_idx <= len(timestamps):
                        detection = {
                            'appliance_id': appliance_id,
                            'appliance_name': appliance_name,
                            'signature_id': matched_signature_id,
                            'start_time': timestamps[start_idx],
                            'end_time': timestamps[min(end_idx, len(timestamps)-1)],
                            'duration_seconds': pattern_data['duration'],
                            'avg_power': pattern_data['avg_power'],
                            'max_power': pattern_data['max_power'],
                            'energy_wh': pattern_data['energy_wh'],
                            'confidence_score': float(confidence),
                            'features': {
                                'detection_method': 'change_point_pattern_matching',
                                'change_point_based': True
                            }
                        }
                        if matched_signature_id is not None:
                            detection['features']['matched_signature_id'] = int(matched_signature_id)
                            detection['features']['matching'] = {
                                'score': float(confidence),
                                'method': 'duration_power_shape_combined'
                            }
                        detections.append(detection)

                        logger.info(f"Pattern matché: {appliance_name} - "
                                  f"{pattern_data['duration']}s - "
                                  f"{pattern_data['avg_power']:.1f}W - "
                                  f"confiance {confidence:.2%}")

            logger.info(f"Total détections avant filtrage: {len(detections)}")
            
            # ✨ NOUVEAU: Filtrer contre les signatures négatives
            detections = self._filter_against_negative_signatures(detections)
            
            # ✨ NOUVEAU: Filtrer par seuil de confiance minimum
            min_confidence = 0.55  # 55% de confiance minimum
            before_conf_filter = len(detections)
            detections = [
                d for d in detections
                if d.get('confidence_score', 0) >= min_confidence
            ]
            if before_conf_filter > len(detections):
                logger.info(
                    f"Filtrage confiance: "
                    f"{before_conf_filter - len(detections)} "
                    f"détections rejetées (confiance < {min_confidence:.0%})"
                )
            
            logger.info(f"Total détections après filtrage: {len(detections)}")
            return detections
            
        except Exception as e:
            logger.error(f"Erreur désagrégation: {e}", exc_info=True)
            return []
    
    def _merge_consecutive_cycles(
        self,
        cycles: List[Dict[str, Any]],
        max_gap_seconds: int = 120
    ) -> List[Dict[str, Any]]:
        """
        Fusionne les cycles consécutifs séparés par moins de max_gap_seconds.
        Générique : fonctionne pour tous les appareils.

        Args:
            cycles: Liste de cycles détectés par KMeans
            max_gap_seconds: Gap maximal en secondes pour fusionner deux cycles

        Returns:
            Liste de cycles fusionnés
        """
        if not cycles or len(cycles) == 0:
            return []

        # Trier les cycles par start_idx
        sorted_cycles = sorted(cycles, key=lambda c: c['start_idx'])

        merged = []
        current_merged = sorted_cycles[0].copy()

        for i in range(1, len(sorted_cycles)):
            cycle = sorted_cycles[i]

            # Calculer le gap entre la fin du cycle fusionné actuel et le début du prochain
            gap = cycle['start_idx'] - current_merged['end_idx']

            if gap <= max_gap_seconds:
                # Fusionner : étendre le cycle actuel
                current_merged['end_idx'] = cycle['end_idx']
                current_merged['duration_seconds'] = current_merged['end_idx'] - current_merged['start_idx']
                # Recalculer avg_power et max_power (moyenne pondérée)
                # Note: on garde la max_power la plus élevée
                current_merged['max_power'] = max(current_merged['max_power'], cycle['max_power'])
                # Pour avg_power, on fait une moyenne simple (approximation)
                current_merged['avg_power'] = (current_merged['avg_power'] + cycle['avg_power']) / 2
                # Sommer l'énergie
                current_merged['energy_wh'] = current_merged['energy_wh'] + cycle['energy_wh']
            else:
                # Gap trop grand : sauvegarder le cycle fusionné actuel et commencer un nouveau
                merged.append(current_merged)
                current_merged = cycle.copy()

        # Ajouter le dernier cycle fusionné
        merged.append(current_merged)

        return merged

    def _find_active_segments(
        self,
        active_mask: np.ndarray,
        timestamps: List[datetime],
        predictions: np.ndarray,
        min_duration: int
    ) -> List[Dict[str, Any]]:
        """
        Trouve les segments actifs dans les prédictions, en détectant les gaps
        pour fragmenter les longues périodes en cycles individuels.

        Args:
            active_mask: Masque booléen des prédictions actives
            timestamps: Timestamps correspondants
            predictions: Prédictions de puissance
            min_duration: Durée minimale en secondes

        Returns:
            Liste de segments actifs
        """
        segments = []

        # Padding pour gérer les indices
        half_window = (settings.effective_sequence_length - 1) // 2

        # Paramètres de détection de gaps (périodes inactives entre deux cycles)
        # Un gap est détecté si la puissance reste < 20% du threshold pendant min_gap_duration
        # Pour un ballon d'eau chaude (3500W), un gap = puissance < 100W
        gap_threshold = settings.cnn_min_power_threshold * 0.2  # 20% du seuil (= 100W avec threshold=500W)
        min_gap_duration = 120  # 2 minutes minimum pour considérer un vrai gap (fin de chauffe)

        in_segment = False
        start_idx = 0
        gap_start = None

        for i in range(len(active_mask)):
            current_power = predictions[i] if i < len(predictions) else 0

            if active_mask[i] and not in_segment:
                # Début d'un nouveau segment
                in_segment = True
                start_idx = i
                gap_start = None

            elif in_segment:
                # Dans un segment actif
                if current_power < gap_threshold:
                    # Puissance faible, début potentiel d'un gap
                    if gap_start is None:
                        gap_start = i
                    elif (i - gap_start) >= min_gap_duration:
                        # Gap confirmé : fin du segment actuel
                        duration = gap_start - start_idx

                        if duration >= min_duration:
                            # Enregistrer le segment avant le gap
                            orig_start = start_idx + half_window
                            orig_end = gap_start + half_window

                            if orig_start < len(timestamps) and orig_end <= len(timestamps):
                                segment_predictions = predictions[start_idx:gap_start]

                                segment = {
                                    'start_time': timestamps[orig_start],
                                    'end_time': timestamps[min(orig_end, len(timestamps)-1)],
                                    'duration_seconds': duration,
                                    'avg_power': float(np.mean(segment_predictions)),
                                    'max_power': float(np.max(segment_predictions)),
                                    'energy_wh': float(np.sum(segment_predictions) / 3600),
                                    'confidence_score': float(np.mean(segment_predictions) / np.max(predictions)) if np.max(predictions) > 0 else 0.0
                                }
                                segments.append(segment)

                        # Réinitialiser pour chercher le prochain segment
                        in_segment = False
                        start_idx = i
                        gap_start = None
                else:
                    # Puissance élevée, réinitialiser le compteur de gap
                    gap_start = None

                # Vérifier aussi si on sort du masque actif (cas standard)
                if not active_mask[i]:
                    duration = i - start_idx

                    if duration >= min_duration:
                        orig_start = start_idx + half_window
                        orig_end = i + half_window

                        if orig_start < len(timestamps) and orig_end <= len(timestamps):
                            segment_predictions = predictions[start_idx:i]

                            segment = {
                                'start_time': timestamps[orig_start],
                                'end_time': timestamps[min(orig_end, len(timestamps)-1)],
                                'duration_seconds': duration,
                                'avg_power': float(np.mean(segment_predictions)),
                                'max_power': float(np.max(segment_predictions)),
                                'energy_wh': float(np.sum(segment_predictions) / 3600),
                                'confidence_score': float(np.mean(segment_predictions) / np.max(predictions)) if np.max(predictions) > 0 else 0.0
                            }
                            segments.append(segment)

                    in_segment = False
                    gap_start = None

        # Dernier segment si actif
        if in_segment:
            duration = len(active_mask) - start_idx
            if duration >= min_duration:
                orig_start = start_idx + half_window
                orig_end = len(active_mask) + half_window

                if orig_start < len(timestamps):
                    segment_predictions = predictions[start_idx:]

                    segment = {
                        'start_time': timestamps[orig_start],
                        'end_time': timestamps[min(orig_end, len(timestamps)-1)],
                        'duration_seconds': duration,
                        'avg_power': float(np.mean(segment_predictions)),
                        'max_power': float(np.max(segment_predictions)),
                        'energy_wh': float(np.sum(segment_predictions) / 3600),
                        'confidence_score': float(np.mean(segment_predictions) / np.max(predictions)) if np.max(predictions) > 0 else 0.0
                    }
                    segments.append(segment)

        return segments
