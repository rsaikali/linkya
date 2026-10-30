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

**Toolchain note**: flake8 + isort + black — not ruff (the default elsewhere in the workspace). Kept as-is deliberately, not retrofitted. `black --check` is enforced in CI (2026-07-25); run `black backend-service/src nilm-service/src ha-ingest-service/src ha-publish-service/src` locally before committing if you touch these dirs.

## Config (`.env`, source of truth `.env.example`)

`HA_URL`, `HA_TOKEN`, `HA_ENTITY_PAPP`, `HA_BACKFILL_DAYS`, `HA_MQTT_*`, `LOCAL_DB_*`, `NILM_URL`, `BACKEND_URL`, `BACKEND_BIND` (prod LAN bind IP, never 0.0.0.0), `NILM_*`.

## NILM engine

`nilm-service/src/` — Seq2Point TF/Keras:
- `seq2point_nilm.py` — manager: `train_all_appliances`, `disaggregate` (PATH A change-point + PATH B Seq2Point sliding window).
- `nilm/detectors/change_point_detector.py` — energy/duration/shape matching.
- `nilm/models/multioutput_model.py` — multi-output Keras model.

**Concurrent loads (PATH A, since 2026-10-22)** — radiators / dishwasher switching during a water-heater cycle used to close or evict its cycle:
- `extract_patterns` pairs each up edge with the down edge of the **same height (±10 %)**, not the next down. A down smaller than an open up is a partial drop (another load went off first); one down equal to the sum of several open ups closes them all. A taller down with nothing matching falls back to the oldest up (legacy behaviour).
- Each pattern has the **other loads' steps subtracted** over the overlap before matching. Known limit: a multi-step appliance whose edges stop together is now split per edge (only the water heater exists today).
- `fill_gaps` forward-fills the event-driven `linky_realtime` onto a regular grid (gaps ≤ 2 h; HA only emits changes, a stable house leaves holes of an hour+). `disaggregate` also carries the last known level in at `start_time`.
- Negative signatures are filtered **before** dedup (a rejected load nested in a real cycle must not evict it).
- Known limits: cycles shorter than the shortest signature (~600 s) are not matched (ratio filter 0.5-1.5); loads with steps within ±10 % of the heater (≈3.1 kW) can still be confused. Replay A/B on real data: 10-18/19/20 identical, 10-22 long cycle recovered, radiators no longer detected as the heater (10-21).

**Matched-filter engine (2026-10-29, `NILM_ENGINE=matched`, default)** — `nilm/detectors/matched_filter.py` + `matched_engine.py`. Generic, no wattage / clock / tariff / house constant:
- Per appliance, a **profile is learned from its own signatures**: robust median / MAD of the up- and down-edge heights (multi-scale step series on a 10 s grid), duration range, plateau power, one profile per power **mode** (clusters of edge height; oven, dishwasher programs). Negative signatures become look-alike edge heights. Cached in `nilm_meta` (`matched_profiles`), rebuilt when signatures change or after 7 days (`VERSION` bump invalidates).
- A cycle = an up edge and a down edge within the learned band (4 sigma, up to 6.5 sigma on one edge when the other is within 2 sigma), duration in range, flat enough in between. An edge carrying another load (**composite**) is accepted only if its excess is balanced by an opposite edge of the same size within 10 min. Two appliances may overlap in time, not share an edge. Energy = learned plateau power x duration (another load switching mid-cycle cannot bias it). A cycle still running at the end of fresh data is emitted `provisional` (live HA sensor), rewritten by the next cron run.
- **Self-training**: after learning, the profile is refit on the signatures plus the clean cycles the detector itself finds (no new label, no DB write). **Gating**: an appliance gets a profile only with >= 15 positive signatures, repeatable edges (sigma/mu <= 8 %, modes explaining >= 60 % of the signatures) and a replay where >= 30 % of the detections fall on its own signatures; otherwise it stays on the legacy matcher. Known limit: look-alikes that appear after the learning period (a new radiator at the same wattage) are only fixed by negative signatures.
- Measured on the house curve (Sep-Oct 2026, learned from the 35 existing signatures only): 99 % of 102 certain 14:24 / 23:54 cycles found, 0 false positive on 69 oven / dishwasher / washing-machine episodes (smart-plug ground truth; legacy: 7), the 7 invalidated radiator detections gone, ~13 cycles the legacy matcher missed found. Generalisation test (same code, signatures from the first 60 % of the timeline): water heater 97 % recall; oven, dishwasher, washing machine have too few signatures (11-12 < 15) and stay legacy. Lab, scripts and the TCN prototype: `nilm-lab/`.
- **Not covered**: appliances without repeatable plateaus (washing machine: heating / spin / drying phases) need a waveform model; prototype in `nilm-lab/` (dilated gated TCN on semi-synthetic mixtures built from real templates). Not wired.
- **One engine per appliance, decided at each run**: matched iff the appliance has a valid profile, else legacy; the legacy events of a matched appliance are dropped (no double detection, one `nilm_detections` row set per appliance, so HA binary / confidence / energy statistics cannot be duplicated). When every appliance with signatures is matched, the TensorFlow inference is skipped and signature adds no longer auto-train the legacy network. `NILM_ENGINE=matched|shadow|legacy`: `shadow` keeps the legacy matcher writing and logs `Shadow ...: matched N / legacy M; only matched ...; only legacy ...` (rollout step), `legacy` is the rollback. `GET /api/nilm/engines` (backend proxy of nilm `/engines`) returns the engine per appliance, its modes and the reason. Matched detections carry `model_name = matched_filter_v<VERSION>` and `features.detection_method = matched_filter`. The scorecard now reads the champion model, not the latest trained one (an experimental model had leaked into the public scorecard).
- **Rollout status (2026-10-30)**: shadow review done (22 h: legacy 2 false positives on radiators, 1 cycle not written, 1 energy overstated by 25 %; matched 0 false positive, 1 miss). The miss (10-29 23:54) had both edges ~5 % low (-5.6 sigma / -2.9 sigma) because sigma learned from 35 signatures was 31 W (1 %) while the real spread on 331 certain cycles is 1.3-1.9 % (mains voltage): `SIGMA_FLOOR` 0.01 -> 0.015, `VERSION` 3 (bench unchanged: recall 101/102, 0 overlap with oven / dishwasher / washer). `NILM_ENGINE=matched` is live on the Pi since 2026-10-30, 10-20 -> 10-30 re-detected with `POST /detect?hours=240`. The nilm service stores `GET /engines` in `nilm_meta.engine_status` after each detection run; the backend scorecard (`engine`, `trained_at` = profile learned date, `val_loss` null) and the ha-publish `NILM ...` diagnostic sensors read it, so with `NILM_ENGINE=matched` they no longer show the legacy network's champion (trained 2026-06-09). ha-ingest also pulls the Linky energy index (`HA_ENTITY_ENERGY`, default `sensor.linky_east`) every 10 min into `linky_energy`; the scorecard `total_kwh` and the history `total_days` use it (summing `papp` samples under-counted: samples are event-driven, not time-weighted, which gave a 163 % recovered share), with the old sum as fallback when no index is stored. The frontend `ModelCard` lists the engine per appliance from `/api/nilm/engines`. On the Pi always run `docker compose -f docker-compose.yml ...` (the dev override mounts an empty models dir and detection then silently does nothing). Earlier: commits `4062560` + `22d6dc8` deployed 2026-10-29 with `NILM_ENGINE=shadow` (in the Pi `.env`, not in git). UI not updated yet (the model card is about the legacy network only; wanted: engine per appliance from `/api/nilm/engines`, provisional badge, hide the training button when no appliance uses the legacy engine). The CD runner on the Pi was re-registered by hand (see `ha-heaters/CLAUDE.md`); if a CD stays `queued`, check `gh api repos/rsaikali/linkya/actions/runners`.
- ZLinky MQTT (`zigbee/Linky`) also carries `rms_voltage`, `rms_current`, `active_power`: checked 2026-10-29, `active_power` is frozen (not a measurement), voltage / current are integers (1 V = 0.9 % on P), so they were not used.

**Full detect (`POST /api/nilm/detect`) and the legacy matcher (2026-10-29)** — a full detect wipes all of `nilm_detections` before rewriting. `run_detection` now refuses a full detect that would replace >= 20 detections with less than half as many (back up with `GET /api/detections` first anyway). The legacy matcher kept only 56 of ~400 detections on the full history (stopped at 2026-08-02; `_pair_change_points` left up edges open forever, now expiring after `MAX_OPEN_SECONDS` = 4 h, test `test_stale_up_edge_does_not_swallow_later_cycle`; a 14-day chunked replay still found ~170 vs ~400). The matched engine processes full history in 14-day chunks. HA energy statistics (`linkya:nilm_ballon_d_eau_chaude_energy`) are rewritten from `nilm_detections` after each detect (`POST /api/appliances/1/ha-backfill` rebuilds them) and the backfill ignores `is_correct`, so invalidated detections still count. `PATCH /api/detections/{id}/invalidate` hides a detection and adds a negative signature. The nilm service `POST /detect?hours=N` (internal, not proxied by the backend) re-detects only the last N hours, like the cron but longer: use it to clean a recent period without erasing older validations.

TensorFlow comes from pyproject (`tensorflow-cpu` on x86_64, `tensorflow` on aarch64/arm64).
