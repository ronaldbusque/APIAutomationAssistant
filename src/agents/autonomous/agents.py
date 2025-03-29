"""
Autonomous Agents - Author and Reviewer agent setup

This module provides setup functions for the autonomous agents
used in the blueprint and script generation pipeline.
"""

import logging
from agents import Agent
from src.config.settings import settings
from src.utils.model_selection import ModelSelectionStrategy

logger = logging.getLogger(__name__)
model_strategy = ModelSelectionStrategy()

def setup_blueprint_author_agent() -> Agent:
    """
    Set up the Blueprint Author Agent that creates the initial test blueprint.
    
    Returns:
        Configured Agent instance
    """
    model_name = model_strategy.select_model("blueprint_authoring", complexity=0.7)
    logger.info(f"Setting up Blueprint Author Agent with model: {model_name}")
    
    return Agent(
        name="BlueprintAuthorAgent",
        model=model_name,
        instructions="""You are an expert API testing specialist who creates detailed, structured test blueprints from API specifications.

**Input Parameters (Provided in the prompt):**
1.  **Spec Analysis Summary:** Key details extracted from the OpenAPI spec.
2.  **Reviewer Feedback:** Instructions from the previous review cycle (or "No feedback yet..." for the first run).
3.  **Previous Blueprint JSON (Optional):** The JSON blueprint from the previous iteration, if this is a revision.

**Your Task:**
- **If generating initial blueprint:** Create a comprehensive JSON blueprint based *only* on the **Spec Analysis Summary**.
- **If revising:** Carefully modify the 'Previous Blueprint JSON' according to *all* points in the 'Reviewer Feedback'.
- **Test Scope:** Cover all endpoints, methods, parameters, response codes, and key scenarios.
- **Blueprint Structure:** Output must be a valid JSON object adhering to this structure:

```json
{
  "apiName": "Name from the spec",
  "version": "Version from spec",
  "baseUrl": "Base URL from the spec",
  "environments": {
    "production": {
      "baseUrl": "https://api.example.com/v1",
      "variables": {
        "apiKey": "{{PROD_API_KEY}}"
      }
    },
    "development": {
      "baseUrl": "https://dev-api.example.com/v1",
      "variables": {
        "apiKey": "{{DEV_API_KEY}}"
      }
    }
  },
  "auth": {
    "type": "apiKey",
    "keyName": "X-API-Key",
    "in": "header",
    "valueFromEnv": "API_KEY"
  },
  "groups": [
    {
      "name": "Logical Grouping Name (e.g., Users, Orders)",
      "setupSteps": [
        {
          "name": "Create test user",
          "endpoint": "/users",
          "method": "POST",
          "body": {"name": "Test User", "email": "{{$randomEmail}}"},
          "saveResponseAs": "testUser"
        }
      ],
      "tests": [
        {
          "id": "unique-test-id",
          "name": "Test Name",
          "endpoint": "/path/{with}/placeholders",
          "method": "HTTP_METHOD",
          "description": "What the test verifies",
          "headers": {"Content-Type": "application/json"},
          "parameters": [
            {
              "name": "param1",
              "value": "value1",
              "in": "path"
            },
            {
              "name": "param2",
              "value": "value2",
              "in": "query"
            }
          ],
          "body": {"key": "exampleValue"},
          "assertions": [
            {
              "type": "statusCode",
              "expectedStatus": 200
            },
            {
              "type": "jsonPath",
              "path": "$.id",
              "operator": "exists"
            },
            {
              "type": "header",
              "headerName": "Content-Type",
              "operator": "equals",
              "expectedValue": "application/json"
            },
            {
              "type": "responseTime",
              "maxMs": 5000
            },
            {
              "type": "schemaValidation",
              "enabled": true
            }
          ],
          "variableExtraction": {
            "userId": "$.id"
          },
          "dependencies": ["id-of-prerequisite-test"]
        },
        {
          "id": "negative-test-id",
          "name": "Negative Test Name - Required Field Missing",
          "endpoint": "/path",
          "method": "POST",
          "description": "Verifies API rejects requests missing required fields",
          "body": {"incomplete": "data"},
          "assertions": [
            {
              "type": "statusCode",
              "expectedStatus": 400
            },
            {
              "type": "jsonPath",
              "path": "$.error",
              "operator": "contains",
              "expectedValue": "required field"
            }
          ]
        }
      ],
      "teardownSteps": [
        {
          "name": "Delete test user",
          "endpoint": "/users/{{testUser.id}}",
          "method": "DELETE"
        }
      ]
    }
  ]
}
```

**Testing Guidelines:**

1. **Structured Assertions:** Generate detailed structured assertions based on response definitions:
   - Use `StatusCodeAssertion` for expected HTTP status codes
   - Use `JsonPathAssertion` to validate specific response fields
   - Use `HeaderAssertion` to verify response headers
   - Use `ResponseTimeAssertion` for performance checks
   - Use `SchemaValidationAssertion` when response schemas are defined

2. **Environments:** Extract server URLs from the spec's servers section:
   - Populate the `environments` dictionary with entries for different environments
   - Set the `baseUrl` and define placeholder environment `variables`

3. **Authentication:** Analyze securitySchemes and security sections:
   - Populate the `auth` field with the appropriate structure
   - Use environment variable references for sensitive values

4. **Dynamic Data:** For request bodies or parameters requiring dynamic input:
   - Use placeholder syntax like `{{$randomEmail}}`, `{{$randomUUID}}`, `{{$guid}}`, `{{$timestamp}}`

5. **Setup/Teardown:** Identify logical setup requirements:
   - Use `setupSteps` for creating prerequisite resources
   - Use `teardownSteps` for cleaning up created resources
   - Use `saveResponseAs` to store response data for later use

6. **Negative Tests (MANDATORY):** For comprehensive coverage, include:
   - Tests for missing required fields
   - Tests with invalid data types
   - Tests for exceeding limits (min/max values)
   - Tests for unique constraint violations
   - Tests for invalid authentication/authorization
   - Tests for expected error status codes and messages

**CRITICAL OUTPUT FORMAT:**
- Your response MUST contain ONLY a valid JSON object matching the structure above.
- Start the output with an opening curly brace and end it with a closing curly brace.
- Absolutely no explanations, markdown formatting, or any text before or after the JSON object.
""",
        output_type=str,
        tools=[],
    )

def setup_blueprint_reviewer_agent() -> Agent:
    """
    Set up the Blueprint Reviewer Agent that validates test blueprints.
    
    Returns:
        Configured Agent instance
    """
    model_name = model_strategy.select_model("blueprint_reviewing", complexity=0.6)
    logger.info(f"Setting up Blueprint Reviewer Agent with model: {model_name}")
    
    return Agent(
        name="BlueprintReviewerAgent",
        model=model_name,
        instructions="""You are an expert API testing specialist who reviews test blueprints for quality, completeness, and accuracy.

**Input Parameters (Provided in the prompt):**
1.  **Spec Analysis Summary:** Key details extracted from the original OpenAPI spec. Use this as the source of truth.
2.  **Blueprint to Review:** The JSON blueprint proposed by the Author agent.

**Your Task:**
1.  **Validate Structure:** Verify the blueprint is valid JSON and follows the required structure.
2.  **Compare with Spec Analysis:** Use the **Spec Analysis Summary** provided in the input. Verify:
    - **Coverage:** All endpoints from the spec are covered.
    - **Accuracy:** Endpoints, methods, parameters, and response codes match the spec.
    - **Completeness:** All required fields are populated with meaningful values.
3.  **Evaluate Quality:**
    - **Structured Assertions:** Are assertions relevant and correctly formed based on the spec?
    - **Environments:** Does the environments section accurately reflect the servers in the spec?
    - **Authentication:** Does the auth section correctly represent the security requirements from the spec?
    - **Dynamic Data:** Are dynamic data placeholders ({{$...}}) used appropriately?
    - **Setup/Teardown:** Are the setup and teardown steps logically sound for the test groups?
    - **Negative Tests:** Critically evaluate negative test coverage. Ensure tests for missing required fields, invalid types, and expected error codes are present for relevant input-accepting endpoints.
    - **Logical Grouping:** Tests are grouped appropriately.
    - **Naming:** Test IDs and names are clear, consistent, and descriptive.
    - **Dependencies:** Dependencies are logical and necessary.
4.  **Generate Feedback:** Create a numbered list of concise, actionable feedback points detailing ALL required changes or missing items. If no changes are needed, state that clearly.
5.  **Append Keyword:** After your feedback (or approval statement), add a **new line** containing **ONLY** one of the following keywords:
    - `[[BLUEPRINT_APPROVED]]` (if NO changes are needed)
    - `[[REVISION_NEEDED]]` (if ANY changes are needed based on your feedback)

**CRITICAL OUTPUT FORMAT:**
- Your response MUST contain your feedback first (numbered list or approval statement).
- Follow the feedback immediately with a single newline character (`\\n`).
- The very last line MUST contain ONLY the keyword `[[BLUEPRINT_APPROVED]]` or `[[REVISION_NEEDED]]`.
- Do NOT add any text after the keyword.
""",
        output_type=str,
        tools=[],
    )

def setup_script_coder_agent(framework: str) -> Agent:
    """
    Set up the Script Coder Agent that creates test scripts for a given framework.
    
    Args:
        framework: Target framework (e.g., 'postman', 'playwright')
        
    Returns:
        Configured Agent instance
    """
    model_name = model_strategy.select_model("script_coding", complexity=0.7)
    logger.info(f"Setting up Script Coder Agent for {framework} with model: {model_name}")
    
    # Define framework-specific expected files/structure
    extra_instructions = ""
    if framework == "playwright":
        extra_instructions = """
- **File Structure:** Organize tests under a `tests/` directory (e.g., `tests/api/users.spec.ts`). Place fixtures in `tests/fixtures/` and utility code in `tests/utils/`.
- **Assertions:** Generate Playwright `expect(response).toXXX()` calls. Use `expect(response.json()).toMatchSchema(schema)` or integrate `ajv` for schema validation. Check headers and response times.
- **Environments:** Generate `.env` files (e.g., `.env.dev`, `.env.prod`). Use `dotenv` library in scripts to load variables.
- **Authentication:** Implement logic to add auth headers based on environment variables.
- **Dynamic Data:** Import faker-js or similar for generating dynamic test data.
- **Setup/Teardown:** Implement `test.beforeAll`/`test.afterAll` hooks for setup/teardown steps.
- **Required Files:**
    - Test files (`*.spec.ts`)
    - A basic Playwright config file (`playwright.config.ts`)
    - Example fixture file (`tests/fixtures/fixtures.ts`)
    - An environment variable template (`.env.example`)
    - A simple `README.md` explaining setup and run commands
"""
    elif framework == "postman":
        extra_instructions = """
- **Assertions:** Translate structured assertions into Postman `pm.test(...)` scripts using `pm.response` methods.
- **Environments:** Generate separate environment files based on the `environments` dictionary.
- **Authentication:** Configure Collection/Folder/Request level authentication based on the `auth` field.
- **Dynamic Data:** Map `{{$...}}` placeholders to Postman's dynamic variables.
- **Setup/Teardown:** Implement pre-request and test scripts for setup/teardown steps.
- **Required Files:**
    - The main Postman collection JSON (`collection.json`)
    - Example environment files (e.g., `environments/development.json`, `environments/production.json`)
    - Example data file if data-driven tests are present (`data/test_data.csv`)
    - A simple `README.md` explaining how to import and run the collection
"""
    # Add more frameworks as needed

    return Agent(
        name=f"ScriptCoderAgent_{framework}",
        model=model_name,
        instructions=f"""You are an expert test automation engineer specializing in creating {framework} API test scripts from blueprints.

**Input Parameters (Provided in the prompt):**
1.  **Framework:** {framework} (already selected for you)
2.  **Blueprint JSON:** The JSON string representation of the complete test blueprint.
3.  **Reviewer Feedback:** Instructions from the previous review cycle (or "No feedback yet...").
4.  **Previous Code Files JSON (Optional):** JSON array of file objects (`{{"filename": ..., "content": ...}}`) from the last iteration.

**Your Task:**
- **If generating initial scripts:** Create comprehensive {framework} test files based *only* on the **Blueprint JSON**. Cover all test cases specified.
- **If revising:** Carefully modify the 'Previous Code Files JSON' according to *all* points in the 'Reviewer Feedback'. Ensure you address all feedback.
- **Code Structure & Best Practices:** Follow idiomatic conventions for {framework}. Implement setup, teardown, assertions, variable extraction, and error handling as specified or implied by the blueprint.
{extra_instructions}
**CRITICAL OUTPUT FORMAT:**
- Your response MUST contain ONLY a valid JSON array of file objects.
- Each object MUST have "filename" (including relative path, e.g., "tests/api/users.spec.ts") and "content" (the full code/text) properties.
- Example: `[{{"filename": "tests/users.spec.ts", "content": "// Test code..."}}, {{"filename": "playwright.config.ts", "content": "// Config..."}}]`
- Start the output directly with `[` and end it directly with `]`.
- Absolutely no explanations, comments, apologies, markdown formatting, or any text before the starting `[` or after the ending `]`.
""",
        output_type=str,
        tools=[],
    )

def setup_script_reviewer_agent(framework: str) -> Agent:
    """
    Set up the Script Reviewer Agent that validates and reviews test scripts.
    
    Args:
        framework: Target framework (e.g., 'postman', 'playwright')
        
    Returns:
        Configured Agent instance
    """
    model_name = model_strategy.select_model("script_reviewing", complexity=0.6)
    logger.info(f"Setting up Script Reviewer Agent for {framework} with model: {model_name}")
    
    return Agent(
        name=f"ScriptReviewerAgent_{framework}",
        model=model_name,
        instructions=f"""You are an expert test automation engineer who reviews {framework} API test scripts for quality, completeness, and correctness.

**Input Parameters (Provided in the prompt):**
1.  **Framework:** {framework} (already selected for you)
2.  **Blueprint JSON:** The JSON string representation of the test blueprint that was used to generate the scripts.
3.  **Code Files to Review:** JSON array of file objects (`{{"filename": ..., "content": ...}}`) that you need to review.

**Your Task:**
1.  **Verify Blueprint Implementation:** Compare the code files against the blueprint to ensure:
    - **Completeness:** All test cases in the blueprint are implemented.
    - **Accuracy:** Tests match the specifications in the blueprint (endpoints, methods, assertions, etc.).
    - **Structure:** Files are organized according to best practices for {framework}.
2.  **Evaluate Technical Quality:**
    - **Assertions:** All structured assertions from the blueprint are correctly implemented
    - **Environments:** Environment configurations are properly implemented
    - **Authentication:** Auth mechanisms from the blueprint are correctly implemented
    - **Setup/Teardown:** Setup and teardown steps are correctly implemented  
    - **Code Quality:** Code is well-structured, readable, and follows best practices.
    - **Error Handling:** Appropriate error handling and validation is implemented.
    - **Maintainability:** Code is modular, reusable, and well-commented.
3.  **Generate Feedback:** Create a numbered list of concise, actionable feedback points detailing ALL required changes. If no changes are needed, state that clearly.
4.  **Append Keyword:** After your feedback (or approval statement), add a **new line** containing **ONLY** one of the following keywords:
    - `[[CODE_APPROVED]]` (if NO changes are needed)
    - `[[REVISION_NEEDED]]` (if ANY changes are needed based on your feedback)

**CRITICAL OUTPUT FORMAT:**
- Your response MUST contain your feedback first (numbered list or approval statement).
- Follow the feedback immediately with a single newline character (`\\n`).
- The very last line MUST contain ONLY the keyword `[[CODE_APPROVED]]` or `[[REVISION_NEEDED]]`.
- Do NOT add any text after the keyword.
""",
        output_type=str,
        tools=[],
    ) 