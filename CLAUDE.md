# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
Keep it simple, no over-engineering, but remain thorough in your actions.
No unnecessary documentation files or reports for your actions, only CLAUDE.md and the root README.md.
Do not create unnecessary scripts, or delete them once they are no longer needed.

## Context Documentation
This "CLAUDE.md" file contains everything you need to know about the project to quickly get a good understanding as a coding assistant.
Update this file periodically as the project evolves.
In this file, do not be too detailed to avoid overloading the context, but be precise enough to help you understand the application quickly when re-reading it.
Regularly reorganize the file so that it is always up to date and coherent, but keep only the essentials such as the overall architecture and how it works, without too many technical details.
Keep an updated architecture diagram in the next 'Schema' section.

## Schema

Empty now, replace this text with an architecture diagram of the project when possible.

## Project Overview

Nilmia is a real-time electrical consumption analysis platform that:
- Ingests Linky smart meter data from remote MySQL into local TimescaleDB
- Applies Sequence-to-Point NILM (Non-Intrusive Load Monitoring) to detect appliance-level consumption
- Uses TensorFlow LSTM/GRU models to disaggregate aggregate power into individual appliances
- Provides React frontend with SSE streaming for real-time monitoring

## Architecture Principles

**Service Architecture**: The system uses a microservices architecture orchestrated by Docker Compose, with services communicating via Redis/Celery queues and TimescaleDB as the central data store.

**Data Pipeline**: Remote MySQL → sync-service (Celery) → TimescaleDB hypertable → nilm-cnn-service (TensorFlow) → detections → backend-service (FastAPI) → frontend-service (React SSE streams)

**Storage Model**:
- TimescaleDB `linky_realtime` hypertable stores 48h rolling window of raw Linky data (PAPP, HCHP, HCHC, temperature)
- NILM tables (`cnn_appliances`, `cnn_signatures`, `cnn_detections`, `cnn_models`) store training data and results
- TensorFlow models persisted in `./models` volume with versioned checkpoints

**NILM Approach**: The project transitioned from classical CNN to Sequence-to-Point (S2P) RNN architecture. The S2P model:
- Takes aggregate power sequence as input (e.g., 600 points = 10 minutes at 1Hz)
- Outputs multi-appliance power predictions (one head per appliance)
- Detects appliance states/cycles using clustering on predicted power
- Handles concurrent appliance operation

## Development Commands

### Essential Commands (Makefile)

```bash
# Start entire stack (checks .env, builds, starts services)
make start

# Check service health and database stats
make check

# View logs from all services
make logs

# Connect to TimescaleDB
make psql

# Redis CLI
make redis-cli
```

### NILM Operations

```bash
# Train S2P model (requires 48h data + signatures)
make nilm-train

# Run detection manually
make nilm-detect

# View detection statistics
make nilm-stats

# List trained models
make nilm-models

# Check signature quality
make nilm-check-signatures
```

### API Operations

```bash
# Test backend health
make backend

# Launch training via API
make api-nilm-train

# Launch detection via API
make api-nilm-detect

# List models with pagination
make api-nilm-models

# Delete model by ID
make api-nilm-delete-model ID=14
```

### Service-Specific Commands

```bash
# Scale sync workers
make scale-workers N=3

# Open monitoring UIs
make flower    # Celery monitoring (localhost:5555)
make pgadmin   # TimescaleDB admin (localhost:8080)
```

## Service Details

### sync-service (Python 3.13 + uv)
- Polls remote MySQL `linky_realtime` every 5 seconds
- Bulk inserts into TimescaleDB with automatic hypertable partitioning
- Enforces 48h retention policy
- Celery tasks: `init_database`, `full_sync`, `incremental_sync`, `get_stats`

### nilm-cnn-service (Python 3.12 + TensorFlow)
- Trains S2P models per appliance using `seq2point_nilm.py` (replaced legacy `cnn_nilm.py`)
- Multi-output RNN architecture (GRU/LSTM) with attention mechanism
- Detects states/cycles using KMeans clustering on predicted power
- GPU support via `runtime: nvidia` (optional, falls back to CPU)
- TensorBoard logs saved per model version
- Celery tasks: `train_cnn_model`, `detect_cnn_appliances`, `add_cnn_signature`, `enrich_cnn_signatures`

### backend-service (FastAPI)
- REST API with Server-Sent Events (SSE) endpoints
- Routes Celery tasks to appropriate queues (`nilm_cnn` for NILM operations)
- Key endpoints:
  - `GET /api/consumption/history` - aggregated time-series data
  - `POST /api/signatures` - create appliance signatures
  - `POST /api/nilm/train` - trigger training
  - `GET /api/stream/consumption/latest` - SSE real-time power
  - `GET /api/stream/detections` - SSE detection updates

### frontend-service (React 18 + MUI)
- Consumption charts with Chart.js
- Interactive range selection for signature creation
- Appliance autocomplete with create-on-demand
- Training management with paginated model history
- SSE-based real-time updates (no polling)

## Configuration

**Single .env file** at project root (copy from `.env.example`). Key variables:

```env
# Remote MySQL Linky source
REMOTE_DB_HOST=192.168.1.200
REMOTE_DB_PASSWORD=***

# Sync intervals
SYNC_INTERVAL_SECONDS=5
SYNC_RETENTION_HOURS=48

# NILM model config
CNN_WINDOW_SIZE_MINUTES=10        # S2P sequence window (10min = 600 points)
NILM_MODEL_TYPE=gru               # lstm, gru, attention
USE_GPU=auto                       # true, false, auto
CNN_EPOCHS=50
CNN_BATCH_SIZE=32

# Detection config
CNN_DETECTION_INTERVAL_MINUTES=5
CNN_MIN_POWER_THRESHOLD=30        # Watts
CNN_MIN_DURATION_SECONDS=30
```

**Important**: `CNN_WINDOW_SIZE_MINUTES` determines S2P sequence length (1Hz sampling). Recommended 10-20 minutes for balance of context vs. speed.

## Database Schema

### TimescaleDB Tables

**linky_realtime** (hypertable, 6h chunks):
- `time` (timestamptz, PK)
- `papp` (smallint) - apparent power in VA
- `hchp`, `hchc` (int) - peak/off-peak index counters
- `temperature` (double)
- `libelle_tarif` (varchar)

**cnn_appliances**:
- `id`, `name`, `description`
- `num_signatures`, `avg_power`, `is_validated`

**cnn_signatures**:
- Stores training examples with `start_time`, `end_time`, `appliance_id`
- Frontend creates these via range selection on consumption chart

**cnn_detections**:
- Detection results: `appliance_id`, `start_time`, `end_time`, `avg_power`, `energy_consumed`, `confidence_score`

**cnn_models**:
- Metadata for trained models: `version`, `model_type`, `training_date`, `metrics` (JSON), `is_active`

## NILM Workflow

1. **Data Collection**: Let system run 48h to gather baseline consumption
2. **Signature Creation**: Use frontend to select time ranges on chart → creates `cnn_signatures`
3. **Model Training**: Run `make nilm-train` or use frontend trigger
   - S2P model trains on all appliance signatures
   - One multi-output model predicts all appliances simultaneously
   - TensorBoard logs saved to `models/tensorboard/`
4. **Detection**: Automatic every 5 minutes (configurable) or manual via `make nilm-detect`
   - Sliding window over recent data
   - Predicts appliance power using S2P model
   - Clusters predicted power to detect states/cycles
   - Saves detections to `cnn_detections`
5. **Validation**: Frontend displays detections; users can delete false positives

## Key Technical Details

### S2P Multi-Output Model (`seq2point_nilm.py`)

The Seq2PointMultiModel class:
- Takes single aggregate input sequence (shape: `[sequence_length, 1]`)
- Outputs N power predictions (one per appliance)
- Uses shared LSTM/GRU layers + separate dense heads
- Compiled with per-output MAE/MSE metrics to avoid `KeyError: power_i_mae`
- StandardScaler fitted separately per appliance before training

### State Detection

ApplianceStateDetector uses KMeans on predicted power to identify cycles:
- Clusters power values into distinct states (e.g., heating, washing, spinning)
- Detects transitions between states
- Assigns semantic labels to detected segments

### GPU Support

Set `USE_GPU=true` or `USE_GPU=auto` in `.env`. Docker Compose enables `runtime: nvidia` for `cnn-worker`. TensorFlow auto-detects GPU via `tf.config.list_physical_devices('GPU')`.

### Celery Queues

Two separate worker pools:
- Default queue: sync tasks (lightweight)
- `nilm_cnn` queue: NILM tasks (GPU-enabled)

Backend routes NILM tasks explicitly to `nilm_cnn` queue.

## Testing & Debugging

### Check Service Health

```bash
docker-compose ps                  # Container status
make check                         # Full health check with stats
docker logs nilmia-cnn-worker      # NILM worker logs
docker logs nilmia-backend         # API logs
```

### Database Queries

```sql
-- Recent detections
SELECT ca.name, cd.start_time, cd.end_time, cd.avg_power, cd.confidence_score
FROM cnn_detections cd
JOIN cnn_appliances ca ON cd.appliance_id = ca.id
ORDER BY cd.start_time DESC
LIMIT 20;

-- Consumption by appliance (24h)
SELECT ca.name, COUNT(*) as activations, SUM(cd.energy_consumed) as total_wh
FROM cnn_detections cd
JOIN cnn_appliances ca ON cd.appliance_id = ca.id
WHERE cd.start_time >= NOW() - INTERVAL '24 hours'
GROUP BY ca.name
ORDER BY total_wh DESC;
```

### TensorBoard

```bash
# Access at http://localhost:6006
# Logs stored per model version in models/tensorboard/
```

### Common Issues

**Training fails**: Check `nilm-check-signatures` for insufficient signature duration
**No GPU detected**: Verify `nvidia-smi` works, Docker nvidia runtime installed
**Sync stopped**: Check remote MySQL connectivity from `sync-worker` container
**Frontend not updating**: Verify SSE connection in browser DevTools Network tab

## Code Style

- Python: uv for dependency management, Pydantic for config, SQLAlchemy for DB
- Keep it simple (per AGENTS.md): avoid over-engineering
- No unnecessary documentation files beyond `README.md` and `documentation.md`
- Update `documentation.md` periodically with architecture changes (not detailed implementation)

## Recent Changes

- Removed legacy `cnn_nilm.py`, replaced by `seq2point_nilm.py` S2P architecture
- Fixed multi-output S2P scaler fitting (fit before normalization to avoid "preprocessor not fit" error)
- Fixed multi-output metrics compilation (use dict with `power_i: ['mae', 'mse']` to avoid KeyError)
- Added `predict_all` + state detection for disaggregation API
- Cleaned detector threshold serialization (convert float32 to float for JSON)
- TensorBoard runs auto-created per model/version
