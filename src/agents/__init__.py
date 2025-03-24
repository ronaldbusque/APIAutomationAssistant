"""
Agents Module - Core agent definitions and execution helpers for API test generation

This module provides agent configuration, initialization, and execution utilities.
Agents are used to process OpenAPI specifications, generate test blueprints,
and create test code for different frameworks.
"""

import os
import importlib
from typing import List, Dict, Any, Optional

# Initialize required agents (will be populated in setup)
test_planner_agent = None
coder_agent = None
triage_agent = None
postman_coder = None
playwright_coder = None 