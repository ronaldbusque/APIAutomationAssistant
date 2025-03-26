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
        5. Create test flows representing end-to-end scenarios across multiple endpoints
        6. Output a complete test blueprint as a JSON object
        
        IMPORTANT: If test data setup or test flow instructions are not provided, you must:
        - Create appropriate test data based on the API schema and example values
        - Determine logical test sequences based on API dependencies (e.g., create before read)
        - Define test flows for common user journeys and business processes
        - Ensure comprehensive test coverage for all endpoints
        - Generate realistic test values for different scenarios (valid/invalid inputs)
        
        ENTERPRISE FEATURES TO INCLUDE:
        - Test Flows: Define sequences of tests that represent user journeys or business processes
        - Environment Variables: Define variables needed across tests (API keys, tokens, etc.)
        - Data-Driven Testing: Create tests that iterate over multiple data sets
        - Variable Extraction: Extract data from responses to use in subsequent tests
        - Setup/Teardown: Define hooks for setting up and cleaning up test data
        - Retry Policies: Configure automatic retries for flaky tests
        
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
          ],
          "testFlows": [
            {
              "name": "Flow name",
              "description": "Flow description",
              "steps": [
                {
                  "testId": "test-id-reference",
                  "description": "Step description"
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
        - Reference previous test responses using the format {{test-id.response.body.field}}
        - Test flows must reference valid test IDs
        
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
        
        IMPORTANT: The blueprints contain advanced enterprise features that you must implement correctly:
        
        1. VARIABLE HANDLING:
           - Extract variables from responses using the 'variableExtraction' field in tests
           - Store extracted variables in Postman environment variables
           - Reference variables using the format {{variableName}} in subsequent requests
           - Support extracting from response body with JSONPath, headers, and status
           - Use pre-request and test scripts for advanced variable manipulation
        
        2. TEST FLOWS:
           - Implement test flows as folders with proper sequencing
           - Use collection runner for orchestrating test flows
           - Ensure proper data sharing between requests in a flow
           - Add descriptions that document the flow's steps and purpose
           - Use folder descriptions to document data dependencies between steps
        
        3. DATA-DRIVEN TESTING:
           - Create parameterized requests using data variables
           - Set up data files or environment variable sets for different test data
           - Implement CSV data sources for extensive data sets
           - Include data descriptions in request names
           - Handle different expected results for each data set
        
        4. RETRY POLICIES:
           - Implement retry logic in pre-request scripts
           - Support both global and request-specific retry settings
           - Add exponential backoff for sophisticated retries
           - Implement status code filtering for retries
           - Add proper logging of retry attempts
        
        5. ENVIRONMENT VARIABLES:
           - Generate environment variable files for different environments
           - Create initial and current value pairs
           - Support hierarchical variable references
           - Include validation for required environment variables
           - Document environment variables in collection description
        
        6. MOCK DATA:
           - Set up mock servers for specific scenarios
           - Implement mock response examples
           - Support conditional mocking based on request properties
           - Include detailed examples for each mock scenario
           - Generate documentation for mock server setup
        
        IMPLEMENTATION REQUIREMENTS:
        
        1. COLLECTION ORGANIZATION:
           - Create a well-structured collection with logical folders
           - Group related endpoints together
           - Order requests to follow natural API workflows
           - Add descriptions at collection, folder, and request levels
           - Implement proper authorization at appropriate levels
        
        2. CODE QUALITY:
           - Write clean, well-commented pre-request and test scripts
           - Follow JavaScript best practices
           - Include proper error handling
           - Create reusable script functions in collection variables
           - Use descriptive names for requests, variables, and tests
        
        IMPORTANT OUTPUT FORMAT:
        Your output must be a JSON object with this exact structure:
        {
            "type": "postman",
            "content": {
                // Valid Postman collection object with:
                "info": {
                    "name": "API Test Collection",
                    "description": "Comprehensive API test suite with enterprise features",
                    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
                },
                "item": [
                    // Test folders and requests with proper scripts
                ]
            },
            "files": [
                {
                    "filename": "environments/development.json",
                    "content": {
                        // Development environment variables
                    }
                },
                {
                    "filename": "environments/production.json",
                    "content": {
                        // Production environment variables
                    }
                },
                {
                    "filename": "data/test-data.csv",
                    "content": "// CSV data for data-driven tests"
                },
                {
                    "filename": "README.md",
                    "content": "// Collection documentation"
                }
            ]
        }
        
        Focus on creating a professional, maintainable Postman collection that implements all the enterprise features correctly and follows Postman best practices.
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
        
        IMPORTANT: The blueprints contain advanced enterprise features that you must implement correctly:
        
        1. VARIABLE HANDLING:
           - Extract variables from responses using the 'variableExtraction' field in tests
           - Reference variables using the format {{testId.variableName}}
           - Implement a robust variable store system for sharing data between tests
           - Support extracting data from response body with JSONPath, headers, and status
           - Implement variable resolution for strings, objects, and arrays
        
        2. TEST FLOWS:
           - Implement each test flow as a separate test suite
           - Each flow should execute tests in the specified order
           - Ensure proper data sharing between tests in a flow
           - Use test.step for each step in the flow
           - Maintain state between steps using fixtures and the variable store
           - Document the data dependencies between steps
        
        3. DATA-DRIVEN TESTING:
           - Use 'dataProvider' for parametrized tests
           - Create separate test cases for each data iteration
           - Support different expected results for each data set
           - Include data description in test names
           - Use test.describe.parallel for independent iterations
        
        4. RETRY POLICIES:
           - Implement blueprint's retryPolicy settings
           - Support both global and test-specific retry counts
           - Add exponential backoff for sophisticated retries
           - Implement status code filtering for retries
           - Add proper logging of retry attempts
        
        5. ENVIRONMENT VARIABLES:
           - Generate proper .env files with all required variables
           - Support different variable types (string, number, boolean, object)
           - Create an environment manager for accessing variables
           - Support different environment configurations (dev, staging, prod)
           - Include validation for required environment variables
        
        6. MOCK DATA:
           - Implement mock data handling as specified in tests
           - Support conditional mocking based on request properties
           - Support probability-based and count-based mocking
           - Add delay option for simulating slow responses
           - Provide clear documentation on mock usage
        
        IMPLEMENTATION REQUIREMENTS:
        
        1. FILE ORGANIZATION:
           - Create main test files grouped by resource under /tests/api
           - Implement test flows in separate files under /tests/flows
           - Create utility files for shared functionality under /tests/utils
           - Add fixtures under /tests/fixtures
           - Generate proper configuration files and documentation
        
        2. CODE QUALITY:
           - Use TypeScript for better type safety
           - Follow best practices for Playwright tests
           - Include proper error handling and logging
           - Create reusable fixtures and utilities
           - Use descriptive test names and clear comments
        
        IMPORTANT OUTPUT FORMAT:
        Your output must be a JSON object with this exact structure:
        {
            "type": "playwright",
            "content": "// Main entry point description",
            "files": [
                {
                    "filename": "tests/api/users.spec.ts",
                    "content": "// Users API test implementation"
                },
                {
                    "filename": "tests/fixtures/auth.fixtures.ts",
                    "content": "// Auth fixtures"
                },
                {
                    "filename": "tests/utils/variable-store.ts",
                    "content": "// Variable handling utilities"
                },
                {
                    "filename": "tests/flows/user-journey.spec.ts",
                    "content": "// Test flow implementation"
                },
                {
                    "filename": "playwright.config.ts",
                    "content": "// Playwright configuration"
                },
                {
                    "filename": ".env.example",
                    "content": "// Environment variables template"
                },
                {
                    "filename": "README.md",
                    "content": "// Usage documentation"
                }
            ]
        }
        
        Focus on creating production-quality tests that handle all the enterprise features properly.
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
        
        ## ENTERPRISE FEATURES TO IMPLEMENT
        
        The blueprint will contain advanced enterprise features that must be correctly implemented:
        
        ### 1. VARIABLE HANDLING
        
        - Extract variables from API responses according to the 'variableExtraction' section
        - Reference extracted variables in subsequent tests using {{variableName}} format
        - Implement proper variable scoping (test-level, flow-level, global)
        - Support variable extraction from different sources (body, headers, status)
        - Ensure variable resolution works for complex nested objects
        
        ### 2. TEST FLOWS
        
        - Implement test flows as ordered sequences with proper data sharing
        - Ensure proper state management between flow steps
        - Validate flow prerequisites before executing dependent tests
        - Maintain detailed logging of flow execution
        - Document data dependencies between steps
        
        ### 3. DATA-DRIVEN TESTING
        
        - Parameterize tests using the provided data sets
        - Support multiple iterations with different expected outcomes
        - Include clear descriptions for each data variation
        - Implement proper error handling for different data scenarios
        - Support both positive and negative test cases
        
        ### 4. RETRY POLICIES
        
        - Implement retry logic based on blueprint specifications
        - Support global and test-specific retry configurations
        - Add exponential backoff where specified
        - Handle specific status codes differently for retries
        - Log retry attempts and outcomes
        
        ### 5. ENVIRONMENT VARIABLES
        
        - Generate proper environment configuration for different environments
        - Support variable substitution in requests
        - Validate required environment variables
        - Create comprehensive environment setup documentation
        - Support hierarchical variable references
        
        ### 6. MOCK DATA
        
        - Implement mock responses for specified scenarios
        - Support conditional mocking based on request properties
        - Set up probability-based and count-based mock responses
        - Add proper documentation for mock setup
        - Include examples of mock usage
        
        ## OUTPUT FORMAT REQUIREMENTS
        
        Your output must be a JSON object with this exact structure:
        ```json
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
        ```
        
        ## IMPLEMENTATION BEST PRACTICES
        
        - Create well-organized file structures with logical grouping
        - Follow framework-specific best practices and idioms
        - Use strong typing where applicable (TypeScript for Playwright)
        - Implement proper error handling and logging
        - Create reusable utilities and fixtures
        - Add comprehensive documentation
        - Include sample usage examples
        
        Focus on creating production-ready, maintainable test code that properly implements
        all the features defined in the blueprint. Output only the JSON structure with generated code.
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