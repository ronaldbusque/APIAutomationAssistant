# Load .env file FIRST before any other imports
import os
from pathlib import Path
from dotenv import load_dotenv

# Load from .env file, with override to ensure values take precedence
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    print(f"Loading environment variables from: {env_path}")
    load_dotenv(dotenv_path=env_path, override=True)
    print(f"Model settings from .env: PLANNING={os.environ.get('MODEL_PLANNING')}, CODING={os.environ.get('MODEL_CODING')}, TRIAGE={os.environ.get('MODEL_TRIAGE')}")
else:
    print(f"Warning: .env file not found at {env_path}")

"""
API Test Automation Assistant - Main Application

This is the main entry point for the API Test Automation Assistant application.
It sets up logging, initializes the FastAPI application, and includes all routes.
"""

import logging
import sys
from typing import Dict, Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .api.generate import create_api_router
from .errors.exceptions import APITestGenerationError
from .utils.model_selection import ModelSelectionStrategy
from .agents.setup import setup_all_agents
from .utils.openai_setup import setup_openai_client

# Configure logging
def configure_logging():
    """Configure application logging with status poll filtering."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Get the root logger
    logger = logging.getLogger() # Get root logger
    logger.setLevel(getattr(logging, log_level))

    # Remove existing handlers to prevent duplicates if app reloads
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Define filter inside the function
    class StatusPollFilter(logging.Filter):
        def filter(self, record):
            try:
                msg = record.getMessage()
                # More specific check for Uvicorn access log format for /status/
                if record.name == "uvicorn.access" and \
                   "GET /status/" in msg and \
                   msg.endswith(" 200 OK"):
                    return False # Filter out successful status polls
                # Also filter health check if desired
                if record.name == "uvicorn.access" and \
                   "GET /health " in msg and \
                   msg.endswith(" 200 OK"):
                     return False
            except Exception:
                pass # Let record pass if there's an error checking
            return True # Let other records pass

    # --- CONFIGURE ROOT LOGGER HANDLERS ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(logging.Formatter(log_format))
    console_handler.addFilter(StatusPollFilter()) # Apply filter
    logger.addHandler(console_handler)

    log_file = os.environ.get("LOG_FILE")
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(getattr(logging, log_level))
            file_handler.setFormatter(logging.Formatter(log_format))
            file_handler.addFilter(StatusPollFilter()) # Apply filter
            logger.addHandler(file_handler)
            logger.info(f"File logging configured at: {log_file}")
        except Exception as e:
            print(f"Error setting up file logging: {e}")

    # --- PREVENT Uvicorn Default Handlers ---
    # Prevent Uvicorn from adding its own handlers to the root logger
    # which might bypass our filter.
    logging.getLogger("uvicorn").propagate = False
    logging.getLogger("uvicorn.error").propagate = False
    # Filter uvicorn access logs specifically if needed (though root filter should catch it)
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.addFilter(StatusPollFilter())
    uvicorn_access_logger.propagate = False # Prevent double logging

    logger.info(f"Logging configured with level {log_level} and status poll filter.")
    return logger

# Initialize logger
logger = configure_logging()

# Initialize OpenAI client
try:
    openai_client = setup_openai_client()
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {str(e)}")
    sys.exit(1)

# Create FastAPI application
app = FastAPI(
    title="API Test Automation Assistant",
    description="AI-powered API test generation from OpenAPI specifications",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom exception handler
@app.exception_handler(APITestGenerationError)
async def api_exception_handler(request: Request, exc: APITestGenerationError):
    """Custom exception handler for API generation errors."""
    logger.error(f"API exception: {exc.message}")
    return JSONResponse(
        status_code=400,
        content={
            "error": exc.message,
            "details": exc.details,
            "trace_id": exc.trace_id
        }
    )

@app.get("/")
async def root():
    """Root endpoint that returns application information."""
    return {
        "app": "API Test Automation Assistant",
        "version": "1.0.0",
        "description": "AI-powered API test generation from OpenAPI specifications"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

# Initialize model selection strategy
model_strategy = ModelSelectionStrategy()
logger.info(f"Model selection strategy initialized")

# Initialize agents
try:
    agents = setup_all_agents()
    logger.info(f"Agents initialized successfully")
except Exception as e:
    logger.error(f"Error initializing agents: {str(e)}")
    agents = None

# Add API routes
api_router = create_api_router(app)

@app.on_event("startup")
async def startup():
    """Application startup event handler."""
    logger.info("Application starting up")
    
    # Add any startup tasks here
    
    logger.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown():
    """Application shutdown event handler."""
    logger.info("Application shutting down")
    
    # Add any cleanup tasks here
    
    logger.info("Application shutdown complete")

# Main function to run the application
def main():
    """Run the application with uvicorn."""
    import uvicorn
    
    # Get configuration from environment variables
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    reload = os.environ.get("RELOAD", "false").lower() == "true"
    
    # Run uvicorn, letting FastAPI/configure_logging handle app logs
    uvicorn.run("src.main:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    main() 