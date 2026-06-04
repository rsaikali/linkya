# Build context = repo root (see docker-compose.yml). Paths are repo-relative.

# ── Stage 1: build the React SPA ────────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /fe
COPY frontend-service/package*.json ./
RUN npm ci --silent
COPY frontend-service/ ./
RUN npm run build

# ── Base python (shared by dev + prod) ──────────────────────────────────────
FROM python:3.12-slim-bookworm AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend-service/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend-service/src/ ./src/

# ── Dev target: API only, hot reload (compose mounts src + sets command) ─────
FROM base AS dev
ENV STATIC_DIR=/nonexistent
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Prod target: bundle React build, FastAPI serves it ──────────────────────
FROM base AS prod
COPY --from=frontend /fe/build /app/static
ENV STATIC_DIR=/app/static
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
