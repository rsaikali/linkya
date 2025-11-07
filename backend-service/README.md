# Backend Service - API REST FastAPI

Service API REST pour exposer les données Linky et NILM de la plateforme Linkya.

## Technologies

- **FastAPI**: Framework web moderne et performant
- **Uvicorn**: Serveur ASGI pour FastAPI
- **SQLAlchemy**: ORM pour accès à TimescaleDB
- **Pydantic**: Validation et sérialisation des données

## Endpoints disponibles

### Santé et informations
- `GET /` - Informations sur l'API
- `GET /health` - Healthcheck du service

### Consommation Linky
- `GET /api/consumption/latest` - Dernière valeur de consommation
- `GET /api/consumption/history?hours=24&interval=5 minutes` - Historique agrégé

### NILM (détection d'appareils)
- `GET /api/appliances` - Liste de tous les appareils connus
- `GET /api/detections?hours=24` - Détections d'appareils sur une période

## Documentation

L'API expose automatiquement sa documentation au format OpenAPI/Swagger :
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Configuration

Les variables d'environnement sont chargées depuis le fichier `.env` à la racine du projet :

```bash
LOCAL_DB_HOST=timescaledb
LOCAL_DB_PORT=5432
LOCAL_DB_NAME=linkya_db
LOCAL_DB_USER=postgres
LOCAL_DB_PASSWORD=postgres
```

## Développement

Pour tester l'API en local :

```bash
# Démarrer le service
docker-compose up backend

# Tester les endpoints
make backend
make api-latest
make api-history HOURS=24
make api-detections
```

## CORS

Le backend est configuré pour accepter les requêtes du frontend React :
- http://localhost:3000
- http://frontend:3000

## Structure

```
backend-service/
├── Dockerfile          # Image Docker Python 3.13 + uv
├── pyproject.toml      # Dépendances Python
└── src/
    ├── __init__.py
    ├── config.py       # Configuration Pydantic
    ├── database.py     # Gestionnaire TimescaleDB
    └── main.py         # Application FastAPI
```
