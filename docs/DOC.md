# Nilmia - Documentation Technique

## Overview
Nilmia is a real-time electrical consumption analysis platform using NILM (Non-Intrusive Load Monitoring) with CNN deep learning to automatically detect electrical appliances from Linky smart meter data.

## Architecture

### Services Stack
```
Frontend (React) → Backend (FastAPI) → TimescaleDB
                                     ↓
                        Celery Workers (Redis broker)
                                     ↓
                   Sync Worker + NILM-CNN Worker
```

**Core Services:**
- **sync-service**: MySQL (Linky) → TimescaleDB sync (every 5s)
- **nilm-cnn-service**: CNN model training & real-time appliance detection
- **backend-service**: FastAPI REST API + SSE streaming for real-time updates
- **frontend-service**: React 18 + Material-UI dashboard

**Infrastructure:**
- **TimescaleDB**: Time-series optimized PostgreSQL with ~48h Linky data (~98k rows)
- **Redis**: Celery message broker + real-time event pub/sub
- **Celery**: Async task orchestration (Beat scheduler + Workers)

### Technology Stack
- **Python 3.13** with `uv` package manager
- **TensorFlow/Keras** for 1D CNN NILM models
- **React 18** with Chart.js for data visualization
- **FastAPI** with SSE (Server-Sent Events) for real-time streaming
- **Docker Compose** for orchestration

## Database Schema

### Main Tables

**linky_realtime** (TimescaleDB hypertable)
- `time` (datetime, PK): Measurement timestamp
- `papp` (smallint): Apparent power (VA)
- `hchp` (int): Peak hours index (Wh)
- `hchc` (int): Off-peak hours index (Wh)
- `temperature` (double): Temperature (°C)
- `libelle_tarif` (varchar): Current tariff label
- **Sync**: Every 2s from Linky → Every 5s to TimescaleDB

**appliances** (managed devices)
- `id` (serial, PK)
- `name` (varchar): Appliance name
- `created_at` (datetime)

**appliance_signatures** (training data)
- `id` (serial, PK)
- `appliance_id` (int, FK): Reference to appliance
- `start_time` (datetime): Signature start
- `end_time` (datetime): Signature end
- `is_negative` (boolean): Negative example for training
- `created_at` (datetime)

**training_sessions** (model training history)
- `id` (serial, PK)
- `status` (varchar): 'pending', 'running', 'completed', 'failed'
- `model_path` (varchar): Saved model file path
- `metadata` (jsonb): Architecture, metrics, hyperparameters
- `started_at`, `completed_at` (datetime)
- `error_message` (text)

**appliance_detections** (real-time detection results)
- `id` (serial, PK)
- `appliance_id` (int, FK)
- `detected_at` (datetime): Detection timestamp
- `confidence` (float): Detection confidence score
- `power_consumption` (float): Estimated power (W)
- `is_validated` (boolean): User validation
- `validation_status` (varchar): 'pending', 'confirmed', 'rejected'

## NILM CNN Architecture

### Model Configuration (Environment Variables)
```env
NILM_MODEL_TYPE=gru     # 'gru' or 'lstm'
```

### Architecture: FiLM (Feature-wise Linear Modulation)
- Multi-appliance with conditional learning
- FiLM layers for appliance-specific feature modulation
- Best for complex appliance patterns (washing machines, dryers)
- Outputs: power + state predictions per appliance
- Single unified model for all appliances

### Model Pipeline
1. **Input**: 599-point sliding window (PAPP values, ~20min at 2s interval)
2. **Preprocessing**: StandardScaler normalization
3. **Architecture**: Conv1D → GRU/LSTM → Attention → Dense
4. **Output**: Power consumption + appliance state per timestep
5. **Loss**: Focal loss (handles class imbalance, reduces false positives)

### Training Process
- **Trigger**: Manual via UI or scheduled (every 24h)
- **Singleton Execution**: New training cancels all pending/running trainings
- **Task Management**: Uses Redis to track current training task ID
- **Revocation**: SIGKILL for running task, graceful cancel for queued tasks
- **Data**: Positive signatures (user-labeled) + negative examples
- **Validation**: Time-series split (80/20)
- **Metrics**: MAE, Accuracy, F1-score
- **GPU**: NVIDIA CUDA (fallback to CPU)
- **Checkpoints**: Saved in `/models` with metadata JSON

### Detection Process
- **Frequency**: Every 5 minutes on latest data
- **Window**: Sliding 599-point sequences
- **Thresholds**: Configurable confidence + power minimum
- **Output**: Stored in `appliance_detections` table
- **Real-time**: Published via Redis → SSE → Frontend

## Frontend Features

### Real-time Dashboard
- **Live Power Chart**: Chart.js with time-series consumption data
- **Signature Creation**: Click & drag on chart to select time ranges
- **Appliance Management**: Autocomplete for existing/new appliances
- **Fine-tuning**: Second-level precision for signature boundaries
- **Training Control**: Manual training trigger + session history
- **Metrics Visualization**: Training accuracy, loss, quality scores
- **SSE Streaming**: No polling, instant updates on new data/detections
- **Annotations Toggle**: Switch between displaying detections (default) or signatures on the graph
  - Detections: Shows real-time appliance detections with colored zones
  - Signatures: Shows training signatures with dashed borders and labels
- **Synchronized Views**: Detection list automatically syncs with the visible time range in the consumption chart

### Key Components
- `ConsumptionChart`: Interactive power consumption graph with signature selection and annotations toggle. Updates global visible time range via ChartContext
- `SignaturesList`: Manage training signatures (positive/negative examples)
- `DetectionsList`: Real-time appliance detection feed with validation. Filters detections based on the visible time range from ConsumptionChart
- `CurrentModel`: Training session status and metrics dashboard
- `ChartContext`: React context that shares the visible time range between ConsumptionChart and DetectionsList

## API Endpoints

### REST API (FastAPI)
- `GET /api/consumption/latest`: Latest Linky measurement
- `GET /api/consumption/history`: Time-range query with aggregation
- `GET /api/appliances`: List managed appliances
- `POST /api/signatures`: Create training signature
- `GET /api/training/sessions`: Training history (paginated)
- `POST /api/training/start`: Trigger model training
- `GET /api/detections`: Recent detections with filters

### WebSocket/SSE Streams
- `/ws/consumption`: Real-time consumption updates
- `/ws/detections`: Live appliance detections
- `/ws/training`: Training progress events

## Celery Tasks

### Sync Service
- **full_sync**: Initial 48h data load (on startup)
- **incremental_sync**: Every 5s, fetch new Linky data
- **Beat Schedule**: Configured via `celery beat`

### NILM Service
- **train_model**: Train CNN model on labeled signatures
- **analyze_consumption**: Detect appliances in recent data
- **init_cnn_database**: Initialize NILM tables
- **Beat Schedule**: 
  - Training: Every 24h (if new signatures)
  - Analysis: Every 5 minutes

## Configuration

### Environment Variables (.env)
```env
# Remote MySQL (Linky data source)
REMOTE_DB_HOST=192.168.1.x
REMOTE_DB_PORT=3306
REMOTE_DB_NAME=linky
REMOTE_DB_USER=linky_user
REMOTE_DB_PASSWORD=***
REMOTE_DB_TABLE=linky_realtime

# Local TimescaleDB
LOCAL_DB_HOST=timescaledb
LOCAL_DB_PORT=5432
LOCAL_DB_NAME=local_data
LOCAL_DB_USER=postgres
LOCAL_DB_PASSWORD=postgres

# Celery/Redis
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# NILM Configuration
NILM_MODEL_TYPE=gru
```

### Docker Compose
- **Networks**: `nilmia-network` for inter-service communication
- **Volumes**: 
  - `timescaledb_data`: Persistent database
  - `redis_data`: Redis persistence
  - `./models`: Shared model storage (host-mounted)
- **Health Checks**: TimescaleDB, Redis readiness probes
- **GPU**: NVIDIA runtime for cnn-worker (optional)

## Development Workflow

### Adding a New Appliance Signature
1. Frontend: Select time range on consumption chart
2. Frontend: Choose/create appliance via autocomplete
3. Backend: POST `/api/signatures` with `{appliance_name, start_time, end_time}`
4. Database: Insert into `appliance_signatures` table
5. Optional: Manually trigger training or wait for scheduled run

### Training a New Model
1. Trigger: Manual (UI button) or scheduled (Celery beat)
2. Celery: `train_model` task picks up signatures
3. NILM Service: Fetch signatures, preprocess, train CNN
4. Model: Saved to `/models/{timestamp}.keras` + metadata.json
5. Database: Update `training_sessions` with metrics
6. SSE: Push training completion event to frontend

### Real-time Detection Flow
1. Sync Service: New Linky data → TimescaleDB every 5s
2. NILM Service: Every 5 min, analyze recent data
3. Model: Predict appliances on sliding windows
4. Database: Insert detections into `appliance_detections`
5. Redis: Publish detection event
6. Backend: SSE stream to connected frontends
7. Frontend: Update detection list in real-time

## Monitoring & Debugging

### Service Access
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000

### Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f cnn-worker
docker-compose logs -f backend

# Celery tasks (via Flower UI or logs)
docker-compose logs -f cnn-worker | grep "Task"
```

### Common Issues
- **No GPU**: Check `nvidia-smi`, ensure `runtime: nvidia` in docker-compose
- **Missing data**: Verify sync-worker logs, check MySQL connectivity
- **Slow training**: Reduce `SEQUENCE_LENGTH` or use smaller dataset
- **False positives**: Adjust confidence threshold, add negative signatures

## Key Files

### Backend Service
- `src/main.py`: FastAPI application, API routes, SSE endpoints
- `src/database.py`: TimescaleDB manager, SQL queries
- `src/config.py`: Settings from environment variables

### NILM CNN Service
- `src/seq2point_nilm.py`: CNN model architecture, training, inference
- `src/tasks.py`: Celery tasks (train, analyze)
- `src/database.py`: Database access for signatures/detections

### Frontend Service
- `src/App.js`: Main React application
- `src/components/ConsumptionChart.js`: Interactive power chart
- `src/services/websocket.js`: SSE connection management
- `src/services/api.js`: REST API client

### Sync Service
- `src/tasks.py`: Celery sync tasks (full/incremental)
- `src/database.py`: MySQL → TimescaleDB sync logic

## Performance Considerations

### Database
- TimescaleDB compression enabled for old data
- Indexes on `time` column (hypertable)
- Connection pooling (10 connections, 20 max overflow)

### Model Inference
- Batch processing for efficiency
- GPU memory growth enabled (avoid OOM)
- Model caching (avoid reload on each detection)

### Real-time Updates
- SSE instead of polling (reduces server load)
- Redis pub/sub for event broadcasting
- Debouncing on frontend to avoid UI thrashing

## Future Enhancements
- Multi-user support with authentication
- Appliance energy cost estimation
- Anomaly detection (unusual consumption patterns)
- Mobile app with push notifications
- Historical trend analysis and predictions
