# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What Linkya does

NILM (Non-Intrusive Load Monitoring) platform: detects appliances without a smart plug (water heater, dryer, oven…) from the aggregate Linky smart meter curve, and publishes them into Home Assistant as native sensors.

**History**: linkystat (global curve) → HA + smart plugs (partial detail) → Linkya fills the gaps via NILM on manual signatures → results injected into HA.

**Source**: `sensor.linky_sinsts` from HA (MQTT statestream + History API backfill).
**Output**: `binary_sensor.nilm_*` (ON/OFF) + `sensor.nilm_*_confidence` (%) via MQTT discovery, energy via HA **external statistics** (`linkya:<slug>_energy`).

## Architecture — 5 services

No broker, no TimescaleDB, no nginx. The FastAPI backend serves the React build and a single SSE stream for live updates.

```
HA (sensor.linky_sinsts)
  ├── MQTT statestream ─┐
  └── History API ──────┴─→ ha-ingest ─→ PostgreSQL (linky_realtime)
PostgreSQL ─→ nilm (Seq2Point GRU) ─→ nilm_detections
nilm_detections ─→ ha-publish ─→ HA MQTT discovery (binary + confidence + stats)
nilm_detections ─→ backend ─→ HA WebSocket recorder/import_statistics (energy)
Browser ─→ backend (REST + SSE + React) ─→ PostgreSQL ─(HTTP)→ nilm
```

| Service | Stack | Role |
|---|---|---|
| `postgres` | PostgreSQL 16 | `linky_realtime` + NILM tables |
| `backend` | FastAPI | REST API, SSE bus, serves the React SPA, proxies to nilm |
| `nilm` | FastAPI + TensorFlow CPU + APScheduler | train / detect / signatures + detection cron |
| `ha-ingest` | asyncio + aiomqtt + httpx | MQTT statestream + History API backfill |
| `ha-publish` | asyncio + aiomqtt | detections → HA MQTT discovery (binary/confidence/diagnostics) |

## Inter-service communication

- **backend → nilm**: HTTP (`NILM_URL`). `POST /train`, `/detect`, `/signatures`, `/models/delete`.
- **nilm → backend**: HTTP callback (`BACKEND_URL` → `POST /internal/event`) for live training/detection.
- **Live UI**: a single `GET /api/events` (SSE). No WebSocket. In-memory bus in `backend/src/events.py`.

## NILM jobs (no more Celery)

`nilm-service/src/jobs.py`: `run_training`, `run_detection`, `add_signature`, `delete_models`. `threading.Lock` — TF is not concurrency-safe.

- **Training**: manual (button/API) or auto after adding a signature (thresholds at 2, 7, 12… positives).
- **Detection**: APScheduler cron every `NILM_DETECTION_INTERVAL_MINUTES` (2h window) + `/detect` for full history.
- **Coalescing** (`request_training` / `request_detection`): **at most 1 pending train + 1 pending detect**. Bursts (CSV import crossing several thresholds, repeated clicks) are merged instead of piling up on the Pi. `/train` `/detect` return `already_pending` if already queued.
- **CSV import**: `add_signature(auto_train=False)` per row → a **single** training run triggered at the end (not one per threshold).

## DB schema (plain PostgreSQL)

| Table | Key columns | Created by |
|---|---|---|
| `linky_realtime` | `time`, `papp` | `ha-ingest` `init_db()` |
| `nilm_appliances` | `id`, `name`, `ha_publish`, `ha_entity_id` | `nilm` `init_tables()` |
| `nilm_signatures` | `appliance_id`, `start_time`, `end_time`, `power_data`, `is_negative` | same |
| `nilm_detections` | `appliance_id`, `start_time`, `end_time`, `avg_power`, `confidence_score` | same |
| `nilm_models` | `model_name`, `metrics`, `model_path`, `is_champion` | same |
| `nilm_meta` | `key`, `value` (heartbeats, markers) | same |

Time bucketing: `to_timestamp(floor(epoch/secs)*secs)` (no TimescaleDB `time_bucket`). No Alembic — lightweight migrations = idempotent `ALTER TABLE … IF (NOT) EXISTS` in `init_tables()`, otherwise `make clean && make up`.

## HA publication

Two channels, one per kind of data:

**MQTT discovery (`ha-publish`)** — per appliance with `ha_publish=True`:
- **`binary_sensor.nilm_<slug>`** — live ON/OFF (cycle in progress). Live only.
- **`sensor.nilm_<slug>_confidence`** — confidence (%) of the last detection.
- **Diagnostic sensors** (device `Linkya NILM`, diagnostic category): model version, type, trained-at, duration, signatures, appliances, epochs, train_loss, val_loss, total detections, last detection. One shared JSON topic + `value_template`. **No F1** — Linkya has no ground truth.

**External statistics (`backend/src/ha_backfill.py`)** — energy in kWh:
- `statistic_id = linkya:<slug>_energy` via WebSocket `recorder/clear_statistics` + `recorder/import_statistics` (like Tibber/EDF). **No entity, no state, no MQTT** — the Energy Dashboard only reads the hourly statistics.
- Triggered after **every** `detection_complete` that found detections (cron or full): NILM always detects late, so each run rewrites history. Hourly buckets with proportional split for cycles straddling an hour boundary (23:54→00:13) + carry-forward.
- Rewriting the past is natively supported → no more HWM clamp, no more `total_increasing`, no more direct SQLite injection.

## Compose

- `docker-compose.yml` = **prod**. `docker-compose.override.yml` = **dev** (auto-loaded locally: localhost ports, src mounts, hot reload, backend `target: dev` without the React build).
- Prod (Pi/CD): `make deploy` = `docker compose -f docker-compose.yml …` (ignores the override).
- Backend prod: multistage (node builds React → python), `STATIC_DIR=/app/static`.

## Commands

```bash
make up / down / clean / status / logs   # dev
make deploy                              # prod (Pi)
make train                                # POST /api/nilm/train
make detect                               # POST /api/nilm/detect
make test                                 # backend-service + nilm-service test suites
make lint                                 # flake8 + isort
```

## Config (`.env`, source of truth `.env.example`)

`HA_URL`, `HA_TOKEN`, `HA_ENTITY_PAPP`, `HA_BACKFILL_DAYS`, `HA_MQTT_*`, `LOCAL_DB_*`, `NILM_URL`, `BACKEND_URL`, `BACKEND_BIND` (prod LAN bind IP, never 0.0.0.0), `NILM_*`.

## NILM engine

`nilm-service/src/` — Seq2Point TF/Keras:
- `seq2point_nilm.py` — manager: `train_all_appliances`, `disaggregate` (PATH A change-point + PATH B Seq2Point sliding window).
- `nilm/detectors/change_point_detector.py` — energy/duration/shape matching.
- `nilm/models/multioutput_model.py` — multi-output Keras model.

TensorFlow comes from pyproject (`tensorflow-cpu` on x86_64, `tensorflow` on aarch64/arm64).
