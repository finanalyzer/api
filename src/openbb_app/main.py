import os
from openbb_app.routes.equity_cn import equity_cn_router
from openbb_app.routes.portfolio import portfolio_router
from openbb_app.core.registry import WIDGETS, add_template, TEMPLATES

import logging
from mysharelib.tools import setup_logger
setup_logger(__name__)
logger = logging.getLogger(__name__)

import subprocess
import sys
from pathlib import Path

using_openbb_api = False

def get_app(openbb_api: bool = True):
    """Get the FastAPI instance"""
    if openbb_api:
        from openbb_platform_api.main import app
    else:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from openbb_app.core.config import config
        app = FastAPI(title=config.title,
            description=config.description,
            version="0.1.2")

        origins = [
            "https://pro.openbb.co",
            "http://localhost:1420"
        ]

        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    return app

def start_api(openbb_api: bool = True):
    if openbb_api:
        os.chdir(Path(__file__).parent)
        subprocess.run([
            sys.executable, 
            "-m", "openbb_platform_api.main", 
            "--host", "0.0.0.0",
            "--port", "8001",
            "--app", Path(__file__).name  # 只使用文件名，不使用绝对路径
        ])
    else:
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=8001)

app = get_app(openbb_api=using_openbb_api)

@app.get("/api/v1/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}

@app.get("/apps.json")
def get_apps():
    """Apps configuration file for the OpenBB Workspace
    
    Returns:
        JSONResponse: The contents of apps.json file
    """
    # Read and return the apps configuration file
    return list(TEMPLATES.values())

if not using_openbb_api:
    @app.get("/widgets.json")
    def get_widgets():
        """Get all registered widgets"""
        #return list(WIDGETS.values())
        return WIDGETS

app.include_router(
    equity_cn_router,
    prefix="/api/v1/cn",
)

app.include_router(
    portfolio_router,
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
    from openbb_app.core.utils import check_api_keys

    check_api_keys()

    print("🚀 Starting OpenBB Backend on http://0.0.0.0:8001")
    start_api(openbb_api=using_openbb_api)

if __name__ == "__main__":
    start()