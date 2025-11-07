# Copilot Instructions - Linkya

## Project Overview

**Linkya** is a NILM (Non-Intrusive Load Monitoring) platform for analyzing electrical consumption data from Linky smart meters. It uses machine learning (Seq2Point deep learning with TensorFlow/Keras) to automatically detect and disaggregate individual appliances from aggregate power consumption data.

**Repository Stats:**
- Size: ~710MB (including dependencies and data)
- Languages: Python (23 files), JavaScript/React (18 files)
- Architecture: Microservices with Docker Compose
- Python Version: 3.12-3.13
- Node Version: 20

**Tech Stack:**
- **Backend:** Python 3.12-3.13, FastAPI, Celery, SQLAlchemy, TensorFlow/Keras
- **Frontend:** React 18, Material-UI, Chart.js, axios
- **Database:** TimescaleDB (PostgreSQL extension for time-series)
- **Message Broker:** Redis
- **Containerization:** Docker Compose with health checks
- **Package Managers:** uv (Python), npm (JavaScript)

## Critical Coding Standards

**LANGUAGE REQUIREMENTS (STRICTLY ENFORCED):**
- All Python code, comments, docstrings, and logs: **ENGLISH ONLY**
- All JavaScript/React UI text, labels, messages: **FRENCH ONLY**
- Backend API responses: English
- Frontend display text: French

**Code Style:**
- Python: Follow PEP 8 guidelines strictly
- JavaScript/React: Follow Airbnb style guide
- **NO emojis or emoticons** in code or logs (note: currently present in logs, should be removed if modifying)
- No unnecessary documentation files - update existing README files only
- Delete temporary scripts after use

**Important:** When modifying a service, update all related services accordingly. This is a tightly coupled microservices system.

## Project Architecture

### Service Overview (10 containers)

```
┌─────────────────┐
│   frontend      │  Nginx reverse proxy (port 80)
│   (nginx)       │  Routes to backend API and React dev server
└────────┬────────┘
         │
    ┌────┴──────────────────────────┐
    │                               │
┌───▼────────────┐          ┌───────▼──────┐
│   react-dev    │          │   backend    │
│   (port 3000)  │          │  (port 8000) │
│   React dev    │          │  FastAPI     │
│   with HMR     │          │  REST API    │
└────────────────┘          └──────┬───────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
            ┌───────▼─────┐  ┌─────▼──────┐  ┌───▼──────────┐
            │ sync-worker │  │ nilm-worker│  │ timescaledb  │
            │ sync-beat   │  │ nilm-beat  │  │ (port 5432)  │
            │ (Celery)    │  │ (Celery+GPU)│ │              │
            └──────┬──────┘  └─────┬──────┘  └──────────────┘
                   │               │
                   └───────┬───────┘
                           │
                    ┌──────▼──────┐
                    │    redis    │
                    │ (port 6379) │
                    └─────────────┘

Additional: pgweb (port 8081) - PostgreSQL web UI
```

**Service Dependencies (start order matters):**
1. timescaledb, redis (infrastructure)
2. sync-worker, sync-beat (data sync + DB init)
3. nilm-worker, nilm-beat (ML processing + table init)
4. backend (API depends on DB)
5. react-dev (dev server)
6. frontend (nginx routing)

### Directory Structure

```
/
├── .env                          # REQUIRED: Environment config (create from .env.example)
├── .env.example                  # Template with all configuration variables
├── docker-compose.yml            # Service orchestration with health checks
├── Makefile                      # All build/run/test commands (USE THIS)
├── AGENTS.md                     # Agent coding guidelines
├── README.md                     # Main documentation
├── backend-service/
│   ├── Dockerfile                # Python 3.12-slim + FastAPI
│   ├── pyproject.toml            # Dependencies (installed via pip)
│   ├── requirements.txt          # Legacy requirements file
│   └── src/
│       ├── main.py               # FastAPI app (1376 lines)
│       ├── config.py             # Pydantic settings
│       └── db/                   # Database managers and models
├── frontend-service/
│   ├── Dockerfile.dev            # React dev server (Node 20)
│   ├── Dockerfile.nginx          # Nginx reverse proxy
│   ├── nginx.conf                # Routing config (API, WebSocket, docs)
│   ├── package.json              # npm dependencies
│   └── src/
│       ├── App.js                # Main React component
│       ├── components/           # React components (French UI)
│       ├── services/             # API and WebSocket clients
│       └── context/              # React contexts
├── sync-service/
│   ├── Dockerfile                # Python 3.13-slim + uv
│   ├── pyproject.toml            # Dependencies (installed via uv)
│   ├── scripts/entrypoint-beat.sh # DB init + Celery beat startup
│   └── src/
│       ├── tasks.py              # Celery tasks for Linky sync
│       └── database.py           # MySQL→TimescaleDB sync logic
└── nilm-service/
    ├── Dockerfile                # TensorFlow GPU + Python 3.12
    ├── pyproject.toml            # ML dependencies (installed via uv)
    ├── scripts/entrypoint-beat.sh # Table init + Celery beat startup
    └── src/
        ├── tasks.py              # Celery tasks for ML training/detection
        ├── seq2point_nilm.py     # Seq2Point ML model (2000+ lines)
        ├── morphology.py         # Signal processing utilities
        └── database.py           # NILM table management
```

## Build, Run, and Validation

### Prerequisites

1. **REQUIRED:** Docker and Docker Compose installed
2. **REQUIRED:** Create `.env` file from `.env.example` and configure:
   - `REMOTE_DB_*` variables (MySQL Linky source database)
   - Leave other variables at defaults for local development
3. **OPTIONAL:** NVIDIA GPU with CUDA for NILM acceleration (auto-falls back to CPU)

### Build and Start Commands

**ALWAYS use Makefile commands - they handle dependencies and proper sequencing:**

```bash
# First time setup - REQUIRED
cp .env.example .env
# Edit .env with your MySQL Linky credentials

# Build all images (uses DOCKER_BUILDKIT=1)
make build

# Start all services (includes healthcheck waits)
make up

# Check service status
make status

# View logs (all services)
make logs

# View specific service logs
docker compose logs -f backend
docker compose logs -f nilm-worker
docker compose logs -f sync-worker
```

**Service Startup Sequence (automatic via depends_on + healthcheck):**
1. TimescaleDB and Redis start and become healthy (~10-15 seconds)
2. sync-beat runs `init_local_db()` via entrypoint script
3. nilm-beat runs `init_tables()` via entrypoint script
4. Workers start processing tasks
5. Backend API becomes available (port 8000)
6. React dev server starts (port 3000)
7. Nginx proxy becomes available (port 80)

**Verification:**
```bash
# All services should show "Up" and "healthy" status
make status

# API should return healthy status
curl http://localhost:8000/health

# Frontend should be accessible
curl http://localhost/
```

### Stop and Clean Commands

```bash
# Stop all services (preserves volumes/data)
make down

# Stop and remove volumes (DESTRUCTIVE - deletes all data)
make clean
```

### NILM Training and Detection

```bash
# Trigger NILM model training (via REST API)
make train

# Run appliance detection
make detect

# View detection statistics
make feedback-stats
make signatures-stats

# View model status
make model-status
make model-compare

# Clean detections (keeps signatures)
make detections-clean

# Rollback to previous model
make model-rollback
```

### Accessing Services

| Service | URL | Purpose |
|---------|-----|---------|
| **Frontend** | http://localhost | Main React application |
| **Swagger UI** | http://localhost/docs | Interactive API documentation |
| **ReDoc** | http://localhost/redoc | Alternative API docs |
| **pgweb** | http://localhost:8081 | TimescaleDB web UI |
| **Backend Health** | http://localhost:8000/health | Health check endpoint |

## Development Workflow

### Modifying Python Services (sync, nilm, backend)

**All Python services use volume mounts for hot reload:**

1. Edit Python files in `{service}/src/` directories
2. Changes are reflected immediately (no rebuild needed)
3. For dependency changes:
   ```bash
   # Edit pyproject.toml
   # Rebuild specific service
   docker compose build {service-name}
   docker compose up -d {service-name}
   ```

**Dependency Management:**
- **backend-service:** Uses `pip install -r requirements.txt`
- **sync-service, nilm-service:** Use `uv pip install -r pyproject.toml`
- NEVER mix uv and pip in the same service
- ALWAYS use `--system` flag with uv in containers

**Testing (limited):**
Only sync-service has pytest configured:
```bash
# Run sync-service tests
docker compose exec sync-worker pytest
```

**No CI/CD is configured - manual testing required.**

### Modifying React Frontend

**Frontend has hot module replacement (HMR) enabled:**

1. Edit files in `frontend-service/src/`
2. Browser auto-refreshes on save
3. **WSL2 users:** If HMR doesn't work, run: `make frontend-reload`

**Dependency changes:**
```bash
# Edit package.json
docker compose build react-dev
docker compose up -d react-dev
```

**Build production bundle:**
```bash
cd frontend-service
npm run build
# Output in build/ directory
```

### Database Schema Changes

**TimescaleDB tables are initialized by entrypoint scripts:**

- **sync-service:** `scripts/entrypoint-beat.sh` → `database.init_local_db()`
- **nilm-service:** `scripts/entrypoint-beat.sh` → `database.init_tables()`

**To modify schema:**
1. Edit `src/database.py` in the relevant service
2. Stop services: `make down`
3. **DESTRUCTIVE:** Delete volume: `docker volume rm linkya_timescaledb_data`
4. Restart: `make up` (will reinitialize with new schema)

**Non-destructive schema updates:**
- Write migration SQL manually
- Execute via pgweb (http://localhost:8081) or psql:
  ```bash
  docker compose exec timescaledb psql -U postgres -d linkya_db
  ```

### Modifying Docker Configuration

**After editing Dockerfile or docker-compose.yml:**
```bash
make down
make build
make up
```

**Note:** DOCKER_BUILDKIT=1 is used in Makefile for optimized builds.

## Common Issues and Workarounds

### Issue: Services fail to start

**Symptom:** Containers exit or restart loop

**Solution:**
1. Check `.env` file exists and is properly configured
2. Ensure REMOTE_DB_* credentials are correct
3. Check logs: `make logs`
4. Verify health checks: `make status`
5. Clean restart: `make clean && make build && make up`

### Issue: Frontend hot reload not working (WSL2)

**Symptom:** Changes to React files don't trigger browser refresh

**Solution:**
```bash
make frontend-reload
```

This touches `index.js` to trigger webpack rebuild.

### Issue: NILM worker crashes with CUDA errors

**Symptom:** nilm-worker exits with TensorFlow GPU errors

**Solution:**
NILM auto-falls back to CPU. To force CPU mode:
1. Edit `docker-compose.yml`: Remove `runtime: nvidia` from nilm-worker
2. Edit `.env`: Set `USE_GPU=false`
3. Restart: `make down && make up`

### Issue: Database connection refused

**Symptom:** Backend or workers can't connect to TimescaleDB

**Solution:**
1. Wait for healthcheck: `docker compose ps` should show "healthy"
2. Typical startup time: 10-15 seconds
3. Check database logs: `docker compose logs timescaledb`

### Issue: Celery tasks not executing

**Symptom:** No logs from workers, tasks timeout

**Solution:**
1. Verify Redis is healthy: `docker compose ps redis`
2. Check worker logs: `docker compose logs sync-worker nilm-worker`
3. Restart workers: `docker compose restart sync-worker nilm-worker`
4. Test Redis connection:
   ```bash
   docker compose exec redis redis-cli ping
   # Should return: PONG
   ```

## File Location Guide

**To modify:**
- **API endpoints:** `backend-service/src/main.py`
- **Database models:** `backend-service/src/db/models.py`, `nilm-service/src/database.py`
- **Celery tasks:** `sync-service/src/tasks.py`, `nilm-service/src/tasks.py`
- **ML model:** `nilm-service/src/seq2point_nilm.py`
- **React components:** `frontend-service/src/components/`
- **API client:** `frontend-service/src/services/api.js`
- **WebSocket client:** `frontend-service/src/services/websocket.js`
- **Environment config:** `.env` (runtime), `.env.example` (template)
- **Service config:** `{service}/src/config.py`
- **Nginx routing:** `frontend-service/nginx.conf`
- **Dependencies:** 
  - Python: `pyproject.toml` (sync/nilm), `requirements.txt` (backend)
  - JavaScript: `frontend-service/package.json`

## Key Configuration Files

- **docker-compose.yml:** Service definitions, ports, volumes, health checks, GPU config
- **Makefile:** All available commands (run `make help`)
- **.env:** Environment variables (NEVER commit this)
- **.env.example:** Template with documentation
- **nginx.conf:** HTTP/WebSocket routing, proxy configuration
- **entrypoint scripts:** Database initialization logic

## Validation Steps Before Submitting Changes

**ALWAYS perform these checks:**

1. **Services start successfully:**
   ```bash
   make down
   make build
   make up
   make status  # All should be "Up" and "healthy"
   ```

2. **API responds:**
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status": "healthy", "timestamp": "..."}
   ```

3. **Frontend loads:**
   ```bash
   curl http://localhost/
   # Should return HTML
   ```

4. **No Python errors:**
   ```bash
   make logs | grep -i "error\|exception\|traceback"
   # Should have minimal output
   ```

5. **Coding standards:**
   - Python code/logs in English
   - React UI text in French
   - No emojis in code or logs
   - PEP 8 compliance for Python
   - Airbnb style for JavaScript

6. **Related services updated:**
   - If modifying database schema, update all services that access those tables
   - If changing API contract, update both backend and frontend
   - If adding environment variables, update .env.example

## Trust These Instructions

These instructions have been validated against the running system. When implementing changes:

1. **Start here** - don't search unless information is missing or contradictory
2. **Use Makefile** - all common operations are scripted
3. **Check logs** - services log extensively at DEBUG level
4. **Verify health** - use health check endpoints and `make status`
5. **Test incrementally** - restart individual services to test changes
6. **Search only if needed** - if these instructions don't cover your use case

The Makefile and docker-compose.yml are the source of truth for build and run commands.
