# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Ce que fait Linkya

Plateforme NILM (Non-Intrusive Load Monitoring) pour détecter des appareils électriques sans prise connectée (ex. ballon d'eau chaude) à partir de la courbe agrégée du compteur Linky.

**Histoire** : linkystat (courbe globale) → Home Assistant avec prises connectées (détail partiel) → Linkya comble les trous via NILM sur signatures manuelles → résultats injectés dans HA comme capteurs natifs.

**Source** : `sensor.linky_sinsts` depuis HA (MQTT statestream + History API backfill).  
**Sortie** : capteurs `sensor.nilm_*` dans HA via MQTT discovery.

## Architecture — 10 services Docker

```
frontend (nginx :80)
  └── react-dev (:3000)   React 18 + MUI, UI en français
  └── backend (:8000)     FastAPI REST + WebSockets

backend
  ├── timescaledb (:5432) TimescaleDB — linky_realtime (time, papp) + tables NILM
  ├── redis (:6379)       Broker Celery + pubsub WebSocket
  ├── ha-ingest           HA History API backfill + MQTT statestream → linky_realtime
  ├── nilm-worker/beat    Celery : training Seq2Point + détection → nilm_detections
  └── ha-publish          nilm_detections → MQTT discovery HA → sensor.nilm_*

pgweb (:8081)             UI web TimescaleDB (debug)
```

**Flux** :
```
HA (sensor.linky_sinsts)
  → ha-ingest (MQTT statestream + backfill API)
    → TimescaleDB linky_realtime
      → nilm-worker (Seq2Point train/detect)
        → nilm_detections
          → ha-publish (MQTT discovery)
            → HA sensor.nilm_ballon_eau_chaude ...
```

**MQTT broker utilisé** : Mosquitto de HA (`homeassistant.local:1883`). Pas de broker propre à Linkya.

## Services — résumé

| Service | Stack | Rôle |
|---|---|---|
| `ha-ingest` | asyncio + aiomqtt + httpx | Backfill HA API + subscribe statestream MQTT |
| `nilm-worker` | Celery + TF/Keras | Training Seq2Point + détection |
| `nilm-beat` | Celery beat | Schedule train/detect périodiques |
| `backend` | FastAPI | API REST + WebSockets (Redis pubsub) |
| `ha-publish` | asyncio + aiomqtt | Poll détections → MQTT discovery HA |
| `react-dev` | React 18 + MUI | Dev server HMR |
| `frontend` | Nginx | Reverse proxy → react-dev + backend |

## Schéma DB

Tables dans TimescaleDB (`linkya_db`) :

| Table | Colonnes clés |
|---|---|
| `linky_realtime` | `time`, `papp` (VA) — hypertable 6h chunks |
| `nilm_appliances` | `id`, `name`, `ha_publish`, `ha_entity_id` |
| `nilm_signatures` | `appliance_id`, `start_time`, `end_time`, `power_data` |
| `nilm_detections` | `appliance_id`, `start_time`, `end_time`, `avg_power`, `confidence_score` |
| `nilm_models` | `model_name`, `metrics`, `model_path` |

Init schéma : `nilm-service/src/database.py` → `init_tables()` au démarrage.  
`linky_realtime` initialisé par `ha-ingest/src/database.py` → `init_db()`.  
**Pas de migrations** — schéma change = `make clean && make up`.

## HA Publish — protocole MQTT

Quand `ha_publish=True` sur un appareil :
```
# Discovery (retain=True) → HA crée l'entité automatiquement
homeassistant/sensor/nilm_{slug}/config  →  JSON discovery payload

# State toutes les 30s
linkya/nilm/nilm_{slug}/state  →  "2100" (W) ou "0" (OFF)
```
Désactivation : discovery payload vide `""` → HA supprime l'entité.

## Commands

```bash
make build        # Build toutes les images
make up           # Démarre tous les services
make down         # Stoppe tout
make clean        # down -v (supprime volumes + données)
make status       # État des containers
make logs         # Logs all services

make train        # POST /api/nilm/train
make detect       # POST /api/nilm/detect
```

## Config

`.env` (non versionné) depuis `.env.example`. Variables critiques :

| Variable | Rôle |
|---|---|
| `HA_URL` | URL Home Assistant |
| `HA_TOKEN` | Token long-lived HA |
| `HA_ENTITY_PAPP` | `sensor.linky_sinsts` |
| `HA_MQTT_HOST/PORT/USER/PASSWORD` | Broker Mosquitto HA |
| `HA_BACKFILL_DAYS` | Jours d'historique au démarrage |

GPU NILM : `runtime: nvidia` dans docker-compose.yml ; fallback CPU auto si CUDA absent.

## Règles de code

- Python (code, commentaires, logs, docstrings) : **anglais**
- React UI (labels, messages) : **français**
- Logs : `loguru` dans `ha-ingest` et `ha-publish` ; stdlib `logging` dans `nilm-service` et `backend-service` (legacy)
- Formatter : `black` + `isort` (`make code-quality-fix`)
- Pas d'emojis dans le code ni les logs

## Dépendances Python

| Service | Gestionnaire |
|---|---|
| `backend-service` | `pip install -r requirements.txt` |
| `nilm-service` | `uv pip install` (pyproject.toml) |
| `ha-ingest-service` | `uv pip install` (pyproject.toml) |
| `ha-publish-service` | `uv pip install` (pyproject.toml) |

Ne pas mélanger `uv` et `pip` dans un même service.

## NILM Engine

`nilm-service/src/` — moteur Seq2Point TF/Keras :

| Fichier | Contenu |
|---|---|
| `seq2point_nilm.py` | Manager : `train_all_appliances`, `disaggregate` |
| `tasks.py` | Celery tasks : train, detect, feedback loop |
| `database.py` | Tables NILM + lecture `linky_realtime` |
| `nilm/nilm/models/multioutput_model.py` | Modèle Keras Seq2Point multi-output |

TensorFlow vient de l'image Docker de base (pas dans pyproject.toml).
