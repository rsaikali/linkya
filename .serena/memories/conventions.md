# Linkya — Code Conventions

## Language split

- Python (code, comments, docstrings, logs): **English**.
- React UI: **French** (mono-langue, no i18n library).

## Logging

- `loguru` in ha-ingest-service and ha-publish-service.
- stdlib `logging` in backend-service and nilm-service.
- Zero `print()`. Never mix within a service.

## Style

- flake8 + isort. Not ruff (project-specific exception to global preference).
- isort: profile=black, line_length=150. Config in root `pyproject.toml`.
- No emojis in code or logs.

## DB conventions

- Pure SQL DDL in service `init_db()` / `init_tables()` — no Alembic, no ORM migrations.
- Temporal bucketing: `to_timestamp(floor(epoch/secs)*secs)` — NOT `time_bucket` (no TimescaleDB extension).
- Schema changes require `make clean && make up` (data loss — plan accordingly).

## NILM jobs pattern (nilm-service/src/jobs.py)

- `request_training()` / `request_detection()` coalesce: max 1 pending of each type.
- CSV import: `add_signature(auto_train=False)` per row → single training trigger at the end.
- TF non-concurrent: `threading.Lock` (`_lock`) guards all model ops in `Seq2PointNILMManager`.
- `_last_id` initialized at startup to prevent replaying old detections after restart.

## ha-publish invariants

- Energy sensor `sensor.nilm_<slug>_energy`: `total_increasing`, value = SUM(detections) clamped to `ha_energy_hwm` (persisted high-water mark) — never decreasing. Prevents HA from interpreting a lower sum as a counter reset.
- Binary sensor `binary_sensor.nilm_<slug>`: live only — HA does not replay historical on/off via MQTT.
- `ha_entity_id` resolved via HA entity registry (not slug pattern matching).

## ha-ingest invariants

- Backfill detection energy distributed proportionally across hour boundaries.

## Config

- `.env.example` = source of truth. `.env` must stay in sync.
- `BACKEND_BIND` = LAN IP, never `0.0.0.0` (behind reverse proxy / NPM).
- `USE_GPU=auto`, `NILM_MODEL_TYPE=gru|lstm`, `NILM_DETECT_STATES=true`.
