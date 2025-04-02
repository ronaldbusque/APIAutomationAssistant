"""
Agent Setup Module - Configuration and initialization for all agents

This module provides functions to set up the various agents needed for the 
API test generation system, including the Test Planner, Coder, and Triage agents.
"""

import os
import logging
import sys
from typing import Dict, Any, Optional

# Import directly from site-packages
site_packages_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.venv', 'Lib', 'site-packages')

# Save original path
original_path = sys.path.copy()

# Insert site-packages at the beginning
sys.path.insert(0, site_packages_path)

# Remove current directory from path to avoid conflicts
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir in sys.path:
    sys.path.remove(current_dir)

# Create the logger before imports to capture any import errors
logger = logging.getLogger(__name__)

try:
    # Import Agent from site-packages, not local module
    from agents import Agent, handoff, function_tool, trace, gen_trace_id, Runner
    from agents.items import RunItem, ItemHelpers
    
    # Use robust import handling for different openai-agents SDK versions
    try:
        # Try the common 0.0.7 structure first
        from agents.models.providers.openai import OpenAIProvider
        logger.info("Successfully imported OpenAIProvider from agents.models.providers.openai")
        OPENAI_PROVIDER_IMPORTED = True
    except ImportError:
        try:
            # Try alternative structure (e.g., 0.0.6)
            from agents.models.providers import OpenAIProvider
            logger.info("Successfully imported OpenAIProvider from agents.models.providers")
            OPENAI_PROVIDER_IMPORTED = True
        except ImportError as e:
            logger.error(f"Failed to import OpenAIProvider: {e}")
            logger.error("OpenAI functionality will be disabled")
            OPENAI_PROVIDER_IMPORTED = False
except Exception as e:
    logger.error(f"Error importing OpenAI agents SDK: {e}")
    OPENAI_PROVIDER_IMPORTED = False
finally:
    # Restore path
    sys.path = original_path

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

# Initialize provider instances with robust error handling
provider_map = {}

if OPENAI_PROVIDER_IMPORTED:
    try:
        openai_provider = OpenAIProvider()  # SDK default provider
        provider_map["openai"] = openai_provider
        logger.info("Successfully initialized OpenAIProvider")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAIProvider: {e}")

if GEMINI_PROVIDER_IMPORTED:
    try:
        gemini_provider = GeminiProvider(api_key=settings.get("API_KEYS", {}).get("google"))
        provider_map["google"] = gemini_provider
        logger.info("Successfully initialized GeminiProvider")
    except Exception as e:
        logger.error(f"Failed to initialize GeminiProvider: {e}")

# Check if API keys exist
OPENAI_API_KEY = settings.get("API_KEYS", {}).get("openai")
if not OPENAI_API_KEY:
    logger.warning("OpenAI API key not found in settings")
else:
    logger.info("OpenAI API key found in settings")

GOOGLE_API_KEY = settings.get("API_KEYS", {}).get("google")
if not GOOGLE_API_KEY:
    logger.warning("Google API key not found in settings")
else:
    logger.info("Google API key found in settings") 