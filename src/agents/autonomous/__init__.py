"""
Autonomous Agents Module - Implements Author-Reviewer agent loops

This module provides functionality for autonomous blueprint and script generation
using iterative Author-Reviewer agent loops.
"""

from .agents import (
    setup_blueprint_author_agent,
    setup_blueprint_reviewer_agent,
    setup_script_coder_agent,
    setup_script_reviewer_agent
)

from .pipeline import (
    run_autonomous_blueprint_pipeline,
    run_autonomous_script_pipeline,
    analyze_initial_spec,
    BLUEPRINT_APPROVED_KEYWORD,
    REVISION_NEEDED_KEYWORD,
    CODE_APPROVED_KEYWORD
)

from .context import PlannerContext

__all__ = [
    'setup_blueprint_author_agent',
    'setup_blueprint_reviewer_agent',
    'setup_script_coder_agent',
    'setup_script_reviewer_agent',
    'run_autonomous_blueprint_pipeline',
    'run_autonomous_script_pipeline',
    'analyze_initial_spec',
    'PlannerContext',
    'BLUEPRINT_APPROVED_KEYWORD',
    'REVISION_NEEDED_KEYWORD',
    'CODE_APPROVED_KEYWORD'
] 