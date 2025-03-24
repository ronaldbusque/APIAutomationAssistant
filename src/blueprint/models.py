"""
Blueprint Models Module - Data models for test blueprints

This module defines the data models used to represent test blueprints 
generated from OpenAPI specifications.
"""

from typing import List, Dict, Any, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, model_validator

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

class HeaderParam(BaseModel):
    """Model for HTTP header parameters."""
    key: str = Field(..., description="Header name")
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
    value: str = Field(..., description="Parameter value")
    in_: str = Field(..., description="Parameter location (path, query, body, etc.)", alias="in")
    required: Optional[bool] = Field(True, description="Whether the parameter is required")
    description: Optional[str] = Field(None, description="Description of the parameter")
    
    model_config = {
        "json_schema_extra": {
            "required": ["name", "value", "in"]
        }
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
    expectedStatus: int = Field(..., description="Expected HTTP status code")
    expectedSchema: Optional[Dict[str, Any]] = Field(None, description="Expected response schema")
    assertions: Optional[List[str]] = Field(None, description="Additional assertions to make")
    dependencies: Optional[List[str]] = Field(None, description="IDs of tests this test depends on")
    businessRules: Optional[List[str]] = Field(None, description="Business rules to test")
    dataFormat: Optional[DataFormat] = Field(None, description="Format of request/response data")
    skip: bool = Field(False, description="Whether to skip this test")
    tags: Optional[List[str]] = Field(None, description="Tags for categorizing the test")
    
    model_config = {
        "json_schema_extra": {
            "required": ["id", "name", "endpoint", "method", "expectedStatus"]
        }
    }

    @model_validator(mode='after')
    def validate_test(self) -> 'Test':
        """
        Validate that the test has the required fields based on HTTP method.
        
        For methods like POST, PUT, and PATCH, validate that there's either a body
        or parameters. For all tests, validate that the endpoint is properly formed.
        """
        # Convert dict parameters to list if needed
        if isinstance(self.parameters, dict):
            param_list = []
            for key, value in self.parameters.items():
                param_list.append(Parameter(
                    name=key,
                    value=str(value),
                    in_="query"  # Default to query parameters
                ))
            self.parameters = param_list
        
        # Validate for POST, PUT, PATCH that there's a body or parameters
        if self.method.upper() in ['POST', 'PUT', 'PATCH'] and not (self.body or self.parameters):
            raise ValueError(f"Test {self.id}: {self.method} request should have either body or parameters")
        
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
    
    model_config = {
        "json_schema_extra": {
            "required": ["name", "tests"]
        }
    }

class Blueprint(BaseModel):
    """Model for test blueprints."""
    apiName: str = Field(..., description="Name of the API being tested")
    version: str = Field(..., description="Version of the API being tested")
    description: Optional[str] = Field(None, description="Description of the test suite")
    baseUrl: Optional[str] = Field(None, description="Base URL of the API")
    mode: Optional[TestMode] = Field(TestMode.BASIC, description="Testing mode (basic or advanced)")
    groups: List[TestGroup] = Field(..., description="Test groups")
    globalHeaders: Optional[List[HeaderParam]] = Field(None, description="Headers to apply to all tests")
    globalParams: Optional[List[Parameter]] = Field(None, description="Parameters to apply to all tests")
    securityScheme: Optional[Dict[str, Any]] = Field(None, description="Security scheme details")
    testData: Optional[Dict[str, Any]] = Field(None, description="Test data for parameterized tests")
    
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
            raise ValueError(f"Duplicate test IDs detected: {', '.join(duplicates)}")
        
        # Check all dependencies are valid
        for group in self.groups:
            if not group.tests:
                continue
                
            for test in group.tests:
                if test.dependencies:
                    for dep_id in test.dependencies:
                        if dep_id not in test_ids:
                            raise ValueError(f"Test {test.id} depends on non-existent test {dep_id}")
        
        return self
        
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