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

try:
    # Import Agent from site-packages, not local module
    from agents import Agent, handoff, function_tool, trace, gen_trace_id, Runner
    from agents.items import RunItem, ItemHelpers
    from agents.models.providers.openai import OpenAIProvider
finally:
    # Restore path
    sys.path = original_path

# Use absolute imports instead of relative
from src.blueprint.models import Blueprint
from src.models.script_output import ScriptOutput
from src.config.settings import settings, BASE_CONFIG
from src.utils.openai_setup import parse_model_identifier
from src.providers.google import GeminiProvider

# Create the logger
logger = logging.getLogger(__name__)

# Initialize provider instances
openai_provider = OpenAIProvider()  # SDK default provider
gemini_provider = GeminiProvider(api_key=settings.get("API_KEYS", {}).get("google"))

provider_map = {
    "openai": openai_provider,
    "google": gemini_provider,
}

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