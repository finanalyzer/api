import uvicorn
from openbb_platform_api.main import app
import logging
from mysharelib.tools import setup_logger

setup_logger(__name__)
logger = logging.getLogger(__name__)

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}

# 2. The CLI Entry Point
def start():
    """
    This function is what 'uvx' or 'openbb-tool' will execute.
    We point uvicorn to the string 'openbb_app.main:app' 
    so it can find the FastAPI instance.
    """
    print("🚀 Starting OpenBB Backend on http://0.0.0.0:8000")
    uvicorn.run(
        "openbb_app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=False  # Set to False for production/tool use
    )

if __name__ == "__main__":
    start()