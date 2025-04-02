"""
LLM Client Configuration and Tracing Utility

Configures the global 'openai' library client based on settings
and manages conditional tracing.
"""

import os
import logging
from typing import Dict, Tuple, Any
from openai import OpenAI
from dotenv import load_dotenv

from src.config.settings import settings, PROVIDER_CONFIG

# Create logger
logger = logging.getLogger(__name__)


# --- Model Identifier Parser ---
def parse_model_identifier(full_model_name: str) -> Tuple[str, str]:
    """Parses 'provider/model-name' string. Defaults to 'openai'."""
    if not isinstance(full_model_name, str):
        full_model_name = str(full_model_name)
    if "/" in full_model_name:
        provider, model_name = full_model_name.split("/", 1)
        return provider.lower(), model_name
    else:
        return "openai", full_model_name


# --- Global Client Configuration ---
def configure_global_llm_client(provider: str):
    """
    Configures the global openai library client attributes (api_key, base_url)
    for the specified provider.

    Args:
        provider: Lowercase name of the provider to configure globally.

    Raises:
        ValueError: If provider config or API key is missing.
    """
    provider_lower = provider.lower()
    logger.info(f"Configuring global 'openai' library client for provider: {provider_lower}")

    if provider_lower not in PROVIDER_CONFIG:
        logger.error(f"Configuration missing for global provider setup: {provider_lower}")
        raise ValueError(f"Unknown LLM provider for global config: {provider_lower}")

    provider_conf = PROVIDER_CONFIG[provider_lower]
    api_key_env_var = provider_conf["api_key_env"]
    api_key = settings.get("API_KEYS", {}).get(provider_lower)

    if not api_key:
        logger.error(f"API key for provider '{provider_lower}' not found for global config. Check env var '{api_key_env_var}'.")
        raise ValueError(f"API key for provider '{provider_lower}' is missing for global config.")

    base_url = provider_conf.get("base_url")

    try:
        # For openai>=1.0, update global vars and configure the client instance
        import openai
        openai.api_key = api_key  # Set global key
        
        # Set global base_url ONLY if it's not None (i.e., for non-openai providers)
        if base_url:
            openai.base_url = base_url
            logger.info(f"Set global openai.base_url for {provider_lower}: {base_url}")
        else:
            # Ensure base_url is reset if switching back to openai default
            if hasattr(openai, 'base_url'):
                openai.base_url = None  # Or openai.api_base for older versions
            logger.info(f"Using default OpenAI base URL (global config).")

        # Log the key being used (masked)
        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "..."
        logger.info(f"Global 'openai' client configured for provider '{provider_lower}' using key from {api_key_env_var} (Key: {masked_key})")

    except Exception as e:
        logger.exception(f"Error configuring global openai client for {provider_lower}: {e}")
        raise ValueError(f"Failed to configure global client for {provider_lower}") from e


# --- Tracing Configuration ---
def configure_tracing():
    """Disables SDK tracing if primary provider is not 'openai'."""
    try:
        default_model_full = settings.get("MODEL_DEFAULT", "openai/gpt-4o-mini")
        primary_provider, _ = parse_model_identifier(default_model_full)
        from agents import set_tracing_disabled  # Dynamic import

        if primary_provider != "openai":
            logger.info(f"Primary provider '{primary_provider}' != 'openai'. Disabling OpenAI tracing.")
            set_tracing_disabled(disabled=True)
        else:
            logger.info("Primary provider is 'openai'. OpenAI tracing enabled.")
            set_tracing_disabled(disabled=False)
    except ImportError:
        logger.warning("Could not import 'set_tracing_disabled'. Tracing config skipped.")
    except Exception as e:
        logger.warning(f"Could not configure tracing: {e}", exc_info=True)


# --- Original Client Setup (now a wrapper) ---
def setup_openai_client():
    """
    Set up and configure the OpenAI client with API key from environment.
    
    This needs to be called before any OpenAI API interaction or Agent usage.
    
    Returns:
        OpenAI client object
    """
    # Load .env file if it exists
    load_dotenv()
    
    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable not found")
        raise ValueError("OPENAI_API_KEY environment variable is required but not found")
    
    # Initialize client
    client = OpenAI(api_key=api_key)
    logger.info("OpenAI client successfully initialized")
    
    return client 