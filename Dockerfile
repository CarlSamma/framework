# ==============================================================================
# Multi-stage Dockerfile per APP_Opzione_Ibrida
# Targets: base | hydra | chronos | tap | adapters
# ==============================================================================

# ------------------------------------------------------------------------------
# BASE — dipendenze Python comuni a tutti i servizi
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS base

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python deps comuni
COPY requirements-hybrid.txt .
RUN pip install --no-cache-dir -r requirements-hybrid.txt

# Copia sorgenti
COPY src/ ./src/
COPY .env.example .env.example

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# ------------------------------------------------------------------------------
# HYDRA — FastAPI API server
# ------------------------------------------------------------------------------
FROM base AS hydra

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.hydra.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2"]

# ------------------------------------------------------------------------------
# CHRONOS — Temporal workflow worker
# ------------------------------------------------------------------------------
FROM base AS chronos

CMD ["python", "-m", "src.chronos.worker"]

# ------------------------------------------------------------------------------
# TAP — Kafka CDC consumer engine
# ------------------------------------------------------------------------------
FROM base AS tap

CMD ["python", "-m", "src.tap.engine"]

# ------------------------------------------------------------------------------
# ADAPTERS — connettori sistemi esterni
# ------------------------------------------------------------------------------
FROM base AS adapters

CMD ["python", "-m", "src.adapters.runner"]
