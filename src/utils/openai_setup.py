"""
OpenAI Setup Utility

This module handles the setup of the OpenAI API client with proper authentication.
"""

import os
import logging
from openai import OpenAI
from dotenv import load_dotenv

# Create logger
logger = logging.getLogger(__name__)

def setup_openai_client():
    """
    Set up and configure the OpenAI client with API key from environment.
    
    This needs to be called before any OpenAI API interaction or Agent usage.
    
    Returns:
        OpenAI client object
    """
    # Load .env file if it exists
    load_dotenv()
    
    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable not found")
        raise ValueError("OPENAI_API_KEY environment variable is required but not found")
    
    # Initialize client
    client = OpenAI(api_key=api_key)
    logger.info("OpenAI client successfully initialized")
    
    return client 