# NILM-CNN Service

Service de détection et classification d'appareils électriques basé sur CNN (Convolutional Neural Networks).

## Description

Ce service utilise un réseau de neurones convolutifs 1D pour identifier automatiquement les appareils électriques à partir de leurs signatures de consommation complexes. Il permet:

- **Apprentissage supervisé** avec signatures manuelles soumises par l'utilisateur
- **Détection de patterns complexes** (cycles, formes de courbes, variations temporelles)
- **Support multi-modes** par appareil (éco, rapide, intensif, etc.)
- **Désagrégation de la consommation** par appareil
- **Entraînement continu** avec nouvelles données

## Architecture

### Modèle CNN

- **Architecture**: CNN 1D avec 3 couches convolutionnelles
- **Features extraites**:
  - Statistiques (moyenne, écart-type, min, max, médiane, quartiles)
  - Gradients et variations temporelles
  - FFT (analyse fréquentielle)
  - Autocorrélation (détection de cycles)
- **Augmentation de données**: bruit, décalage temporel, mise à l'échelle
- **Normalisation**: StandardScaler sur les séquences

### Stack technique

- **Python 3.12** avec uv
- **TensorFlow/Keras** pour le deep learning
- **NumPy/SciPy** pour le traitement du signal
- **Celery** pour les tâches asynchrones
- **TimescaleDB** pour le stockage

## Tables en base de données

### cnn_appliances
Appareils électriques identifiés.

| Colonne | Type | Description |
|---------|------|-------------|
| id | INTEGER | Identifiant unique |
| name | VARCHAR(255) | Nom de l'appareil |
| description | VARCHAR(1000) | Description |
| avg_power | FLOAT | Puissance moyenne (W) |
| power_std | FLOAT | Écart-type puissance |
| avg_duration | FLOAT | Durée moyenne (s) |
| num_signatures | INTEGER | Nombre de signatures |
| is_validated | BOOLEAN | Validé par utilisateur |
| created_at | DATETIME | Date de création |
| updated_at | DATETIME | Date de mise à jour |

### cnn_signatures
Signatures de courbes soumises manuellement par l'utilisateur.

| Colonne | Type | Description |
|---------|------|-------------|
| id | INTEGER | Identifiant unique |
| appliance_id | INTEGER | Référence appareil |
| start_time | DATETIME | Début de la signature |
| end_time | DATETIME | Fin de la signature |
| avg_power | FLOAT | Puissance moyenne |
| power_std | FLOAT | Écart-type |
| energy_consumed | FLOAT | Énergie totale (Wh) |
| features | JSON | Features extraites |
| created_at | DATETIME | Date d'ajout |

**Note**: `raw_data` supprimé - les données sont récupérées dynamiquement depuis `linky_realtime` via `start_time`/`end_time`

### cnn_detections
Détections automatiques d'appareils.

| Colonne | Type | Description |
|---------|------|-------------|
| id | INTEGER | Identifiant unique |
| appliance_id | INTEGER | Appareil détecté |
| signature_id | INTEGER | Signature correspondante |
| start_time | DATETIME | Début détection |
| end_time | DATETIME | Fin détection |
| avg_power | FLOAT | Puissance moyenne |
| energy_consumed | FLOAT | Énergie désagrégée (Wh) |
| confidence_score | FLOAT | Confiance [0-1] |
| prediction_class | INTEGER | Classe CNN |
| features | JSON | Features |
| is_validated | BOOLEAN | Validé |
| created_at | DATETIME | Date détection |

### cnn_models
Versionnement des modèles CNN.

| Colonne | Type | Description |
|---------|------|-------------|
| id | INTEGER | Identifiant unique |
| version | VARCHAR(50) | Version (timestamp) |
| model_type | VARCHAR(100) | Type (CNN1D) |
| architecture | JSON | Architecture détaillée |
| training_date | DATETIME | Date d'entraînement |
| num_signatures | INTEGER | Nb signatures train |
| num_classes | INTEGER | Nb classes/appareils |
| metrics | JSON | Performances |
| model_path | VARCHAR(500) | Chemin modèle |
| is_active | BOOLEAN | Modèle actif |

## Tâches Celery

### init_cnn_database
Initialise les tables en base de données (automatique au démarrage).

### train_cnn_model
Entraîne le modèle CNN sur toutes les signatures disponibles.

- **Déclenchement**: Automatique toutes les 24h ou manuel
- **Prérequis**: Minimum 10 signatures
- **Sortie**: Modèle versionné + métriques

```bash
# Manuel
docker exec nilmia-cnn-worker celery -A src.tasks.celery_app call train_cnn_model
```

### detect_cnn_appliances
Détecte les appareils dans la période récente.

- **Déclenchement**: Automatique toutes les 5 minutes
- **Paramètres**: hours (période), min_confidence (seuil)
- **Sortie**: Détections sauvegardées en base

```bash
# Manuel - dernière heure
docker exec nilmia-cnn-worker celery -A src.tasks.celery_app call detect_cnn_appliances --kwargs='{"hours": 1}'
```

### add_cnn_signature
Ajoute une signature manuelle soumise par l'utilisateur.

```bash
# Exemple
docker exec nilmia-cnn-worker celery -A src.tasks.celery_app call add_cnn_signature \
  --kwargs='{"appliance_name": "Lave-linge", "start_time_str": "2025-10-22T10:00:00Z", "end_time_str": "2025-10-22T11:30:00Z", "description": "Cycle éco 40°C"}'
```

### get_cnn_stats
Récupère les statistiques du service (automatique toutes les 5 minutes).

```bash
docker exec nilmia-cnn-worker celery -A src.tasks.celery_app call get_cnn_stats
```

## Workflow utilisateur

### 1. Soumission de signatures

L'utilisateur observe un pic de consommation et soumet une signature:

```json
{
  "appliance_name": "Lave-linge",
  "start_time": "2025-10-22T10:00:00Z",
  "end_time": "2025-10-22T11:30:00Z",
  "description": "Cycle éco 40°C"
}
```

### 2. Entraînement

- Automatique toutes les 24h
- Déclenché automatiquement tous les 5 nouvelles signatures
- Manuel via commande Celery

### 3. Détection automatique

- Fenêtre glissante sur les données récentes
- Classification CNN des séquences
- Fusion des événements consécutifs
- Sauvegarde avec score de confiance

### 4. Visualisation

- Liste des appareils avec consommation
- Timeline des détections
- Consommation désagrégée par appareil

## Configuration

Variables dans `.env`:

```bash
# Intervalles
CNN_TRAINING_INTERVAL_HOURS=24
CNN_DETECTION_INTERVAL_MINUTES=5
CNN_WINDOW_SIZE_MINUTES=60

# Seuils
CNN_MIN_POWER_THRESHOLD=30
CNN_MIN_DURATION_SECONDS=30

# Modèle CNN
CNN_MODEL_PATH=/app/models/cnn
CNN_SEQUENCE_LENGTH=600
CNN_BATCH_SIZE=32
CNN_EPOCHS=50
CNN_LEARNING_RATE=0.001
CNN_VALIDATION_SPLIT=0.2

# Augmentation
CNN_AUGMENTATION_ENABLED=true
CNN_NOISE_FACTOR=0.02
CNN_SHIFT_RANGE=30

# Features
CNN_FFT_ENABLED=true
CNN_GRADIENT_ENABLED=true
CNN_STATISTICS_ENABLED=true
```

## Développement

### Build

```bash
make build
# ou
docker-compose build cnn-worker cnn-beat
```

### Logs

```bash
docker logs nilmia-cnn-worker -f
docker logs nilmia-cnn-beat -f
```

### Tests

```bash
# Ajouter une signature de test
make cnn-add-signature

# Entraîner
make cnn-train

# Détecter
make cnn-detect

# Stats
make cnn-stats
```

## TODO

- [ ] API REST pour soumission de signatures depuis frontend
- [ ] Interface web de validation/correction
- [ ] Export des modèles pour déploiement offline
- [ ] Support de signatures multi-phases (triphasé)
- [ ] Détection d'anomalies (consommation anormale)
- [ ] Recommandations d'économie d'énergie
