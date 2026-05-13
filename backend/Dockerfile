FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libtiff6 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --upgrade pip uv \
    && uv pip install --system \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -e .

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY scripts/ ./scripts/

RUN groupadd -r appuser && useradd -r -g appuser appuser && chown -R appuser:appuser /app

USER appuser
