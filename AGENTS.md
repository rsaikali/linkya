Différents services seront créés au fur et à mesure du développement de l'application.

Nous utiliserons:
- docker compose pour manager l'application finale.
- Python avec 'uv'.

Keep it simple, pas d'over engineering, mais reste complet dans tes actions.
Ne crée pas de scripts inutiles, efface les une fois que tu les a utilisés et qu'ils sont inutiles.
Chaque service aura son propre Dockerfile et sera documenté dans ce fichier.
Mets à jour périodiquement cette documentation au fur et à mesure de l'évolution du projet.
Pas de fichiers markdown de rapport inutiles.

## Configuration
Un fichier `.env` global à la racine du projet contient toutes les variables d'environnement pour tous les services.
Le fichier `.env.example` fournit un template avec des valeurs par défaut.
Tous les services Docker Compose utilisent ce fichier `.env` unique via `env_file: - .env`.
## Services
- sync-service: Service de synchronisation des données Linky depuis MySQL vers TimescaleDB.
    - Langage: Python 3.13 (3.12 pour nilm-service avec CUDA)
    - Dépendances: uv, celery, flower, pymysql, psycopg, sqlalchemy, pydantic
    - Fonctionnalités:
        - Synchronisation complète au démarrage (48h de données)
        - Synchronisation incrémentale toutes les 1 secondes
        - Utilisation de Celery pour la gestion des tâches
        - Monitoring avec Flower
    - Configuration via fichier .env global à la racine
- nilm-service: Service d'analyse NILM (Non-Intrusive Load Monitoring) pour détecter les appareils électriques.
    - Langage: Python 3.12 avec support GPU CUDA (Ubuntu 24.04)
    - Dépendances: uv, celery, psycopg, sqlalchemy, pydantic, pypots, torch, numpy, pandas, scikit-learn
    - Fonctionnalités:
        - Détection automatique des signatures d'appareils électriques complexes
        - Utilisation de PyPOTS pour l'analyse de séries temporelles (clustering CRLI, imputation SAITS)
        - Training périodique automatique (toutes les 24h par défaut)
        - Détection en temps réel toutes les 5 minutes
        - Support CUDA/GPU pour accélération des calculs ML
        - API Celery pour ajout manuel de signatures par l'utilisateur
        - Validation et correction des détections
        - Stockage des modèles versionnés et métriques de performance
    - Architecture ML:
        - Clustering CRLI pour identifier les patterns de consommation
        - Imputation SAITS pour gérer les données manquantes
        - Features extraction: puissance, variations, cycles, stabilité
        - Détection d'événements par analyse des transitions entre clusters
    - Tables TimescaleDB:
        - appliances: Appareils détectés avec signatures
        - appliance_signatures: Données d'entraînement (manuelles ou auto)
        - detection_events: Événements de détection avec timestamps et scores
        - model_versions: Versionnement des modèles ML
    - Configuration via fichier .env global à la racine
    - Commandes Makefile: nilm-train, nilm-detect, nilm-stats, nilm-models
    - **Cache de build optimisé**:
        - BuildKit cache avec persistence locale (.buildcache/)
        - Mounted cache UV pour réutilisation des packages
        - Volume Docker persistant (nilm_uv_cache)
        - Réduit les temps de rebuild de 90% (5-10min → 30-60s)
- timescaledb: Base de données TimescaleDB pour stocker les données Linky et NILM.
    - Image Docker officielle TimescaleDB
    - Conservation de toutes les données (pas de rétention limitée)
    - Tables sync: linky_realtime
    - Tables NILM: appliances, appliance_signatures, detection_events, model_versions
- redis: Broker Redis pour Celery (sync + nilm).
    - Image Docker officielle Redis
    - Configuration de la persistance des données
    - Partagé entre sync-service et nilm-service
- flower: Interface web de monitoring pour Celery.
    - Image Docker officielle Flower
    - Connectée au broker Redis
    - Monitoring des workers sync et nilm
- pgadmin: Interface web d'administration pour TimescaleDB.
    - Image Docker officielle pgAdmin4
    - Interface graphique complète pour gestion de la base
    - Accès via port 8080

## Orchestration
Tous les services seront orchestrés via un fichier docker-compose.yml à la racine du projet.
Chaque service sera défini avec ses dépendances, volumes, et réseaux nécessaires.
## Documentation
Chaque service aura une section dédiée dans la documentation du projet, expliquant son rôle, sa configuration, et comment l'utiliser.
## Développement futur
- API REST pour exposer les données Linky et NILM
- Dashboard Grafana pour la visualisation des consommations et détections
- Interface web pour gérer les appareils détectés (validation, correction, ajout manuel de signatures)
- Service d'alerting pour surveiller les pics de consommation et les anomalies
- Amélioration du modèle NILM avec feedback utilisateur (apprentissage continu)
- Export des données de consommation par appareil
## Bonnes pratiques
- Utilisation de variables d'environnement pour la configuration sensible.
- Documentation claire et concise pour chaque service.
- Tests unitaires pour les composants critiques du service de synchronisation.
- Surveillance et logging pour faciliter le debugging et la maintenance.

