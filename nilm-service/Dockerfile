# Dockerfile for nilm-service
# Python 3.12 with TensorFlow/Keras + CUDA
# Optimized single-stage build

FROM tensorflow/tensorflow:latest-gpu

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    TF_FORCE_GPU_ALLOW_GROWTH=true \
    LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH} \
    TF_CPP_MIN_LOG_LEVEL=2 \
    TF_ENABLE_ONEDNN_OPTS=0 \
    PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python \
    PYTHONWARNINGS=ignore::UserWarning:google.protobuf.runtime_version,ignore::DeprecationWarning

# Install system dependencies and cuDNN 9, clean up in single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    && wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb \
    && dpkg -i cuda-keyring_1.1-1_all.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libcudnn9-cuda-12 \
    && rm -rf /var/lib/apt/lists/* cuda-keyring_1.1-1_all.deb \
    && apt-get clean

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies with uv and clean up Python cache
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r pyproject.toml \
    && find /usr/local/lib/python3.12 -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.12 -type f -name '*.pyc' -delete 2>/dev/null || true

# Copy source code
COPY src/ ./src/

# Copy entrypoint script for beat
COPY scripts/entrypoint-beat.sh /app/scripts/
RUN chmod +x /app/scripts/entrypoint-beat.sh

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "from src.database import db_manager; db_manager.test_connection()" || exit 1

# Default entry point
CMD ["celery", "-A", "src.tasks.celery_app", "worker", "--loglevel=info", "--pool=solo", "-Q", "nilm_cnn"]
