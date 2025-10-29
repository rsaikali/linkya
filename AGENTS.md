# AGENTS.md

This file acts as a guide when working with code in this repository.
Keep it simple, no over-engineering, but remain thorough in your actions.
No unnecessary documentation files or reports for your actions, only AGENTS.md and the root README.md.
Do not create unnecessary scripts, or delete them once they are no longer needed.
Everything in the codebase must be in English language.

## Context Documentation
This "AGENTS.md" file contains everything you need to know about the project to quickly get a good understanding as a coding assistant.
Update this file periodically as the project evolves.
In this file, do not be too detailed to avoid overloading the context, but be precise enough to help you understand the application quickly when re-reading it.
Regularly reorganize the file so that it is always up to date and coherent, but keep only the essentials such as the overall architecture and how it works, without too many technical details.

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

**Data Pipeline**: Remote MySQL → sync-service (Celery) → TimescaleDB hypertable → nilm-cnn-service (TensorFlow) → detections → backend-service (FastAPI) → frontend-service (React WebSocket/SSE streams)

**Real-time Training Communication**:
- Keras callback (nilm-cnn-service) → Redis Pub/Sub channel `training:logs` → FastAPI WebSocket (`/ws/training`) → React frontend
- Events: `training_start`, `epoch_start`, `epoch_end`, `batch_update`, `training_complete`
- Auto-reconnection and broadcast to multiple clients

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
- REST API with WebSocket and SSE endpoints
- **Real-time Training Logs**: WebSocket endpoint (`/ws/training`) for live training progress
- Routes Celery tasks to appropriate queues (`nilm_cnn` for NILM operations)
- **Redis Pub/Sub Integration**: Subscribes to training events and broadcasts via WebSocket
- Key endpoints:
  - `GET /api/consumption/history` - aggregated time-series data
  - `POST /api/signatures` - create appliance signatures
  - `POST /api/nilm/train` - trigger training
  - `GET /api/stream/consumption/latest` - SSE real-time power
  - `GET /api/stream/detections` - SSE detection updates
  - `WS /ws/training` - WebSocket for real-time training logs

### frontend-service (React 18 + MUI)
- Consumption charts with Chart.js
- Interactive range selection for signature creation
- Appliance autocomplete with create-on-demand
- Training management with paginated model history
- **Real-time Training Logs**: WebSocket-based live training progress viewer
- **Model Status Display**: Badges for current (green), backup (orange), archived (gray)
- **Flexible Model Deletion**: Delete any model with appropriate warnings (current deletion auto-promotes backup)
- **Manual Backup Creation**: Button to save current model as backup before risky operations
- WebSocket-based real-time training logs with auto-reconnection
- SSE-based real-time updates for consumption data (migrating to WebSocket)
- CSV export/import for signatures (bulk operations)

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
- Metadata for trained models: `version`, `model_type`, `training_date` (timestamptz), `metrics` (JSON)
- **Model Status System** (`model_status` ENUM):
  - `current`: Active model used for detection (only one at a time, enforced by unique index)
  - `backup`: Previous model saved before last training (only one, for rollback)
  - `archived`: Historical models no longer active
- **Model Management**:
  - All models can be deleted from the frontend (current/backup/archived)
  - Deleting 'current' automatically promotes 'backup' → 'current' to ensure always-active model
  - Manual backup: Button in frontend to save 'current' → 'backup' (archives old backup)
  - Automatic backup: Training automatically saves current → backup before fine-tuning

## NILM Workflow

1. **Data Collection**: Let system run 48h to gather baseline consumption
2. **Signature Creation**: Use frontend to select time ranges on chart → creates `cnn_signatures`
3. **Model Training**: Run `make train` or use frontend trigger
   - **Incremental Fine-Tuning**: System automatically detects if a `current` model exists
     - If yes: Saves current → backup, loads model, fine-tunes with lower learning rate (0.0001 vs 0.001) and fewer epochs (max 15)
     - If no: Trains from scratch
   - **Feedback Learning**: Automatically uses negative signatures (persistent examples of what NOT to detect)
   - One multi-output model predicts all appliances simultaneously
   - TensorBoard logs saved to `models/tensorboard/`
   - Model always saved as version "current" (not timestamped)
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
   - Compare current vs backup: `make model-compare`
   - Rollback to previous model if needed: `make model-rollback`
   - Check model status: `make model-status`
   - More user validations → more negative signatures → better model accuracy

## Key Technical Details

### Incremental Fine-Tuning System

The system maintains only two active models:
- **current**: Production model used for all detections
- **backup**: Safety net for rollback if new training degrades performance

**Training Workflow**:
1. Check for existing `current` model
2. If found:
   - Archive old `backup` → `archived`
   - Promote `current` → `backup`
   - Load `current` model weights
   - Fine-tune with reduced learning rate (10x lower) and max 15 epochs
3. If not found: Train from scratch with standard parameters (learning rate 0.001, 30 epochs)
4. Save new model as `current`

**Rollback Workflow**:
- `make model-rollback` atomically promotes `backup` → `current` and archives old `current`
- Useful if fine-tuned model performs worse due to overfitting or bad feedback data

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

- **Flexible Model Management System** (October 2025):
  - Frontend now displays `model_status` (current/backup/archived) with color-coded badges
  - All models can be deleted from frontend, including current and backup
  - Deleting 'current' model automatically promotes 'backup' → 'current' for continuity
  - New "Backup manuel" button to save current model before risky operations
  - Backend endpoint `POST /api/nilm/models/backup` for manual backup creation
  - Improved delete dialog with status-specific warnings (current/backup/archived)
  - Model list sorted by status priority (current first, then backup, then archived by date)

- **Incremental Fine-Tuning System**: Revolutionary continuous learning approach replacing version-based training
  - Migrated from `is_active` (boolean) to `model_status` (ENUM: current/backup/archived)
  - System now maintains only ONE active model ("current") instead of accumulating versions
  - Automatic backup before training: current → backup (old backup → archived)
  - Fine-tuning when current exists: loads weights, reduces learning rate to 0.0001, max 15 epochs
  - From-scratch when no current: standard parameters (lr=0.001, 30 epochs)
  - New commands: `make model-compare`, `make model-rollback`, `make model-status`
  - Model improves incrementally with each training cycle instead of starting over
  - Rollback capability if fine-tuned model underperforms

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


