import logging
import os

from fastapi.responses import JSONResponse
from mysharelib.tools import setup_logger
from openbb_app.core.registry import TEMPLATES, WIDGETS, add_template
from openbb_app.routes.dashboard import dashboard_router
from openbb_app.routes.equity_cn import equity_cn_router
from openbb_app.routes.portfolio import portfolio_router
from openbb_app.routes.agents import agent_router
from importlib.metadata import version, PackageNotFoundError

setup_logger(__name__)
logger = logging.getLogger(__name__)

import subprocess
import sys
from pathlib import Path

using_openbb_api = False
try:
    # IMPORTANT: Use the "distribution name" (name = "my-project" in pyproject.toml), 
    # NOT the import name.
    __version__ = version("openbb-app") 
except PackageNotFoundError:
    # Package is not installed
    __version__ = "unknown"

print(f"openbb-app version: {__version__}")

def get_app(openbb_api: bool = True):
    from openbb_app.core.utils import check_api_keys
    check_api_keys()

    """Get the FastAPI instance"""
    if openbb_api:
        from openbb_platform_api.main import app
    else:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from openbb_app.core.config import config

        app = FastAPI(
            title=config.title, description=config.description, version=__version__,
            docs_url="/api/docs",
            redoc_url="/api/redoc",
            openapi_url="/api/openapi.json",
            swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect"
        )

        logger.info(f"CORS: {config.cors_origins}")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    return app


def start_api(openbb_api: bool = True):
    if openbb_api:
        os.chdir(Path(__file__).parent)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "openbb_platform_api.main",
                "--host",
                "0.0.0.0",
                "--port",
                "8001",
                "--app",
                Path(__file__).name,  # 只使用文件名，不使用绝对路径
            ]
        )
    else:
        import uvicorn

        uvicorn.run(app, host="127.0.0.1", port=8001)


app = get_app(openbb_api=using_openbb_api)


@app.get("/api/apps.json")
def get_apps():
    """Apps configuration file for the OpenBB Workspace

    Returns:
        JSONResponse: The contents of apps.json file
    """
    # Read and return the apps configuration file
    return list(TEMPLATES.values())


@app.get("/api/agents.json")
def agents_json() -> JSONResponse:
    """Return agent configuration for OpenBB Copilot discovery."""
    return JSONResponse(
        content={
            "openbb_app_builder_agent": {
                "name": "OpenBB App Builder Agent",
                "description": (
                    "Build custom OpenBB Workspace backend apps using Claude Code CLI "
                    "and local .claude skills. Supports widget context for data-driven "
                    "app generation."
                ),
                "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Anthropic_logo.svg/1280px-Anthropic_logo.svg.png",
                "endpoints": {"query": "/api/v1/query"},
                "features": {
                    "streaming": True,
                    "widget-dashboard-select": True,
                    "widget-dashboard-search": True,
                },
            }
        }
    )


if not using_openbb_api:

    @app.get("/api/widgets.json")
    def get_widgets():
        """Get all registered widgets"""
        # return list(WIDGETS.values())
        return WIDGETS


app.include_router(
    agent_router,
    prefix="/api/v1",
)

app.include_router(
    equity_cn_router,
    prefix="/api/v1/cn",
)

app.include_router(
    portfolio_router,
    prefix="/api/v1",
)

app.include_router(
    dashboard_router,
    prefix="/api/v1",
)
add_template("portfolio")


# 2. The CLI Entry Point
def start():
    """
    This function is what 'uvx' or 'openbb-tool' will execute.
    We point uvicorn to the string 'openbb_app.main:app'
    so it can find the FastAPI instance.
    """

    print("🚀 Starting OpenBB Backend on http://0.0.0.0:8001")
    start_api(openbb_api=using_openbb_api)


if __name__ == "__main__":
    start()
