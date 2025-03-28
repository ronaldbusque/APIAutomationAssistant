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
    """Configure application logging."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Create the logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))
    
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler - using utf-8 encoding to handle unicode characters
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # Create a filter to exclude status poll messages
    class StatusPollFilter(logging.Filter):
        def filter(self, record):
            if record.getMessage().find("GET /status/") >= 0 and record.getMessage().find("200 OK") >= 0:
                return False
            return True
    
    # Apply the filter to the console handler
    console_handler.addFilter(StatusPollFilter())
    
    # Add handlers
    logger.addHandler(console_handler)
    
    # Also create a file handler if LOG_FILE is specified
    log_file = os.environ.get("LOG_FILE")
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(getattr(logging, log_level))
            file_handler.setFormatter(logging.Formatter(log_format))
            file_handler.addFilter(StatusPollFilter())
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Error setting up file logging: {e}")
    
    logger.info(f"Logging configured with level {log_level} and utf-8 encoding")
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
    from uvicorn.config import LOGGING_CONFIG
    
    # Get configuration from environment variables
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    reload = os.environ.get("RELOAD", "false").lower() == "true"
    
    # Configure uvicorn logging to handle Unicode and filter status requests
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOGGING_CONFIG["formatters"]["access"]["fmt"] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Define a custom filter function that will be used to filter access logs
    class StatusEndpointFilter(logging.Filter):
        def filter(self, record):
            try:
                # Check the message directly as a string
                message = str(record.msg)
                if "/status/" in message:
                    return False
            except Exception:
                # If any error occurs during filtering, just pass it through
                pass
            return True
    
    # Create custom log config with modified settings
    log_config = LOGGING_CONFIG.copy()
    log_config["filters"] = {
        "status_filter": {
            "()": StatusEndpointFilter
        }
    }
    
    # Set very high log level for access logs
    log_config["loggers"]["uvicorn.access"] = {
        "level": "WARNING",  # Only log warnings and above
        "propagate": False,
        "handlers": ["custom_access"],
    }
    
    # Apply our custom filter to all handlers
    for handler_name in log_config["handlers"]:
        log_config["handlers"][handler_name]["filters"] = ["status_filter"]
    
    # Run the application with the custom log config
    uvicorn.run("src.main:app", host=host, port=port, reload=reload, log_config=log_config)

if __name__ == "__main__":
    main() 