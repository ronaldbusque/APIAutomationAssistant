"""
Agent Setup Module - Initialization and configuration for all agents

This module provides functions to set up and configure the agents needed
for API test generation using the OpenAI Agents SDK.
"""

import logging
import importlib.util
from typing import Dict, Any, Optional

# Create the logger before imports to capture any import errors
logger = logging.getLogger(__name__)

# Clean import approach to avoid circular imports
try:
    # Import Agent and related tools directly from the package
    import agents
    from agents import Agent, function_tool, trace, gen_trace_id, Runner
    from agents.items import RunItem, ItemHelpers
    
    # Correct import path for OpenAI agents SDK version 0.0.7
    from agents.models.openai_provider import OpenAIProvider
    from agents.models.interface import Model, ModelProvider
    
    logger.info(f"Successfully imported OpenAI agents SDK version: {getattr(agents, '__version__', 'unknown')}")
    OPENAI_PROVIDER_IMPORTED = True
except ImportError as e:
    logger.error(f"Failed to import OpenAI agents SDK: {e}")
    logger.error("OpenAI functionality will be disabled")
    OPENAI_PROVIDER_IMPORTED = False

# Import application-specific modules
from src.blueprint.models import Blueprint
from src.models.script_output import ScriptOutput
from src.config.settings import settings, BASE_CONFIG
from src.utils.openai_setup import parse_model_identifier

# Import GeminiProvider with error handling
try:
    from src.providers.google import GeminiProvider
    logger.info("Successfully imported GeminiProvider")
    GEMINI_PROVIDER_IMPORTED = True
except ImportError as e:
    logger.error(f"Failed to import GeminiProvider: {e}")
    logger.error("Gemini functionality will be disabled")
    GEMINI_PROVIDER_IMPORTED = False

# Initialize provider instances with proper error handling
provider_map = {}

if OPENAI_PROVIDER_IMPORTED:
    try:
        openai_api_key = settings.get("API_KEYS", {}).get("openai")
        if not openai_api_key:
            logger.error("Cannot initialize OpenAIProvider: API key is missing")
            logger.error("Check the .env file and make sure OPENAI_API_KEY is properly set")
        else:
            # Properly initialize with API key
            openai_provider = OpenAIProvider(api_key=openai_api_key)
            provider_map["openai"] = openai_provider
            logger.info("Successfully initialized OpenAIProvider with API key")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAIProvider: {e}")
        logger.exception("Detailed exception info:")

if GEMINI_PROVIDER_IMPORTED:
    try:
        google_api_key = settings.get("API_KEYS", {}).get("google")
        if not google_api_key:
            logger.error("Cannot initialize GeminiProvider: API key is missing")
            logger.error("Check the .env file and make sure GOOGLE_API_KEY is properly set")
        else:
            gemini_provider = GeminiProvider(api_key=google_api_key)
            provider_map["google"] = gemini_provider
            logger.info("Successfully initialized GeminiProvider with API key")
    except Exception as e:
        logger.error(f"Failed to initialize GeminiProvider: {e}")
        logger.exception("Detailed exception info:")

# Helper function to get the default provider instance
def get_default_provider_instance():
    """Gets the provider instance configured as the default."""
    try:
        # Get the default provider name from settings
        default_model_full = settings.get('MODEL_DEFAULT', BASE_CONFIG.get('MODEL_DEFAULT', 'google/gemini-1.5-pro'))
        default_provider_name, _ = parse_model_identifier(default_model_full)
        
        logger.info(f"Provider map contents: {list(provider_map.keys())}")
        logger.info(f"Default provider from settings: {default_provider_name}")
        
        # First try to use the configured default provider
        if default_provider_name in provider_map:
            logger.info(f"Using configured default provider: {default_provider_name}")
            return provider_map[default_provider_name]
            
        # If we can't find the configured default, try Google then OpenAI
        if "google" in provider_map:
            logger.info("Falling back to Google provider")
            return provider_map["google"]
            
        if "openai" in provider_map:
            logger.info("Falling back to OpenAI provider")
            return provider_map["openai"]
            
        # If none of the above work, use the first available provider
        if provider_map:
            fallback_provider_name = next(iter(provider_map))
            logger.info(f"Using first available provider: {fallback_provider_name}")
            return provider_map[fallback_provider_name]
            
        # If provider_map is empty, log the error and return None
        logger.error(f"Default provider '{default_provider_name}' not available - no providers were initialized")
        logger.error(f"Available API keys: {list(settings.get('API_KEYS', {}).keys())}")
        logger.error("Check your .env file and ensure API keys are properly configured")
        return None
    except Exception as e:
        logger.exception(f"Error determining default provider: {e}")
        return None 