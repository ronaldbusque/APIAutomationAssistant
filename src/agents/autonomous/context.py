"""
Context Module - Provides data containers for agent communication context

This module defines context objects used to share data between agents
in the autonomous pipeline.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel

class PlannerContext(BaseModel):
    """Context object holding data for the blueprint generation phase."""
    spec_analysis: Optional[Dict[str, Any]] = None
    business_rules: Optional[str] = None
    test_data: Optional[str] = None
    test_flow: Optional[str] = None 