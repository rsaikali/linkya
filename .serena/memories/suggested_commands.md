# Linkya — Suggested Commands

## Dev (local, docker-compose.override.yml auto-loaded)

```bash
make up          # docker compose up -d (all services)
make down        # stop
make clean       # stop + delete volumes — WIPES ALL DATA, schema reset
make status      # docker compose ps
make logs        # tail all logs
make restart     # docker compose restart
make build       # DOCKER_BUILDKIT=1 build (dev)
```

## NILM triggers

```bash
make train       # POST http://localhost:8000/api/nilm/train
make detect      # POST http://localhost:8000/api/nilm/detect (full history)
```

## Quality

```bash
make lint        # flake8 + isort --check-only (all 4 Python service src dirs)
isort backend-service/src nilm-service/src ha-ingest-service/src ha-publish-service/src  # auto-fix imports
```

## Prod (Pi / CD)

```bash
make deploy      # DOCKER_BUILDKIT=0 prod build + up --remove-orphans + ps
```

## System utils (Darwin — non-standard)

- `grep` → `ugrep`
- `find` → `bfs`
- `sed` GNU 4.10 (Homebrew), `awk` GNU 5.4 (Homebrew)

## Service endpoints (dev)

- backend: `http://localhost:8000`
- nilm: internal Docker network only (`http://nilm:8001`)
- postgres: internal Docker network only
