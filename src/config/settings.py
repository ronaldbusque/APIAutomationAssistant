"""
Application settings loaded from environment variables.

This module loads configuration settings from environment variables
and provides default values when needed.
"""

import os
import logging
from typing import Dict, Any

# Set up logger
logger = logging.getLogger(__name__)

# Base configuration
BASE_CONFIG = {
    # Application settings
    "HOST": "0.0.0.0",
    "PORT": "8000",
    "RELOAD": "false",
    "LOG_LEVEL": "INFO",
    "LOG_FILE": None,
    
    # Model selection settings
    "MODEL_PLANNING": "o3-mini",
    "MODEL_CODING": "gpt-4o-mini",
    "MODEL_TRIAGE": "gpt-4o-mini",
    "MODEL_DEFAULT": "gpt-4o-mini",
    
    # Complexity thresholds
    "MODEL_PLANNING_HIGH_THRESHOLD": "0.7",
    "MODEL_PLANNING_MEDIUM_THRESHOLD": "0.4",
    "MODEL_CODING_HIGH_THRESHOLD": "0.8",
    "MODEL_CODING_MEDIUM_THRESHOLD": "0.5",
    
    # Performance settings
    "MAX_RETRIES": "3",
    "BASE_TIMEOUT": "300",
    "MAX_JITTER": "1.0"
}

def load_settings() -> Dict[str, Any]:
    """
    Load settings from environment variables with defaults.
    
    Returns:
        Dictionary of application settings
    """
    settings = {}
    
    # Log which models are set in the environment, for debugging
    logger.info(f"Environment MODEL_PLANNING: {os.environ.get('MODEL_PLANNING')}")
    logger.info(f"Environment MODEL_CODING: {os.environ.get('MODEL_CODING')}")
    logger.info(f"Environment MODEL_TRIAGE: {os.environ.get('MODEL_TRIAGE')}")
    
    # Load settings from environment with defaults
    for key, default in BASE_CONFIG.items():
        env_value = os.environ.get(key)
        settings[key] = env_value if env_value is not None else default
        
        # Log model values for debugging
        if key.startswith("MODEL_"):
            logger.info(f"Setting {key} to '{settings[key]}' (from {'environment' if env_value is not None else 'default'})")
    
    # Convert numeric settings
    numeric_settings = [
        "PORT", "MAX_RETRIES", "BASE_TIMEOUT", "MAX_JITTER",
        "MODEL_PLANNING_HIGH_THRESHOLD", "MODEL_PLANNING_MEDIUM_THRESHOLD",
        "MODEL_CODING_HIGH_THRESHOLD", "MODEL_CODING_MEDIUM_THRESHOLD"
    ]
    
    for key in numeric_settings:
        if key in settings and settings[key] is not None:
            try:
                if "." in settings[key]:
                    settings[key] = float(settings[key])
                else:
                    settings[key] = int(settings[key])
            except ValueError:
                # Keep as string if conversion fails
                pass
    
    # Convert boolean settings
    bool_settings = ["RELOAD"]
    for key in bool_settings:
        if key in settings:
            settings[key] = settings[key].lower() in ("true", "yes", "1", "t", "y")
    
    return settings

def update_settings():
    """
    Update the global settings by reloading from environment variables.
    
    This function is useful for tests or runtime updates where
    environment variables may change after module initialization.
    """
    global settings
    
    # First clear all existing settings to ensure we start fresh
    settings.clear()
    
    # Then load fresh settings
    new_settings = load_settings()
    
    # Update the global settings dict with new values
    settings.update(new_settings)
    
    logger.info("Settings have been updated from environment variables")
    return settings

# Load settings once at module import
settings = load_settings() 