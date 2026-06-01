FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_VERSION=0.9.7

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        gcc \
        g++ \
        pkg-config \
        libssl-dev \
        libffi-dev \
        libpq-dev \
        libsqlite3-dev \
        && rm -rf /var/lib/apt/lists/*

RUN pip install "uv>=${UV_VERSION}" && \
    uv venv

COPY pyproject.toml .
COPY README.md .
COPY src/ src/

RUN uv pip install --system -e .

RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8001

CMD ["uv", "run", "uvicorn", "openbb_app.main:app", "--host", "0.0.0.0", "--port", "8001"]
