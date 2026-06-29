# ==============================================================================
# Multi-stage Dockerfile per APP_Opzione_Ibrida
# Targets: base | hydra | tap | adapters | chronos
#
# PYTHONPATH=/app/src  ->  consente import diretti tipo:
#   from tap.config import Settings
#   from hydra.v_genome import VGenome
# ==============================================================================

# ------------------------------------------------------------------------------
# BASE — dipendenze Python comuni
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY requirements-hybrid.txt .
RUN pip install --no-cache-dir -r requirements-hybrid.txt

COPY src/ ./src/

# CRITICO: PYTHONPATH punta a /app/src
# cosi' "from tap.config import ..." funziona direttamente
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# ------------------------------------------------------------------------------
# HYDRA-API  — FastAPI server (src/tap/api.py contiene l'app FastAPI)
# http://localhost:8000/docs
# ------------------------------------------------------------------------------
FROM base AS hydra

EXPOSE 8000

CMD ["uvicorn", "tap.api:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2"]

# ------------------------------------------------------------------------------
# TAP ENGINE  — core processing engine (src/tap/engine.py)
# ------------------------------------------------------------------------------
FROM base AS tap

CMD ["python", "-m", "tap.engine"]

# ------------------------------------------------------------------------------
# ADAPTERS  — stream listener X/Twitter (src/tap/stream_listener.py)
# ------------------------------------------------------------------------------
FROM base AS adapters

CMD ["python", "-m", "tap.stream_listener"]

# ------------------------------------------------------------------------------
# CHRONOS  — Temporal worker
# src/chronos/ ha solo __init__.py per ora -> usa tap.engine come fallback
# ------------------------------------------------------------------------------
FROM base AS chronos

CMD ["python", "-c", \
     "import tap; print('TAP chronos worker ready - implement src/chronos/worker.py to override')"]
