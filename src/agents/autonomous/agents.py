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
  "groups": [
    {
      "name": "Logical Grouping Name (e.g., Users, Orders)",
      "tests": [
        {
          "id": "unique-test-id",
          "name": "Test Name",
          "endpoint": "/path/{with}/placeholders",
          "method": "HTTP_METHOD",
          "description": "What the test verifies",
          "preconditions": "Any prerequisites",
          "request": {
            "pathParams": {"param1": "value1"},
            "queryParams": {"param2": "value2"},
            "headers": {"Content-Type": "application/json"},
            "body": {"key": "exampleValue"}
          },
          "expectedResponse": {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": {"keyToValidate": "expectedValue"}
          },
          "assertions": [
            "Specific checks to perform",
            "e.g., 'Response contains user ID'"
          ],
          "testData": {
            "variables": {"username": "test_user"},
            "datasets": [{}, {}]
          },
          "dependencies": ["id-of-prerequisite-test"],
          "priority": "high"
        }
      ]
    }
  ]
}
```

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
    - **Logical Grouping:** Tests are grouped appropriately.
    - **Naming:** Test IDs and names are clear, consistent, and descriptive.
    - **Assertions:** Assertions are specific and cover important scenarios.
    - **Test Data:** Appropriate test variables and datasets.
    - **Dependencies:** Dependencies are logical and necessary.
    - **Priority:** Priority levels are appropriate.
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
- **Required Files:** Ensure your output includes:
    - Test files (`*.spec.ts`).
    - A basic Playwright config file (`playwright.config.ts`).
    - Example fixture file (`tests/fixtures/fixtures.ts`).
    - An environment variable template (`.env.example`).
    - A simple `README.md` explaining setup and run commands.
"""
    elif framework == "postman":
        extra_instructions = """
- **Required Files:** Ensure your output includes:
    - The main Postman collection JSON (`collection.json`).
    - Example environment files (e.g., `environments/development.json`, `environments/production.json`).
    - Example data file if data-driven tests are present (`data/test_data.csv`).
    - A simple `README.md` explaining how to import and run the collection.
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
    Set up the Script Reviewer Agent that validates the test scripts for a given framework.
    
    Args:
        framework: Target framework (e.g., 'postman', 'playwright')
        
    Returns:
        Configured Agent instance
    """
    model_name = model_strategy.select_model("script_reviewing", complexity=0.6)
    logger.info(f"Setting up Script Reviewer Agent for {framework} with model: {model_name}")
    
    # Define framework-specific review criteria
    extra_instructions = ""
    if framework == "playwright":
        extra_instructions = """
    - **Framework-Specific Requirements:**
        - Test files correctly use Playwright's test structure, fixtures, and API.
        - Test files are organized in appropriate directories.
        - Config file is properly set up with necessary options.
        - Environment variables are properly managed.
        - All required files are present (tests, config, fixtures, README).
"""
    elif framework == "postman":
        extra_instructions = """
    - **Framework-Specific Requirements:**
        - Collection JSON is valid and properly structured.
        - Environment files are correctly defined with all necessary variables.
        - Collection includes appropriate pre-request scripts and test scripts.
        - All required files are present (collection, environments, README).
"""
    # Add more frameworks as needed

    return Agent(
        name=f"ScriptReviewerAgent_{framework}",
        model=model_name,
        instructions=f"""You are an expert test automation engineer who reviews {framework} API test scripts for quality and accuracy.

**Input Parameters (Provided in the prompt):**
1.  **Framework:** {framework} (already selected for you)
2.  **Blueprint JSON:** The JSON string representation of the complete test blueprint.
3.  **Generated Script Files JSON:** An array of file objects (`{{"filename": ..., "content": ...}}`) to review.

**Your Task:**
1.  **Validate Structure:** Check if the provided code files follow proper {framework} structure and best practices.
2.  **Compare with Blueprint:** Verify against the provided **Blueprint JSON** that:
    - **Coverage:** All test cases from the blueprint are implemented.
    - **Accuracy:** The tests correctly implement the endpoints, methods, parameters, and assertions.
    - **Completeness:** The tests include proper setup, teardown, and error handling.
3.  **Code Quality:** Evaluate the code for:
    - **Readability:** Well-structured code with clear variable names and comments.
    - **Maintainability:** DRY principles, reusable components, and configuration.
    - **Robustness:** Proper error handling and test isolation.{extra_instructions}
4.  **Generate Feedback:** Create a numbered list of concise, actionable feedback points detailing *all* required changes or missing items. If no changes are needed, state that clearly.
5.  **Append Keyword:** After your feedback (or approval statement), add a **new line** containing **ONLY** one of the following keywords:
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