# Build stage - contains build dependencies
FROM python:3.13-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_VERSION=0.9.7 \
    VIBE_TRADING_HOME=/opt/vibe-trading \
    VIBE_TRADING_AGENT_DIR=/usr/local/lib/python3.13/site-packages

WORKDIR /app

# Install build dependencies (removed git - not needed)
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        gcc \
        g++ \
        pkg-config \
        libssl-dev \
        libffi-dev \
        libpq-dev \
        libsqlite3-dev \
        ca-certificates \
        gnupg \
        && rm -rf /var/lib/apt/lists/*

# Ensure critical system libraries are upgraded to patched versions
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --only-upgrade libgnutls30 libgcrypt20 || true && \
    rm -rf /var/lib/apt/lists/*

# Install uv and Python packages as wheels
# hadolint ignore=DL3013
RUN pip install --no-cache-dir "uv==${UV_VERSION}" && \
    pip install --no-cache-dir vibe-trading-ai

# Copy and install application
COPY pyproject.toml README.md ./
COPY src/ src/
RUN uv pip install --system -e . --no-cache

# Runtime stage - minimal image with only runtime dependencies
FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIBE_TRADING_HOME=/opt/vibe-trading \
    VIBE_TRADING_AGENT_DIR=/usr/local/lib/python3.13/site-packages

WORKDIR /app

# Install ONLY runtime dependencies
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        supervisor \
        libpq5 \
        libsqlite3-0 \
        gnupg \
        && rm -rf /var/lib/apt/lists/* && \
    apt-get autoremove -y && \
    apt-get clean

# Upgrade critical system libraries in runtime image to patched versions
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --only-upgrade libgnutls30 libgcrypt20 || true && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js 20 (LTS) for opencode-ai runtime
# hadolint ignore=DL3008
RUN mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key -o /tmp/nodesource.gpg && \
    gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg /tmp/nodesource.gpg && \
    rm -f /tmp/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get autoremove -y && \
    apt-get clean

# Install opencode-ai globally via npm (needed at runtime)
# hadolint ignore=DL3016
RUN npm install -g opencode-ai && \
    npm cache clean --force

# Copy Python packages and application from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

# Create OpenCode configuration
RUN mkdir -p /etc/opencode && \
    python -c "import os, json; print(json.dumps({'\$schema': 'https://opencode.ai/config.json', 'mcp': {'vibe-trading': {'type': 'local', 'command': ['vibe-trading-mcp'], 'enabled': True, 'environment': {'VIBE_TRADING_HOME': os.environ['VIBE_TRADING_HOME']}}}}, indent=2))" > /etc/opencode/config.json

# Create appuser and setup permissions
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /home/appuser/.config/opencode /home/appuser/.vibe-trading /opt/vibe-trading /var/log/supervisor /home/appuser/OpenBBUserData/cache/openbb_akshare /app/.venv && \
    cp /etc/opencode/config.json /home/appuser/.config/opencode/config.json && \
    chown -R appuser:appuser /app /home/appuser ${VIBE_TRADING_AGENT_DIR} /opt/vibe-trading /var/log/supervisor && \
    chmod -R 777 /app/.venv

# Copy remaining files
COPY docs/equity.db /home/appuser/OpenBBUserData/cache/openbb_akshare/equity.db
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chown appuser:appuser /home/appuser/OpenBBUserData/cache/openbb_akshare/equity.db

EXPOSE 8001 4096 8899

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
