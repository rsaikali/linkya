# NILM Module

Ce module contient les composants de l'algorithme NILM (Non-Intrusive Load Monitoring) pour la désagrégation d'appareils électriques.

## Structure

```
nilm/
├── __init__.py                   # Exports publics
├── losses.py                     # Fonctions de perte personnalisées (focal_loss, asymmetric_loss)
├── callbacks.py                  # Callbacks Keras (RedisTrainingCallback)
├── layers.py                     # Couches personnalisées (MultiHeadAttentionLayer)
├── preprocessing.py              # Préprocessing des données (Seq2PointPreprocessor)
├── morphology.py                 # Analyse morphologique des signatures (MorphologyAnalyzer)
├── utils.py                      # Utilitaires (normalize_name_for_tensorflow)
├── models/                       # Modèles de deep learning
│   ├── __init__.py
│   └── multioutput_model.py     # Seq2PointMultiOutputModel
└── detectors/                    # Détecteurs de patterns
    ├── __init__.py
    ├── change_point_detector.py # ChangePointPatternDetector
    └── state_detector.py        # ApplianceStateDetector
```

## Composants principaux

### Losses (`losses.py`)
- **focal_loss_fixed**: Focal Loss pour se concentrer sur les exemples difficiles
- **asymmetric_loss**: Loss asymétrique qui pénalise plus les faux positifs

### Callbacks (`callbacks.py`)
- **RedisTrainingCallback**: Publie les événements d'entraînement sur Redis Pub/Sub pour suivi en temps réel

### Layers (`layers.py`)
- **MultiHeadAttentionLayer**: Couche d'attention multi-têtes pour capturer les patterns de multiples appareils simultanés

### Preprocessing (`preprocessing.py`)
- **Seq2PointPreprocessor**: Préprocessing pour modèle Sequence-to-Point (création de séquences, normalisation)

### Morphology (`morphology.py`)
- **MorphologyAnalyzer**: Analyse morphologique avancée des signatures de puissance (forme, oscillations, gradients, plateaux, features fréquentielles)

### Models (`models/`)
- **Seq2PointMultiOutputModel**: Modèle principal avec architecture Multi-Output (N sorties, une par appareil)

### Detectors (`detectors/`)
- **ChangePointPatternDetector**: Détection de change points et pattern matching
- **ApplianceStateDetector**: Détection d'états/cycles via clustering (KMeans)

### Utils (`utils.py`)
- **normalize_name_for_tensorflow**: Normalise les noms pour compatibilité TensorFlow/Keras

## Usage

```python
from nilm.models import Seq2PointMultiOutputModel
from nilm.detectors import ChangePointPatternDetector
from nilm.preprocessing import Seq2PointPreprocessor
from nilm.morphology import MorphologyAnalyzer

# Créer un modèle
model = Seq2PointMultiOutputModel(
    appliance_ids=[1, 2, 3],
    appliance_names=["Ballon", "Lave-linge", "Lave-vaisselle"],
    sequence_length=599,
    model_type="gru"
)

# Entraîner
metrics = model.train(all_signatures, model_name="linkya_model_20250108")

# Charger un détecteur
detector = ChangePointPatternDetector(
    min_power_change=500,
    min_duration=300
)

# Analyser la morphologie d'une signature
analyzer = MorphologyAnalyzer(sampling_rate_hz=1.0)
morphology = analyzer.analyze(power_values, start_time)
```

## Principes de conception

- **Code en anglais**: Tous les commentaires, docstrings, logs
- **Séparation des responsabilités**: Chaque module a un rôle précis
- **Testabilité**: Les classes sont indépendantes et facilement testables
- **Réutilisabilité**: Les composants peuvent être utilisés séparément

## Références

Architecture basée sur Sequence-to-Point NILM avec:
- Extraction de features (Conv1D + GRU/LSTM)
- Mécanisme d'attention multi-têtes
- Détection hybride (change points + pattern matching)
- Gestion de plusieurs appareils concurrents
