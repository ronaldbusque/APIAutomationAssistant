# Load .env file FIRST before any other imports
import os
from pathlib import Path
from dotenv import load_dotenv

# Load from .env file, with override to ensure values take precedence
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    print(f"Loading environment variables from: {env_path}")
    load_dotenv(dotenv_path=env_path, override=True)
    print(f"Model settings from .env: MODEL_BP_AUTHOR={os.environ.get('MODEL_BP_AUTHOR')}, MODEL_BP_REVIEWER={os.environ.get('MODEL_BP_REVIEWER')}, MODEL_SCRIPT_CODER={os.environ.get('MODEL_SCRIPT_CODER')}")
else:
    print(f"Warning: .env file not found at {env_path}")

"""
API Test Automation Assistant - Main Application

This is the main entry point for the API Test Automation Assistant application.
It sets up logging, initializes the FastAPI application, and includes all routes.
"""

import logging
import sys
import json
import asyncio
import logging.config
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from uuid import UUID
from enum import Enum
import pprint

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

# Add the src directory to the path to enable absolute imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import application-specific modules
from src.config.settings import settings, BASE_CONFIG
from src.api import generate
from src.errors.exceptions import APITestGenerationError
from .utils.model_selection import ModelSelectionStrategy
from .utils.openai_setup import setup_openai_client

# Configure logging
def configure_logging():
    """Configure application logging."""
    log_level = settings.get("LOG_LEVEL", "INFO").upper()
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))

    # Remove existing handlers to prevent duplicates if re-run
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console_handler)

    # Add file handler if LOG_FILE is specified
    log_file = settings.get("LOG_FILE")
    if log_file:
        try:
            # Make log file path absolute if needed
            log_file_path = Path(log_file)
            if not log_file_path.is_absolute():
                log_file_path = Path.cwd() / log_file
            
            # Ensure parent directory exists
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create file handler
            file_handler = logging.FileHandler(str(log_file_path), encoding='utf-8')
            file_handler.setLevel(getattr(logging, log_level))
            file_handler.setFormatter(logging.Formatter(log_format))
            logger.addHandler(file_handler)
            
            # We can log this now since we've added at least one handler
            logger.info(f"File logging configured at: {log_file_path}")
        except Exception as e:
            print(f"Error setting up file logging: {e}")
            logger.error(f"Failed to set up file logging: {str(e)}")
    
    # Configure library loggers to prevent excessive messages
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    
    logger.info(f"Logging configured with level {log_level}")
    return logger

# Initialize logger
logger = configure_logging()

# Initialize the FastAPI application
app = FastAPI(
    title="API Automation Assistant",
    description="Generate API tests from OpenAPI specifications or other sources",
    version="1.0.0"
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development - restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to suppress noisy logs
@app.middleware("http")
async def suppress_health_logs(request: Request, call_next):
    """Suppress log messages for health check endpoints."""
    response = await call_next(request)
    return response

# Custom exception handler for APITestGenerationError
@app.exception_handler(APITestGenerationError)
async def test_generation_exception_handler(request: Request, exc: APITestGenerationError):
    """Handle custom API test generation errors with meaningful error messages."""
    logger.error(f"API test generation error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )

# Create API router and include it in the app
router = generate.create_api_router()
app.include_router(router)
logger.info("Included API router with prefix /api/v1")

# Health check endpoint
@app.get("/health", tags=["Monitoring"])
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok"}

# System info endpoint (returns config - remove sensitive data in production)
@app.get("/system/info", tags=["Monitoring"])
async def system_info():
    """Returns system configuration (non-sensitive info only)."""
    # Filter out sensitive information
    safe_config = {k: v for k, v in BASE_CONFIG.items() if "KEY" not in k and "SECRET" not in k}
    return {"config": safe_config}

# Version info endpoint
@app.get("/version", tags=["Monitoring"])
async def version():
    """Returns API version information."""
    return {
        "version": app.version,
        "name": app.title
    }

# Mount static files for UI (if directory exists)
ui_path = Path("static/ui")
if ui_path.exists():
    app.mount("/", StaticFiles(directory=str(ui_path), html=True), name="ui")
    logger.info(f"Mounted UI static files from {ui_path}")
else:
    logger.warning(f"UI path {ui_path} not found, static UI will not be available")

# Import providers to register them early
try:
    import src.providers
    logger.info("Successfully imported provider modules")
except ImportError as e:
    logger.error(f"Failed to import provider modules: {e}")
    logger.error("Some provider functionality may be disabled")

# Start standalone server if executed directly
if __name__ == "__main__":
    # Get host and port from settings
    host = settings.get("HOST", "0.0.0.0")
    port = int(settings.get("PORT", 8000))
    
    # Log startup message
    logger.info(f"Starting API Automation Assistant on http://{host}:{port}")
    
    # Run the server
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=settings.get("ENVIRONMENT") == "development",
        log_level=settings.get("LOG_LEVEL", "info").lower(),
    ) 