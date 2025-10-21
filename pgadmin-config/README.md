# Configuration pgAdmin

Ce répertoire contient la configuration automatique de pgAdmin pour TimescaleDB.

## Fichiers

- **`pgadmin-servers.json`** : Configuration des serveurs (automatiquement chargée)
- **`pgpass`** : Fichier de mots de passe pour l'authentification automatique
- **`init-pgadmin.sh`** : Script d'initialisation qui configure pgAdmin au démarrage
- **`pgadmin-setup.sh`** : Guide manuel (fallback)

## Configuration automatique

Au démarrage du container pgAdmin :

1. **Attente de TimescaleDB** : Le script attend que TimescaleDB soit prêt
2. **Configuration des mots de passe** : Copie le fichier `pgpass` avec les bonnes permissions
3. **Chargement des serveurs** : pgAdmin charge automatiquement la configuration depuis `pgadmin-servers.json`

## Résultat

Une fois pgAdmin démarré, le serveur **"TimescaleDB Local"** sera automatiquement disponible et connecté :

- Host : `timescaledb`
- Port : `5432`
- Database : `local_data`
- User : `postgres`

Pas besoin de configuration manuelle ! 🎉

## Accès

- **URL** : http://localhost:8080
- **Email** : admin@example.com
- **Password** : admin