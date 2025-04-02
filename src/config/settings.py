"""
Application settings loaded from environment variables.

This module loads configuration settings from environment variables
and provides default values when needed.
"""

import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv

# Set up logger
logger = logging.getLogger(__name__)

# Define Gemini Model Constant (default, can be overridden by env vars)
GEMINI_FLASH = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-thinking-exp-01-21")

# Base configuration
BASE_CONFIG = {
    # Application settings
    "HOST": "0.0.0.0",
    "PORT": "8000",
    "RELOAD": "false",
    "LOG_LEVEL": "INFO",
    "LOG_FILE": None,
    
    # Model selection settings (PROVIDER/MODEL format)
    "MODEL_DEFAULT": os.environ.get("MODEL_DEFAULT", f"google/{GEMINI_FLASH}"),
    "MODEL_BP_AUTHOR": os.environ.get("MODEL_BP_AUTHOR", f"google/{GEMINI_FLASH}"),
    "MODEL_BP_REVIEWER": os.environ.get("MODEL_BP_REVIEWER", f"google/{GEMINI_FLASH}"),
    "MODEL_SCRIPT_CODER": os.environ.get("MODEL_SCRIPT_CODER", f"google/{GEMINI_FLASH}"),
    "MODEL_SCRIPT_REVIEWER": os.environ.get("MODEL_SCRIPT_REVIEWER", f"google/{GEMINI_FLASH}"),
    
    # Model selection by task type
    "MODEL_SELECTION": {
        "blueprint_authoring": os.environ.get("MODEL_BLUEPRINT_AUTHORING", f"google/{GEMINI_FLASH}"),
        "code_generation": os.environ.get("MODEL_CODE_GENERATION", f"google/{GEMINI_FLASH}"),
        "code_review": os.environ.get("MODEL_CODE_REVIEW", f"google/{GEMINI_FLASH}"),
        "documentation": os.environ.get("MODEL_DOCUMENTATION", f"google/{GEMINI_FLASH}"),
        "testing": os.environ.get("MODEL_TESTING", f"google/{GEMINI_FLASH}")
    },
    
    # Complexity thresholds
    "MODEL_PLANNING_HIGH_THRESHOLD": "0.7",
    "MODEL_PLANNING_MEDIUM_THRESHOLD": "0.4",
    "MODEL_CODING_HIGH_THRESHOLD": "0.8",
    "MODEL_CODING_MEDIUM_THRESHOLD": "0.5",
    
    # Performance settings
    "MAX_RETRIES": "3",
    "BASE_TIMEOUT": "300",
    "MAX_JITTER": "1.0",
    "AUTONOMOUS_MAX_ITERATIONS": "3"
}

# Define provider configurations
PROVIDER_CONFIG = {
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
    },
    "google": {
        "api_key_env": "GOOGLE_API_KEY",
    },
}

def load_settings() -> Dict[str, Any]:
    """
    Load settings from environment variables with defaults.
    
    Returns:
        Dictionary of application settings
    """
    settings_dict = {}
    logger.info("Loading application settings...")
    load_dotenv(override=True)  # Ensure .env overrides system env

    # Load general settings from BASE_CONFIG
    for key, default in BASE_CONFIG.items():
        # Skip API key patterns here, load them specifically later
        if "_API_KEY" in key: continue
        env_value = os.environ.get(key)
        settings_dict[key] = env_value if env_value is not None else default
        if key.startswith("MODEL_"):
            logger.info(f"Setting {key} = '{settings_dict[key]}' (Source: {'Environment' if env_value is not None else 'Default'})")

    # Load API keys into nested dict
    settings_dict["API_KEYS"] = {}
    for provider, config in PROVIDER_CONFIG.items():
        provider_key = provider.lower()
        api_key_env_var = config["api_key_env"]
        api_key = os.environ.get(api_key_env_var)
        if api_key:
            settings_dict["API_KEYS"][provider_key] = api_key
            logger.info(f"Loaded API key for provider: {provider_key} (from {api_key_env_var})")
        else:
            # Log warning only if a model for this provider is configured
            provider_models = [v for k, v in settings_dict.items() if k.startswith("MODEL_") and v.startswith(f"{provider_key}/")]
            if provider_models:
                logger.warning(f"API key environment variable '{api_key_env_var}' not found for provider: {provider_key}. Configured models ({provider_models}) may fail.")
            else:
                logger.debug(f"API key environment variable '{api_key_env_var}' not found for provider: {provider_key} (no models configured for this provider).")
    
    # Convert numeric settings
    numeric_settings = [
        "PORT", "MAX_RETRIES", "BASE_TIMEOUT", "MAX_JITTER",
        "MODEL_PLANNING_HIGH_THRESHOLD", "MODEL_PLANNING_MEDIUM_THRESHOLD",
        "MODEL_CODING_HIGH_THRESHOLD", "MODEL_CODING_MEDIUM_THRESHOLD",
        "AUTONOMOUS_MAX_ITERATIONS"
    ]
    
    for key in numeric_settings:
        if key in settings_dict and settings_dict[key] is not None:
            try:
                if "." in str(settings_dict[key]):
                    settings_dict[key] = float(settings_dict[key])
                else:
                    settings_dict[key] = int(settings_dict[key])
            except (ValueError, TypeError):
                # Keep as string if conversion fails
                pass
    
    # Convert boolean settings
    bool_settings = ["RELOAD"]
    for key in bool_settings:
        if key in settings_dict and isinstance(settings_dict[key], str):
            settings_dict[key] = settings_dict[key].lower() in ("true", "yes", "1", "t", "y")
    
    logger.info("Settings loading complete.")
    return settings_dict

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