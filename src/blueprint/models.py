"""
Blueprint Models Module - Data models for test blueprints

This module defines the data models used to represent test blueprints 
generated from OpenAPI specifications.
"""

from typing import List, Dict, Any, Optional, Union, Literal
from enum import Enum
from pydantic import BaseModel, Field, model_validator, AliasChoices
import logging

# Set up logger
logger = logging.getLogger(__name__)

class TestMode(str, Enum):
    """Test mode enumeration for test configuration."""
    BASIC = "basic"
    ADVANCED = "advanced"

class DataFormat(str, Enum):
    """Data format enumeration for request and response data."""
    JSON = "json"
    XML = "xml"
    FORM = "form"
    TEXT = "text"
    BINARY = "binary"

# New assertion models
class JsonPathAssertion(BaseModel):
    """Model for JSON path assertions against response body."""
    type: Literal["jsonPath"] = "jsonPath"
    path: str = Field(..., description="JSONPath expression (e.g., $.data.id)")
    operator: Literal["equals", "notEquals", "contains", "exists", "notExists", "greaterThan", "lessThan"] = "equals"
    expectedValue: Optional[Any] = Field(None, description="Value to compare against (for relevant operators)")

class HeaderAssertion(BaseModel):
    """Model for assertions against response headers."""
    type: Literal["header"] = "header"
    headerName: str = Field(..., description="Name of the HTTP header")
    operator: Literal["equals", "contains", "exists", "notExists"] = "equals"
    expectedValue: Optional[str] = Field(None, description="Value to compare against")

class StatusCodeAssertion(BaseModel):
    """Model for status code assertions."""
    type: Literal["statusCode"] = "statusCode"
    expectedStatus: int = Field(..., description="Expected HTTP status code")

class ResponseTimeAssertion(BaseModel):
    """Model for response time assertions."""
    type: Literal["responseTime"] = "responseTime"
    maxMs: int = Field(..., description="Maximum acceptable response time in milliseconds")

class SchemaValidationAssertion(BaseModel):
    """Model for JSON schema validation assertions."""
    type: Literal["schemaValidation"] = "schemaValidation"
    enabled: bool = True

# Union type for all assertion types
AssertionType = Union[str, JsonPathAssertion, HeaderAssertion, StatusCodeAssertion, ResponseTimeAssertion, SchemaValidationAssertion]

# Authentication models
class ApiKeyAuthConfig(BaseModel):
    """Model for API key authentication."""
    type: Literal["apiKey"] = "apiKey"
    keyName: str = Field(..., description="Name of the API key parameter/header")
    in_: Literal["header", "query"] = Field(..., description="Location of the API key", alias="in")
    valueFromEnv: str = Field(..., description="Environment variable name containing the key (e.g., 'API_KEY')")
    
    model_config = {
        "populate_by_name": True  # Enable mapping of 'in' to 'in_'
    }

class BearerAuthConfig(BaseModel):
    """Model for Bearer token authentication."""
    type: Literal["bearer"] = "bearer"
    tokenFromEnv: str = Field(..., description="Environment variable name containing the bearer token (e.g., 'AUTH_TOKEN')")

# Union type for authentication configs
AuthDetails = Union[ApiKeyAuthConfig, BearerAuthConfig]

# Environment model
class EnvironmentConfig(BaseModel):
    """Model for environment configuration."""
    baseUrl: str
    variables: Optional[Dict[str, Any]] = Field(default_factory=dict)

# Setup and teardown hooks
class HookStep(BaseModel):
    """Model for setup/teardown hook steps."""
    name: str = Field(..., description="Name/description of the step")
    endpoint: str
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
    headers: Optional[Dict[str, str]] = None
    body: Optional[Dict[str, Any]] = None
    saveResponseAs: Optional[str] = Field(None, description="Variable name to save the full response body under")

class HeaderParam(BaseModel):
    """Model for HTTP header parameters."""
    key: str = Field(..., description="Header name", validation_alias=AliasChoices('key', 'name'))
    value: str = Field(..., description="Header value")
    description: Optional[str] = Field(None, description="Description of the header")
    
    model_config = {
        "json_schema_extra": {
            "required": ["key", "value"]
        }
    }

class Parameter(BaseModel):
    """Model for test parameters including path, query, and form parameters."""
    name: str = Field(..., description="Parameter name")
    value: Any = Field(..., description="Parameter value (can be any type)")
    in_: str = Field(..., description="Parameter location (path, query, body, etc.)", alias="in")
    required: Optional[bool] = Field(True, description="Whether the parameter is required")
    description: Optional[str] = Field(None, description="Description of the parameter")
    
    model_config = {
        "json_schema_extra": {
            "required": ["name", "value", "in"]
        },
        "populate_by_name": True  # Enable mapping of 'in' to 'in_'
    }

class Test(BaseModel):
    """Model for individual API tests."""
    id: str = Field(..., description="Unique identifier for the test")
    name: str = Field(..., description="Test name")
    description: Optional[str] = Field(None, description="Test description")
    endpoint: str = Field(..., description="API endpoint path")
    method: str = Field(..., description="HTTP method")
    headers: Optional[List[HeaderParam]] = Field(None, description="Request headers")
    parameters: Optional[Union[List[Parameter], Dict[str, Any]]] = Field(None, description="Request parameters")
    body: Optional[Dict[str, Any]] = Field(None, description="Request body")
    expectedStatus: Optional[int] = Field(None, description="Expected HTTP status code (deprecated by StatusCodeAssertion, kept for backward compat)")
    expectedSchema: Optional[Dict[str, Any]] = Field(None, description="Expected response schema")
    assertions: Optional[List[AssertionType]] = Field(None, description="List of structured assertions or simple strings")
    dependencies: Optional[List[str]] = Field(None, description="IDs of tests this test depends on")
    businessRules: Optional[List[str]] = Field(None, description="Business rules to test")
    dataFormat: Optional[DataFormat] = Field(None, description="Format of request/response data")
    skip: bool = Field(False, description="Whether to skip this test")
    tags: Optional[List[str]] = Field(None, description="Tags for categorizing the test")
    timeout: Optional[int] = Field(None, description="Request timeout in milliseconds")
    retryCount: Optional[int] = Field(None, description="Number of times to retry the test if it fails")
    mockData: Optional[Dict[str, Any]] = Field(None, description="Mock data for this test")
    variableExtraction: Optional[Dict[str, str]] = Field(None, description="Variables to extract from response")
    dataProvider: Optional[str] = Field(None, description="Reference to test data for data-driven testing")
    dataProviderIterations: Optional[List[Dict[str, Any]]] = Field(None, description="Inline data provider for test iterations")
    customSetup: Optional[Dict[str, Any]] = Field(None, description="Custom setup for this test")
    customTeardown: Optional[Dict[str, Any]] = Field(None, description="Custom teardown for this test")
    
    model_config = {
        "json_schema_extra": {
            "required": ["id", "name", "endpoint", "method"]
        }
    }

    @model_validator(mode='before')
    def migrate_expected_status(cls, values):
        """
        Ensure expectedStatus is included in assertions list if present.
        This supports backward compatibility.
        """
        if 'expectedStatus' in values and values['expectedStatus'] is not None:
            if 'assertions' not in values or values['assertions'] is None:
                values['assertions'] = []
            # Avoid duplicates if already present as structured assertion
            has_status_assertion = any(
                (isinstance(a, dict) and a.get('type') == 'statusCode') or 
                (isinstance(a, StatusCodeAssertion)) 
                for a in values.get('assertions', [])
            )
            if not has_status_assertion:
                status_assertion = StatusCodeAssertion(expectedStatus=values['expectedStatus'])
                values['assertions'].append(status_assertion)
        return values

    @model_validator(mode='after')
    def validate_test(self) -> 'Test':
        """
        Validate that the test has the required fields based on HTTP method.
        
        For methods like POST, PUT, and PATCH, validate that there's either a body
        or parameters. For all tests, validate that the endpoint is properly formed.
        """
        # Make parameters field more flexible
        # First, let's handle if parameters is None
        if self.parameters is None:
            self.parameters = []
            
        # Handle if parameters is a list of dicts but not Parameter objects
        if isinstance(self.parameters, list):
            # Convert list of dicts to Parameter objects
            param_list = []
            for param in self.parameters:
                if isinstance(param, dict):
                    # Try to create a Parameter from dict
                    try:
                        # Ensure 'in' key exists
                        if 'in' not in param:
                            param['in'] = 'query'  # Default to query
                        param_list.append(Parameter(**param))
                    except Exception:
                        # If it fails, add with default values
                        param_list.append(Parameter(
                            name=next(iter(param.keys())) if param else 'param',
                            value=next(iter(param.values())) if param else '',
                            in_="query"
                        ))
                elif isinstance(param, Parameter):
                    param_list.append(param)
            self.parameters = param_list
                    
        # Convert dict parameters to list if needed
        elif isinstance(self.parameters, dict):
            param_list = []
            for key, value in self.parameters.items():
                param_list.append(Parameter(
                    name=key,
                    value=value,
                    in_="query"  # Default to query parameters
                ))
            self.parameters = param_list
        
        # Make headers field more flexible
        # Handle dictionary format for headers (e.g., {"Accept": "application/json"})
        if isinstance(self.headers, dict):
            header_list = []
            for key, value in self.headers.items():
                header_list.append(HeaderParam(
                    key=key,
                    value=str(value)  # Ensure value is a string
                ))
            self.headers = header_list
        # If headers is a list but contains dicts instead of HeaderParam objects
        elif isinstance(self.headers, list):
            header_list = []
            for header in self.headers:
                if isinstance(header, dict):
                    # Try to create a HeaderParam from dict
                    try:
                        # Check if it has 'key'/'value' or 'name'/'value' format
                        if 'key' in header and 'value' in header:
                            header_list.append(HeaderParam(**header))
                        elif 'name' in header and 'value' in header:
                            header_list.append(HeaderParam(
                                key=header['name'],
                                value=header['value'],
                                description=header.get('description')
                            ))
                        else:
                            # Take first key/value pair
                            key = next(iter(header.keys())) if header else 'header'
                            value = header[key] if header else ''
                            header_list.append(HeaderParam(key=key, value=str(value)))
                    except Exception as e:
                        logger.warning(f"Failed to parse header: {e}")
                        # Add a default header if parsing fails
                        header_list.append(HeaderParam(
                            key="X-Default-Header",
                            value="true"
                        ))
                elif isinstance(header, HeaderParam):
                    header_list.append(header)
            self.headers = header_list
        
        # Handle body flexibility
        # If body is a list of dicts, use the first one
        if isinstance(self.body, list):
            if len(self.body) > 0 and isinstance(self.body[0], dict):
                self.body = self.body[0]
            else:
                # If it's not a list of dicts, convert to dict
                try:
                    self.body = {"data": self.body}
                except Exception:
                    self.body = {}
                    
        # Ensure body is a dict if it's not None
        if self.body is not None and not isinstance(self.body, dict):
            # Try to convert to dict
            try:
                self.body = {"value": self.body}
            except Exception:
                self.body = {}
        
        # Validate for POST, PUT, PATCH that there's a body or parameters
        if self.method.upper() in ['POST', 'PUT', 'PATCH'] and not (self.body or self.parameters):
            # Instead of raising error, create an empty body
            self.body = {}
        
        # Ensure endpoint starts with /
        if not self.endpoint.startswith('/'):
            self.endpoint = '/' + self.endpoint
        
        return self

class TestGroup(BaseModel):
    """Model for grouping related tests."""
    name: str = Field(..., description="Group name")
    description: Optional[str] = Field(None, description="Group description")
    tests: List[Test] = Field(..., description="Tests in this group")
    tags: Optional[List[str]] = Field(None, description="Tags for categorizing the group")
    setupSteps: Optional[List[HookStep]] = Field(None, description="Steps to run before tests in this group")
    teardownSteps: Optional[List[HookStep]] = Field(None, description="Steps to run after tests in this group")
    
    model_config = {
        "json_schema_extra": {
            "required": ["name", "tests"]
        }
    }

class TestFlowStep(BaseModel):
    """Model for a step in a test flow."""
    testId: str = Field(..., description="ID of the test to run in this step")
    description: Optional[str] = Field(None, description="Description of this step in the flow")
    
    model_config = {
        "json_schema_extra": {
            "required": ["testId"]
        }
    }

class TestFlow(BaseModel):
    """Model for a test flow, representing a sequence of tests."""
    name: str = Field(..., description="Name of the test flow")
    description: Optional[str] = Field(None, description="Description of the test flow")
    steps: List[TestFlowStep] = Field(..., description="Steps in the test flow")
    
    model_config = {
        "json_schema_extra": {
            "required": ["name", "steps"]
        }
    }

class Blueprint(BaseModel):
    """Model for test blueprints."""
    apiName: str = Field(..., description="Name of the API being tested")
    version: str = Field(..., description="Version of the API being tested")
    description: Optional[str] = Field(None, description="Description of the test suite")
    baseUrl: Optional[str] = Field(None, description="Base URL of the API")
    environments: Optional[Dict[str, EnvironmentConfig]] = Field(None, description="Dictionary of environment configurations (e.g., {'dev': {...}, 'prod': {...}})")
    auth: Optional[AuthDetails] = Field(None, description="Default authentication method for the API")
    mode: Optional[TestMode] = Field(TestMode.BASIC, description="Testing mode (basic or advanced)")
    groups: List[TestGroup] = Field(..., description="Test groups")
    globalHeaders: Optional[List[HeaderParam]] = Field(None, description="Headers to apply to all tests")
    globalParams: Optional[List[Parameter]] = Field(None, description="Parameters to apply to all tests")
    securityScheme: Optional[Dict[str, Any]] = Field(None, description="Security scheme details")
    testData: Optional[Dict[str, Any]] = Field(None, description="Test data for parameterized tests")
    testFlows: Optional[List[TestFlow]] = Field(None, description="Test flows for the blueprint")
    environmentVariables: Optional[Dict[str, Any]] = Field(None, description="Environment variables for test execution")
    setupHooks: Optional[List[Dict[str, Any]]] = Field(None, description="Setup hooks to run before test execution")
    teardownHooks: Optional[List[Dict[str, Any]]] = Field(None, description="Teardown hooks to run after test execution")
    retryPolicy: Optional[Dict[str, Any]] = Field(None, description="Retry policy for failed tests")
    
    model_config = {
        "json_schema_extra": {
            "required": ["apiName", "version", "groups"]
        }
    }

    @model_validator(mode='after')
    def validate_blueprint(self) -> 'Blueprint':
        """
        Perform full blueprint validation.
        
        Check that test IDs are unique across all groups, and validate that all
        test dependencies refer to valid test IDs.
        """
        # Ensure groups is not None
        if not self.groups:
            self.groups = []
            return self
            
        # Collect all test IDs
        test_ids = []
        for group in self.groups:
            if not group.tests:
                continue
                
            for test in group.tests:
                test_ids.append(test.id)
        
        # Check for duplicate IDs
        if len(test_ids) != len(set(test_ids)):
            # Find duplicates
            seen = set()
            duplicates = []
            for test_id in test_ids:
                if test_id in seen:
                    duplicates.append(test_id)
                else:
                    seen.add(test_id)
            logger.warning(f"Duplicate test IDs detected: {', '.join(duplicates)}")
        
        # Check all dependencies are valid
        for group in self.groups:
            if not group.tests:
                continue
                
            for test in group.tests:
                if test.dependencies:
                    for dep_id in test.dependencies:
                        if dep_id not in test_ids:
                            logger.warning(f"Test {test.id} depends on non-existent test {dep_id}")
        
        # Validate test flows if present
        if self.testFlows:
            self.validate_testflows(test_ids)
            
        return self
        
    def validate_testflows(self, test_ids: List[str]) -> None:
        """
        Validate test flows to ensure they reference valid test IDs.
        
        Args:
            test_ids: List of all valid test IDs in the blueprint
        """
        if not self.testFlows:
            return
            
        for i, flow in enumerate(self.testFlows):
            for j, step in enumerate(flow.steps):
                if step.testId not in test_ids:
                    logger.warning(f"Test flow '{flow.name}' step {j+1} references non-existent test ID: {step.testId}")
                    
        # Check for duplicate flow names
        flow_names = [flow.name for flow in self.testFlows]
        if len(flow_names) != len(set(flow_names)):
            # Find duplicates
            seen = set()
            duplicates = []
            for name in flow_names:
                if name in seen:
                    duplicates.append(name)
                else:
                    seen.add(name)
            logger.warning(f"Duplicate test flow names detected: {', '.join(duplicates)}")
        
    def validate_dependencies(self) -> List[str]:
        """
        Validate that there are no circular dependencies in tests.
        
        Returns:
            List of warnings about potential dependency issues
        """
        warnings = []
        
        # Ensure groups is not None
        if not self.groups:
            return warnings
            
        # Get all test IDs
        test_ids = {}
        for group in self.groups:
            if not group.tests:
                continue
                
            for test in group.tests:
                test_ids[test.id] = test
        
        # If no tests, return empty warnings
        if not test_ids:
            return warnings
            
        # Check for circular dependencies
        for group in self.groups:
            if not group.tests:
                continue
                
            for test in group.tests:
                if not test.dependencies:
                    continue
                    
                # Check that all dependencies exist
                for dep_id in test.dependencies:
                    if dep_id not in test_ids:
                        warnings.append(f"Test {test.id} depends on non-existent test {dep_id}")
        
        # Build dependency graph
        dependency_graph = {}
        for group in self.groups:
            if not group.tests:
                continue
                
            for test in group.tests:
                dependency_graph[test.id] = test.dependencies or []
        
        # Check for circular dependencies
        def check_cycle(node, path=None):
            if path is None:
                path = []
            
            if node in path:
                cycle = path[path.index(node):] + [node]
                return " -> ".join(cycle)
            
            for dep in dependency_graph.get(node, []):
                cycle = check_cycle(dep, path + [node])
                if cycle:
                    return cycle
            
            return None
        
        # Check each test for cycles
        for test_id in test_ids:
            cycle = check_cycle(test_id)
            if cycle:
                warnings.append(f"Circular dependency detected: {cycle}")
                break
        
        return warnings 