# ============================
# Étape 1: Base système avec dépendances
# ============================
FROM nvidia/cuda:12.6.0-cudnn-runtime-ubuntu24.04 AS base

# Configuration de la timezone
ENV TZ=Europe/Paris
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Installation de Python 3.12 et dépendances de build (version par défaut d'Ubuntu 24.04)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    curl \
    cmake \
    g++ \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Installation de uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# ============================
# Étape 2: Construction des dépendances Python
# ============================
FROM base AS dependencies

WORKDIR /app

# Copie des fichiers de dépendances uniquement
COPY pyproject.toml .

# Création de l'environnement virtuel et installation des dépendances
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install -r pyproject.toml

# ============================
# Étape 3: Image finale runtime
# ============================
FROM nvidia/cuda:12.6.0-cudnn-runtime-ubuntu24.04 AS runtime

# Configuration de la timezone
ENV TZ=Europe/Paris
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Installation uniquement des runtime dependencies (sans les outils de build)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-venv \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copie de l'environnement virtuel depuis l'étape de build
COPY --from=dependencies /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copie du code source (cette étape change souvent)
COPY src/ ./src/

# Variables d'environnement pour CUDA
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

CMD ["celery", "-A", "src.tasks.celery_app", "worker", "--loglevel=info"]
