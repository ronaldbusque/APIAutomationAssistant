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
    """Configure application logging (Simplified - remove StatusPollFilter)."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))

    # Remove existing handlers to prevent duplicates if re-run
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console_handler)

    log_file = os.environ.get("LOG_FILE")
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(getattr(logging, log_level))
            file_handler.setFormatter(logging.Formatter(log_format))
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Error setting up file logging: {e}")

    logger.info(f"Logging configured with level {log_level}")
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

# --- ADD MIDDLEWARE ---
@app.middleware("http")
async def suppress_noisy_logs_middleware(request: Request, call_next):
    """Middleware to prevent logging for specific paths if needed."""
    # You can customize this logic
    path = request.url.path
    if path.startswith("/status/") or path == "/health":
         # Skip logging for these frequent polls by handling directly
         # For /health, just return ok
         if path == "/health":
             return JSONResponse({"status": "healthy"})
         # For /status/, we still need to call the actual endpoint
         # but prevent standard access logging. We can't easily stop
         # uvicorn's default access logger here without complex setup.
         # The best approach is often to configure uvicorn directly
         # to use a log format that excludes these, or filter post-hoc.
         # For now, we just proceed but the logger config change below
         # should handle it better.
         pass # Let the request proceed normally

    response = await call_next(request)
    return response
# --- END MIDDLEWARE ---

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