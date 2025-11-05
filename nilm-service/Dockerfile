# Dockerfile pour nilm-service
# Python 3.12 avec TensorFlow/Keras + CUDA

FROM tensorflow/tensorflow:latest-gpu

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    TF_FORCE_GPU_ALLOW_GROWTH=true \
    LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH} \
    # Désactiver les warnings TensorFlow/CUDA verbeux
    TF_CPP_MIN_LOG_LEVEL=2 \
    # Désactiver les warnings oneDNN
    TF_ENABLE_ONEDNN_OPTS=0 \
    # Désactiver les warnings Protobuf (incompatibilité connue, non critique)
    PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python \
    # Désactiver les warnings Python
    PYTHONWARNINGS=ignore::UserWarning:google.protobuf.runtime_version,ignore::DeprecationWarning

# Installation des dépendances système et cuDNN 9
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    python3-pip \
    wget \
    gnupg \
    && wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb \
    && dpkg -i cuda-keyring_1.1-1_all.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libcudnn9-cuda-12 \
        libcudnn9-dev-cuda-12 \
    && rm -rf /var/lib/apt/lists/* cuda-keyring_1.1-1_all.deb

# Installation de uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Répertoire de travail
WORKDIR /app

# Copie des fichiers de dépendances
COPY pyproject.toml ./

# Installation des dépendances avec uv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install -r pyproject.toml

# Copie du code source
COPY src/ ./src/

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "from src.database import db_manager; db_manager.test_connection()" || exit 1

# Point d'entrée par défaut
CMD ["celery", "-A", "src.tasks.celery_app", "worker", "--loglevel=info", "--pool=solo", "-Q", "nilm_cnn"]
