# Nilmia - Documentation des services et architecture

Plateforme complète pour la synchronisation et l'analyse intelligente des données de consommation électrique Linky avec détection automatique d'appareils (NILM).

## Principes de développement

Nous utilisons:
- **Docker Compose** pour l'orchestration de l'application
- **Python 3.13** (3.12 pour nilm-cnn-service) avec **uv** pour la gestion des dépendances
- **TimescaleDB** pour le stockage optimisé des séries temporelles
- **Celery + Redis** pour la gestion des tâches asynchrones
- **TensorFlow/Keras** pour le machine learning CNN

Keep it simple, pas d'over engineering, mais reste complet dans tes actions.
Chaque service a son propre Dockerfile et est documenté dans ce fichier.
Mets à jour périodiquement cette documentation au fur et à mesure de l'évolution du projet.
Pas de fichiers de documentation et de rapports inutiles de toutes tes actions, uniquement ce fichier AGENTS.md et le README.md à la racine.
Ne crée pas de scripts inutiles, efface les une fois que tu les as utilisés et qu'ils sont inutiles.

## Configuration

Un fichier `.env` global à la racine du projet contient toutes les variables d'environnement pour tous les services.
Le fichier `.env.example` fournit un template avec des valeurs par défaut et commentées.
Tous les services Docker Compose utilisent ce fichier `.env` unique via `env_file: - .env`.

### Variables d'environnement principales

```bash
# Base MySQL distante (lecture seule)
REMOTE_DB_HOST=192.168.1.200
REMOTE_DB_PORT=3306
REMOTE_DB_NAME=linky
REMOTE_DB_USER=linky
REMOTE_DB_PASSWORD=***
REMOTE_DB_TABLE=linky_realtime

# Base TimescaleDB locale
LOCAL_DB_HOST=timescaledb
LOCAL_DB_PORT=5432
LOCAL_DB_NAME=local_data
LOCAL_DB_USER=postgres
LOCAL_DB_PASSWORD=postgres

# Redis/Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Configuration sync
SYNC_INTERVAL_SECONDS=5
SYNC_RETENTION_HOURS=48

# Configuration NILM
TRAINING_INTERVAL_HOURS=24
DETECTION_INTERVAL_MINUTES=5
WINDOW_SIZE_MINUTES=60
MIN_POWER_THRESHOLD=50
MIN_DURATION_SECONDS=60
N_CLUSTERS=10
MODEL_PATH=/app/models

# Paramètres CUDA/GPU
BATCH_SIZE=2
MAX_SAMPLES_TRAINING=1000
IMPUTATION_EPOCHS=5
CLUSTERING_EPOCHS=20
MODEL_HIDDEN_SIZE=64
```

## Services

### sync-service
Service de synchronisation des données Linky depuis MySQL vers TimescaleDB.

- **Langage**: Python 3.13
- **Image**: Ubuntu 24.04 + Python 3.13 + uv
- **Dépendances**: 
  - celery[redis]>=5.4.0
  - flower>=2.0.1
  - psycopg[binary]>=3.2.1
  - pymysql>=1.1.1
  - sqlalchemy>=2.0.35
  - pydantic>=2.9.2
  
- **Containers Docker**:
  - `sync-worker`: Worker Celery pour les tâches de synchronisation
  - `sync-beat`: Planificateur Celery Beat pour les tâches périodiques
  - `flower`: Interface de monitoring Celery (port 5555)
  - `init-db`: Initialisation de la base TimescaleDB au démarrage

- **Fonctionnalités**:
  - Synchronisation complète au démarrage (48h de données, ~98 000 lignes)
  - Synchronisation incrémentale automatique toutes les 5 secondes
  - Utilisation de Celery pour la gestion des tâches asynchrones
  - Monitoring en temps réel avec Flower
  - Gestion automatique de la rétention des données (48h)
  - Conversion automatique en hypertable TimescaleDB
  - Politique de compression et suppression automatique

- **Tâches Celery**:
  - `init_database`: Initialise la base locale avec TimescaleDB (auto)
  - `full_sync`: Synchronisation complète des 48h (manuel/démarrage)
  - `incremental_sync`: Synchronisation incrémentale (auto, 5s)
  - `get_stats`: Statistiques de synchronisation (auto, 60s)

- **Table TimescaleDB**: `linky_realtime`
  - `time` (datetime): Timestamp (clé primaire)
  - `papp` (smallint): Puissance apparente (VA)
  - `hchp` (int): Index heures pleines (Wh)
  - `hchc` (int): Index heures creuses (Wh)
  - `temperature` (double): Température (°C)
  - `libelle_tarif` (varchar): Libellé du tarif

- **Configuration**: Fichier .env global à la racine
- **Commandes Makefile**: stats, logs, flower, psql

---

### nilm-cnn-service (service NILM principal)
Service NILM basé sur CNN (Convolutional Neural Networks) pour détection supervisée d'appareils électriques.

- **Langage**: Python 3.12 avec TensorFlow/Keras
- **Image**: tensorflow/tensorflow:latest-gpu (Ubuntu + CUDA 12.3 + cuDNN 9)
- **GPU**: Support NVIDIA CUDA complet avec runtime nvidia
- **Dépendances**:
  - celery[redis]>=5.4.0
  - psycopg[binary]>=3.2.1
  - sqlalchemy>=2.0.35
  - pydantic>=2.9.2
  - tensorflow>=2.18.0
  - numpy>=2.0.0
  - pandas>=2.2.0
  - scikit-learn>=1.5.0
  - scipy>=1.14.0

- **Containers Docker**:
  - `cnn-worker`: Worker Celery pour CNN (queue: nilm_cnn, pool: solo, runtime: nvidia)
  - `cnn-beat`: Planificateur Celery Beat
  - `init-cnn-db`: Initialisation des tables CNN au démarrage

- **Fonctionnalités**:
  - **Apprentissage supervisé** avec signatures manuelles soumises par utilisateur
  - Détection de **signatures complexes** (cycles, formes, variations temporelles)
  - **Support multi-modes** par appareil (éco, rapide, intensif, etc.)
  - **Désagrégation** de la consommation par appareil
  - **Entraînement continu** avec nouvelles données
  - **Gestion intelligente des détections** : mise à jour automatique si meilleure confiance
  - Feature engineering avancé (FFT, gradients, autocorrélation)
  - Augmentation de données (bruit, décalage, scaling)
  - CPU/GPU compatible (pas de CUDA obligatoire)

- **Architecture CNN**:
  - **Modèle**: CNN 1D avec 3 couches convolutionnelles
  - **Features extraites**:
    - Statistiques: moyenne, écart-type, min, max, médiane, quartiles
    - Gradients et changements de direction
    - FFT (analyse fréquentielle, fréquence dominante)
    - Autocorrélation (détection de cycles)
  - **Couches**:
    - Conv1D (64 filtres, kernel 5) + BatchNorm + MaxPool + Dropout
    - Conv1D (128 filtres, kernel 5) + BatchNorm + MaxPool + Dropout
    - Conv1D (256 filtres, kernel 3) + BatchNorm + MaxPool + Dropout
    - Dense (256) + BatchNorm + Dropout
    - Dense (128) + Dropout
    - Dense (num_classes, softmax)
  - **Optimisation**: Adam avec learning rate adaptatif
  - **Early stopping** et **ReduceLROnPlateau**
  - **Séquences**: 600 timesteps (10min à 1Hz)

- **Tâches Celery**:
  - `init_cnn_database`: Initialise les tables CNN (auto)
  - `train_cnn_model`: Entraîne le modèle CNN (auto 24h, manuel)
  - `detect_cnn_appliances`: Détecte appareils avec fenêtre glissante (auto 5min)
    - Gestion intelligente des détections superposées par appareil
    - Mise à jour automatique si meilleure confiance (> existante)
    - Conservation de la meilleure détection (confiance maximale)
  - `add_cnn_signature`: Ajoute signature manuelle utilisateur (manuel)
  - `get_cnn_stats`: Statistiques CNN (auto 5min)

- **Tables TimescaleDB**:
  - `cnn_appliances`: Appareils avec métadonnées (statistiques calculées dynamiquement par le backend)
    - id, name, description, created_at, updated_at
    - Note: num_signatures, avg_power, power_std, avg_duration supprimés (calculés dynamiquement depuis cnn_signatures)
  - `cnn_signatures`: Signatures soumises par utilisateur (sans duplication de données)
    - id, appliance_id, start_time, end_time, mode, avg_power, power_std, energy_consumed, features, created_at
    - Note: raw_data supprimé - les données sont récupérées depuis linky_realtime via start_time/end_time
  - `cnn_detections`: Détections automatiques
    - id, appliance_id, signature_id, start_time, end_time, avg_power, energy_consumed, confidence_score, prediction_class, features
  - `cnn_models`: Modèles CNN versionnés
    - id, version, model_type, architecture, training_date, num_signatures, num_classes, metrics, model_path, is_active

- **Configuration**: Fichier .env global à la racine
- **Commandes Makefile**: cnn-train, cnn-detect, cnn-stats, cnn-add-signature, cnn-models, cnn-appliances
- **Volumes**:
  - `./nilm-cnn-service/src:/app/src` (code source)
  - `./models:/app/models` (modèles CNN persistés)

- **Paramètres CNN ajustables**:
  - `CNN_TRAINING_INTERVAL_HOURS`: 24
  - `CNN_DETECTION_INTERVAL_MINUTES`: 5
  - `CNN_WINDOW_SIZE_MINUTES`: 60
  - `CNN_MIN_POWER_THRESHOLD`: 30W
  - `CNN_MIN_DURATION_SECONDS`: 30s
  - `CNN_SEQUENCE_LENGTH`: 600 (10min)
  - `CNN_BATCH_SIZE`: 32
  - `CNN_EPOCHS`: 50 (max, peut s'arrêter avant avec EarlyStopping)
  - `CNN_LEARNING_RATE`: 0.001
  - `CNN_VALIDATION_SPLIT`: 0.2
  - `CNN_AUGMENTATION_ENABLED`: true
  - `CNN_NOISE_FACTOR`: 0.02
  - `CNN_SHIFT_RANGE`: 30s

- **Mécanismes d'entraînement**:
  - **Minimum 2 appareils** différents requis (sinon erreur explicite)
  - **EarlyStopping** : Arrêt auto si val_loss stagne 15 epochs (patience=15)
    - Désactivé automatiquement si <50 samples d'entraînement
    - Restaure les meilleurs poids automatiquement
  - **ReduceLROnPlateau** : Réduit learning rate si val_loss stagne 7 epochs
  - **TensorBoard** : Logs de métriques pour visualisation

- **Workflow utilisateur**:
  1. Observer un pic de consommation
  2. Soumettre signature (start_time, end_time, appliance, description optionnelle)
  3. Entraînement auto ou manuel
  4. Détection automatique avec fenêtre glissante
  5. Visualisation des appareils et consommation désagrégée

---

### backend-service
Service API REST FastAPI pour exposer les données Linky et NILM-CNN avec streaming SSE.

- **Langage**: Python 3.12
- **Image**: python:3.12-slim-bookworm
- **Dépendances**:
  - fastapi>=0.115.0
  - uvicorn[standard]>=0.32.0
  - psycopg2-binary>=2.9.0
  - sqlalchemy>=2.0.35
  - pydantic>=2.9.2
  - python-dotenv>=1.0.1

- **Container Docker**:
  - `backend`: Serveur FastAPI avec uvicorn (port 8000)

- **Fonctionnalités**:
  - API REST pour accès aux données TimescaleDB (linky_realtime et tables CNN)
  - Streaming SSE (Server-Sent Events) pour mise à jour temps réel
  - CORS configuré pour le frontend React
  - Endpoints de santé et monitoring
  - Agrégation intelligente des données (time_bucket)
  - Documentation automatique OpenAPI/Swagger
  - Intégration avec nilm-cnn-service via Celery

- **Endpoints REST**:
  - `GET /`: Informations sur l'API et liste des endpoints
  - `GET /health`: Healthcheck du service
  - `GET /api/consumption/latest`: Dernière mesure de consommation
  - `GET /api/consumption/history`: Historique agrégé (paramètres: hours, interval)
  - `GET /api/appliances`: Liste de tous les appareils CNN connus
  - `PATCH /api/appliances/{id}`: Mise à jour d'un appareil (nom, description)
  - `DELETE /api/appliances/{id}`: Suppression d'un appareil et ses données
  - `GET /api/detections`: Détections NILM-CNN sur une période (paramètre: hours)
  - `POST /api/signatures`: Création de signature CNN (envoie tâche add_cnn_signature)
  - `POST /api/nilm/train`: Lance l'entraînement manuel du modèle CNN
  - `POST /api/nilm/detect`: Lance la détection manuelle d'appareils
  - `GET /api/nilm/models`: Historique paginé des modèles entraînés (paramètres: page, per_page)

- **Endpoints Streaming SSE**:
  - `GET /api/stream/consumption/latest?update_interval=5`: Stream temps réel de la consommation
  - `GET /api/stream/detections?hours=24&update_interval=10`: Stream des détections NILM-CNN
  - `GET /api/stream/appliances?update_interval=30`: Stream de la liste des appareils

- **Tables utilisées**:
  - `linky_realtime`: Données de consommation Linky
  - `cnn_appliances`: Appareils détectés par CNN
  - `cnn_signatures`: Signatures d'entraînement CNN
  - `cnn_detections`: Détections CNN en temps réel

- **Configuration**: Fichier .env global à la racine
- **Commandes Makefile**: backend, api-latest, api-history, api-detections
- **URL**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs (Swagger UI)

---

### frontend-service
Service interface utilisateur React avec Material-UI et streaming SSE.

- **Langage**: JavaScript/React 18
- **Image**: Node.js 20 Alpine
- **Dépendances**:
  - react>=18.3.1
  - react-dom>=18.3.1
  - @mui/material>=5.15.20
  - @mui/icons-material>=5.15.20
  - chart.js>=4.4.3
  - react-chartjs-2>=5.2.0
  - axios>=1.7.2

- **Container Docker**:
  - `frontend`: Serveur de développement React (port 3000)

- **Fonctionnalités**:
  - Dashboard temps réel de consommation électrique
  - Streaming SSE pour mise à jour instantanée (sans polling)
  - Affichage de la dernière valeur avec indicateur de connexion
  - Graphique Chart.js avec historique de consommation
  - Overlay des détections NILM avec chips interactives
  - Thème Material-UI personnalisé avec palette Nilmia
  - Design responsive et moderne
  - Fallback automatique au polling si SSE indisponible

- **Composants React**:
  - `App.js`: Composant principal avec AppBar et layout
  - `LatestConsumption.js`: Carte affichant la dernière consommation (SSE + fallback polling)
  - `ConsumptionChart.js`: Graphique interactif avec détections NILM (SSE)
  - `AppliancesList.js`: Liste des appareils détectés avec gestion (édition, suppression)
  - `NilmTraining.js`: Gestion de l'entraînement NILM et historique des modèles
  - `theme.js`: Thème Material-UI personnalisé
  - `services/api.js`: Service de communication avec le backend (REST)
  - `services/sse.js`: Service de streaming SSE (EventSource API)

- **Palette de couleurs**:
  - Primary: #BD2A2E (rouge Big-Machine-1)
  - Secondary: #486966 (vert foncé Big-Machine-5)
  - Background: #B2BEBF (gris clair Big-Machine-3)
  - Text: #3B3936 (gris foncé Big-Machine-2)

- **Configuration**: .env dans frontend-service/
- **Commandes Makefile**: frontend
- **URL**: http://localhost:3000
- **Documentation SSE**: Voir `SSE_IMPLEMENTATION.md`

---

### timescaledb
Base de données TimescaleDB pour stocker les données Linky et NILM.

- **Image**: timescale/timescaledb:latest-pg16
- **Container**: nilmia-timescaledb
- **Port**: 5432
- **Base de données**: local_data
- **Credentials**: postgres/postgres
- **Volume**: timescaledb_data (persistence)

- **Fonctionnalités**:
  - Conservation de toutes les données (pas de limite de rétention globale)
  - Hypertable automatique pour linky_realtime (chunks de 6h)
  - Politique de rétention configurable (48h par défaut pour sync)
  - Optimisation pour les séries temporelles
  - Healthcheck: pg_isready

- **Tables**:
  - Sync: `linky_realtime` (hypertable)
  - NILM: `appliances`, `appliance_signatures`, `detection_events`, `model_versions`

---

### redis
Broker Redis pour Celery (partagé entre tous les services).

- **Image**: redis:7-alpine
- **Container**: nilmia-redis
- **Port**: 6379
- **Volume**: redis_data (persistence)
- **Configuration**: Persistance activée avec AOF
- **Healthcheck**: redis-cli ping

---

### flower
Interface web de monitoring pour Celery.

- **Image**: Basée sur sync-service
- **Container**: nilmia-flower
- **Port**: 5555
- **URL**: http://localhost:5555
- **Connexion**: Redis broker
- **Monitoring**: Workers sync et nilm, tâches, résultats, GPU

---

### pgadmin
Interface web d'administration pour TimescaleDB.

- **Image**: dpage/pgadmin4:latest
- **Container**: nilmia-pgadmin
- **Port**: 8080
- **URL**: http://localhost:8080
- **Credentials**: admin@example.com / admin
- **Configuration**: Serveurs pré-configurés via JSON
- **Volumes**: 
  - pgadmin_data (persistence)
  - pgadmin-config/pgadmin-servers.json (config)
  - pgadmin-config/pgpass (credentials)
  - pgadmin-config/init-pgadmin.sh (script init)
- **Fonctionnalités**: Interface graphique complète pour gestion de la base



## Orchestration

Tous les services sont orchestrés via le fichier `docker-compose.yml` à la racine du projet.

### Structure des services Docker Compose

```yaml
services:
  timescaledb          # Base de données TimescaleDB (port 5432)
  redis                # Broker Redis pour Celery (port 6379)
  sync-worker          # Worker Celery pour synchronisation
  sync-beat            # Planificateur Celery pour sync
  flower               # Interface monitoring Celery (port 5555)
  pgadmin              # Interface admin TimescaleDB (port 8080)
  init-db              # Initialisation base TimescaleDB (oneshot)
  cnn-worker           # Worker Celery NILM-CNN avec GPU optionnel
  cnn-beat             # Planificateur Celery pour NILM-CNN
  init-cnn-db          # Initialisation tables NILM-CNN (oneshot)
  tensorboard          # Interface visualisation TensorBoard (port 6006)
  backend              # API REST FastAPI (port 8000)
  frontend             # Interface React (port 3000)
```

### Dépendances entre services

- `sync-worker` et `sync-beat` dépendent de `timescaledb` et `redis` (healthcheck)
- `cnn-worker` et `cnn-beat` dépendent de `timescaledb`, `redis` et `sync-worker`
- `init-db` s'exécute une fois au démarrage (restart: no)
- `init-cnn-db` s'exécute après `init-db` (restart: no)
- `backend` dépend de `timescaledb` et `sync-worker`
- `frontend` dépend de `backend` (healthcheck)
- `flower` et `pgadmin` dépendent de leurs services respectifs
- `tensorboard` utilise le volume `./models` partagé avec `cnn-worker` et `cnn-beat`

### Volumes persistants

```yaml
volumes:
  timescaledb_data    # Données PostgreSQL/TimescaleDB
  redis_data          # Données Redis (AOF)
  pgadmin_data        # Configuration pgAdmin
  nilm_uv_cache       # Cache uv pour builds NILM-CNN rapides
```

### Réseau

- Un seul réseau bridge: `nilmia-network`
- Tous les services communiquent via ce réseau interne
- Ports exposés: 3000, 5432, 5555, 6006, 6379, 8000, 8080

### Configuration GPU

Le service `cnn-worker` peut utiliser le GPU via la configuration (optionnel, fallback CPU):
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

---

## Makefile - Commandes disponibles

Le fichier `Makefile` à la racine fournit des commandes pour gérer l'application.

### Commandes principales

| Commande | Description |
|----------|-------------|
| `make start` | Démarrage complet (vérifie .env, build, up, affiche infos) |
| `make check` | Vérifie l'état des services et affiche les statistiques |
| `make build` | Construit les images Docker avec BuildKit |
| `make up` | Démarre tous les services en arrière-plan |
| `make down` | Arrête tous les services |
| `make restart` | Redémarre tous les services |
| `make clean` | Supprime containers et volumes |
| `make logs` | Affiche les logs de tous les services |
| `make status` | Affiche le statut des services |
| `make help` | Affiche l'aide des commandes |

### Commandes Sync

| Commande | Description |
|----------|-------------|
| `make stats` | Statistiques de synchronisation |
| `make psql` | Se connecte à TimescaleDB via psql |
| `make redis-cli` | Se connecte à Redis via redis-cli |
| `make flower` | Affiche l'URL de Flower |
| `make pgadmin` | Affiche l'URL et credentials pgAdmin |

### Commandes Backend/Frontend

| Commande | Description |
|----------|-------------|
| `make backend` | Teste l'API backend |
| `make frontend` | Affiche l'URL du frontend |
| `make api-latest` | Récupère la dernière consommation via l'API |
| `make api-history` | Récupère l'historique via l'API |
| `make api-detections` | Récupère les détections via l'API |

### Commandes NILM

| Commande | Description |
|----------|-------------|
| `make nilm-train` | Lance l'entraînement du modèle NILM |
| `make nilm-detect` | Lance une détection manuelle d'appareils |
| `make nilm-stats` | Affiche les statistiques de détection NILM |
| `make nilm-models` | Liste les modèles ML entraînés |
| `make api-nilm-train` | Lance l'entraînement via l'API REST |
| `make api-nilm-detect` | Lance la détection via l'API REST |
| `make api-nilm-models` | Récupère l'historique des modèles via l'API |

### Exemples d'utilisation

```bash
# Premier démarrage
make start

# Vérifier que tout fonctionne
make check

# Consulter les logs
make logs

# Entraîner le modèle NILM (après 48h de données)
make nilm-train

# Voir les détections
make nilm-stats

# Arrêter proprement
make down
```

---

## Structure du projet

```
nilmia/
├── .env                          # Configuration globale (à créer depuis .env.example)
├── .env.example                  # Template de configuration
├── docker-compose.yml            # Orchestration des services
├── Makefile                      # Commandes de gestion
├── README.md                     # Documentation utilisateur
├── AGENTS.md                     # Documentation architecture (ce fichier)
│
├── sync-service/                 # Service de synchronisation Linky
│   ├── Dockerfile                # Python 3.13 + uv
│   ├── pyproject.toml            # Dépendances Python
│   └── src/
│       ├── __init__.py
│       ├── config.py             # Configuration Pydantic
│       ├── database.py           # Gestion bases MySQL/TimescaleDB
│       └── tasks.py              # Tâches Celery (sync, stats)
│
├── nilm-cnn-service/             # Service NILM-CNN (ML supervisé)
│   ├── Dockerfile                # Python 3.12 + TensorFlow + uv
│   ├── pyproject.toml            # Dépendances Python (TensorFlow, Keras)
│   └── src/
│       ├── __init__.py
│       ├── config.py             # Configuration NILM-CNN
│       ├── database.py           # Gestion tables CNN
│       ├── cnn_nilm.py           # Modèles CNN 1D
│       └── tasks.py              # Tâches Celery (train, detect)
│
├── backend-service/              # Service API REST FastAPI
│   ├── Dockerfile                # Python 3.13 + uv
│   ├── pyproject.toml            # Dépendances Python
│   └── src/
│       ├── __init__.py
│       ├── config.py             # Configuration API
│       ├── database.py           # Gestion connexion TimescaleDB
│       └── main.py               # Application FastAPI
│
├── frontend-service/             # Service interface utilisateur React
│   ├── Dockerfile                # Node.js 20 Alpine
│   ├── package.json              # Dépendances Node.js
│   ├── public/
│   │   └── index.html            # Page HTML principale
│   └── src/
│       ├── index.js              # Point d'entrée React
│       ├── App.js                # Composant principal
│       ├── theme.js              # Thème Material-UI
│       ├── components/           # Composants React
│       │   ├── LatestConsumption.js
│       │   └── ConsumptionChart.js
│       └── services/
│           └── api.js            # Service API
│
├── models/                       # Modèles ML persistés (volume)
│   └── [modèles PyTorch versionnés]
│
└── pgadmin-config/               # Configuration pgAdmin
    ├── init-pgadmin.sh           # Script d'initialisation
    ├── pgadmin-servers.json      # Serveurs pré-configurés
    ├── pgpass                    # Credentials
    └── README.md
```

---

## Documentation

### Documentation utilisateur (README.md)
- Guide de démarrage rapide
- Configuration des variables d'environnement
- Utilisation des commandes Makefile
- Accès aux interfaces web (Flower, pgAdmin)
- Exemples d'utilisation du NILM

### Documentation architecture (AGENTS.md)
- Ce fichier
- Description détaillée de chaque service
- Architecture technique
- Choix de conception
- Guide pour les contributeurs

### Documentation inline
- Chaque fichier Python contient des docstrings
- Configuration Pydantic avec validation et description
- Commentaires dans docker-compose.yml et Makefile

---

## Développement futur

### Court terme (MVP)
- ✅ Service de synchronisation Linky fonctionnel
- ✅ Service NILM avec détection automatique
- ✅ Interface monitoring (Flower)
- ✅ Interface admin base de données (pgAdmin)
- ✅ API REST pour exposer les données
- ✅ Interface web React avec Material-UI
- ⏳ Tests unitaires complets

### Moyen terme
- 📊 Dashboard Grafana pour visualisation
- 🌐 Interface web pour gestion des appareils
  - Validation/correction des détections
  - Ajout manuel de signatures
  - Historique de consommation par appareil
- 🔔 Service d'alerting (pics, anomalies)
- 📱 Application mobile (optionnel)

### Long terme
- 🤖 Amélioration continue du modèle NILM
  - Apprentissage avec feedback utilisateur
  - Support de nouveaux types d'appareils
  - Modèles personnalisés par foyer
- 📊 Export et rapports de consommation
  - PDF, Excel, CSV
  - Rapports mensuels automatiques
  - Comparaison avec historique
- 🌍 Multi-compteurs (plusieurs foyers)
- 💡 Recommandations d'économie d'énergie
- 🔌 Intégration domotique (Home Assistant, etc.)

---

## Bonnes pratiques

### Code
- ✅ Type hints Python partout
- ✅ Configuration via Pydantic Settings
- ✅ Validation des données en entrée/sortie
- ✅ Gestion des erreurs avec logging approprié
- ✅ Séparation des responsabilités (config, database, tasks, ML)
- ⏳ Tests unitaires pour les composants critiques
- ⏳ Tests d'intégration pour les workflows complets

### Docker
- ✅ Images légères basées sur Alpine/Ubuntu 24.04
- ✅ Multi-stage builds pour réduire la taille
- ✅ Cache de build optimisé (BuildKit, uv cache)
- ✅ Healthchecks pour tous les services critiques
- ✅ Restart policies appropriées
- ✅ Volumes pour la persistence des données

### Sécurité
- ✅ Variables sensibles dans .env (git ignored)
- ✅ Credentials stockés de manière sécurisée
- ✅ Accès base distante en lecture seule
- ✅ Réseau Docker interne isolé
- ⏳ HTTPS pour les interfaces web (production)
- ⏳ Authentification renforcée (production)

### Monitoring
- ✅ Logs structurés avec timestamps
- ✅ Monitoring Celery avec Flower
- ✅ Healthchecks Docker
- ✅ Statistiques de performance ML
- ⏳ Alerting sur erreurs critiques
- ⏳ Métriques Prometheus (optionnel)

### Documentation
- ✅ README.md pour les utilisateurs
- ✅ AGENTS.md pour l'architecture
- ✅ Docstrings Python
- ✅ Commentaires dans les configs
- ✅ .env.example avec descriptions
- ✅ Documentation API (OpenAPI/Swagger)

---

## Dépannage

### Problèmes courants

**Service ne démarre pas**
```bash
# Vérifier les logs
make logs

# Vérifier l'état
make check

# Rebuild depuis zéro
make clean
make start
```

**Erreur mémoire lors de l'entraînement CNN**
```bash
# Réduire les paramètres dans .env
CNN_BATCH_SIZE=16
CNN_SEQUENCE_LENGTH=300
CNN_EPOCHS=30

# Redémarrer le service CNN
docker-compose restart cnn-worker cnn-beat
```

**Base de données corrompue**
```bash
# Sauvegarder si possible
docker exec nilmia-timescaledb pg_dump -U postgres local_data > backup.sql

# Nettoyer et redémarrer
make clean
make start
```

**Synchronisation bloquée**
```bash
# Vérifier la connexion MySQL distante
docker exec nilmia-sync-worker python -c "from src.database import db_manager; db_manager.test_remote_connection()"

# Forcer une sync complète
docker exec nilmia-sync-worker celery -A src.tasks.celery_app call full_sync
```

**Modèle CNN ne détecte rien**
```bash
# Vérifier qu'il y a assez de signatures
make cnn-stats

# Vérifier les modèles
make cnn-models

# Ré-entraîner manuellement
make cnn-train
```

### Logs utiles

```bash
# Tous les logs
make logs

# Logs d'un service spécifique
docker logs nilmia-sync-worker -f
docker logs nilmia-cnn-worker -f

# Logs Celery
docker exec nilmia-sync-worker celery -A src.tasks.celery_app inspect active
docker exec nilmia-cnn-worker celery -A src.tasks.celery_app inspect active

# Logs TimescaleDB
docker logs nilmia-timescaledb
```

---

## Performance

### Optimisations actuelles

**Synchronisation**
- Requêtes SQL optimisées avec index sur `time`
- Utilisation de hypertables TimescaleDB
- Batch inserts pour réduire les transactions
- Politique de rétention automatique (48h)

**NILM**
- Cache de build Docker (réduction 90% du temps)
- Batch processing GPU
- Limitation des échantillons d'entraînement
- Modèles versionnés et réutilisables
- Pool solo Celery pour éviter les conflits GPU

**Base de données**
- TimescaleDB avec chunks de 6h
- Index optimisés sur colonnes temporelles
- Compression automatique des anciennes données
- Statistiques précalculées

### Métriques observées

- Sync: ~5-10ms par cycle (toutes les 5s)
- NILM training: ~2-5min (selon GPU et données)
- NILM détection: ~10-30s (fenêtre 60min)
- Stockage: ~100MB pour 48h de données Linky

---

## Contact et support

Pour toute question ou problème:
1. Consulter cette documentation (AGENTS.md)
2. Vérifier le README.md pour l'usage courant
3. Consulter les logs avec `make logs`
4. Utiliser `make check` pour diagnostiquer

