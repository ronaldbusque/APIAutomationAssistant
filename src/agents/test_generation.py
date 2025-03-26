"""
Test Generation Module - Core logic for generating tests from OpenAPI specs

This module orchestrates the process of generating API tests by:
1. Validating and parsing OpenAPI specs
2. Calculating complexity for model selection
3. Generating test blueprints
4. Validating blueprints
5. Generating test scripts from blueprints
"""

import json
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple, Callable, Union

from ..utils.spec_validation import validate_openapi_spec
from ..utils.model_selection import ModelSelectionStrategy
from ..utils.execution import run_agent_with_retry, run_agent_with_streaming, RetryConfig, RunConfig
from ..blueprint.validation import validate_and_clean_blueprint
from ..errors.exceptions import SpecValidationError, BlueprintGenerationError, ScriptGenerationError
from ..blueprint.models import Blueprint
from ..models.script_output import ScriptOutput, TargetOutput, FileContent, ScriptType

from .setup import setup_test_planner_agent, setup_coder_agent

# Create the logger
logger = logging.getLogger(__name__)

def calculate_spec_complexity(parsed_spec: Dict[str, Any]) -> float:
    """
    Calculate the complexity of an OpenAPI spec for model selection.
    
    Args:
        parsed_spec: Parsed OpenAPI specification
        
    Returns:
        Complexity score (0-1) where higher values indicate more complex specs
    """
    # Initialize weights for different factors
    weights = {
        "size": 0.4,          # Weight for overall spec size
        "endpoints": 0.6,     # Weight for number of endpoints
    }
    
    # Calculate size score (based on JSON serialized length)
    spec_size = len(json.dumps(parsed_spec))
    max_size = 1_000_000  # 1MB max size
    size_score = min(1.0, spec_size / max_size)
    
    # Calculate endpoint complexity
    path_count = len(parsed_spec.get("paths", {}))
    endpoint_count = 0
    complex_endpoints = 0
    
    # Count endpoints and assess their complexity
    for path, methods in parsed_spec.get("paths", {}).items():
        endpoint_count += len([m for m in methods if m.lower() in [
            "get", "post", "put", "delete", "patch", "options", "head"
        ]])
        
        # Check for complexity factors in endpoints
        for method, details in methods.items():
            if method.lower() not in ["get", "post", "put", "delete", "patch", "options", "head"]:
                continue
                
            # Check request body complexity
            if details.get("requestBody") and "content" in details.get("requestBody", {}):
                for content_type, content_details in details["requestBody"]["content"].items():
                    if "schema" in content_details and "properties" in content_details["schema"]:
                        # More complex if it has a request body with many properties
                        property_count = len(content_details["schema"]["properties"])
                        if property_count > 5:
                            complex_endpoints += 1
            
            # Check for complex response schemas
            for status, response in details.get("responses", {}).items():
                if "content" in response:
                    for content_type, content_details in response["content"].items():
                        if "schema" in content_details and "properties" in content_details["schema"]:
                            # More complex if it has a response with many properties
                            property_count = len(content_details["schema"]["properties"])
                            if property_count > 5:
                                complex_endpoints += 1
    
    # Calculate endpoints score
    max_endpoints = 500  # reasonable upper limit
    endpoint_score = min(1.0, endpoint_count / max_endpoints)
    
    # Calculate complexity score with additional factor for complex endpoints
    complexity_score = (
        weights["size"] * size_score +
        weights["endpoints"] * endpoint_score +
        0.2 if complex_endpoints / max(1, endpoint_count) > 0.3 else 0  # Bonus for many complex endpoints
    )
    
    # Ensure score is in range 0-1
    complexity_score = min(1.0, max(0.0, complexity_score))
    
    logger.info(f"Calculated complexity score: {complexity_score:.2f} (size: {spec_size}, endpoints: {endpoint_count})")
    return complexity_score

def construct_planner_message(
    spec: str,
    mode: str,
    business_rules: Optional[str] = None,
    test_data: Optional[str] = None,
    test_flow: Optional[str] = None,
    parse_warnings: List[str] = []
) -> str:
    """
    Construct a message for the test planner agent.
    
    Args:
        spec: OpenAPI spec (JSON-serialized if parsed, raw string otherwise)
        mode: "basic" or "advanced"
        business_rules: Optional business rules
        test_data: Optional test data setup
        test_flow: Optional test flow
        parse_warnings: List of parsing warnings
        
    Returns:
        Formatted message for the test planner agent
    """
    message = f"OpenAPI Spec:\n{spec}\n\n"
    if parse_warnings:
        message += f"Parsing Warnings:\n{'; '.join(parse_warnings)}\n\n"
    message += f"Mode: {mode}\n"
    if business_rules:
        message += f"Business Rules:\n{business_rules}\n"
    if test_data:
        message += f"Test Data:\n{test_data}\n"
    if test_flow:
        message += f"Test Flow:\n{test_flow}\n"
    return message

async def process_openapi_spec(
    spec_text: str, 
    mode: str,
    business_rules: Optional[str] = None,
    test_data: Optional[str] = None,
    test_flow: Optional[str] = None,
    progress_callback: Optional[Callable] = None
) -> Tuple[Dict[str, Any], str]:
    """
    Process an OpenAPI spec and generate a test blueprint.
    
    Args:
        spec_text: Raw OpenAPI spec text
        mode: "basic" or "advanced"
        business_rules: Optional business rules
        test_data: Optional test data setup
        test_flow: Optional test flow
        progress_callback: Optional callback for progress updates
        
    Returns:
        Tuple of (blueprint, trace_id)
    """
    try:
        # Validate and parse the spec
        parsed_spec, parse_warnings = await validate_openapi_spec(spec_text)
        
        # Calculate complexity for model selection
        complexity = calculate_spec_complexity(parsed_spec)
        
        # Set up model selection strategy
        model_strategy = ModelSelectionStrategy()
        
        # Set up test planner agent with appropriate model
        test_planner = setup_test_planner_agent(
            model=model_strategy.select_model("planning", complexity)
        )
        
        # Construct message for the test planner
        message = construct_planner_message(
            json.dumps(parsed_spec) if len(json.dumps(parsed_spec)) < 100000 else spec_text,
            mode,
            business_rules,
            test_data,
            test_flow,
            parse_warnings
        )
        
        # Run test planner with streaming if progress callback is provided
        if progress_callback:
            # Progress reporting handler
            async def report_progress(agent_name, item_type, content):
                # Create more descriptive progress message based on agent and item type
                message = content
                if isinstance(content, str):
                    # Limit message length to prevent UI issues, but try to keep meaningful content
                    message = content[:150] + ("..." if len(content) > 150 else "")
                elif isinstance(content, dict):
                    message = content.get("message", "Processing...")
                
                # Add more context based on the agent and item type
                if agent_name == "Test Planner" and item_type == "MessageContentItem":
                    message = f"Planning tests: {message}"
                elif agent_name == "Coder" and item_type == "MessageContentItem":
                    message = f"Generating code: {message}"
                
                await progress_callback(
                    stage="planning",
                    progress={
                        "percent": 50, # We keep percent for backward compatibility
                        "message": message,
                        "agent": agent_name,
                        "item_type": item_type,
                        "trace_id": trace_id
                    },
                    agent=agent_name
                )
            
            try:
                # Run with streaming
                config = RunConfig(complexity=complexity, task="planning")
                result = await run_agent_with_streaming(
                    test_planner,
                    message,
                    report_progress,
                    config=config,
                    model_selection=model_strategy
                )
                # Ensure the result is a dictionary - parse from JSON if it's a string
                if isinstance(result, str):
                    try:
                        blueprint = json.loads(result)
                    except json.JSONDecodeError as je:
                        logger.error(f"Failed to parse streaming result as JSON: {str(je)}")
                        # Extract JSON object from the string if possible
                        import re
                        json_match = re.search(r'(\{.*\})', result, re.DOTALL)
                        if json_match:
                            try:
                                blueprint = json.loads(json_match.group(1))
                            except json.JSONDecodeError:
                                logger.error("Failed to extract valid JSON from the result")
                                raise BlueprintGenerationError("Invalid blueprint format from streaming agent")
                        else:
                            raise BlueprintGenerationError("Failed to extract blueprint from streaming agent result")
                else:
                    blueprint = result
                trace_id = "streaming"  # Placeholder for streaming mode
            except Exception as e:
                logger.error(f"Streaming execution failed: {str(e)}, falling back to non-streaming mode")
                # Fall back to non-streaming mode
                retry_config = RetryConfig()
                run_config = RunConfig(
                    complexity=complexity,
                    task="planning"
                )
                result, trace_id = await run_agent_with_retry(
                    test_planner,
                    message,
                    config=retry_config,
                    run_config=run_config,
                    model_selection=model_strategy
                )
                # Get raw dictionary from result instead of using final_output_as
                blueprint = result.final_output
        
        # Validate and clean up the blueprint
        try:
            # Ensure blueprint is a dictionary before creating the model
            if isinstance(blueprint, str):
                try:
                    blueprint = json.loads(blueprint)
                except json.JSONDecodeError:
                    logger.error("Failed to parse blueprint string as JSON")
                    # Try to extract JSON part
                    import re
                    json_match = re.search(r'(\{.*\})', blueprint, re.DOTALL)
                    if json_match:
                        try:
                            blueprint = json.loads(json_match.group(1))
                        except:
                            # Create a minimal blueprint
                            logger.warning("Creating minimal blueprint due to parse failure")
                            blueprint = {
                                "apiName": "Unknown API",
                                "version": "1.0.0",
                                "groups": []
                            }
                    else:
                        # Create a minimal blueprint
                        logger.warning("Creating minimal blueprint due to parse failure")
                        blueprint = {
                            "apiName": "Unknown API",
                            "version": "1.0.0", 
                            "groups": []
                        }
            
            validation_warnings = []
            try:
                # Try to create and validate the blueprint model
                blueprint_model = Blueprint(**blueprint)
                blueprint_dict, validation_warnings = await validate_and_clean_blueprint(blueprint_model)
            except Exception as validation_error:
                # If the model creation fails, use the dict directly
                logger.warning(f"Blueprint model validation error, using dict directly: {str(validation_error)}")
                blueprint_dict, validation_warnings = await validate_and_clean_blueprint(blueprint)
                
        except Exception as e:
            logger.error(f"Blueprint processing error: {str(e)}")
            # Return a minimal working blueprint
            blueprint_dict = {
                "apiName": blueprint.get("apiName", "Unknown API"),
                "version": blueprint.get("version", "1.0.0"),
                "groups": blueprint.get("groups", [])
            }
            validation_warnings = [f"Blueprint validation had errors: {str(e)}"]
        
        # Log trace ID for debugging
        logger.info(f"Blueprint generation completed with trace_id: {trace_id}")
        if validation_warnings:
            logger.info(f"Blueprint validation produced {len(validation_warnings)} warnings")
            for warning in validation_warnings[:5]:  # Log first 5 warnings
                logger.warning(f"Blueprint warning: {warning}")
            if len(validation_warnings) > 5:
                logger.warning(f"... and {len(validation_warnings) - 5} more warnings")
        
        return blueprint_dict, trace_id
        
    except SpecValidationError as e:
        logger.error(f"Spec validation error: {e.message}")
        raise
    except Exception as e:
        error_message = f"Blueprint generation error: {str(e)}"
        logger.error(error_message)
        raise BlueprintGenerationError(error_message, trace_id="error")

async def generate_test_scripts(
    blueprint: Dict[str, Any],
    targets: List[str],
    progress_callback: Optional[Callable] = None
) -> Tuple[Dict[str, Dict[str, str]], str]:
    """
    Generate test scripts from a blueprint for specified targets.
    
    Args:
        blueprint: Test blueprint
        targets: List of target frameworks (e.g., ["postman", "playwright"])
        progress_callback: Optional callback for progress updates
        
    Returns:
        Dictionary mapping target frameworks to generated scripts, and trace ID
    """
    try:
        # Try to validate and clean the blueprint, but don't let validation errors block generation
        try:
            cleaned_blueprint, validation_warnings = await validate_and_clean_blueprint(blueprint)
            
            # Log validation warnings but continue with the cleaned blueprint
            if validation_warnings:
                logger.info(f"Blueprint validation produced {len(validation_warnings)} warnings")
                for warning in validation_warnings[:3]:  # Log first 3 warnings
                    logger.warning(f"Blueprint warning: {warning}")
                if len(validation_warnings) > 3:
                    logger.warning(f"... and {len(validation_warnings) - 3} more warnings")
        except Exception as e:
            # If validation fails completely, use the original blueprint
            logger.warning(f"Blueprint validation failed, using original: {str(e)}")
            cleaned_blueprint = blueprint
            # Ensure the blueprint has the minimum required structure
            if not cleaned_blueprint.get("apiName"):
                cleaned_blueprint["apiName"] = "Unknown API"
            if not cleaned_blueprint.get("version"):
                cleaned_blueprint["version"] = "1.0.0"
            if not cleaned_blueprint.get("groups"):
                cleaned_blueprint["groups"] = []
        
        # Calculate complexity for model selection
        complexity = calculate_blueprint_complexity(blueprint)
        
        # Set up model selection strategy
        model_strategy = ModelSelectionStrategy()
        
        # Select the appropriate model based on complexity
        model = model_strategy.select_model("code_generation", complexity)
        logger.info(f"Selected model {model} for script generation with complexity {complexity}")
        
        # Set up coder agent with the selected model
        coder_agent = setup_coder_agent(model=model)
        
        # Prepare input data for the coder agent, always include the original blueprint too
        input_data = {
            "blueprint": cleaned_blueprint,
            "original_blueprint": blueprint,  # Include the original in case the agent needs it
            "targets": targets,
            # Add context with enterprise features and template examples
            "context": {
                "instructions": """
                IMPORTANT: The examples below are PATTERNS to follow, not actual code to copy directly. 
                Your generated tests should be based on the specific details from the blueprint, not these examples.
                Each example demonstrates a pattern or technique that you can apply to the ACTUAL endpoints and tests from the blueprint.
                """,
                "templates_directory": "src/examples/templates",
                "features": {
                    "variable_extraction": {
                        "description": "Pattern: Extract variables from API responses and use them in subsequent tests",
                        "example": """
                        // PATTERN EXAMPLE - adapt to actual endpoints from the blueprint
                        const response = await request.post('/users', { name: 'John' });
                        const userId = response.body.id;
                        variableStore.set('userId', userId);
                        
                        // Later, use the variable in another request
                        const userResponse = await request.get(`/users/${variableStore.get('userId')}`);
                        """
                    },
                    "test_flow": {
                        "description": "Pattern: Implement test flows as defined in the blueprint",
                        "example": """
                        // PATTERN EXAMPLE - adapt to actual endpoints from the blueprint
                        createTestFlow(
                          'User Management',
                          'Complete flow for creating and managing users',
                          [
                            { testId: 'auth-login', description: 'Login to get authentication token' },
                            { testId: 'create-user', description: 'Create a new user' },
                            { testId: 'get-user', description: 'Retrieve the user profile' },
                            { testId: 'update-user', description: 'Update user information' },
                            { testId: 'delete-user', description: 'Delete the user' }
                          ],
                          {
                            'auth-login': async (state) => {
                              // Test implementation with shared state
                              const response = await sendRequest({
                                url: '/auth/login',
                                method: 'POST',
                                body: { username: 'test', password: 'password' }
                              });
                              state.variables.token = response.body.token;
                            },
                            // Additional step implementations...
                          }
                        );
                        """
                    },
                    "retry_policy": {
                        "description": "Pattern: Configure retry policies for flaky tests",
                        "example": """
                        // PATTERN EXAMPLE - adapt to actual endpoints from the blueprint
                        const rateLimitPolicy = createRetryPolicy({
                          maxRetries: 3,
                          retryDelay: 1000,
                          exponentialBackoff: true,
                          retriableStatusCodes: [429, 503],
                          timeout: 10000
                        });
                        
                        // Apply retry policy to a request
                        const response = await sendRequest({
                          url: '/high-traffic-endpoint',
                          method: 'GET',
                          retryPolicy: rateLimitPolicy
                        });
                        """
                    },
                    "environment_variables": {
                        "description": "Pattern: Manage environment variables for different deployment environments",
                        "example": """
                        // PATTERN EXAMPLE - adapt to actual endpoints from the blueprint
                        env.setEnvironment('staging');
                        
                        // Use environment variables in requests
                        const response = await sendRequest({
                          url: `${env.getBaseUrl()}/users`,
                          method: 'GET',
                          headers: env.getHeaders()
                        });
                        
                        // Access specific config values
                        const timeout = env.get('timeouts.request', 5000);
                        """
                    },
                    "mock_data": {
                        "description": "Pattern: Generate and use mock data for testing",
                        "example": """
                        // PATTERN EXAMPLE - adapt to actual endpoints from the blueprint
                        const userData = DataGenerator.randomUser();
                        
                        // Register a mock response
                        mockServer.enableMocking(true);
                        mockServer.mock('/users', 'POST', {
                          status: 201,
                          body: { id: DataGenerator.randomString(10), ...userData },
                          delay: 100
                        });
                        
                        // Use the mock in a test
                        const response = await sendRequest({
                          url: '/users',
                          method: 'POST',
                          body: userData,
                          useMock: true
                        });
                        """
                    },
                    "setup_teardown": {
                        "description": "Pattern: Implement setup and teardown hooks for tests",
                        "example": """
                        // PATTERN EXAMPLE - adapt to actual endpoints from the blueprint
                        apiTest.beforeAll(async ({ request, env }) => {
                          // Set up test data
                          const response = await request.post('/test-data/setup', {
                            data: { users: 5, items: 10 }
                          });
                          
                          // Store the cleanup token
                          env.set('cleanupToken', response.body.cleanupToken);
                        });
                        
                        apiTest.afterAll(async ({ request, env }) => {
                          // Clean up test data
                          await request.post('/test-data/cleanup', {
                            data: { token: env.get('cleanupToken') }
                          });
                        });
                        """
                    }
                }
            }
        }
        
        # Log blueprint structure for debugging
        if cleaned_blueprint and "groups" in cleaned_blueprint:
            logger.info(f"Blueprint for {cleaned_blueprint.get('apiName', 'Unknown API')} has {len(cleaned_blueprint.get('groups', []))} groups")
            for i, group in enumerate(cleaned_blueprint.get("groups", [])):
                group_name = group.get("name", f"Group {i+1}")
                test_count = len(group.get("tests", []))
                logger.info(f"  Group '{group_name}' has {test_count} tests")
                # Log first few tests as examples
                for j, test in enumerate(group.get("tests", [])[:3]):  # Show first 3 tests per group
                    logger.info(f"    Test '{test.get('name', test.get('id', f'Test {j+1}'))}': {test.get('method', 'GET')} {test.get('endpoint', '/unknown')} → {test.get('expectedStatus', 200)}")
                if len(group.get("tests", [])) > 3:
                    logger.info(f"    ... and {len(group.get('tests', [])) - 3} more tests in this group")
        else:
            logger.warning("Blueprint has no groups or invalid structure!")
        
        # Log the exact input data being sent to the agent
        logger.info("=== FULL INPUT DATA BEING SENT TO CODER AGENT ===")
        try:
            # Log each key separately to avoid potential serialization issues
            logger.info("Input data keys: %s", list(input_data.keys()))
            
            # Log the actual blueprint content
            logger.info("=== BLUEPRINT CONTENT ===")
            if cleaned_blueprint:
                logger.info("Blueprint API Name: %s", cleaned_blueprint.get('apiName'))
                logger.info("Blueprint Version: %s", cleaned_blueprint.get('version'))
                logger.info("Blueprint Description: %s", cleaned_blueprint.get('description'))
                logger.info("Blueprint Base URL: %s", cleaned_blueprint.get('baseUrl'))
                
                # Log each group and its tests
                for group in cleaned_blueprint.get('groups', []):
                    logger.info("Group: %s", group.get('name'))
                    for test in group.get('tests', []):
                        logger.info("  Test: %s", test.get('id'))
                        logger.info("    Endpoint: %s %s", test.get('method'), test.get('endpoint'))
                        logger.info("    Expected Status: %s", test.get('expectedStatus'))
                        if test.get('headers'):
                            logger.info("    Headers: %s", test.get('headers'))
                        if test.get('parameters'):
                            logger.info("    Parameters: %s", test.get('parameters'))
                        if test.get('body'):
                            logger.info("    Body: %s", test.get('body'))
            else:
                logger.warning("No blueprint content available!")
            logger.info("=== END BLUEPRINT CONTENT ===")
            
            logger.info("Targets: %s", targets)
            logger.info("Context keys: %s", list(input_data.get("context", {}).keys()))
            logger.info("Features keys: %s", list(input_data.get("context", {}).get("features", {}).keys()))
        except Exception as e:
            logger.error("Error logging input data structure: %s", str(e))
        logger.info("=== END INPUT DATA ===")
        
        # Ask the coder agent to generate scripts
        message = f"""Generate API test scripts based EXCLUSIVELY on the provided blueprint. Target frameworks: {', '.join(targets)}.

CRITICAL: You MUST generate tests that match the EXACT endpoints, methods, and test cases from the blueprint. The examples below are ONLY for reference on how to implement features - they should NOT be copied or used as templates.

Here is the actual blueprint content you MUST use:

API Name: {cleaned_blueprint.get('apiName', 'Unknown API')}
Version: {cleaned_blueprint.get('version', '1.0.0')}
Base URL: {cleaned_blueprint.get('baseUrl', 'http://localhost:3000')}

Test Groups:
{chr(10).join(f'''
Group: {group.get('name', 'Unnamed Group')}
Tests:
{chr(10).join(f'''  - {test.get('id', 'Unnamed Test')}
    Endpoint: {test.get('method', 'GET')} {test.get('endpoint', '/unknown')}
    Expected Status: {test.get('expectedStatus', 200)}
    {f"Headers: {test.get('headers', {})}" if test.get('headers') else ""}
    {f"Parameters: {test.get('parameters', [])}" if test.get('parameters') else ""}
    {f"Body: {test.get('body', {})}" if test.get('body') else ""}''' for test in group.get('tests', []))}''' for group in cleaned_blueprint.get('groups', []))}

Your generated tests MUST:
1. Use the EXACT endpoints from the blueprint above
2. Use the EXACT HTTP methods from the blueprint above
3. Expect the EXACT status codes from the blueprint above
4. Follow the EXACT test groups from the blueprint above
5. Include the EXACT test names from the blueprint above

DO NOT use the example endpoints or methods. Use ONLY the endpoints and methods from the blueprint above.

The examples below show HOW to implement features, but you MUST use your own endpoints and methods from the blueprint above."""
        
        # Log the exact message being sent to the agent
        logger.info("=== FULL MESSAGE BEING SENT TO CODER AGENT ===")
        logger.info(message)
        logger.info("=== END MESSAGE ===")
        
        # Run with streaming if progress callback is provided
        if progress_callback:
            # Progress reporting handler
            async def report_progress(agent_name, item_type, content):
                # Create more descriptive progress message based on agent and item type
                message = content
                if isinstance(content, str):
                    # Limit message length to prevent UI issues, but try to keep meaningful content
                    message = content[:150] + ("..." if len(content) > 150 else "")
                elif isinstance(content, dict):
                    message = content.get("message", "Processing...")
                
                # Add more context based on the agent and item type
                if agent_name == "Test Planner" and item_type == "MessageContentItem":
                    message = f"Planning tests: {message}"
                elif agent_name == "Coder" and item_type == "MessageContentItem":
                    message = f"Generating code: {message}"
                
                await progress_callback(
                    stage="coding",
                    progress={
                        "percent": 50, # We keep percent for backward compatibility
                        "message": message,
                        "agent": agent_name,
                        "item_type": item_type,
                        "trace_id": trace_id
                    },
                    agent=agent_name
                )
            
            try:
                # Run with streaming
                config = RunConfig(
                    complexity=complexity,
                    task="code_generation",
                    input_data=input_data
                )
                result = await run_agent_with_streaming(
                    coder_agent,
                    message,
                    report_progress,
                    config=config,
                    model_selection=model_strategy
                )
                
                # Parse the result as a ScriptOutput object
                try:
                    # Ensure result is a dictionary
                    if isinstance(result, str):
                        import json
                        try:
                            result = json.loads(result)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse streaming result as JSON: {str(e)}")
                            # Extract JSON object from the string if possible
                            import re
                            json_match = re.search(r'(\{.*\})', result, re.DOTALL)
                            if json_match:
                                try:
                                    result = json.loads(json_match.group(1))
                                except json.JSONDecodeError:
                                    logger.error("Failed to extract valid JSON from the result")
                                    raise BlueprintGenerationError("Invalid blueprint format from streaming agent")
                            else:
                                raise BlueprintGenerationError("Failed to extract blueprint from streaming agent result")
                    
                    # Create ScriptOutput from the result
                    logger.info(f"Creating ScriptOutput from result type {type(result)}")
                    
                    # Handle empty result data
                    if result is None or (isinstance(result, str) and not result.strip()):
                        logger.warning("Received empty result from streaming agent")
                        # Create a default output for the requested targets
                        output = ScriptOutput(
                            apiName="API Tests",
                            version="1.0.0",
                            outputs=[
                                TargetOutput(
                                    name=f"{target.capitalize()} Scripts",
                                    type=ScriptType(target),
                                    content={"info": f"Default content created for {target}"},
                                    files=[
                                        FileContent(
                                            filename=f"default_{target}.txt",
                                            content=f"// This is a placeholder created for {target} when the streaming agent returned an empty response"
                                        )
                                    ]
                                ) for target in targets
                            ]
                        )
                    else:
                        try:
                            output = ScriptOutput.from_dict(result)
                        except Exception as e:
                            logger.error(f"Failed to create ScriptOutput: {str(e)}")
                            # Create a minimal valid output
                            logger.warning("Creating minimal ScriptOutput due to parse failure")
                            output = ScriptOutput(
                                apiName="API Tests",
                                version="1.0.0",
                                outputs=[
                                    TargetOutput(
                                        name="Default Test Scripts",
                                        type=ScriptType.CUSTOM if "custom" in targets else ScriptType(targets[0]),
                                        content={"info": "Default content created for invalid response"},
                                        files=[
                                            FileContent(
                                                filename="default.txt",
                                                content=f"// This is a placeholder created when the agent returned an invalid response.\n// Targets requested: {', '.join(targets)}"
                                            )
                                        ]
                                    )
                                ]
                            )
                except Exception as e:
                    logger.error(f"Error processing streaming result: {str(e)}")
                    raise
                trace_id = "streaming"  # Placeholder for streaming mode
            except Exception as e:
                logger.error(f"Streaming execution failed: {str(e)}, falling back to non-streaming mode")
                # Fall back to non-streaming mode
                retry_config = RetryConfig()
                run_config = RunConfig(
                    complexity=complexity,
                    task="code_generation",
                    input_data=input_data
                )
                result, trace_id = await run_agent_with_retry(
                    coder_agent,
                    message,
                    config=retry_config,
                    run_config=run_config,
                    model_selection=model_strategy
                )
                # Get raw dictionary from result instead of using final_output_as
                try:
                    # Extract raw output from the result
                    result_data = result.final_output
                    logger.info(f"Creating ScriptOutput from result_data type {type(result_data)}")
                    
                    # Handle empty result data
                    if result_data is None or (isinstance(result_data, str) and not result_data.strip()):
                        logger.warning("Received empty result data from agent")
                        # Create a default output for the requested targets
                        output = ScriptOutput(
                            apiName="API Tests",
                            version="1.0.0",
                            outputs=[
                                TargetOutput(
                                    name=f"{target.capitalize()} Scripts",
                                    type=ScriptType(target),
                                    content={"info": f"Default content created for {target}"},
                                    files=[
                                        FileContent(
                                            filename=f"default_{target}.txt",
                                            content=f"// This is a placeholder created for {target} when the agent returned an empty response"
                                        )
                                    ]
                                ) for target in targets
                            ]
                        )
                    else:
                        # Create ScriptOutput from the result
                        try:
                            output = ScriptOutput.from_dict(result_data)
                        except Exception as e:
                            logger.error(f"Failed to create ScriptOutput from retry result: {str(e)}")
                            # Create a minimal valid output
                            logger.warning("Creating minimal ScriptOutput due to parse failure")
                            output = ScriptOutput(
                                apiName="API Tests",
                                version="1.0.0",
                                outputs=[
                                    TargetOutput(
                                        name="Default Test Scripts",
                                        type=ScriptType.CUSTOM if "custom" in targets else ScriptType(targets[0]),
                                        content={"info": "Default content created for invalid response"},
                                        files=[
                                            FileContent(
                                                filename="default.txt",
                                                content=f"// This is a placeholder created when the agent returned an invalid response.\n// Targets requested: {', '.join(targets)}"
                                            )
                                        ]
                                    )
                                ]
                            )
                except Exception as e:
                    logger.error(f"Error processing retry result: {str(e)}")
                    raise
        else:
            # Run without streaming
            retry_config = RetryConfig()
            run_config = RunConfig(
                complexity=complexity,
                task="code_generation",
                input_data=input_data
            )
            result, trace_id = await run_agent_with_retry(
                coder_agent,
                message,
                config=retry_config,
                run_config=run_config,
                model_selection=model_strategy
            )
            # Get raw dictionary from result instead of using final_output_as
            try:
                # Extract raw output from the result
                result_data = result.final_output
                logger.info(f"Creating ScriptOutput from result_data type {type(result_data)}")
                
                # Handle empty result data
                if result_data is None or (isinstance(result_data, str) and not result_data.strip()):
                    logger.warning("Received empty result data from agent")
                    # Create a default output for the requested targets
                    output = ScriptOutput(
                        apiName="API Tests",
                        version="1.0.0",
                        outputs=[
                            TargetOutput(
                                name=f"{target.capitalize()} Scripts",
                                type=ScriptType(target),
                                content={"info": f"Default content created for {target}"},
                                files=[
                                    FileContent(
                                        filename=f"default_{target}.txt",
                                        content=f"// This is a placeholder created for {target} when the agent returned an empty response"
                                    )
                                ]
                            ) for target in targets
                        ]
                    )
                else:
                    # Create ScriptOutput from the result
                    try:
                        output = ScriptOutput.from_dict(result_data)
                    except Exception as e:
                        logger.error(f"Failed to create ScriptOutput from retry result: {str(e)}")
                        # Create a minimal valid output
                        logger.warning("Creating minimal ScriptOutput due to parse failure")
                        output = ScriptOutput(
                            apiName="API Tests",
                            version="1.0.0",
                            outputs=[
                                TargetOutput(
                                    name="Default Test Scripts",
                                    type=ScriptType.CUSTOM if "custom" in targets else ScriptType(targets[0]),
                                    content={"info": "Default content created for invalid response"},
                                    files=[
                                        FileContent(
                                            filename="default.txt",
                                            content=f"// This is a placeholder created when the agent returned an invalid response.\n// Targets requested: {', '.join(targets)}"
                                        )
                                    ]
                                )
                            ]
                        )
            except Exception as e:
                logger.error(f"Error processing retry result: {str(e)}")
                raise
        
        # Transform output to expected format
        target_scripts = {}
        
        logger.info(f"Output object: {output}")
        logger.info(f"Number of outputs: {len(output.outputs)}")

        for output_item in output.outputs:
            # Get target type as string
            if hasattr(output_item.type, 'value'):
                # Extract the value from the ScriptType enum
                script_type = output_item.type.value
            else:
                # If already a string or not an enum, use as is
                script_type = str(output_item.type) if not isinstance(output_item.type, str) else output_item.type
            
            target_scripts[script_type] = {}
            
            logger.info(f"Processing output item: type={script_type}, name={output_item.name}")
            
            # Add content as a file if it's a dictionary
            if output_item.content and isinstance(output_item.content, dict):
                main_filename = f"{script_type}_collection.json"
                # Format JSON with proper indentation for readability
                target_scripts[script_type][main_filename] = json.dumps(output_item.content, indent=2)
                logger.info(f"Added main content file: {main_filename}")
            
            # Add all files
            if output_item.files:
                logger.info(f"Number of files in output item: {len(output_item.files)}")
                for file in output_item.files:
                    target_scripts[script_type][file.filename] = file.content
                    logger.info(f"Added file: {file.filename}")
            else:
                logger.warning(f"No files found in output item for {script_type}")

        logger.info(f"Final target_scripts structure: {json.dumps({k: list(v.keys()) for k, v in target_scripts.items()})}")
        
        return target_scripts, trace_id
    except Exception as e:
        logger.error(f"Failed to generate test scripts: {str(e)}")
        raise ScriptGenerationError(f"Failed to generate test scripts: {str(e)}")

def calculate_blueprint_complexity(blueprint: Dict[str, Any]) -> float:
    """
    Calculate the complexity of a blueprint for model selection.
    
    Args:
        blueprint: Blueprint dictionary
        
    Returns:
        Complexity score (0-1) where higher values indicate more complex blueprints
    """
    # Initialize weights for different factors
    weights = {
        "test_count": 0.4,        # Weight for number of tests
        "dependencies": 0.3,       # Weight for number of dependencies
        "business_rules": 0.2,     # Weight for number of business rules
        "setup_teardown": 0.1      # Weight for setup and teardown complexity
    }
    
    # Handle edge cases
    if not blueprint or not isinstance(blueprint, dict):
        logger.warning("Invalid blueprint for complexity calculation")
        return 0.0
    
    # Count the total number of tests from all groups
    test_count = 0
    dependency_count = 0
    business_rule_count = 0
    
    # Check if the blueprint has the new structure with "groups"
    if "groups" in blueprint and isinstance(blueprint.get("groups"), list):
        # New structure - groups of tests
        for group in blueprint.get("groups", []):
            if not isinstance(group, dict):
                continue
                
            # Count tests in this group
            tests = group.get("tests", [])
            if not isinstance(tests, list):
                continue
                
            test_count += len(tests)
            
            # Count dependencies and business rules
            for test in tests:
                if not isinstance(test, dict):
                    continue
                    
                # Count dependencies
                dependencies = test.get("dependencies", [])
                if dependencies and isinstance(dependencies, list):
                    dependency_count += len(dependencies)
                
                # Count business rules
                business_rules = test.get("businessRules", [])
                if business_rules and isinstance(business_rules, list):
                    business_rule_count += len(business_rules)
    else:
        # Legacy structure - check for "suite"
        suite = blueprint.get("suite", {})
        if not isinstance(suite, dict):
            suite = {}
            
        # Count the total number of tests
        tests = suite.get("tests", [])
        if isinstance(tests, list):
            test_count = len(tests)
            
            # Count dependencies and business rules
            for test in tests:
                if not isinstance(test, dict):
                    continue
                    
                # Count dependencies
                dependencies = test.get("dependencies", [])
                if dependencies and isinstance(dependencies, list):
                    dependency_count += len(dependencies)
                
                # Count business rules
                business_rules = test.get("businessRules", [])
                if business_rules and isinstance(business_rules, list):
                    business_rule_count += len(business_rules)
    
    # Set reasonable upper limits
    max_tests = 100
    max_dependencies = 50
    max_business_rules = 50
    max_setup_teardown = 20
    
    # Calculate scores
    test_score = min(1.0, test_count / max_tests)
    dependency_score = min(1.0, dependency_count / max_dependencies)
    business_rules_score = min(1.0, business_rule_count / max_business_rules)
    
    # Setup and teardown is assumed 0 for now (structure isn't consistent)
    setup_teardown_score = 0
    
    # Calculate complexity score
    complexity_score = (
        weights["test_count"] * test_score +
        weights["dependencies"] * dependency_score +
        weights["business_rules"] * business_rules_score +
        weights["setup_teardown"] * setup_teardown_score
    )
    
    # Ensure score is in range 0-1
    complexity_score = min(1.0, max(0.0, complexity_score))
    
    logger.info(f"Calculated blueprint complexity: {complexity_score:.2f} (tests: {test_count}, dependencies: {dependency_count})")
    return complexity_score

async def full_test_generation_pipeline(
    spec_text: str,
    mode: str,
    targets: List[str],
    business_rules: Optional[str] = None,
    test_data: Optional[str] = None,
    test_flow: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
    wait_for_review: bool = True
) -> Dict[str, Any]:
    """
    Run the full test generation pipeline from OpenAPI spec to test scripts.
    
    Args:
        spec_text: Raw OpenAPI spec text
        mode: "basic" or "advanced"
        targets: List of target frameworks (e.g., ["postman", "playwright"])
        business_rules: Optional business rules
        test_data: Optional test data setup
        test_flow: Optional test flow
        progress_callback: Optional callback for progress updates
        wait_for_review: Whether to wait for user review before generating scripts
        
    Returns:
        Dictionary with blueprint and generated scripts
    """
    # Process OpenAPI spec to generate a blueprint
    blueprint, trace_id = await process_openapi_spec(
        spec_text,
        mode,
        business_rules,
        test_data,
        test_flow,
        progress_callback
    )
    
    # If wait_for_review is True, return just the blueprint for user review
    if wait_for_review:
        logger.info("Blueprint generation completed, waiting for user review")
        if progress_callback:
            await progress_callback(
                stage="waiting_for_review",
                progress={"percent": 100, "message": "Blueprint ready for review"},
                agent="system"
            )
        return {
            "blueprint": blueprint,
            "scripts": {},
            "trace_id": trace_id,
            "status": "awaiting_review"
        }
    
    # Otherwise, continue with script generation
    scripts, trace_id = await generate_test_scripts(
        blueprint,
        targets,
        progress_callback
    )
    
    # Return the complete result
    return {
        "blueprint": blueprint,
        "scripts": scripts,
        "trace_id": trace_id,
        "status": "completed"
    }

async def generate_blueprint(
    openapi_spec: str,
    business_rules: Optional[str] = None,
    test_data: Optional[str] = None,
    test_flow: Optional[str] = None,
    mode: str = "basic",
    progress_callback: Optional[Callable] = None
) -> Tuple[Dict[str, Any], str]:
    """
    Generate a test blueprint from an OpenAPI specification.
    
    Args:
        openapi_spec: OpenAPI specification in JSON or YAML format
        business_rules: Business rules for the API
        test_data: Test data considerations
        test_flow: Test flow instructions
        mode: Generation mode (basic or advanced)
        progress_callback: Optional callback for progress updates
        
    Returns:
        Tuple of (blueprint dictionary, trace ID)
    """
    # Process OpenAPI spec to generate a blueprint
    blueprint, trace_id = await process_openapi_spec(
        openapi_spec,
        mode,
        business_rules,
        test_data,
        test_flow,
        progress_callback
    )
    
    return blueprint, trace_id 