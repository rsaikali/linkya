# Linkya — Tech Stack

## Python services

| Service | Python | Key deps |
|---|---|---|
| backend-service | >=3.13 | FastAPI >=0.115, uvicorn[standard] >=0.32, psycopg[binary] >=3.2 (async), SQLAlchemy >=2.0, Pydantic >=2 |
| nilm-service | >=3.12 | FastAPI, APScheduler >=3.10, tensorflow-cpu 2.16–2.18 (x86) / tensorflow (arm64), numpy <2.1, pandas >=2.2, scikit-learn >=1.5, scipy >=1.14, hmmlearn >=0.3, psycopg2-binary |
| ha-ingest-service | >=3.13 | aiomqtt >=2.3, httpx >=0.27, psycopg[binary] >=3.2, SQLAlchemy >=2.0, loguru |
| ha-publish-service | >=3.13 | aiomqtt >=2.3, httpx >=0.27, psycopg[binary] >=3.2, SQLAlchemy >=2.0, loguru |

Note: backend-service pyproject.toml still lists `celery[redis]` and `websockets` — these are not used in the current architecture (no Celery, no WebSocket).

## Frontend

- React SPA (JavaScript), served as static build by backend in prod.
- Dev: separate `frontend-service/` container with own node_modules.

## Infrastructure

- PostgreSQL 16 Alpine (Docker volume `postgres_data`).
- Docker Compose: `docker-compose.yml` = prod, `docker-compose.override.yml` = dev (auto-loaded).
- Prod: Raspberry Pi (aarch64), CI/CD via self-hosted GitHub Actions runner.
- `DOCKER_BUILDKIT=0` on Pi (`make deploy`) — classic builder avoids snapshotter corruption on this Pi.

## Build / tooling

- **Package manager**: `uv` preferred (each service has its own `pyproject.toml` + `hatchling` build backend).
- **Linter**: `flake8` + `isort`. Not ruff (project-specific exception to global CLAUDE.md preference — flake8 is explicit in Makefile).
- **isort config** (root `pyproject.toml`): profile=black, line_length=150, multi_line_output=3, known_first_party=`src`.
- **No test suite** — no pytest, no test files anywhere.
- **Logging**: `loguru` in ha-ingest + ha-publish; stdlib `logging` in backend + nilm-service.
