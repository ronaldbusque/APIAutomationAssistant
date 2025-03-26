"""
Agents Module - Core agent definitions and execution helpers for API test generation

This module provides agent configuration, initialization, and execution utilities.
Agents are used to process OpenAPI specifications, generate test blueprints,
and create test code for different frameworks.
"""

import os
import importlib
from typing import List, Dict, Any, Optional
import sys

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
    
    # Export Agent, Runner, and utility functions
    __all__ = ['Agent', 'Runner', 'trace', 'gen_trace_id', 'handoff', 'function_tool', 'RunItem', 'ItemHelpers',
               'test_planner_agent', 'coder_agent', 'triage_agent', 'postman_coder', 'playwright_coder']
finally:
    # Restore path
    sys.path = original_path

# Initialize required agents (will be populated in setup)
test_planner_agent = None
coder_agent = None
triage_agent = None
postman_coder = None
playwright_coder = None 