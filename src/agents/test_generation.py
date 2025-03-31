"""
Test Generation Module - Core logic for generating tests from OpenAPI specs

This module provides utility functions for the test generation process.
"""

import json
import logging
from typing import Dict, Any, Optional, List

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

def calculate_blueprint_complexity(blueprint: Dict[str, Any]) -> float:
    """
    Calculate the complexity of a test blueprint for model selection.
    
    Args:
        blueprint: Test blueprint dictionary
        
    Returns:
        Complexity score (0-1) where higher values indicate more complex blueprints
    """
    # Initialize weights for different factors
    weights = {
        "size": 0.3,          # Weight for overall blueprint size
        "tests": 0.4,         # Weight for number of tests
        "features": 0.3       # Weight for advanced features
    }
    
    # Calculate size score (based on JSON serialized length)
    blueprint_size = len(json.dumps(blueprint))
    max_size = 500_000  # 500KB max size
    size_score = min(1.0, blueprint_size / max_size)
    
    # Calculate test count score
    test_count = 0
    for group in blueprint.get("groups", []):
        test_count += len(group.get("tests", []))
    
    # More tests = more complex
    max_tests = 200  # reasonable upper limit
    test_score = min(1.0, test_count / max_tests)
    
    # Calculate feature complexity score based on presence of advanced features
    feature_score = 0.0
    
    # Check for environments
    if "environments" in blueprint and blueprint["environments"]:
        feature_score += 0.1
    
    # Check for authentication
    if "auth" in blueprint and blueprint["auth"]:
        feature_score += 0.1
    
    # Check for test flows
    if "testFlows" in blueprint and blueprint["testFlows"]:
        feature_score += 0.2
    
    # Check for variable extraction
    var_extraction_count = 0
    for group in blueprint.get("groups", []):
        for test in group.get("tests", []):
            if "variableExtraction" in test and test["variableExtraction"]:
                var_extraction_count += 1
    
    # More variable extractions = more complex
    if var_extraction_count > 0:
        feature_score += min(0.2, var_extraction_count / 20)
    
    # Check for setup/teardown steps
    setup_teardown_count = 0
    for group in blueprint.get("groups", []):
        setup_teardown_count += len(group.get("setupSteps", []))
        setup_teardown_count += len(group.get("teardownSteps", []))
    
    # More setup/teardown steps = more complex
    if setup_teardown_count > 0:
        feature_score += min(0.2, setup_teardown_count / 15)
    
    # Check for advanced assertions (beyond simple status code checks)
    advanced_assertion_count = 0
    for group in blueprint.get("groups", []):
        for test in group.get("tests", []):
            assertions = test.get("assertions", [])
            if not assertions and "expectedStatus" in test:
                # Convert legacy expectedStatus to a StatusCodeAssertion
                assertions = [{"type": "statusCode", "expectedStatus": test["expectedStatus"]}]
            
            # Count assertions that aren't just status code checks
            for assertion in assertions:
                if assertion.get("type") != "statusCode":
                    advanced_assertion_count += 1
    
    # More advanced assertions = more complex
    if advanced_assertion_count > 0:
        feature_score += min(0.2, advanced_assertion_count / 30)
    
    # Ensure feature score is in range 0-1
    feature_score = min(1.0, feature_score)
    
    # Calculate overall complexity score
    complexity_score = (
        weights["size"] * size_score +
        weights["tests"] * test_score +
        weights["features"] * feature_score
    )
    
    # Ensure score is in range 0-1
    complexity_score = min(1.0, max(0.0, complexity_score))
    
    logger.info(f"Calculated blueprint complexity score: {complexity_score:.2f} (size: {blueprint_size}, tests: {test_count}, features: {feature_score:.2f})")
    return complexity_score 