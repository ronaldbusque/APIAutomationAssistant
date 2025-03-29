"""
Test Module for Blueprint Models

This module contains tests for the blueprint models to verify they work as expected.
"""

import pytest
import json
from ..blueprint.models import (
    Blueprint, TestGroup, Test, JsonPathAssertion, HeaderAssertion, 
    StatusCodeAssertion, ResponseTimeAssertion, SchemaValidationAssertion,
    ApiKeyAuthConfig, BearerAuthConfig, EnvironmentConfig, HookStep
)

def test_json_path_assertion():
    """Test JsonPathAssertion model."""
    assertion = JsonPathAssertion(path="$.data.id", operator="equals", expectedValue=123)
    assert assertion.type == "jsonPath"
    assert assertion.path == "$.data.id"
    assert assertion.operator == "equals"
    assert assertion.expectedValue == 123

def test_header_assertion():
    """Test HeaderAssertion model."""
    assertion = HeaderAssertion(headerName="Content-Type", operator="contains", expectedValue="application/json")
    assert assertion.type == "header"
    assert assertion.headerName == "Content-Type"
    assert assertion.operator == "contains"
    assert assertion.expectedValue == "application/json"

def test_status_code_assertion():
    """Test StatusCodeAssertion model."""
    assertion = StatusCodeAssertion(expectedStatus=200)
    assert assertion.type == "statusCode"
    assert assertion.expectedStatus == 200

def test_response_time_assertion():
    """Test ResponseTimeAssertion model."""
    assertion = ResponseTimeAssertion(maxMs=5000)
    assert assertion.type == "responseTime"
    assert assertion.maxMs == 5000

def test_schema_validation_assertion():
    """Test SchemaValidationAssertion model."""
    assertion = SchemaValidationAssertion(enabled=True)
    assert assertion.type == "schemaValidation"
    assert assertion.enabled == True

def test_api_key_auth_config():
    """Test ApiKeyAuthConfig model."""
    auth = ApiKeyAuthConfig(keyName="X-API-Key", in_="header", valueFromEnv="API_KEY")
    assert auth.type == "apiKey"
    assert auth.keyName == "X-API-Key"
    assert auth.in_ == "header"
    assert auth.valueFromEnv == "API_KEY"

def test_bearer_auth_config():
    """Test BearerAuthConfig model."""
    auth = BearerAuthConfig(tokenFromEnv="AUTH_TOKEN")
    assert auth.type == "bearer"
    assert auth.tokenFromEnv == "AUTH_TOKEN"

def test_environment_config():
    """Test EnvironmentConfig model."""
    env = EnvironmentConfig(
        baseUrl="https://api.example.com/v1",
        variables={"apiKey": "{{API_KEY}}", "userId": "123"}
    )
    assert env.baseUrl == "https://api.example.com/v1"
    assert env.variables["apiKey"] == "{{API_KEY}}"
    assert env.variables["userId"] == "123"

def test_hook_step():
    """Test HookStep model."""
    step = HookStep(
        name="Create test user",
        endpoint="/users",
        method="POST",
        body={"name": "Test User", "email": "test@example.com"},
        saveResponseAs="testUser"
    )
    assert step.name == "Create test user"
    assert step.endpoint == "/users"
    assert step.method == "POST"
    assert step.body["name"] == "Test User"
    assert step.saveResponseAs == "testUser"

def test_test_with_assertions():
    """Test the Test model with structured assertions."""
    test = Test(
        id="test-1",
        name="Test with assertions",
        endpoint="/users",
        method="GET",
        assertions=[
            StatusCodeAssertion(expectedStatus=200),
            JsonPathAssertion(path="$.data", operator="exists"),
            HeaderAssertion(headerName="Content-Type", operator="equals", expectedValue="application/json"),
            ResponseTimeAssertion(maxMs=5000)
        ]
    )
    assert test.id == "test-1"
    assert test.endpoint == "/users"
    assert test.method == "GET"
    assert len(test.assertions) == 4
    assert isinstance(test.assertions[0], StatusCodeAssertion)
    assert isinstance(test.assertions[1], JsonPathAssertion)
    assert isinstance(test.assertions[2], HeaderAssertion)
    assert isinstance(test.assertions[3], ResponseTimeAssertion)

def test_expected_status_migration():
    """Test that expectedStatus is migrated to a StatusCodeAssertion."""
    test = Test(
        id="test-1",
        name="Test with expectedStatus",
        endpoint="/users",
        method="GET",
        expectedStatus=200
    )
    assert test.expectedStatus == 200
    assert len(test.assertions) == 1
    assert isinstance(test.assertions[0], StatusCodeAssertion)
    assert test.assertions[0].expectedStatus == 200

def test_test_group_with_hooks():
    """Test TestGroup model with setup and teardown hooks."""
    group = TestGroup(
        name="User Tests",
        tests=[
            Test(id="test-1", name="Get User", endpoint="/users/{id}", method="GET")
        ],
        setupSteps=[
            HookStep(
                name="Create test user",
                endpoint="/users",
                method="POST",
                body={"name": "Test User"},
                saveResponseAs="testUser"
            )
        ],
        teardownSteps=[
            HookStep(
                name="Delete test user",
                endpoint="/users/{id}",
                method="DELETE"
            )
        ]
    )
    assert group.name == "User Tests"
    assert len(group.tests) == 1
    assert len(group.setupSteps) == 1
    assert len(group.teardownSteps) == 1
    assert group.setupSteps[0].name == "Create test user"
    assert group.teardownSteps[0].name == "Delete test user"

def test_blueprint_with_environments_and_auth():
    """Test Blueprint model with environments and auth configuration."""
    blueprint = Blueprint(
        apiName="Test API",
        version="1.0.0",
        environments={
            "production": EnvironmentConfig(
                baseUrl="https://api.example.com/v1",
                variables={"apiKey": "{{PROD_API_KEY}}"}
            ),
            "development": EnvironmentConfig(
                baseUrl="https://dev-api.example.com/v1",
                variables={"apiKey": "{{DEV_API_KEY}}"}
            )
        },
        auth=ApiKeyAuthConfig(keyName="X-API-Key", in_="header", valueFromEnv="API_KEY"),
        groups=[
            TestGroup(
                name="User Tests",
                tests=[
                    Test(id="test-1", name="Get User", endpoint="/users/{id}", method="GET")
                ]
            )
        ]
    )
    assert blueprint.apiName == "Test API"
    assert blueprint.version == "1.0.0"
    assert "production" in blueprint.environments
    assert "development" in blueprint.environments
    assert blueprint.environments["production"].baseUrl == "https://api.example.com/v1"
    assert blueprint.environments["development"].baseUrl == "https://dev-api.example.com/v1"
    assert isinstance(blueprint.auth, ApiKeyAuthConfig)
    assert blueprint.auth.keyName == "X-API-Key"
    assert len(blueprint.groups) == 1
    assert blueprint.groups[0].name == "User Tests"

def test_complete_blueprint_serialization():
    """Test that a complete blueprint with all new features can be serialized to JSON."""
    blueprint = Blueprint(
        apiName="Complete Test API",
        version="1.0.0",
        baseUrl="https://api.example.com/v1",
        environments={
            "production": EnvironmentConfig(
                baseUrl="https://api.example.com/v1",
                variables={"apiKey": "{{PROD_API_KEY}}"}
            ),
            "development": EnvironmentConfig(
                baseUrl="https://dev-api.example.com/v1",
                variables={"apiKey": "{{DEV_API_KEY}}"}
            )
        },
        auth=ApiKeyAuthConfig(keyName="X-API-Key", in_="header", valueFromEnv="API_KEY"),
        groups=[
            TestGroup(
                name="User Tests",
                setupSteps=[
                    HookStep(
                        name="Create test user",
                        endpoint="/users",
                        method="POST",
                        body={"name": "Test User", "email": "{{$randomEmail}}"},
                        saveResponseAs="testUser"
                    )
                ],
                tests=[
                    Test(
                        id="test-get-user",
                        name="Get User",
                        endpoint="/users/{id}",
                        method="GET",
                        parameters=[
                            {"name": "id", "value": "{{testUser.id}}", "in_": "path"}
                        ],
                        assertions=[
                            StatusCodeAssertion(expectedStatus=200),
                            JsonPathAssertion(path="$.name", operator="equals", expectedValue="Test User"),
                            HeaderAssertion(headerName="Content-Type", operator="equals", expectedValue="application/json"),
                            ResponseTimeAssertion(maxMs=5000)
                        ]
                    ),
                    Test(
                        id="test-create-user-missing-required",
                        name="Create User - Missing Required Field",
                        endpoint="/users",
                        method="POST",
                        body={"email": "test@example.com"},  # Missing 'name' field
                        assertions=[
                            StatusCodeAssertion(expectedStatus=400),
                            JsonPathAssertion(path="$.error", operator="contains", expectedValue="required")
                        ]
                    )
                ],
                teardownSteps=[
                    HookStep(
                        name="Delete test user",
                        endpoint="/users/{{testUser.id}}",
                        method="DELETE"
                    )
                ]
            )
        ]
    )
    
    # Test that the blueprint can be serialized to JSON without errors
    json_str = blueprint.model_dump_json()
    assert json_str
    
    # Test that it can be deserialized back into a Blueprint object
    json_dict = json.loads(json_str)
    new_blueprint = Blueprint.model_validate(json_dict)
    assert new_blueprint.apiName == "Complete Test API"
    assert new_blueprint.environments["production"].baseUrl == "https://api.example.com/v1"
    assert new_blueprint.groups[0].tests[0].assertions[0].expectedStatus == 200
    assert new_blueprint.groups[0].setupSteps[0].saveResponseAs == "testUser" 