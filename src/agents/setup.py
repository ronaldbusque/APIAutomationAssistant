"""
Agent Setup Module - Configuration and initialization for all agents

This module provides functions to set up the various agents needed for the 
API test generation system, including the Test Planner, Coder, and Triage agents.
"""

import os
import logging
from typing import Dict, Any, Optional

from agents import Agent, handoff, function_tool, trace, gen_trace_id, Runner
from agents.items import RunItem, ItemHelpers
from ..blueprint.models import Blueprint
from ..models.script_output import ScriptOutput
from ..config.settings import settings

# Create the logger
logger = logging.getLogger(__name__)

# Check if API key exists in environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not found in environment variables")
else:
    logger.info("OPENAI_API_KEY found in environment variables")

def setup_test_planner_agent(model: Optional[str] = None) -> Agent:
    """
    Set up the Test Planner agent for generating test blueprints from OpenAPI specs.
    
    Args:
        model: Optional model to use, defaults to settings
        
    Returns:
        Configured Test Planner agent
    """
    # If model not specified, use from settings
    if model is None:
        model = settings.get("MODEL_PLANNING")
        
    logger.info(f"Setting up Test Planner agent with model: {model}")
    
    test_planner_agent = Agent(
        name="Test Planner",
        model=model,
        instructions="""
        You are an API Test Planning Assistant. Your role is to analyze OpenAPI specifications 
        and create comprehensive test plans.
        
        You'll receive an OpenAPI spec and additional context such as business rules,
        test data, and test flows. Your task is to:
        
        1. Analyze the API specification to understand endpoints, methods, and data models
        2. Create a structured test blueprint with test groups for related endpoints
        3. Design individual tests to verify functionality, validations, and error cases
        4. Include tests for business rules and specific scenarios if provided
        5. Output a complete test blueprint as a JSON object
        
        The blueprint should have the following top-level structure:
        {
          "apiName": "Name of the API",
          "version": "API version",
          "description": "Optional description",
          "baseUrl": "Optional base URL",
          "groups": [
            {
              "name": "Group name",
              "description": "Group description",
              "tests": [
                {
                  "id": "unique-test-id",
                  "name": "Test name",
                  "description": "Test description",
                  "endpoint": "/path",
                  "method": "GET",
                  "expectedStatus": 200,
                  ...other test fields...
                }
              ]
            }
          ]
        }
        
        PARAMETERS FORMAT:
        You can specify parameters in either format:
        
        1. As a list (preferred):
        "parameters": [
          {
            "name": "userId",
            "value": "123",
            "in": "query"
          }
        ]
        
        2. Or as a dictionary (also accepted):
        "parameters": {
          "userId": "123"
        }
        
        IMPORTANT REQUIREMENTS:
        - All POST, PUT, and PATCH requests must include either a "body" or "parameters"
        - All test IDs must be unique across the entire blueprint
        - Ensure all endpoints begin with a forward slash (/)
        
        Focus on creating a thorough test plan that includes positive and negative test cases,
        validations, and security considerations. Output only the JSON blueprint.
        """
    )
    
    logger.info(f"Test Planner agent set up with model: {model}")
    return test_planner_agent

def setup_postman_coder(model: str = "gpt-4o-mini") -> Agent:
    """
    Set up the Postman Coder agent for generating Postman collections.
    
    Args:
        model: The model to use for this agent
        
    Returns:
        Configured Postman Coder agent
    """
    postman_coder = Agent(
        name="PostmanCoder",
        model=model,
        instructions="""
        You are a Postman collection generator. You create Postman collections from test blueprints.
        Follow these guidelines:
        1. Create a collection with folders for each logical group of tests
        2. Include pre-request scripts for setup when needed
        3. Add appropriate assertions based on expectedStatus and assertions
        4. Handle dependencies by using environment variables for data sharing
        5. Implement any businessRules provided in the tests
        
        IMPORTANT OUTPUT FORMAT:
        Your output must be a JSON object with this exact structure:
        {
            "type": "postman",
            "content": {
                // Valid Postman collection object with:
                "info": {
                    "name": "API Test Collection",
                    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
                },
                "item": [
                    // Test folders and requests
                ]
            },
            "files": [
                {
                    "filename": "environment.json",
                    "content": {
                        // Environment variables
                    }
                },
                {
                    "filename": "pre-request.js",
                    "content": "// Pre-request script content"
                }
            ]
        }
        """
    )
    
    logger.info(f"Postman Coder agent set up with model: {model}")
    return postman_coder

def setup_playwright_coder(model: str = "gpt-4o-mini") -> Agent:
    """
    Set up the Playwright Coder agent for generating Playwright test scripts.
    
    Args:
        model: The model to use for this agent
        
    Returns:
        Configured Playwright Coder agent
    """
    playwright_coder = Agent(
        name="PlaywrightCoder",
        model=model,
        instructions="""
        You are a Playwright test script generator. You create Playwright API tests from test blueprints.
        Follow these guidelines:
        1. Use the Playwright test framework with appropriate fixtures
        2. Organize tests by logical grouping
        3. Implement proper assertions based on expectedStatus and assertions
        4. Handle dependencies through proper test ordering and data sharing
        5. Implement any businessRules provided in the tests
        
        IMPORTANT OUTPUT FORMAT:
        Your output must be a JSON object with this exact structure:
        {
            "type": "playwright",
            "content": "// Main test file content (e.g., tests/api.spec.ts)",
            "files": [
                {
                    "filename": "tests/api.spec.ts",
                    "content": "// Main test file content"
                },
                {
                    "filename": "tests/fixtures.ts",
                    "content": "// Fixtures and helper functions"
                },
                {
                    "filename": "playwright.config.ts",
                    "content": "// Playwright configuration"
                }
            ]
        }
        """
    )
    
    logger.info(f"Playwright Coder agent set up with model: {model}")
    return playwright_coder

def setup_coder_agent(model: Optional[str] = None) -> Agent:
    """
    Set up the Coder agent for generating test scripts.
    
    Args:
        model: Optional model to use, defaults to settings
        
    Returns:
        Configured Coder agent with appropriate tools
    """
    # If model not specified, use from settings
    if model is None:
        model = settings.get("MODEL_CODING")
        
    logger.info(f"Setting up Coder agent with model: {model}")
    
    # If agents weren't provided, create them
    postman_agent = setup_postman_coder(model)
    playwright_agent = setup_playwright_coder(model)
    
    coder_agent = Agent(
        name="Test Coder",
        model=model,
        instructions="""
        You are an API Test Code Generator. Your role is to generate test scripts based on
        test blueprints for various testing frameworks.
        
        You'll receive a test blueprint with detailed information about API endpoints,
        test cases, and expectations. Your task is to:
        
        1. Generate test scripts for the requested target frameworks (like Postman, Playwright, etc.)
        2. Ensure the scripts correctly implement all tests defined in the blueprint
        3. Create maintainable, well-organized code that follows best practices
        4. Return the code in a structured format that can be saved as files
        
        IMPORTANT OUTPUT FORMAT:
        Your output must be a JSON object with this exact structure:
        {
            "outputs": [
                {
                    "type": "postman",  // or "playwright" for each target
                    "content": {
                        // Main collection/test file content
                        // For Postman: A valid Postman collection object
                        // For Playwright: A valid test file content
                    },
                    "files": [
                        {
                            "filename": "filename.ext",
                            "content": "file content"
                        }
                    ]
                }
            ]
        }
        
        For Postman:
        - Generate a collection.json with the main collection
        - Include environment.json if needed
        - Add any pre-request scripts as separate files
        
        For Playwright:
        - Generate the main test file (e.g., tests/api.spec.ts)
        - Include any fixtures or helper files
        - Add any configuration files if needed
        
        Focus on creating working, production-quality test code with proper error handling,
        assertions, and setup/teardown as needed. Output only the JSON structure with generated code.
        """,
        tools=[
            postman_agent.as_tool(
                tool_name="generate_postman", 
                tool_description="Generate Postman collection from blueprint"
            ),
            playwright_agent.as_tool(
                tool_name="generate_playwright", 
                tool_description="Generate Playwright test scripts from blueprint"
            )
        ]
    )
    
    logger.info(f"Coder agent set up with model: {model}")
    return coder_agent

def setup_triage_agent(model: Optional[str] = None) -> Agent:
    """
    Set up the Triage agent for coordinating the workflow.
    
    Args:
        model: Optional model to use, defaults to settings
        
    Returns:
        Configured Triage agent with appropriate handoffs
    """
    # If model not specified, use from settings
    if model is None:
        model = settings.get("MODEL_TRIAGE")
        
    logger.info(f"Setting up Triage agent with model: {model}")
    
    # Create and configure the triage agent
    agent = Agent(
        name="Test Triage",
        model=model,
        instructions="""
        You are an API Test Triage Assistant. Your role is to analyze test failures and
        suggest potential causes and solutions.
        
        You'll receive test results that include failures, API specifications, and test code.
        Your task is to:
        
        1. Analyze test failures to identify patterns and root causes
        2. Determine if issues are with the API implementation, test code, or specification
        3. Suggest specific fixes or workarounds for each issue
        4. Prioritize issues based on severity and impact
        
        Focus on providing actionable insights that help developers quickly resolve the issues.
        Consider all possible causes including environment issues, timing problems, data validation,
        and API behavior changes.
        """
    )
    
    logger.info(f"Triage agent set up with model: {model}")
    return agent

def setup_all_agents() -> Dict[str, Agent]:
    """
    Set up all agents with configuration from settings.
    
    Returns:
        Dictionary of agents by name
    """
    # Load model names from settings
    planning_model = settings.get("MODEL_PLANNING")
    coding_model = settings.get("MODEL_CODING")
    triage_model = settings.get("MODEL_TRIAGE")
    
    logger.info(f"Setting up all agents with models: planning={planning_model}, coding={coding_model}, triage={triage_model}")
    
    # Create all agents
    agents = {
        "planning": setup_test_planner_agent(planning_model),
        "coding": setup_coder_agent(coding_model),
        "triage": setup_triage_agent(triage_model)
    }
    
    return agents 