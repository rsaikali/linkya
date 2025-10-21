# Service NILM (Non-Intrusive Load Monitoring)

Service d'analyse intelligent pour la détection automatique d'appareils électriques à partir des données de consommation Linky.

## Architecture

Le service utilise des algorithmes ML avancés pour identifier les signatures d'appareils :

- **PyPOTS CRLI** : Clustering pour identifier les patterns de consommation
- **PyPOTS SAITS** : Imputation pour gérer les données manquantes
- **CUDA/GPU** : Accélération des calculs ML

## Fonctionnalités

### Détection automatique
- Analyse des signatures complexes (cycles, variations, pics)
- Détection en temps réel toutes les 5 minutes
- Score de confiance pour chaque détection

### Training automatique
- Réentraînement périodique (24h par défaut)
- Versionnement des modèles
- Métriques de performance (Silhouette Score, Davies-Bouldin)

### Interactions utilisateur
- Ajout manuel de signatures entre deux timestamps
- Validation/correction des détections
- Consultation des statistiques par appareil

## Tables de données

### `appliances`
Appareils détectés avec leurs caractéristiques :
- Nom, description, validation utilisateur
- Puissance moyenne/max/min, variance
- Features de signature extraites

### `appliance_signatures`
Données d'entraînement (signatures validées) :
- Période de référence (start_time, end_time)
- Ajout manuel ou automatique

### `detection_events`
Événements de détection en temps réel :
- Timestamps début/fin
- Puissance moyenne, énergie consommée
- Score de confiance
- Statut de validation

### `model_versions`
Historique des modèles ML :
- Version, type, path
- Date d'entraînement
- Métriques de performance

## Commandes Makefile

```bash
# Lancer un entraînement manuel
make nilm-train

# Lancer une détection manuelle
make nilm-detect

# Afficher les statistiques
make nilm-stats

# Lister les modèles
make nilm-models
```

## API Celery

### Tâches périodiques
- `train_nilm_model` : Entraînement toutes les 24h
- `detect_appliances_task` : Détection toutes les 5 minutes

### Tâches manuelles
```python
# Ajouter une signature manuelle
add_manual_signature.delay(
    appliance_name="Lave-linge",
    start_time="2025-10-20T10:00:00",
    end_time="2025-10-20T11:30:00",
    description="Cycle complet"
)

# Valider une détection
validate_detection.delay(
    detection_id=123,
    is_correct=True
)

# Corriger une détection
validate_detection.delay(
    detection_id=456,
    is_correct=False,
    correct_appliance_id=789
)

# Statistiques
get_detection_stats.delay(hours=24)
```

## Configuration

Fichier `.env` :
```bash
# Training
TRAINING_INTERVAL_HOURS=24
DETECTION_INTERVAL_MINUTES=5

# Analyse
WINDOW_SIZE_MINUTES=60
MIN_POWER_THRESHOLD=50
MIN_DURATION_SECONDS=60

# ML
N_CLUSTERS=10
MODEL_PATH=/app/models
```

## Prérequis GPU

Le service nécessite :
- Docker avec support GPU (nvidia-docker2)
- Driver NVIDIA compatible
- CUDA 12.6+

Vérification :
```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu24.04 nvidia-smi
```
