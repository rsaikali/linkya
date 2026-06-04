# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Ce que fait Linkya

Plateforme NILM (Non-Intrusive Load Monitoring) : détecte des appareils sans prise connectée (ballon d'eau chaude, sèche-linge, four…) à partir de la courbe agrégée du compteur Linky, et les publie dans Home Assistant comme capteurs natifs.

**Histoire** : linkystat (courbe globale) → HA + prises connectées (détail partiel) → Linkya comble les trous via NILM sur signatures manuelles → résultats injectés dans HA.

**Source** : `sensor.linky_sinsts` depuis HA (MQTT statestream + History API backfill).
**Sortie** : `binary_sensor.nilm_*` (ON/OFF) + `sensor.nilm_*_energy` (kWh) via MQTT discovery.

## Architecture — 5 services

Pas de broker, pas de TimescaleDB, pas de nginx. Le backend FastAPI sert le build React et un flux SSE unique pour le live.

```
HA (sensor.linky_sinsts)
  ├── MQTT statestream ─┐
  └── History API ──────┴─→ ha-ingest ─→ PostgreSQL (linky_realtime)
PostgreSQL ─→ nilm (Seq2Point GRU) ─→ nilm_detections
nilm_detections ─→ ha-publish ─→ HA MQTT discovery
Browser ─→ backend (REST + SSE + React) ─→ PostgreSQL ─(HTTP)→ nilm
```

| Service | Stack | Rôle |
|---|---|---|
| `postgres` | PostgreSQL 16 | `linky_realtime` + tables NILM |
| `backend` | FastAPI | REST API, bus SSE, sert le SPA React, proxy vers nilm |
| `nilm` | FastAPI + TensorFlow CPU + APScheduler | train / detect / signatures + cron détection |
| `ha-ingest` | asyncio + aiomqtt + httpx | statestream MQTT + backfill History API |
| `ha-publish` | asyncio + aiomqtt | détections → MQTT discovery HA + statistics |

## Communication inter-services

- **backend → nilm** : HTTP (`NILM_URL`). `POST /train`, `/detect`, `/signatures`, `/models/delete`.
- **nilm → backend** : HTTP callback (`BACKEND_URL` → `POST /internal/event`) pour le live training/detection.
- **Live UI** : un seul `GET /api/events` (SSE). Pas de WebSocket. Bus en mémoire dans `backend/src/events.py`.

## Jobs NILM (plus de Celery)

`nilm-service/src/jobs.py` : `run_training`, `run_detection`, `add_signature`, `delete_models`. Appelés via FastAPI `BackgroundTasks` ou le cron APScheduler (`nilm-service/src/main.py`). Verrou `threading.Lock` — TF non concurrent.

- **Training** : manuel (bouton/API) ou auto après ajout de signature (paliers 2, 7, 12… positives).
- **Détection** : cron toutes les `NILM_DETECTION_INTERVAL_MINUTES` (fenêtre 2h) + `/detect` full history.

## Schéma DB (PostgreSQL pur)

| Table | Colonnes clés | Créée par |
|---|---|---|
| `linky_realtime` | `time`, `papp` | `ha-ingest` `init_db()` |
| `nilm_appliances` | `id`, `name`, `ha_publish`, `ha_entity_id` | `nilm` `init_tables()` |
| `nilm_signatures` | `appliance_id`, `start_time`, `end_time`, `power_data`, `is_negative` | idem |
| `nilm_detections` | `appliance_id`, `start_time`, `end_time`, `avg_power`, `confidence_score` | idem |
| `nilm_models` | `model_name`, `metrics`, `model_path` | idem |

Bucketing temporel : `to_timestamp(floor(epoch/secs)*secs)` (pas de `time_bucket` TimescaleDB). **Pas de migrations** — `make clean && make up`.

## Compose

- `docker-compose.yml` = **prod**. `docker-compose.override.yml` = **dev** (auto-chargé localement : ports localhost, mounts src, hot reload, backend `target: dev` sans build React).
- Prod (Pi/CD) : `make deploy` = `docker compose -f docker-compose.yml …` (ignore l'override).
- Backend prod : multistage (node build React → python), `STATIC_DIR=/app/static`.

## Commands

```bash
make up / down / clean / status / logs   # dev
make deploy                              # prod (Pi)
make train                               # POST /api/nilm/train
make detect                              # POST /api/nilm/detect
make lint                                # flake8 + isort
```

## Config (`.env`, source de vérité `.env.example`)

`HA_URL`, `HA_TOKEN`, `HA_ENTITY_PAPP`, `HA_BACKFILL_DAYS`, `HA_MQTT_*`, `LOCAL_DB_*`, `NILM_URL`, `BACKEND_URL`, `BACKEND_BIND` (IP LAN du bind prod, jamais 0.0.0.0), `NILM_*`.

## Règles de code

- Python : anglais. UI React : français.
- Logs : `loguru` (ha-ingest, ha-publish) ; stdlib `logging` (backend, nilm).
- Pas d'emojis. flake8 + isort.

## NILM Engine

`nilm-service/src/` — Seq2Point TF/Keras :
- `seq2point_nilm.py` — manager : `train_all_appliances`, `disaggregate` (PATH A change-point + PATH B Seq2Point sliding window).
- `nilm/detectors/change_point_detector.py` — matching énergie/durée/forme.
- `nilm/models/multioutput_model.py` — modèle Keras multi-output.

TensorFlow vient de pyproject (`tensorflow-cpu` x86 / `tensorflow` arm64).
