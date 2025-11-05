# Nilmia - Plateforme d'analyse de consommation électrique

Plateforme complète pour la synchronisation et l'analyse intelligente des données de consommation électrique Linky, avec détection automatique d'appareils (NILM).

## 🏗️ Architecture

### Services principaux

- **frontend** : Interface web React avec Material-UI (dev server avec hot reload)
- **sync-service** : Synchronisation des données Linky (MySQL → TimescaleDB)
- **nilm-service** : Détection automatique d'appareils électriques par IA (NILM Seq2Point)
- **backend** : API REST FastAPI avec streaming SSE et WebSocket
- **TimescaleDB** : Base de données locale optimisée pour les séries temporelles
- **Redis** : Broker de messages pour Celery
- **Celery** : Gestionnaire de tâches asynchrones (sync + NILM)

### Technologies

- **React 18** avec Material-UI, Chart.js et hot reload
- **Python 3.13** avec `uv` pour la gestion des dépendances
- **TensorFlow/Keras** pour les réseaux de neurones (GRU/LSTM + Attention)
- **FastAPI** pour l'API REST avec streaming SSE et WebSocket
- **Docker Compose** pour l'orchestration

## 📊 Données synchronisées

La table `linky_realtime` contient les données de consommation Linky :

| Colonne | Type | Description |
|---------|------|-------------|
| `time` | datetime | Timestamp de la mesure (clé primaire) |
| `PAPP` | smallint | Puissance apparente (VA) |
| `HCHP` | int | Index heures pleines (Wh) |
| `HCHC` | int | Index heures creuses (Wh) |
| `temperature` | double | Température (°C) |
| `libelle_tarif` | varchar(16) | Libellé du tarif en cours |

- **~48h de données** (~98 000 lignes)
- **Mise à jour toutes les 2 secondes** depuis le compteur Linky

## ✨ Fonctionnalités

### Synchronisation Linky (sync-service)
- ✅ Synchronisation complète au démarrage (48h de données)
- ✅ Synchronisation incrémentale automatique (toutes les 5 secondes)
- ✅ Stockage optimisé dans TimescaleDB
- ✅ Monitoring avec Flower

### Détection d'appareils NILM (nilm-service)
- 🧠 Détection automatique d'appareils électriques par Seq2Point NILM
- 🔄 Training périodique automatique (toutes les 24h)
- 📊 Analyse en temps réel (toutes les 5 minutes)
- 🎯 Architecture Multi-Output : un seul modèle pour tous les appareils
- 🎯 Signatures complexes (cycles, variations, pics de consommation)
- 🚀 Accélération GPU optionnelle (fallback CPU)
- ✏️ Ajout manuel de signatures d'appareils via interface web
- 📈 Statistiques de consommation par appareil

### Interface utilisateur (frontend)
- 📱 Dashboard temps réel de consommation électrique
- 🎯 **Sélection de plages horaires sur le graphique** pour créer des signatures d'appareils
- 🗂️ Autocomplete pour sélectionner ou créer des appareils
- ⏱️ Ajustement fin des plages horaires (au niveau des secondes)
- 💾 Création instantanée de signatures entraînement NILM
- 🤖 **Gestion de l'entraînement NILM** avec lancement manuel et historique paginé
- 📊 **Visualisation des métriques** d'entraînement (accuracy, loss, qualité)
- 🔄 Streaming SSE pour mise à jour en temps réel sans polling
- 🎨 Design responsive avec Material-UI
- 🔗 **Liens rapides dans le header** vers Swagger UI, ReDoc et pgweb

## �📋 Prérequis

- Docker & Docker Compose
- Accès à une base de données MySQL Linky distante (lecture seule)
- **Optionnel** : GPU NVIDIA avec CUDA pour accélération NILM

## 🚀 Démarrage rapide

### 1. Configuration

Créer et configurer les fichiers `.env` :

**Fichier .env unique à la racine** (créer depuis .env.example) :
```env
# Base MySQL Linky
REMOTE_DB_HOST=192.168.1.200
REMOTE_DB_PORT=3306
REMOTE_DB_NAME=linky
REMOTE_DB_USER=linky
REMOTE_DB_PASSWORD=***
REMOTE_DB_TABLE=linky_realtime

# Base TimescaleDB locale
LOCAL_DB_HOST=timescaledb
LOCAL_DB_PORT=5432
LOCAL_DB_NAME=linkya_db
LOCAL_DB_USER=postgres
LOCAL_DB_PASSWORD=postgres

# Redis/Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Configuration sync
SYNC_INTERVAL_SECONDS=5
SYNC_RETENTION_HOURS=48

# Configuration NILM
NILM_TRAINING_INTERVAL_HOURS=24
NILM_DETECTION_INTERVAL_MINUTES=5
NILM_WINDOW_SIZE_MINUTES=60
NILM_MIN_POWER_THRESHOLD=30
NILM_MIN_DURATION_SECONDS=30
```

### 2. Lancement avec Makefile

```bash
# Démarrage complet (vérifie la configuration, build, lance les services)
make start

# Vérifier l'état des services
make check

# Consulter les logs
make logs
```

Services démarrés :
- TimescaleDB (port 5432)
- Redis (port 6379)
- Sync Worker + Beat
- CNN Worker + Beat (avec GPU optionnel)
- Backend API (port 8000)
- Frontend React Dev Server (port 3000)

**Accès à l'application** : http://localhost:3000

### 3. Utilisation du NILM

```bash
# Lancer le premier entraînement (nécessite 48h de données)
make train

# Consulter les détections
make nilm-stats

# Lancer une détection manuelle
make nilm-detect

# Voir les modèles ML
make nilm-models
```

## 📊 Interfaces de monitoring

| Interface | URL | Description |
|-----------|-----|-------------|
| **Application** | http://localhost | Interface React principale |
| **Swagger UI** | http://localhost/docs | Documentation interactive de l'API |
| **ReDoc** | http://localhost/redoc | Documentation API alternative |
| **Flower** | http://localhost:5555 | Monitoring Celery (sync + NILM) |
| **pgAdmin** | http://localhost:8080 | Administration TimescaleDB |

### Swagger UI
- Documentation interactive de toutes les routes API
- Test direct des endpoints depuis l'interface
- Schémas de données détaillés
- Organisation par tags (System, Consumption, Appliances, Signatures, Detections, NILM)

### Flower
- Tâches en cours et historique
- Statistiques des workers (sync + NILM)
- État GPU pour le worker NILM
- Résultats des détections

### pgAdmin
Login: `admin@example.com` / Password: `admin`
- Consultation des tables Linky et NILM
- Requêtes SQL personnalisées
- Visualisation des détections d'appareils

## 🔄 Tâches Celery

### Tâches Sync Service

| Tâche | Description | Déclenchement |
|-------|-------------|---------------|
| `init_database` | Initialise la base locale avec TimescaleDB | Au démarrage (automatique) |
| `full_sync` | Synchronisation complète des 48h | Manuel ou au démarrage |
| `incremental_sync` | Synchronisation incrémentale | Automatique (toutes les 5s) |
| `get_stats` | Statistiques de la base locale | Automatique (toutes les 60s) |

### Tâches NILM Service

| Tâche | Description | Déclenchement |
|-------|-------------|---------------|
| `init_nilm_database` | Initialise les tables NILM | Au démarrage (automatique) |
| `train_nilm_model` | Entraînement du modèle ML | Automatique (toutes les 24h) |
| `detect_appliances_task` | Détection d'appareils | Automatique (toutes les 5 min) |
| `add_manual_signature` | Ajout signature manuelle | Manuel |
| `validate_detection` | Validation/correction détection | Manuel |
| `get_detection_stats` | Statistiques NILM | Manuel |

### Commandes Makefile

```bash
# Sync
make stats          # Statistiques de synchronisation

# NILM
make nilm-train     # Entraîner le modèle
make nilm-detect    # Lancer une détection
make nilm-stats     # Statistiques détections
make nilm-models    # Liste des modèles ML
```

## 🗄️ TimescaleDB - Fonctionnalités

### Hypertables
La table `linky_realtime` est automatiquement convertie en hypertable TimescaleDB, optimisée pour :
- Insertion rapide de données temporelles
- Requêtes efficaces sur des plages de temps
- Partitionnement automatique par chunks de 6 heures

### Politique de rétention
Les données plus anciennes que 48h sont automatiquement supprimées (configurable via `SYNC_RETENTION_HOURS`).

## 🧠 NILM - Détection d'appareils

### Principe de fonctionnement

Le service NILM utilise l'architecture FiLM (Feature-wise Linear Modulation) pour identifier les appareils électriques :

1. **Extraction de features** : Analyse de la puissance, variations, cycles, pics
2. **Architecture FiLM** : Modulation des features par appareil cible (un seul modèle pour tous)
3. **Détection d'événements** : Analyse des transitions et patterns
4. **Scoring** : Calcul de confiance pour chaque détection

### Signatures détectées

Le système peut identifier des signatures complexes :
- **Cycles réguliers** : Lave-linge, lave-vaisselle, sèche-linge
- **Consommation stable** : Réfrigérateur, congélateur, box internet
- **Pics de démarrage** : Four, bouilloire, micro-ondes
- **Variations graduelles** : Chauffage, climatisation

### Workflow d'utilisation

1. **Collecte de données** : Laisser tourner 48h minimum
2. **Premier training** : `make nilm-train`
3. **Observations** : Le système détecte automatiquement
4. **Enrichissement** : Ajouter des signatures manuelles pour les appareils non détectés
5. **Validation** : Corriger les fausses détections
6. **Amélioration continue** : Le modèle se réentraîne avec les nouvelles données

### Exemples de requêtes NILM

```sql
-- Appareils détectés
SELECT name, is_validated, avg_power, cluster_id
FROM appliances;

-- Dernières détections CNN
SELECT 
    ca.name,
    cd.start_time,
    cd.end_time,
    cd.avg_power,
    cd.energy_consumed,
    cd.confidence_score
FROM nilm_detections cd
JOIN nilm_appliances ca ON cd.appliance_id = ca.id
ORDER BY cd.start_time DESC
LIMIT 20;

-- Consommation par appareil sur 24h
SELECT 
    ca.name,
    COUNT(*) as activations,
    SUM(cd.energy_consumed) as total_wh,
    AVG(cd.avg_power) as avg_power
FROM nilm_detections cd
JOIN nilm_appliances ca ON cd.appliance_id = ca.id
WHERE cd.start_time >= NOW() - INTERVAL '24 hours'
GROUP BY ca.name
ORDER BY total_wh DESC;
```

Pour plus de détails, consultez [nilm-service/README.md](nilm-service/README.md).

### Requêtes optimisées - Exemples

```sql
-- Données des dernières 24h
SELECT * FROM linky_realtime 
WHERE time > NOW() - INTERVAL '24 hours'
ORDER BY time DESC;

-- Consommation moyenne par heure
SELECT 
    time_bucket('1 hour', time) AS hour,
    AVG(papp) as avg_power,
    MAX(papp) as max_power,
    MIN(papp) as min_power
FROM linky_realtime
WHERE time > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC;

-- Consommation par tarif (heures creuses/pleines)
SELECT 
    libelle_tarif,
    COUNT(*) as nb_mesures,
    AVG(papp) as avg_power,
    SUM((hchp - LAG(hchp) OVER (ORDER BY time))) as consommation_hp,
    SUM((hchc - LAG(hchc) OVER (ORDER BY time))) as consommation_hc
FROM linky_realtime
WHERE time > NOW() - INTERVAL '24 hours'
GROUP BY libelle_tarif;

-- Température moyenne par heure
SELECT 
    time_bucket('1 hour', time) AS hour,
    AVG(temperature) as avg_temp,
    MAX(temperature) as max_temp,
    MIN(temperature) as min_temp
FROM linky_realtime
WHERE time > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC;

-- Vue matérialisée pour agrégation continue (optionnel)
CREATE MATERIALIZED VIEW IF NOT EXISTS linky_hourly
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', time) AS hour,
    AVG(papp) as avg_power,
    MAX(papp) as max_power,
    MIN(papp) as min_power,
    AVG(temperature) as avg_temp,
    COUNT(*) as nb_mesures
FROM linky_realtime
GROUP BY hour;

-- Politique de rafraîchissement automatique
SELECT add_continuous_aggregate_policy('linky_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
```

## 🔧 Configuration avancée

### Variables d'environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `REMOTE_DB_HOST` | Hôte de la base distante | - |
| `REMOTE_DB_PORT` | Port de la base distante | 5432 |
| `REMOTE_DB_NAME` | Nom de la base distante | - |
| `REMOTE_DB_USER` | Utilisateur (lecture seule) | - |
| `REMOTE_DB_PASSWORD` | Mot de passe | - |
| `REMOTE_DB_TABLE` | Table source | sensor_data |
| `LOCAL_DB_HOST` | Hôte TimescaleDB | timescaledb |
| `LOCAL_DB_PORT` | Port TimescaleDB | 5432 |
| `LOCAL_DB_NAME` | Nom base locale | linkya_db |
| `LOCAL_DB_USER` | Utilisateur local | postgres |
| `LOCAL_DB_PASSWORD` | Mot de passe local | postgres |
| `SYNC_INTERVAL_SECONDS` | Intervalle de sync | 5 |
| `SYNC_RETENTION_HOURS` | Rétention des données | 48 |

### Scaling

Pour augmenter le nombre de workers :

```bash
docker-compose up -d --scale sync-worker=3
```

## 🛠️ Développement

### Installation locale avec uv

```bash
cd sync-service
uv venv
source .venv/bin/activate  # Linux/Mac
uv pip install -e .
```

### Tests

```bash
uv run pytest
```

## 📝 Logs

```bash
# Logs du worker
docker logs -f nilmia-sync-worker

# Logs du beat scheduler
docker logs -f nilmia-sync-beat

# Logs de TimescaleDB
docker logs -f nilmia-timescaledb
```

## 🐛 Dépannage

### La synchronisation ne démarre pas

1. Vérifiez que la base distante est accessible
2. Vérifiez les logs du worker
3. Vérifiez que Redis et TimescaleDB sont en bonne santé

```bash
docker-compose ps
```

### Flower n'est pas accessible

Vérifiez que le port 5555 n'est pas utilisé :

```bash
netstat -tulpn | grep 5555
```

### Erreur de connexion à la base distante

Testez la connexion depuis le container :

```bash
docker exec -it nilmia-sync-worker python -c "from src.database import db_manager; print(db_manager.get_data_stats())"
```

## 📦 Structure du projet

```
```
nilmia/
├── sync-service/                # Service de synchronisation Linky
│   ├── src/
│   │   ├── config.py           # Configuration (Pydantic)
│   │   ├── database.py         # Gestionnaire de BDD
│   │   └── tasks.py            # Tâches Celery
│   ├── Dockerfile
│   └── pyproject.toml          # Dépendances (uv)
├── nilm-service/                # Service NILM (détection IA)
│   ├── src/
│   │   ├── config.py           # Configuration NILM
│   │   ├── database.py         # Tables NILM (appareils, signatures, détections)
│   │   ├── seq2point_nilm.py   # Modèle Sequence-to-Point multi-appareils
│   │   └── tasks.py            # Tâches Celery NILM
│   ├── Dockerfile              # Image TensorFlow avec GPU optionnel
│   ├── pyproject.toml          # Dépendances ML
│   └── README.md               # Documentation NILM
├── backend-service/             # API REST FastAPI
│   ├── src/
│   │   ├── config.py           # Configuration API
│   │   ├── database.py         # Requêtes TimescaleDB
│   │   └── main.py             # Application FastAPI avec SSE
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend-service/            # Interface web React
│   ├── src/
│   │   ├── App.js              # Composant principal
│   │   ├── theme.js            # Thème Material-UI
│   │   ├── components/         # Composants React
│   │   └── services/           # API et SSE
│   ├── Dockerfile
│   └── package.json
├── models/                      # Modèles CNN persistés (volume)
├── pgadmin-config/              # Configuration pgAdmin
├── .env                         # Configuration unique (à créer depuis .env.example)
├── .env.example                 # Template de configuration
├── docker-compose.yml           # Orchestration complète
├── Makefile                     # Commandes rapides
└── AGENTS.md                    # Documentation architecture
## 📚 Documentation

- **[AGENTS.md](AGENTS.md)** : Architecture complète des services
- **[nilm-service/README.md](nilm-service/README.md)** : Documentation technique NILM
- **[.env.example](.env.example)** : Configuration complète avec toutes les variables

## 🤝 Contribution

Ce projet utilise :
- Python 3.13 (sync) et 3.12 (NILM) avec uv pour les dépendances
- TensorFlow/Keras pour les réseaux de neurones (Seq2Point)
- React 18 avec Material-UI pour l'interface web
- FastAPI pour l'API REST avec streaming SSE
- Docker Compose avec support GPU optionnel
- TimescaleDB pour l'optimisation temporelle
