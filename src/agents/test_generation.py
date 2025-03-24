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
from ..models.script_output import ScriptOutput

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
                await progress_callback(
                    stage="planning",
                    progress=content,
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
                result, trace_id = await run_agent_with_retry(
                    test_planner,
                    message,
                    config=retry_config,
                    complexity=complexity,
                    task="planning",
                    model_selection=model_strategy
                )
                # Get raw dictionary from result instead of using final_output_as
                blueprint = result.final_output
        else:
            # Run without streaming
            retry_config = RetryConfig()
            result, trace_id = await run_agent_with_retry(
                test_planner,
                message,
                config=retry_config,
                complexity=complexity,
                task="planning",
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
                    raise BlueprintGenerationError("Invalid blueprint format")
            
            blueprint_model = Blueprint(**blueprint)
            blueprint_dict, validation_warnings = await validate_and_clean_blueprint(blueprint_model)
        except Exception as e:
            logger.error(f"Blueprint validation error: {str(e)}")
            error_details = ""
            if isinstance(blueprint, dict):
                error_details = f" Blueprint keys: {', '.join(blueprint.keys())}"
            elif isinstance(blueprint, str) and len(blueprint) < 200:
                error_details = f" Blueprint content: {blueprint}"
            raise BlueprintGenerationError(f"Blueprint validation failed: {str(e)}.{error_details}")
        
        # Log trace ID for debugging
        logger.info(f"Blueprint generation completed with trace_id: {trace_id}")
        if validation_warnings:
            logger.info(f"Blueprint validation produced {len(validation_warnings)} warnings")
        
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
) -> Dict[str, Dict[str, str]]:
    """
    Generate test scripts from a blueprint.
    
    Args:
        blueprint: Blueprint dictionary
        targets: List of target frameworks (e.g., ["postman", "playwright"])
        progress_callback: Optional callback for progress updates
        
    Returns:
        Dictionary of generated scripts by target and filename
    """
    try:
        logger.info(f"Starting script generation for targets: {', '.join(targets)}")
        logger.info(f"Blueprint contains {len(blueprint.get('groups', []))} test groups")
        
        # Calculate complexity based on blueprint contents
        complexity = calculate_blueprint_complexity(blueprint)
        logger.info(f"Blueprint complexity score: {complexity}")
        
        # Set up model selection strategy
        model_strategy = ModelSelectionStrategy()
        
        # Set up coder agent with appropriate model
        selected_model = model_strategy.select_model("coding", complexity)
        logger.info(f"Selected model for coding: {selected_model}")
        
        coder = setup_coder_agent(model=selected_model)
        logger.info("Coder agent initialized successfully")
        
        # Prepare input for the coder agent
        input_data = {
            "blueprint": blueprint,
            "targets": targets
        }
        logger.info("Input data prepared for coder agent")
        
        # Run coder agent with streaming if progress callback is provided
        if progress_callback:
            logger.info("Using streaming mode for progress updates")
            # Progress reporting handler
            async def report_progress(agent_name, item_type, content):
                logger.debug(f"Progress update from {agent_name}: {content}")
                await progress_callback(
                    stage="coding",
                    progress=content,
                    agent=agent_name
                )
            
            try:
                # Run with streaming
                config = RunConfig(complexity=complexity, task="coding")
                logger.info("Starting streaming execution")
                result = await run_agent_with_streaming(
                    coder,
                    input_data,
                    report_progress,
                    config=config,
                    model_selection=model_strategy
                )
                script_output = result
                logger.info("Streaming execution completed successfully")
            except Exception as e:
                logger.error(f"Streaming execution failed: {str(e)}, falling back to non-streaming mode")
                # Fall back to non-streaming mode
                retry_config = RetryConfig()
                logger.info("Starting non-streaming execution with retries")
                result, _ = await run_agent_with_retry(
                    coder,
                    input_data,
                    config=retry_config,
                    complexity=complexity,
                    task="coding",
                    model_selection=model_strategy
                )
                script_output = result.final_output
                logger.info("Non-streaming execution completed successfully")
        else:
            # Run without streaming
            logger.info("Using non-streaming mode")
            retry_config = RetryConfig()
            result, _ = await run_agent_with_retry(
                coder,
                input_data,
                config=retry_config,
                complexity=complexity,
                task="coding",
                model_selection=model_strategy
            )
            script_output = result.final_output
            logger.info("Non-streaming execution completed successfully")
        
        # Log the raw output for debugging
        logger.debug(f"Raw script output: {script_output}")
        
        # Ensure script_output is a dictionary by parsing it if it's a string
        if isinstance(script_output, str):
            logger.info("Parsing string output as JSON")
            try:
                script_output = json.loads(script_output)
                logger.info("Successfully parsed JSON output")
            except json.JSONDecodeError as je:
                logger.error(f"Failed to parse script output as JSON: {str(je)}")
                # Try to extract JSON object from the string
                import re
                json_match = re.search(r'(\{.*\})', script_output, re.DOTALL)
                if json_match:
                    try:
                        script_output = json.loads(json_match.group(1))
                        logger.info("Successfully extracted and parsed JSON from string")
                    except json.JSONDecodeError:
                        logger.error("Failed to extract valid JSON from the script output")
                        # Create a default output structure
                        script_output = {"outputs": []}
                else:
                    # Create a default output structure
                    script_output = {"outputs": []}
        
        # Ensure script_output is a dictionary (not None or other type)
        if not isinstance(script_output, dict):
            logger.error(f"Invalid script output type: {type(script_output)}")
            script_output = {"outputs": []}
        
        # Convert to output format
        output = {}
        logger.info("Converting script output to final format")
        
        # Ensure "outputs" key exists and is a list
        if "outputs" not in script_output or not isinstance(script_output.get("outputs"), list):
            logger.warning("Script output missing 'outputs' list, using empty list")
            script_output["outputs"] = []
        
        for target_output in script_output.get("outputs", []):
            # Skip if target_output is not a dictionary
            if not isinstance(target_output, dict):
                logger.warning(f"Skipping invalid target output: {target_output}")
                continue
                
            target = target_output.get("type", "unknown")
            logger.info(f"Processing output for target: {target}")
            output[target] = {}
            
            # Handle main content if needed
            if "content" in target_output and target_output["content"]:
                logger.info(f"Processing main content for {target}")
                # Ensure content is JSON serializable if it's a dictionary
                if isinstance(target_output["content"], dict):
                    output[target]['collection.json'] = json.dumps(target_output["content"])
                else:
                    # For string content, store as-is
                    output[target]['collection.json'] = target_output["content"]
            
            # Handle individual files
            files = target_output.get("files", [])
            if files and isinstance(files, list):
                logger.info(f"Processing {len(files)} additional files for {target}")
                for file in files:
                    if not isinstance(file, dict):
                        logger.warning(f"Skipping invalid file entry: {file}")
                        continue
                        
                    if "filename" in file and "content" in file:
                        output[target][file["filename"]] = file["content"]
                        logger.debug(f"Added file: {file['filename']}")
        
        logger.info(f"Script generation completed for targets: {', '.join(targets)}")
        logger.info(f"Generated files: {[f for target in output.values() for f in target.keys()]}")
        return output
        
    except Exception as e:
        error_message = f"Script generation error: {str(e)}"
        logger.error(error_message)
        raise ScriptGenerationError(error_message)

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
    scripts = await generate_test_scripts(
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