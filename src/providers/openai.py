"""
OpenAI provider implementation - OpenAI agents SDK version 0.0.7
"""

import logging
from typing import Optional, List, Dict, Any, Union, AsyncIterator

logger = logging.getLogger(__name__)

# Import direct from openai_provider.py (version 0.0.7)
try:
    from agents.models.openai_provider import OpenAIProvider
    from agents.models.interface import Model, ModelProvider
    from agents.model_settings import ModelSettings
    from agents.items import TResponseInputItem, TResponseOutputItem, TResponseStreamEvent
    from agents.tool import Tool
    from agents.usage import Usage
    logger.info("Successfully imported OpenAI provider from 0.0.7 paths")
except ImportError as e:
    logger.error(f"Failed to import OpenAI provider: {e}")
    logger.error("OpenAI provider functionality will be disabled")
    
    # Define stub classes for import to succeed
    class OpenAIProvider:
        pass
    
    class ModelProvider:
        pass
    
    class Model:
        pass
    
    class ModelSettings:
        pass
    
    class Tool:
        pass
    
    class Usage:
        pass
    
    class TResponseInputItem:
        pass
    
    class TResponseOutputItem:
        pass
    
    class TResponseStreamEvent:
        pass 