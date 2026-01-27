# Test Coverage Analysis Report

## Executive Summary

**Current State:** The Linkya codebase contains **12,680 lines of production code** across 4 services with **zero automated tests**.

| Service | Lines of Code | Test Files | Coverage |
|---------|---------------|------------|----------|
| Backend Service (FastAPI) | 2,322 | 0 | 0% |
| Sync Service (Celery) | 371 | 0 | 0% |
| NILM Service (ML/Celery) | 3,825 | 0 | 0% |
| Frontend (React) | 6,162 | 0 | 0% |
| **Total** | **12,680** | **0** | **0%** |

---

## Priority Areas for Test Improvement

### Priority 1: CRITICAL - Backend API Tests

**Location:** `backend-service/src/api/`

The backend exposes 21 REST endpoints handling real energy data. These should be tested first as they're the primary interface for all clients.

**Files requiring tests:**

| File | Routes | Risk Level |
|------|--------|------------|
| `api/consumption.py` | 3 routes | HIGH - Core data retrieval |
| `api/appliances.py` | 4 routes | HIGH - CRUD operations |
| `api/signatures.py` | 3 routes | MEDIUM - Training data |
| `api/detections.py` | 3 routes | MEDIUM - Detection results |
| `api/nilm.py` | 5 routes | HIGH - ML triggering |
| `api/system.py` | 3 routes | LOW - Health checks |

**Recommended test types:**
- Unit tests with mocked database repositories
- Integration tests with test database
- Validation tests for request/response models

**Example test file structure:**
```
backend-service/
├── tests/
│   ├── conftest.py              # Fixtures, test database setup
│   ├── unit/
│   │   ├── test_consumption_api.py
│   │   ├── test_appliances_api.py
│   │   ├── test_signatures_api.py
│   │   ├── test_detections_api.py
│   │   └── test_nilm_api.py
│   └── integration/
│       └── test_api_integration.py
```

**Dependencies to add to `pyproject.toml`:**
```toml
[tool.uv]
dev-dependencies = [
    "pytest>=8.3.3",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",  # For TestClient
    "pytest-cov>=4.1.0",
]
```

---

### Priority 2: CRITICAL - Database Repository Tests

**Location:** `backend-service/src/db/`

The database layer handles all TimescaleDB operations including time-series aggregation.

**Files requiring tests:**

| File | Functions | Risk Level |
|------|-----------|------------|
| `db/consumption.py` | 5 methods | HIGH - Time-series queries |
| `db/appliances.py` | 4 methods | MEDIUM - CRUD |
| `db/signatures.py` | 3 methods | MEDIUM - Training data |
| `db/detections.py` | 4 methods | MEDIUM - Detection storage |
| `db/models_db.py` | 3 methods | LOW - Model metadata |

**Key test scenarios:**
1. Time-series aggregation with different intervals
2. Date range filtering
3. Pagination behavior
4. Empty result handling
5. Database transaction integrity

---

### Priority 3: HIGH - Sync Service Tests

**Location:** `sync-service/src/`

The sync service is critical infrastructure - it transfers data from remote MySQL to local TimescaleDB.

**Note:** pytest is already configured in `sync-service/pyproject.toml`

**Files requiring tests:**

| File | Functions | Risk Level |
|------|-----------|------------|
| `tasks.py` | `full_sync()`, `incremental_sync()` | CRITICAL |
| `database.py` | DB connection management | HIGH |

**Key test scenarios:**
1. Full sync with mocked MySQL data
2. Incremental sync timestamp handling
3. Data transformation accuracy
4. Error recovery when remote DB unavailable
5. Duplicate data handling

**Example tests:**
```python
# tests/test_tasks.py
import pytest
from unittest.mock import Mock, patch

def test_full_sync_fetches_48_hours():
    """Full sync should fetch 48 hours of historical data."""
    pass

def test_incremental_sync_respects_last_timestamp():
    """Incremental sync should only fetch data after last sync."""
    pass

def test_sync_handles_remote_db_connection_failure():
    """Sync should handle MySQL connection failures gracefully."""
    pass
```

---

### Priority 4: HIGH - NILM ML Pipeline Tests

**Location:** `nilm-service/src/nilm/`

This is the most complex service (3,825 lines) handling machine learning for appliance detection.

**Files requiring tests:**

| File | Functions | Risk Level |
|------|-----------|------------|
| `preprocessing.py` | Data pipeline | CRITICAL |
| `models/multioutput_model.py` | Neural network | HIGH |
| `detectors/change_point_detector.py` | Event detection | HIGH |
| `detectors/state_detector.py` | State classification | HIGH |
| `utils.py` | Utility functions | MEDIUM |
| `losses.py` | Custom loss functions | MEDIUM |
| `layers.py` | Custom Keras layers | MEDIUM |

**Key test scenarios:**
1. Preprocessing normalization accuracy
2. Model architecture validation
3. Change point detection with known signals
4. State detection with labeled data
5. Loss function gradient computation

**Dependencies to add:**
```toml
[tool.uv]
dev-dependencies = [
    "pytest>=8.3.3",
    "pytest-cov>=4.1.0",
]
```

---

### Priority 5: MEDIUM - WebSocket Tests

**Location:** `backend-service/src/websockets/`

Real-time communication channels for live updates.

**Files requiring tests:**

| File | Channels | Risk Level |
|------|----------|------------|
| `consumption.py` | `/ws/consumption` | MEDIUM |
| `detections.py` | `/ws/detections` | MEDIUM |
| `training.py` | `/ws/training` | MEDIUM |
| `import_progress.py` | `/ws/import` | LOW |

**Key test scenarios:**
1. Client connection/disconnection handling
2. Message broadcasting to multiple clients
3. Redis pub/sub integration
4. Connection timeout handling

---

### Priority 6: MEDIUM - Frontend Component Tests

**Location:** `frontend-service/src/`

React components with Material-UI and Chart.js.

**Files requiring tests:**

| File | Type | Risk Level |
|------|------|------------|
| `components/CombinedChart.js` | Chart rendering | HIGH |
| `components/AppliancesList.js` | Data display | MEDIUM |
| `components/DetectionsList.js` | Data display | MEDIUM |
| `components/SignatureModal.js` | User interaction | MEDIUM |
| `services/api.js` | API client | HIGH |
| `services/websocket.js` | WS client | HIGH |

**Dependencies to add:**
```json
{
  "devDependencies": {
    "@testing-library/react": "^14.0.0",
    "@testing-library/jest-dom": "^6.0.0",
    "@testing-library/user-event": "^14.0.0"
  }
}
```

---

## Recommended Testing Strategy

### Phase 1: Foundation (Week 1-2)
1. Set up pytest infrastructure in backend-service and nilm-service
2. Create test database fixtures
3. Write API endpoint tests for `consumption.py` (most used endpoint)
4. Write sync service tests (already has pytest configured)

### Phase 2: Core Coverage (Week 3-4)
1. Complete backend API test coverage
2. Database repository unit tests
3. NILM preprocessing pipeline tests
4. WebSocket connection tests

### Phase 3: ML & Frontend (Week 5-6)
1. NILM model and detector tests
2. React component tests
3. API client mocking tests

### Phase 4: Integration (Week 7-8)
1. End-to-end tests with docker-compose
2. Performance tests for NILM training
3. Load tests for API endpoints

---

## Test Configuration Templates

### Backend Service pytest.ini
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --cov=src --cov-report=html
```

### GitHub Actions CI Template
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: timescale/timescaledb:latest-pg15
        env:
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
      redis:
        image: redis:7
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: |
          pip install uv
          cd backend-service && uv sync --all-extras
      - name: Run tests
        run: |
          cd backend-service && pytest --cov
```

---

## Key Metrics to Target

| Metric | Current | Target (3 months) | Target (6 months) |
|--------|---------|-------------------|-------------------|
| Backend API Coverage | 0% | 80% | 90% |
| Sync Service Coverage | 0% | 70% | 85% |
| NILM Service Coverage | 0% | 50% | 75% |
| Frontend Coverage | 0% | 40% | 70% |
| Integration Tests | 0 | 10 | 25 |

---

## Summary of Recommendations

1. **Immediate Action:** Add pytest configuration to backend-service and create first API tests
2. **Quick Win:** Write sync-service tests (pytest already configured)
3. **High Impact:** Focus on consumption API and database layer tests first
4. **Risk Mitigation:** NILM preprocessing tests to prevent ML pipeline regressions
5. **CI/CD:** Set up GitHub Actions to run tests on every PR
