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
finally:
    # Restore path
    sys.path = original_path

# Use absolute imports instead of relative
from src.blueprint.models import Blueprint
from src.models.script_output import ScriptOutput
from src.config.settings import settings

# Create the logger
logger = logging.getLogger(__name__)

# Check if API key exists in environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not found in environment variables")
else:
    logger.info("OPENAI_API_KEY found in environment variables") 