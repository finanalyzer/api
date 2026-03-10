import os
from openbb_platform_api.main import app
import logging
from mysharelib.tools import setup_logger
from openbb_app.routes.equity_cn import equity_cn_router

setup_logger(__name__)
logger = logging.getLogger(__name__)

import subprocess
import sys
from pathlib import Path
 
def start_api():
    os.chdir(Path(__file__).parent)
    subprocess.run([
        sys.executable, 
        "-m", "openbb_platform_api.main", 
        "--host", "0.0.0.0",
        "--port", "8001",
        "--app", Path(__file__).name  # 只使用文件名，不使用绝对路径
    ])

@app.get("/api/v1/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}

app.include_router(
    equity_cn_router,
    prefix="/api/v1/cn",
)

# 2. The CLI Entry Point
def start():
    """
    This function is what 'uvx' or 'openbb-tool' will execute.
    We point uvicorn to the string 'openbb_app.main:app' 
    so it can find the FastAPI instance.
    """
    print("🚀 Starting OpenBB Backend on http://0.0.0.0:8001")
    start_api()

if __name__ == "__main__":
    start()