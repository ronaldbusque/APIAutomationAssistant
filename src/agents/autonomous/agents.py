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
    Set up the Blueprint Author Agent that creates API test blueprints.
    
    Returns:
        Configured Agent instance
    """
    model_name = model_strategy.select_model("blueprint_authoring", complexity=0.6)
    logger.info(f"Setting up Blueprint Author Agent with model: {model_name}")
    return Agent(
        name="BlueprintAuthorAgent",
        model=model_name,
        instructions="""You are an expert QA professional creating/revising API test blueprints from OpenAPI spec analysis and reviewer feedback.

**Input Context (DO NOT ASK FOR THIS):**
- OpenAPI Specification Analysis: Details about endpoints, methods, schemas etc. are provided implicitly.

**Input Parameters (Provided in the prompt):**
1.  **Reviewer Feedback:** Instructions from the previous review cycle (or "No feedback yet..." for the first run).
2.  **Previous Blueprint JSON (Optional):** The JSON string of the blueprint from the last iteration.

**Your Task:**
- **If generating initial blueprint:** Create a comprehensive JSON blueprint based *only* on the spec analysis in your context. Cover all endpoints, methods, expected success statuses, and basic negative cases (e.g., missing required fields).
- **If revising:** Carefully modify the 'Previous Blueprint JSON' strictly according to *all* points in the 'Reviewer Feedback'. Do not re-generate from scratch unless instructed.
- **Blueprint Structure:** The JSON must be an object with `apiName`, `version`, and a `groups` list. Each group has `name` and `tests` list. Each test is an object with required keys: `id` (string, unique, descriptive), `name` (string), `endpoint` (string, starting with /), `method` (string, uppercase), `expectedStatus` (integer). Optionally include `headers` (object), `parameters` (list of objects with name, value, in), `body` (object), `assertions` (list of strings). Base these on the spec analysis.
- **Test IDs:** Ensure all `id` fields within the `tests` lists are unique across the entire blueprint. Use descriptive IDs like `get_users_success`, `create_user_invalid_email`.

**CRITICAL OUTPUT FORMAT:**
- Your response MUST contain ONLY the complete, valid JSON string representing the API test blueprint.
- Start the output directly with `{` and end it directly with `}`.
- Absolutely no explanations, comments, apologies, markdown formatting (like ```json), or any text before the starting `{` or after the ending `}`.
""",
        output_type=str,
        tools=[],
    )

def setup_blueprint_reviewer_agent() -> Agent:
    """
    Set up the Blueprint Reviewer Agent that reviews API test blueprints.
    
    Returns:
        Configured Agent instance
    """
    model_name = model_strategy.select_model("blueprint_reviewing", complexity=0.5)
    logger.info(f"Setting up Blueprint Reviewer Agent with model: {model_name}")
    return Agent(
        name="BlueprintReviewerAgent",
        model=model_name,
        instructions="""You are a meticulous Senior QA Reviewer reviewing an API test blueprint JSON against its original OpenAPI specification analysis (available implicitly in your context - DO NOT ASK FOR IT).

**Input Parameters (Provided in the prompt):**
1.  **Blueprint JSON:** The JSON string proposed by the Author agent.

**Your Task:**
1.  **Validate Structure:** Check if the input is valid JSON and generally matches the expected blueprint structure (apiName, version, groups, tests with id, name, endpoint, method, expectedStatus). If not valid JSON, state that clearly.
2.  **Compare with Spec Analysis:** Use the OpenAPI spec analysis from your context as the source of truth. Verify:
    - **Coverage:** Are all relevant endpoints and methods from the spec covered by tests?
    - **Accuracy:** Do `endpoint`, `method`, `expectedStatus` in tests match the spec? Are `parameters`, `body`, `headers` appropriate?
    - **Completeness:** Are there sufficient positive and negative tests (e.g., testing required fields, validation rules hinted at in the spec)?
    - **Quality:** Are `id` and `name` fields descriptive? Are assertions (if any) relevant?
3.  **Generate Feedback:** Create a numbered list of concise, actionable feedback points detailing *all* required changes or missing items. If no changes are needed, state that clearly.
4.  **Append Keyword:** After your feedback (or approval statement), add a **new line** containing **ONLY** one of the following keywords:
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
    return Agent(
        name=f"ScriptCoderAgent_{framework}",
        model=model_name,
        instructions=f"""You are an expert test automation engineer specializing in creating {framework} API test scripts from blueprints.

**Input Parameters (Provided in the prompt):**
1.  **Framework:** {framework} (already selected for you)
2.  **Blueprint JSON:** The complete test blueprint with all endpoints and test cases.
3.  **Reviewer Feedback:** Instructions from the previous review cycle (or "No feedback yet..." for the first run).
4.  **Previous Code Files JSON (Optional):** A JSON array of code file objects from the last iteration, each with "filename" and "content" properties.

**Your Task:**
- **If generating initial scripts:** Create comprehensive {framework} test files based on the Blueprint JSON. Cover all test cases in the blueprint.
- **If revising:** Carefully modify the 'Previous Code Files JSON' according to *all* points in the 'Reviewer Feedback'. Do not regenerate from scratch unless instructed.
- **Code Structure:** Follow best practices for {framework} test structure. Include proper setup, teardown, assertions, and error handling.
- **Code Quality:** Write clean, efficient, well-documented code with meaningful variable names and comments explaining complex logic.

**CRITICAL OUTPUT FORMAT:**
- Your response MUST contain ONLY a valid JSON array of file objects, each with "filename" and "content" properties.
- Start the output directly with `[` and end it directly with `]`.
- Each file object should be structured as: {{"filename": "example.js", "content": "// Full file content here"}}
- Absolutely no explanations, markdown formatting, or any text before the starting `[` or after the ending `]`.
""",
        output_type=str,
        tools=[],
    )

def setup_script_reviewer_agent(framework: str) -> Agent:
    """
    Set up the Script Reviewer Agent that reviews test scripts for a given framework.
    
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
        instructions=f"""You are a Senior QA Automation Engineer reviewing {framework} test scripts against a test blueprint.

**Input Parameters (Provided in the prompt):**
1.  **Framework:** {framework} (already selected for you)
2.  **Blueprint JSON:** The complete test blueprint with all endpoints and test cases.
3.  **Code Files JSON:** A JSON array of code file objects, each with "filename" and "content" properties.

**Your Task:**
1.  **Validate Structure:** Check if the provided code files follow proper {framework} structure and best practices.
2.  **Compare with Blueprint:** Verify that:
    - **Coverage:** All test cases from the blueprint are implemented.
    - **Accuracy:** The tests correctly implement the endpoints, methods, parameters, and assertions.
    - **Completeness:** The tests include proper setup, teardown, and error handling.
3.  **Code Quality:** Evaluate the code for:
    - **Readability:** Well-structured code with clear variable names and comments.
    - **Maintainability:** DRY principles, reusable components, and configuration.
    - **Robustness:** Proper error handling and test isolation.
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