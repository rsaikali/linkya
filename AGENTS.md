# AGENTS.md

This file acts as a guide when working with code in this repository.
No unnecessary documentation files or reports for your actions, only AGENTS.md and the root README.md.
Do not create unnecessary scripts, or delete them once they are no longer needed.
Everything in the codebase must be in English language.
The environment to use for every command you should launch is defined in the root .env file.
Keep it simple: no over-engineering in your actions, but try to be the expert you are in every domain asked.

## Context Documentation

This "AGENTS.md" file contains everything you need to know about the project to quickly get a good understanding as an expert coding assistant.
Update this file periodically as the project evolves.
In this file, do not be too detailed to avoid overloading the context, but be precise enough to help you understand the application quickly when re-reading it.
Regularly reorganize the file so that it is always up to date and coherent, but keep only the essentials such as the overall architecture and how it works, without too many technical details.

## Project Overview

Nilmia is a real-time electrical consumption analysis platform that:
- Ingests Linky smart meter data from remote MySQL into local TimescaleDB
- Applies Sequence-to-Point NILM (Non-Intrusive Load Monitoring) to detect appliance-level consumption
- Uses TensorFlow LSTM/GRU models to disaggregate aggregate power into individual appliances
- Provides React frontend with WebSocket streaming for real-time monitoring

## Architecture Principles

**Service Architecture**: The system uses a microservices architecture orchestrated by Docker Compose, with services communicating via Redis/Celery queues and TimescaleDB as the central data store.

**Data Pipeline**: Remote MySQL → sync-service (Celery) → TimescaleDB hypertable → nilm-cnn-service (TensorFlow) → detections → backend-service (FastAPI) → frontend-service (React WebSocket)

**Real-time Communication (WebSocket + Redis Pub/Sub)**:
- **Training logs**: Keras callback → Redis `training:logs` → WebSocket `/ws/training` → React frontend
- **Consumption updates**: sync-service → Redis `consumption:updates` → WebSocket `/ws/consumption` → React frontend
- **Detection updates**: nilm-cnn-service + backend-service → Redis `detections:updates` → WebSocket `/ws/detections` → React frontend
- Events: `training_start`, `epoch_start`, `epoch_end`, `new_consumption`, `new_detection`, `detection_start`, `detection_complete`, `detection_deleted`, `detections_cleared`
- Frontend updates detection list in real-time (new, deleted, cleared) - zero polling
- Auto-reconnection and broadcast to multiple clients

**Storage Model**:
- TimescaleDB `linky_realtime` hypertable stores all raw Linky data (PAPP, HCHP, HCHC, temperature) - no automatic retention policy
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

### NILM Model Improvements (2025-10-28)

**Architecture améliorée pour réduire les faux positifs** :

1. **Loss asymétrique** : Utilisation d'une fonction de perte personnalisée qui pénalise 2.5x plus les faux positifs (quand le modèle prédit de la puissance alors que target=0). Cela force le modèle à mieux apprendre les signatures négatives.

2. **Augmentation de données négatives** : Les signatures négatives (créées lors de l'invalidation de détections) sont augmentées avec :
   - Bruit gaussien (±5%)
   - Scaling (±10%)
   - Répétition (2x) pour augmenter leur poids dans le dataset
   
3. **Filtrage post-détection contre signatures négatives** : Chaque détection est comparée aux signatures négatives du même appareil. Si durée (±15%), puissance (±12%) et énergie (±15%) correspondent, la détection est rejetée comme faux positif.

4. **Seuil de confiance minimum** : Les détections avec un score de confiance < 55% sont automatiquement rejetées.

**Impact attendu** : Réduction drastique des faux positifs tout en conservant les vraies détections, grâce à l'apprentissage explicite des patterns à rejeter.

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

# Create manual backup of current model
curl -X POST http://localhost:8000/api/nilm/models/backup

# Delete model by ID (auto-promotes backup if deleting current)
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
- No automatic data deletion (all data persisted)
- `SYNC_RETENTION_HOURS=48` only limits initial sync, not ongoing storage
- Publishes new consumption data to Redis `consumption:updates` channel for real-time WebSocket streaming
- Celery tasks: `init_database`, `full_sync`, `incremental_sync`, `get_stats`

### nilm-cnn-service (Python 3.12 + TensorFlow)
- Trains S2P models per appliance using `seq2point_nilm.py` (replaced legacy `cnn_nilm.py`)
- Multi-output RNN architecture (GRU/LSTM) with attention mechanism
- Detects states/cycles using KMeans clustering on predicted power
- GPU support via `runtime: nvidia` (optional, falls back to CPU)
- TensorBoard logs saved per model in `models/tensorboard/`
- **Single Model System**: Only one model at a time, named `linkya_model_<timestamp>`
- Publishes new detections to Redis `detections:updates` channel for real-time WebSocket streaming
- Celery tasks: `train_cnn_model`, `detect_cnn_appliances`, `add_cnn_signature`, `enrich_cnn_signatures`

### backend-service (FastAPI)
- REST API with WebSocket endpoints (SSE removed October 2025)
- **Real-time Updates**: Three WebSocket endpoints for live streaming
- Routes Celery tasks to appropriate queues (`nilm_cnn` for NILM operations)
- **Redis Pub/Sub Integration**: Subscribes to Redis channels and broadcasts via WebSocket
- Key endpoints:
  - `GET /api/consumption/history` - aggregated time-series data (supports both relative duration and absolute start/end times)
  - `POST /api/signatures` - create appliance signatures
  - `POST /api/nilm/train` - trigger training
  - `WS /ws/training` - WebSocket for real-time training logs
  - `WS /ws/consumption` - WebSocket for real-time consumption updates
  - `WS /ws/detections` - WebSocket for real-time detection updates

### frontend-service (React 18 + MUI)
**Active Components**:
- `CurrentModel` - Display current trained model with delete action
- `LatestConsumption` - Real-time power/temperature via WebSocket
- `ConsumptionChart` - Interactive chart with signature creation via range selection
- `DetectionsList` - Paginated detection list with validation controls
- `SignaturesList` - Manage training signatures with CSV import/export
- `SignatureModal` - Modal for creating signatures from chart selection

**Real-time Features**:
- Three WebSocket connections: `/ws/training`, `/ws/consumption`, `/ws/detections`
- No polling - all updates event-driven via WebSocket
- Auto-refresh on `detection_complete` event (replaces 60s polling)
- Live training logs, consumption updates, and detection streaming

**Removed Components** (October 2025):
- `NilmTraining` - Unused, replaced by CurrentModel
- `DetectionsTimeline` - Unused, DetectionsList is the main view

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

**Timezone handling**: All timestamp columns use `timestamp with time zone` (timestamptz). The database timezone is set to `Europe/Paris`. API responses include timezone offset (e.g., `2025-10-23T23:53:57+02:00`).

**linky_realtime** (hypertable, 6h chunks):
- `time` (timestamptz, PK)
- `papp` (smallint) - apparent power in VA
- `hchp`, `hchc` (int) - peak/off-peak index counters
- `temperature` (double)
- `libelle_tarif` (varchar)

**cnn_appliances**:
- `id`, `name`, `description`
- `created_at`, `updated_at` (timestamptz)
- `num_signatures`, `avg_power`, `is_validated`

**cnn_signatures**:
- Stores training examples with `start_time`, `end_time` (timestamptz), `appliance_id`
- Frontend creates these via range selection on consumption chart
- **Negative signatures**: `is_negative` (boolean, default FALSE)
  - `is_negative=FALSE`: Positive examples (what TO detect)
  - `is_negative=TRUE`: Negative examples (what NOT to detect)
  - Negative signatures are automatically created when user invalidates a detection with `confidence_score >= 0.6`
  - Persist in database, allow cleaning detections table without losing learning

**cnn_detections**:
- Detection results: `appliance_id`, `start_time`, `end_time` (timestamptz), `avg_power`, `energy_consumed`, `confidence_score`
- `created_at` (timestamptz)
- **Validation fields**: `user_validated` (boolean), `is_correct` (boolean), `validated_at` (timestamptz)
- Can be cleaned periodically (`make detections-clean`) - negative signatures are preserved

**cnn_models**:
- Metadata for trained models: `model_name`, `model_type`, `training_date` (timestamptz), `metrics` (JSON)
- **Single Model System**: 
  - Only ONE model at a time (table typically contains 0 or 1 row)
  - `model_name` format: `linkya_model_<timestamp>` (e.g., `linkya_model_20251029_143052`)
  - Training replaces the existing model (old model is deleted)
  - No versioning, no backup system - simplicity over complexity

## NILM Workflow

1. **Data Collection**: Let system run 48h to gather baseline consumption
2. **Signature Creation**: Use frontend to select time ranges on chart → creates `cnn_signatures`
3. **Model Training**: Run `make train` or use frontend trigger
   - **From-Scratch Training**: Each training creates a NEW model and deletes the old one
     - New model named `linkya_model_<timestamp>`
     - Old model files (.keras, .metadata.json, logs) automatically deleted
     - If no: Trains from scratch
   - **Feedback Learning**: Automatically uses negative signatures (persistent examples of what NOT to detect)
     - New model named `linkya_model_<timestamp>`
     - Old model files (.keras, .metadata.json, logs) automatically deleted
     - Training always from scratch (no fine-tuning)
   - One multi-output model predicts all appliances simultaneously
   - TensorBoard logs saved to `models/tensorboard/film_gru/<model_name>/`
   - Model saved with timestamp in name for tracking
4. **Detection**: Automatic every 5 minutes (configurable) or manual via `make detect`
   - Sliding window over recent data
   - Predicts appliance power using S2P model
   - Clusters predicted power to detect states/cycles
   - Saves detections to `cnn_detections`
5. **User Validation**: Frontend displays detections with validation controls
   - ✓ Validate button: marks detection as correct (`is_correct=true`)
   - ✗ Invalidate button: marks detection as incorrect + **creates a negative signature** (`is_negative=true`) if `confidence_score >= 0.6`
   - Validated/invalidated detections highlighted with colored backgrounds
   - **Negative signatures persist** in database, can clean detections without losing learning
6. **Iterative Improvement**: Model improves with each training cycle
   - View feedback statistics: `make feedback-stats`
   - View signature statistics: `make signatures-stats` (positive + negative)
   - Clean old detections: `make detections-clean` (negative signatures preserved)
   - More user validations → more negative signatures → better model accuracy on next training

## Key Technical Details

### Single Model System (Simplified)

The system maintains only ONE active model at a time:
- **model_name**: Format `linkya_model_<timestamp>` (e.g., `linkya_model_20251029_143052`)
- Training creates a new model and deletes the old one (both DB entry and files)
- No versioning, no backup/archived states - keep it simple

**Training Workflow**:
1. Generate model name with timestamp: `linkya_model_YYYYMMDD_HHMMSS`
2. Train model from scratch (always, no fine-tuning)
3. Delete old model entry and files if exists
4. Save new model to database with new name
5. Model files: `<model_name>.keras`, `<model_name>.metadata.json`
**Training Workflow**:
1. Generate model name with timestamp: `linkya_model_YYYYMMDD_HHMMSS`
2. Train model from scratch (always, no fine-tuning)
3. Delete old model entry and files if exists
4. Save new model to database with new name
5. Model files: `<model_name>.keras`, `<model_name>.metadata.json`

**Model Deletion**:
- Delete from frontend or via `make api-nilm-delete-model ID=<id>`
- Removes DB entry, .keras file, .metadata.json, and TensorBoard logs
- After deletion, no model available until next training

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

- **Optimized Data Loading with Decimation** (October 30, 2025):
  - **Problem**: Loading 360k raw points caused slow page load and rendering issues
  - **Solution**: Smart compromise with decimation
    - Load data with **10 seconds interval** (~36k points instead of 360k)
    - Added **Chart.js Decimation plugin** with LTTB algorithm
    - LTTB (Largest-Triangle-Three-Buckets) preserves peaks and valleys
    - Default display: 1000 samples, full precision available on zoom
  - **Frontend changes**:
    - Import and register `Decimation` from Chart.js
    - Added `decimation` plugin config with `algorithm: 'lttb'` and `samples: 1000`
    - Progress bar during load (10% → 30% → 70% → 100%)
    - Removed problematic `parsing: false` and `normalized: true` flags
  - **Benefits**:
    - Fast loading (~36k points vs 360k)
    - Smooth rendering with automatic downsampling
    - Better UX with progress feedback
    - Chart.js handles zoom/pan efficiently
  - **Performance**: 10s interval = good detail level + Chart.js decimation for fluid display

- **Fix Model Loading for Detection** (October 30, 2025):
  - **Problem**: Detection failed with "Aucun modèle FiLM disponible" error
  - **Root causes**: 
    1. Model was never loaded before detection, only checked in database
    2. Loss function `asymmetric_loss()` returned anonymous closure that couldn't be serialized by Keras
  - **Solution**:
    - Added automatic model loading in `detect_cnn_appliances` task
    - Fixed model compilation to use `asymmetric_loss` directly instead of calling it as constructor
    - Keras can now properly serialize/deserialize the registered loss function
    - Model loads correctly with full compilation (no need for `compile=False`)
  - Modified files:
    - `nilm-cnn-service/src/tasks.py`: Added `nilm_manager.load_model()` call with proper error handling
    - `nilm-cnn-service/src/seq2point_nilm.py`: Changed `loss=asymmetric_loss(...)` to `loss=asymmetric_loss` for proper serialization
  - **Impact**: Models can now be saved/loaded with their loss function intact, enabling proper inference without recompilation hacks

- **Client-Side Zoom with Full Data Loading** (October 30, 2025) - **REPLACED by Raw Data Loading**:
  - **Complete architecture redesign** for consumption chart zoom
  - **Single data load**: All available data loaded once at component mount
  - **Backend changes**:
    - `/api/consumption/history` now accepts optional `start_time`/`end_time`
    - If omitted, returns ALL data from `linky_realtime` table
    - `interval='auto'` adapts aggregation to total data range
    - New `get_consumption_time_range()` function to get min/max timestamps
  - **Frontend changes**:
    - Load all data once: `getConsumptionHistory(null, null, '1 minute')`
    - **Smart interval selection**: 1 minute aggregation = ~10k points (359k raw would be too much)
    - Initial view: last 48h (zoom applied after data load)
    - Zoom/pan handled 100% by Chart.js without backend requests
    - Reset button restores full data view
  - **Benefits**:
    - Zero network requests during zoom/pan
    - Instant zoom response
    - Good detail level with 1-minute aggregation
    - Better UX (no loading indicators during zoom)
  - **Data volume**: 359k raw points → 10.5k points at 1-minute intervals
  - **Fix Oct 30 PM**: Removed displayData/visibleRange states that were blocking pan/zoom
    - Chart.js now handles all 10k points natively (no client-side sampling needed)
    - Pan/zoom fully functional with modifierKey: null

- **Interactive Chart Zoom with Optimized Data Loading** (October 2025) - **REPLACED Oct 30**:

- **Interactive Chart Zoom with Optimized Data Loading** (October 2025) - **REPLACED Oct 30**:
  - ~~Smart loading strategy with dynamic intervals~~ → **Replaced by client-side zoom**
  - ~~Reload when interval changes~~ → **No more reloads**
  - ~~Dynamic data granularity based on visible range~~ → **Client-side sampling**

- **Time Series Cross-Validation** (October 2025) ✅ **IN PRODUCTION**:
  - **Replaced random train/val split** with temporal cross-validation
  - Uses sklearn's `TimeSeriesSplit` with 5 folds and sliding window
  - Final model trained on last fold (80% oldest → 20% most recent)
  - **Prevents temporal data leakage** - no future data visible during training
  - **Tests real generalization** on most recent data (simulates production)
  - More robust than simple split, validates across multiple temporal windows
  - Modified `seq2point_nilm.py`:
    - Track timestamps from signatures during data preparation
    - Sort data by timestamp and apply TimeSeriesSplit
    - Use last fold for final train/val split
    - Updated `_add_negative_examples_film()` to track timestamps
  - Follows time series ML best practices for production systems

- **Complete WebSocket Implementation** (October 2025):
  - **Removed SSE**: Deleted `sse.js`, removed all SSE endpoints (`/api/stream/*`)
  - **Backend**: Added WebSocket managers for consumption and detections (similar to training)
    - `ConsumptionUpdatesManager` listens to Redis `consumption:updates`
    - `DetectionUpdatesManager` listens to Redis `detections:updates`
    - Endpoints: `/ws/consumption`, `/ws/detections`
  - **sync-service**: Publishes to Redis after inserting new consumption data
  - **nilm-cnn-service**: Publishes to Redis after creating new detections
  - **Frontend**: Extended `websocket.js` with `GenericWebSocket` class
    - `consumptionWS` singleton for consumption updates
    - `detectionsWS` singleton for detection updates
    - `LatestConsumption.js` uses WebSocket for real-time power/temp
    - `ConsumptionChart.js` uses WebSocket for real-time detections
  - **Architecture**: Full event-driven real-time system via Redis Pub/Sub + WebSocket

- **Fix Duplicate Training Logs** (October 2025):
  - **Root cause**: Event handlers were redefined inside `useEffect` without stable references, causing multiple registrations
  - **Solution**: Wrapped all handlers in `useCallback` with proper dependencies to ensure stable function references
  - Modified `TrainingLogsViewer.js`:
    - Added `useCallback` import
    - Moved `addLog`, `formatDuration`, and all event handlers outside `useEffect`
    - Wrapped each in `useCallback` with appropriate dependency arrays
    - Updated `useEffect` dependency array to include all handlers (ensures proper cleanup on handler changes)
  - Modified `websocket.js`:
    - Added guard in `connect()` to skip if already connected (prevents duplicate WebSocket instances)
    - Closes existing connection before creating new one
  - **Impact**: Each event now triggers exactly once (no more duplicates), proper cleanup when component unmounts

- **Real-time Training Logs via WebSocket** (October 2025):
  - Custom Keras callback `RedisTrainingCallback` publishes training events to Redis Pub/Sub channel `training:logs`
  - FastAPI WebSocket endpoint `/ws/training` subscribes to Redis and broadcasts to multiple clients
  - Frontend `TrainingLogsViewer` component displays live training progress with auto-reconnection
  - Events: `training_start`, `epoch_start`, `epoch_end` (with metrics, ETA), `batch_update`, `training_complete`
  - Real-time metrics: loss, accuracy, progress bar, elapsed time, ETA
  - Migration path from SSE to WebSocket for better bidirectional communication

- **Simplified Single Model System** (October 2025):
  - Removed complex `model_status` ENUM (current/backup/archived) in favor of simplicity
  - Only ONE model at a time with name format `linkya_model_<timestamp>`
  - Removed `is_active`, `version` columns from `cnn_models` table
  - Training always from-scratch (no fine-tuning) - creates new model and deletes old one
  - Frontend simplified: removed status badges, backup button, complex warnings
  - Backend simplified: removed `/api/nilm/models/backup` endpoint
  - Migration SQL: `migrations/simplify_single_model.sql`

- **Negative Signatures System**: Persistent learning from invalidated detections
  - Added `is_negative` field to `cnn_signatures` table (boolean, default FALSE)
  - When user invalidates a detection with `confidence_score >= 0.6`, a **negative signature** is automatically created
  - Negative signatures persist in database (unlike ephemeral detections)
  - Training uses negative signatures instead of querying `cnn_detections` table
  - **Can now clean detections table** without losing learning: `make detections-clean`
  - New command: `make signatures-stats` shows positive/negative signature counts by appliance
  - Workflow: User invalidates → Negative signature created → Training uses it → Can clean old detections

- **Feedback Learning (Phase 1)**: Implemented user-driven model improvement through detection validation
  - Added validation fields to `cnn_detections` table (`user_validated`, `is_correct`, `validated_at`)
  - Frontend validation UI with ✓/✗ buttons and visual feedback (colored row backgrounds)
  - Backend API endpoints: `PATCH /api/detections/{id}/validate` and `/invalidate`
  - Invalidate button creates persistent negative signatures (if confidence >= 0.6)
  - New Makefile commands: `make feedback-stats`, `make signatures-stats`, `make detections-clean`
- **Timezone fix**: Migrated all NILM tables to `timestamp with time zone` (timestamptz) for proper Europe/Paris timezone handling. Backend now returns ISO timestamps with timezone offset (e.g., `+02:00`) instead of forcing UTC conversion. Frontend displays correct local times.
- Removed legacy `cnn_nilm.py`, replaced by `seq2point_nilm.py` S2P architecture
- Fixed multi-output S2P scaler fitting (fit before normalization to avoid "preprocessor not fit" error)
- Fixed multi-output metrics compilation (use dict with `power_i: ['mae', 'mse']` to avoid KeyError)
- Added `predict_all` + state detection for disaggregation API
- Cleaned detector threshold serialization (convert float32 to float for JSON)
- TensorBoard runs auto-created per model/version


