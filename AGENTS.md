# Nilmia - Documentation des services et architecture

Plateforme complète pour la synchronisation et l'analyse intelligente des données de consommation électrique Linky avec détection automatique d'appareils (NILM).

## Principes de développement

Nous utilisons:
- **Docker Compose** pour l'orchestration de l'application
- **Python 3.13** (3.12 pour nilm-service avec CUDA) avec **uv** pour la gestion des dépendances
- **TimescaleDB** pour le stockage optimisé des séries temporelles
- **Celery + Redis** pour la gestion des tâches asynchrones
- **PyTorch avec CUDA** pour l'accélération GPU du machine learning

Keep it simple, pas d'over engineering, mais reste complet dans tes actions.
Ne crée pas de scripts inutiles, efface les une fois que tu les as utilisés et qu'ils sont inutiles.
Chaque service a son propre Dockerfile et est documenté dans ce fichier.
Mets à jour périodiquement cette documentation au fur et à mesure de l'évolution du projet.
Pas de fichiers markdown de rapport inutiles.

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

### nilm-service
Service d'analyse NILM (Non-Intrusive Load Monitoring) pour détecter automatiquement les appareils électriques.

- **Langage**: Python 3.12 avec support GPU CUDA
- **Image**: Ubuntu 24.04 + Python 3.12 + CUDA 12.1
- **Dépendances**:
  - celery[redis]>=5.4.0
  - psycopg[binary]>=3.2.1
  - sqlalchemy>=2.0.35
  - pydantic>=2.9.2
  - pypots>=0.9.0 (analyse séries temporelles)
  - torch>=2.5.0 (PyTorch avec CUDA)
  - numpy>=2.0.0
  - pandas>=2.2.0
  - scikit-learn>=1.5.0
  - scipy>=1.14.0

- **Containers Docker**:
  - `nilm-worker`: Worker Celery avec accès GPU (queue: nilm, pool: solo)
  - `nilm-beat`: Planificateur Celery Beat pour les tâches périodiques
  - `init-nilm-db`: Initialisation des tables NILM au démarrage

- **Fonctionnalités**:
  - Détection automatique des signatures d'appareils électriques complexes
  - Utilisation de PyPOTS pour l'analyse de séries temporelles
    - Clustering CRLI pour identifier les patterns de consommation
    - Imputation SAITS pour gérer les données manquantes
  - Training périodique automatique (toutes les 24h par défaut)
  - Détection en temps réel toutes les 5 minutes
  - Support CUDA/GPU pour accélération des calculs ML
  - API Celery pour ajout manuel de signatures par l'utilisateur
  - Validation et correction des détections
  - Stockage des modèles versionnés et métriques de performance

- **Architecture ML**:
  - **Features extraction**: 
    - Puissance moyenne, écart-type, min, max
    - Variations et gradients temporels
    - Détection de cycles et patterns répétitifs
    - Indices de stabilité
  - **Clustering CRLI**: Identification des états de consommation
  - **Imputation SAITS**: Gestion robuste des données manquantes
  - **Détection d'événements**: Analyse des transitions entre clusters
  - **Scoring**: Calcul de confiance basé sur la stabilité et durée

- **Tâches Celery**:
  - `init_nilm_database`: Initialise les tables NILM (auto)
  - `train_nilm_model`: Entraînement du modèle ML (auto, 24h)
  - `detect_appliances_task`: Détection d'appareils (auto, 5min)
  - `add_manual_signature`: Ajout signature manuelle (manuel)
  - `validate_detection`: Validation/correction détection (manuel)
  - `get_detection_stats`: Statistiques NILM (manuel)

- **Tables TimescaleDB**:
  - `appliances`: Appareils détectés avec signatures
    - id, name, description, avg_power, power_std, is_validated, created_at, updated_at
  - `appliance_signatures`: Données d'entraînement (manuelles ou auto)
    - id, appliance_id, start_time, end_time, avg_power, power_std, features, is_validated
  - `detection_events`: Événements de détection avec timestamps et scores
    - id, appliance_id, start_time, end_time, avg_power, energy_consumed, confidence_score
  - `model_versions`: Versionnement des modèles ML
    - id, version, model_type, training_date, is_active, metrics, model_path

- **Configuration**: Fichier .env global à la racine
- **Commandes Makefile**: nilm-train, nilm-detect, nilm-stats, nilm-models
- **Volumes**:
  - `./nilm-service/src:/app/src` (code source)
  - `./models:/app/models` (modèles ML persistés)
  - `nilm_uv_cache` (cache uv pour builds rapides)

- **Cache de build optimisé**:
  - BuildKit cache avec persistence locale (.buildcache/)
  - Mounted cache UV pour réutilisation des packages Python
  - Volume Docker persistant (nilm_uv_cache)
  - Réduit les temps de rebuild de 90% (5-10min → 30-60s)
  - Commande: `DOCKER_BUILDKIT=1 docker-compose build nilm-worker`

- **Paramètres CUDA ajustables** (selon GPU):
  - `BATCH_SIZE`: 2 (1 pour GPU < 4GB)
  - `MAX_SAMPLES_TRAINING`: 1000 (500 pour GPU < 4GB)
  - `IMPUTATION_EPOCHS`: 5
  - `CLUSTERING_EPOCHS`: 20
  - `MODEL_HIDDEN_SIZE`: 64 (32 pour GPU < 4GB)

---

### backend-service
Service API REST FastAPI pour exposer les données Linky et NILM avec streaming SSE.

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
  - API REST pour accès aux données TimescaleDB
  - Streaming SSE (Server-Sent Events) pour mise à jour temps réel
  - CORS configuré pour le frontend React
  - Endpoints de santé et monitoring
  - Agrégation intelligente des données (time_bucket)
  - Documentation automatique OpenAPI/Swagger

- **Endpoints REST**:
  - `GET /`: Informations sur l'API et liste des endpoints
  - `GET /health`: Healthcheck du service
  - `GET /api/consumption/latest`: Dernière mesure de consommation
  - `GET /api/consumption/history`: Historique agrégé (paramètres: hours, interval)
  - `GET /api/appliances`: Liste de tous les appareils connus
  - `GET /api/detections`: Détections NILM sur une période (paramètre: hours)

- **Endpoints Streaming SSE**:
  - `GET /api/stream/consumption/latest?update_interval=5`: Stream temps réel de la consommation
  - `GET /api/stream/detections?hours=24&update_interval=10`: Stream des détections NILM
  - `GET /api/stream/appliances?update_interval=30`: Stream de la liste des appareils

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
Broker Redis pour Celery (partagé entre sync-service et nilm-service).

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
  nilm-worker          # Worker Celery NILM avec GPU
  nilm-beat            # Planificateur Celery pour NILM
  init-nilm-db         # Initialisation tables NILM (oneshot)
  backend              # API REST FastAPI (port 8000)
  frontend             # Interface React (port 3000)
```

### Dépendances entre services

- `sync-worker` et `sync-beat` dépendent de `timescaledb` et `redis` (healthcheck)
- `nilm-worker` et `nilm-beat` dépendent de `timescaledb`, `redis` et `sync-worker`
- `init-db` s'exécute une fois au démarrage (restart: no)
- `init-nilm-db` s'exécute après `init-db` (restart: no)
- `backend` dépend de `timescaledb` et `sync-worker`
- `frontend` dépend de `backend` (healthcheck)
- `flower` et `pgadmin` dépendent de leurs services respectifs

### Volumes persistants

```yaml
volumes:
  timescaledb_data    # Données PostgreSQL/TimescaleDB
  redis_data          # Données Redis (AOF)
  pgadmin_data        # Configuration pgAdmin
  nilm_uv_cache       # Cache uv pour builds NILM rapides
```

### Réseau

- Un seul réseau bridge: `nilmia-network`
- Tous les services communiquent via ce réseau interne
- Ports exposés: 3000, 5432, 5555, 6379, 8000, 8080

### Configuration GPU

Le service `nilm-worker` utilise le GPU via la configuration:
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
├── nilm-service/                 # Service NILM (ML)
│   ├── Dockerfile                # Python 3.12 + CUDA 12.1 + uv
│   ├── pyproject.toml            # Dépendances Python (PyTorch, PyPOTS)
│   └── src/
│       ├── __init__.py
│       ├── config.py             # Configuration NILM
│       ├── database.py           # Gestion tables NILM
│       ├── nilm.py               # Modèles ML (CRLI, SAITS)
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

**Erreur CUDA Out of Memory (NILM)**
```bash
# Réduire les paramètres dans .env
BATCH_SIZE=1
MAX_SAMPLES_TRAINING=500
MODEL_HIDDEN_SIZE=32

# Redémarrer le service NILM
docker-compose restart nilm-worker nilm-beat
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

**Modèle NILM ne détecte rien**
```bash
# Vérifier qu'il y a assez de données (48h minimum)
make stats

# Vérifier les modèles
make nilm-models

# Ré-entraîner manuellement
make nilm-train
```

### Logs utiles

```bash
# Tous les logs
make logs

# Logs d'un service spécifique
docker logs nilmia-sync-worker -f
docker logs nilmia-nilm-worker -f

# Logs Celery
docker exec nilmia-sync-worker celery -A src.tasks.celery_app inspect active
docker exec nilmia-nilm-worker celery -A src.tasks.celery_app inspect active

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

