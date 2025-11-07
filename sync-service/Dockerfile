FROM python:3.12-slim-bookworm

# Environment variables
ENV TZ=Europe/Paris \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CELERY_BROKER_URL=redis://redis:6379/0 \
    CELERY_RESULT_BACKEND=redis://redis:6379/0

# Install tzdata and clean up in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies and clean up
RUN uv pip install --system -r pyproject.toml \
    && find /usr/local/lib/python3.12 -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.12 -type f -name '*.pyc' -delete 2>/dev/null || true

# Copy source code
COPY src/ ./src/

# Copy entrypoint script for beat
COPY scripts/entrypoint-beat.sh /app/scripts/
RUN chmod +x /app/scripts/entrypoint-beat.sh

CMD ["celery", "-A", "src.tasks.celery_app", "worker", "--loglevel=info"]
