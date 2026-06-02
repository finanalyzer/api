FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_VERSION=0.9.7 \
    VIBE_TRADING_HOME=/opt/vibe-trading \
    VIBE_TRADING_AGENT_DIR=/usr/local/lib/python3.13/site-packages

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
        ca-certificates \
        gnupg \
        supervisor \
        && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 (LTS) from NodeSource to get npm
RUN mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install opencode globally via npm
RUN npm install -g opencode-ai

# ---------------------------------------------------------------------------
# Vibe-Trading installation
# ---------------------------------------------------------------------------
# Install Vibe-Trading from PyPI (vibe-trading-ai). The package ships three
# entry points: `vibe-trading` (CLI/TUI), `vibe-trading serve` (FastAPI web),
# and `vibe-trading-mcp` (Model Context Protocol server exposing 22 finance
# research tools to any MCP-compatible client).
# Configuration is provided at runtime by bind-mounting the host's `.env` to
# `${VIBE_TRADING_AGENT_DIR}/.env` (see docker-compose.yml).
RUN pip install --no-cache-dir vibe-trading-ai

# ---------------------------------------------------------------------------
# OpenCode configuration for vibe-trading-mcp
# ---------------------------------------------------------------------------
# Register the vibe-trading-mcp stdio server as a local MCP inside opencode
# so any opencode session automatically inherits the 22 finance research
# tools (list_skills, load_skill, backtest, factor_analysis, web_search, ...).
# The MCP server runs over stdio and is launched on demand by opencode.
RUN mkdir -p /etc/opencode && \
    printf '%s\n' \
        '{' \
        '  "$schema": "https://opencode.ai/config.json",' \
        '  "mcp": {' \
        '    "vibe-trading": {' \
        '      "type": "local",' \
        '      "command": ["vibe-trading-mcp"],' \
        '      "enabled": true,' \
        '      "environment": {' \
        '        "VIBE_TRADING_HOME": "'${VIBE_TRADING_HOME}'"' \
        '      }' \
        '    }' \
        '  }' \
        '}' \
        > /etc/opencode/config.json

RUN pip install "uv>=${UV_VERSION}" && \
    uv venv

COPY pyproject.toml .
COPY README.md .
COPY src/ src/

RUN uv pip install --system -e .

# Create appuser and setup permissions - do this AFTER all package installations
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /home/appuser/.config/opencode /home/appuser/.vibe-trading /opt/vibe-trading /var/log/supervisor /home/appuser/OpenBBUserData/cache/openbb_akshare && \
    cp /etc/opencode/config.json /home/appuser/.config/opencode/config.json && \
    chown -R appuser:appuser /app /home/appuser ${VIBE_TRADING_AGENT_DIR} /opt/vibe-trading /var/log/supervisor

# Copy equity.db to OpenBBUserData cache directory
COPY docs/equity.db /home/appuser/OpenBBUserData/cache/openbb_akshare/equity.db
RUN chown appuser:appuser /home/appuser/OpenBBUserData/cache/openbb_akshare/equity.db

# Copy supervisord configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 8001 4096 8899

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]