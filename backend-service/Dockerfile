# Backend FastAPI with Python 3.12
FROM python:3.12-slim-bookworm

# Environment variables for Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies and clean up in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy dependency files first for better cache usage
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt \
    && find /usr/local/lib/python3.12 -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.12 -type f -name '*.pyc' -delete 2>/dev/null || true

# Copy source code
COPY src/ ./src/

# Expose FastAPI port
EXPOSE 8000

# Start command (uvicorn)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "debug"]
