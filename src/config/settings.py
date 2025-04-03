"""
Application settings loaded from environment variables.

This module loads configuration settings from environment variables
and provides default values when needed.
"""

import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from pathlib import Path

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
    """Load settings from environment."""
    settings_dict = {}
    
    # Prioritize environment variables
    for key, default in BASE_CONFIG.items():
        value = os.environ.get(key, default)
        settings_dict[key] = value
    
    # Check if .env file exists
    env_file = Path(".env")
    if env_file.exists():
        logger.info(f"Loading additional settings from {env_file}")
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    settings_dict[key.strip()] = value.strip()
    else:
        logger.warning(f".env file not found at {env_file.absolute()}")
    
    # Load API keys from environment and .env
    api_keys = {}
    
    # Helper function to securely log API key info
    def log_api_key(provider: str, key: str, source: str):
        if key:
            key_preview = key[:4] + "..." if len(key) > 8 else "***"
            logger.info(f"Found {provider.upper()}_API_KEY in {source}: {key_preview} (length: {len(key)})")
            return True
        return False
    
    # Check OpenAI API Key - env takes precedence over .env
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if log_api_key("openai", openai_api_key, "environment"):
        api_keys["openai"] = openai_api_key
    else:
        openai_api_key = settings_dict.get("OPENAI_API_KEY")
        if log_api_key("openai", openai_api_key, ".env"):
            api_keys["openai"] = openai_api_key
        else:
            logger.warning("OPENAI_API_KEY not found")

    # Check Google API Key - env takes precedence over .env
    google_api_key = os.environ.get("GOOGLE_API_KEY")
    if log_api_key("google", google_api_key, "environment"):
        api_keys["google"] = google_api_key
    else:
        google_api_key = settings_dict.get("GOOGLE_API_KEY")
        if log_api_key("google", google_api_key, ".env"):
            api_keys["google"] = google_api_key
        else:
            logger.warning("GOOGLE_API_KEY not found")
    
    # Store API keys in settings
    settings_dict["API_KEYS"] = api_keys
    
    # Automatically load API key from env if not provided in settings
    for provider in ("openai", "google"):
        # Check models for a provider
        has_configured_models = any(
            k.startswith("MODEL_") and isinstance(v, str) and v.startswith(f"{provider}/")
            for k, v in settings_dict.items()
        )
        
        # Log warning if provider has models configured but no API key
        if has_configured_models and provider not in api_keys:
            logger.warning(f"{provider.upper()} models configured but no API key found")
    
    # Convert string booleans to Python booleans
    for key, value in settings_dict.items():
        if isinstance(value, str) and value.lower() in ("true", "false", "yes", "no", "1", "0", "t", "f", "y", "n"):
            settings_dict[key] = value.lower() in ("true", "yes", "1", "t", "y")
    
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
    
    # Handle MODEL_X provider settings, e.g. MODEL_GEMINI_PRO=google/gemini-1.0-pro
    providers = settings_dict.get("PROVIDERS", "").split(",")
    provider_configs = {}
    
    for provider_key in providers:
        provider_key = provider_key.strip().lower()
        if not provider_key:
            continue
        provider_configs[provider_key] = {"models": []}
        
        # Map models to providers based on prefix
        provider_models = []
        for k, v in settings_dict.items():
            if k.startswith("MODEL_") and isinstance(v, str) and v.startswith(f"{provider_key}/"):
                provider_models.append(v)
            
        provider_configs[provider_key]["models"] = provider_models
        
        # API key might be a string or a dict depending on source
        api_key = settings_dict.get(f"{provider_key.upper()}_API_KEY", None)
        api_keys = settings_dict.get("API_KEYS", {})
        
        if isinstance(api_keys, dict) and provider_key in api_keys:
            provider_configs[provider_key]["api_key"] = api_keys[provider_key]
        elif api_key:
            provider_configs[provider_key]["api_key"] = api_key
    
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