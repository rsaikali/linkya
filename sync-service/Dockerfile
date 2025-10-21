FROM python:3.13-slim

# Configuration de la timezone
ENV TZ=Europe/Paris
RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Installation de uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copie des fichiers de dépendances
COPY pyproject.toml ./

# Installation des dépendances
RUN uv pip install --system -r pyproject.toml

# Copie du code source
COPY src/ ./src/

# Variables d'environnement par défaut
ENV PYTHONUNBUFFERED=1
ENV CELERY_BROKER_URL=redis://redis:6379/0
ENV CELERY_RESULT_BACKEND=redis://redis:6379/0

CMD ["celery", "-A", "src.tasks.celery_app", "worker", "--loglevel=info"]
