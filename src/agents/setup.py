"""
Agent Setup Module - Configuration and initialization for all agents

This module provides functions to set up the various agents needed for the 
API test generation system, including the Test Planner, Coder, and Triage agents.
"""

import os
import logging
import importlib.util
from typing import Dict, Any, Optional

# Create the logger before imports to capture any import errors
logger = logging.getLogger(__name__)

# Clean import approach without modifying sys.path
try:
    # Import Agent and related tools directly
    from agents import Agent, handoff, function_tool, trace, gen_trace_id, Runner
    from agents.items import RunItem, ItemHelpers
    
    # Single, correct import path for OpenAI agents SDK version 0.0.7
    from agents.models.providers.openai import OpenAIProvider
    from agents.models.interface import Model, ModelProvider
    
    logger.info("Successfully imported OpenAI agents SDK modules")
    OPENAI_PROVIDER_IMPORTED = True
except ImportError as e:
    logger.error(f"Failed to import OpenAI agents SDK: {e}")
    logger.error("OpenAI functionality will be disabled")
    OPENAI_PROVIDER_IMPORTED = False

# Use absolute imports instead of relative
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

# Initialize provider instances with specific error handling
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