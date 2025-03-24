
---

## 1. Overview

**Purpose:**  
The AI-Powered API Test Automation Tool leverages artificial intelligence to generate comprehensive API test suites from an OpenAPI specification. It supports two modes:  
- **Basic Mode:** Generates baseline test cases focusing on endpoint contract validation, HTTP status codes, and JSON schema validation.  
- **Advanced Mode:** Extends Basic Mode with user-defined business rules, custom assertions, test data setup, test sequencing, and environment management.

**Target Outputs:**  
- **Postman Collection:** A JSON file adhering to the Postman Collection v2.1 schema, including variables, pre-request scripts, and assertions.  
- **Playwright Test Scripts:** Modular JavaScript/TypeScript scripts for API testing with integrated variable handling.

---

## 2. Architectural Overview

### 2.1 Components

1. **User Interface (UI):**  
   - **Spec Input:**  
     - **Upload File:** Accepts `.yaml`, `.yml`, or `.json` files (max 1MB).  
     - **Enter URL:** Fetches the OpenAPI spec from a provided URL.  
     - **Paste Spec:** Text area with YAML/JSON syntax highlighting (max 1MB).  
   - **Mode Selector:** Toggle or dropdown for **Basic** or **Advanced** mode.  
   - **Advanced Inputs (Visible in Advanced Mode):**  
     - **Business Rules:** Text area (e.g., "Invalid tokens must return 401").  
     - **Test Data Setup:** Text area (e.g., "POST /users to create a resource").  
     - **Test Flow:** Text area (e.g., "POST /users must run before GET /users/{id}").  
   - **Target Selector:** Checkboxes for **Postman**, **Playwright**, or both.  
   - **Review Interface:** Monaco Editor for reviewing and editing the generated JSON blueprint with real-time validation.
   - **Progress Indicator:** Shows real-time streaming progress during test generation with detailed stage information.

2. **Backend Services:**  
   - **Triage Agent:**  
     - Analyzes user input and decides whether to hand off to the Test Planner Agent (for OpenAPI specs) or directly to the Coder Agent (for blueprints).  
   - **Test Planner Agent:**  
     - Generates a structured `Blueprint` from the OpenAPI spec using Structured Outputs.
     - Uses dynamic model selection based on complexity.
     - Provides streaming updates during generation.
   - **Coder Agent:**  
     - Uses sub-agents (e.g., `PostmanCoder`, `PlaywrightCoder`) as tools to generate framework-specific test scripts.
     - Implements intelligent retry logic with exponential backoff.
   - **Export Module:**  
     - Manages export of test scripts and provides REST API endpoints for automation.

### 2.2 Data Flow

```
User Interface → Triage Agent → Test Planner Agent → User Review → Coder Agent → Export
  (Spec/Input)     (Handoff)       (Structured Blueprint)  (Validated Blueprint)  (Scripts)
```

- **Triage Agent:** Routes the workflow based on input type (spec or blueprint).  
- **Test Planner Agent:** Produces a structured `Blueprint` with streaming support and robust error handling.  
- **Coder Agent:** Generates test scripts using sub-agents for selected frameworks with dynamic model selection.

---

## 3. Functional Requirements

### 3.1 Spec Input & Mode Selection

- **Input Methods:**  
  - **Upload File:** Accepts `.yaml`, `.yml`, `.json` (max 1MB). Validates file type and size.  
  - **Enter URL:** Fetches spec via HTTP GET. Displays guidance to avoid query parameters.  
  - **Paste Spec:** Text area with syntax highlighting (max 1MB).  
- **Validation:**  
  - Parses as YAML or JSON with comprehensive error handling.
  - If parsing fails: "The provided spec may be incorrectly formatted. Proceed with caution."  
  - If `paths` is missing: "Critical fields are missing. Continue anyway?" (Yes/No).  
- **Mode Selector:**  
  - **Basic Mode:** Focuses on endpoint contracts, status codes, and schema validation.  
  - **Advanced Mode:** Includes business rules, test data, and test flow.  
- **Target Selector:** Checkboxes for **Postman**, **Playwright**, or both.

### 3.2 Triage Agent

- **Purpose:** Coordinates the workflow by analyzing input and routing to the appropriate agent.  
- **Setup:** Configured with handoffs to Test Planner Agent and Coder Agent.  
- **Instructions:** "If the user provides an OpenAPI spec, hand off to the Test Planner Agent. If the user provides a test blueprint, hand off to the Coder Agent."  
- **Input:**  
  - `input_type: str` ("spec" or "blueprint")  
  - `spec: Optional[str]` (OpenAPI spec)  
  - `blueprint: Optional[dict]` (pre-existing blueprint)  
  - `mode: str` ("basic" or "advanced")  
  - `targets: List[str]` (e.g., ["postman", "playwright"])  
- **Behavior:**  
  - If `input_type == "spec"`, hands off to Test Planner Agent with `spec`, `mode`, and advanced inputs.  
  - If `input_type == "blueprint"`, hands off to Coder Agent with `blueprint` and `targets`.  
- **Error Handling:**  
  - If neither spec nor blueprint is provided: "Please provide either an OpenAPI spec or a test blueprint."
  - Uses a simpler model (gpt-3.5-turbo) since it's a straightforward routing task.

### 3.3 Test Planner Agent

- **Setup:** Configured with Structured Outputs using the `Blueprint` Pydantic model, using dynamic model selection based on spec complexity.
- **Input (from Triage Agent):**  
  - `spec: str` (JSON-serialized if parsed, raw string otherwise)  
  - `mode: str`  
  - `business_rules: Optional[str]`  
  - `test_data: Optional[str]`  
  - `test_flow: Optional[str]`  
  - `parse_warnings: List[str]`  
- **Message Construction:**  
  ```python
  def construct_planner_message(
      spec: str,
      mode: str,
      business_rules: Optional[str] = None,
      test_data: Optional[str] = None,
      test_flow: Optional[str] = None,
      parse_warnings: List[str] = []
  ) -> str:
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
  ```
- **Dynamic Model Selection:**
  ```python
  def select_model(task: str, complexity: float) -> str:
      """Select the appropriate model based on task and complexity."""
      if task == "planning":
          if complexity > 0.7:
              return "gpt-4o"  # Complex OpenAPI spec
          else:
              return "gpt-4o-mini"  # Simpler OpenAPI spec
      # Other task types handled elsewhere
      return "gpt-4o-mini"  # Default fallback
  ```
- **Streaming Support:**
  ```python
  # Stream the test planning process to provide real-time feedback
  result = Runner.run_streamed(
      test_planner_agent,
      construct_planner_message(spec, mode, business_rules, test_data, test_flow, parse_warnings)
  )
  
  # Process stream events to update UI
  async for event in result.stream_events():
      # Update progress in UI
      if hasattr(event, 'delta') and event.delta:
          await update_progress(event.delta)
  
  blueprint = result.final_output_as(Blueprint)
  ```
- **Enhanced Error Handling:**
  ```python
  async def run_test_planner_with_retry(
      spec: str,
      mode: str,
      business_rules: Optional[str] = None,
      test_data: Optional[str] = None,
      test_flow: Optional[str] = None,
      parse_warnings: List[str] = [],
      max_retries: int = 3
  ) -> Blueprint:
      message = construct_planner_message(
          spec, mode, business_rules, test_data, test_flow, parse_warnings
      )
      
      for attempt in range(max_retries):
          try:
              result = await Runner.run(
                  test_planner_agent, 
                  message,
                  timeout=300  # 5-minute timeout
              )
              return result.final_output_as(Blueprint)
          except Exception as e:
              logger.error(f"Test planner failed (attempt {attempt+1}/{max_retries}): {str(e)}")
              if attempt == max_retries - 1:  # Last attempt
                  # Return a minimal valid blueprint with error information
                  return Blueprint(
                      schemaVersion="1.0",
                      suite=Suite(
                          tests=[
                              Test(
                                  name="Error Test",
                                  endpoint="/error",
                                  method="GET",
                                  expectedStatus=200
                              )
                          ]
                      ),
                      warnings=[f"Blueprint generation failed after {max_retries} attempts: {str(e)}"]
                  )
              # Exponential backoff with jitter
              await asyncio.sleep(2 ** attempt + random.uniform(0, 1))
  ```
- **Output:**  
  - A `Blueprint` instance with:  
    - `schemaVersion: str` (default: "1.0")  
    - `suite: Suite` (containing `setup`, `tests`, `teardown`)  
    - `warnings: Optional[List[str]]`  

### 3.4 User Review Interface

- **Blueprint Display:**  
  - Monaco Editor with JSON syntax highlighting and real-time validation against `blueprint_schema`.  
  - Warnings displayed in a sidebar or as annotations.  
- **Editing:**  
  - Real-time editing with schema validation.  
  - "Approve" button disabled if the blueprint is invalid.  
- **Approval:**  
  - Submits the validated blueprint to the Coder Agent.
- **Output Validation:**
  ```python
  def validate_blueprint(blueprint: Blueprint) -> list[str]:
      """Validate the blueprint for common issues beyond schema validation."""
      warnings = []
      
      # Check for empty test suites
      if not blueprint.suite.tests:
          warnings.append("Warning: Blueprint contains no tests")
      
      # Check for duplicate test names
      test_names = [test.name for test in blueprint.suite.tests]
      duplicate_names = set([name for name in test_names if test_names.count(name) > 1])
      if duplicate_names:
          warnings.append(f"Warning: Duplicate test names found: {', '.join(duplicate_names)}")
      
      # Check for missing dependencies
      all_test_names = set(test_names)
      for test in blueprint.suite.tests:
          if test.dependencies:
              for dep in test.dependencies:
                  if dep not in all_test_names:
                      warnings.append(f"Warning: Test '{test.name}' depends on non-existent test '{dep}'")
      
      # Check for circular dependencies
      dependency_graph = {}
      for test in blueprint.suite.tests:
          dependency_graph[test.name] = test.dependencies or []
      
      # Improved cycle detection that reports the actual cycle path
      def detect_cycle(node, path=None):
          if path is None:
              path = []
          
          # Check if the current node is already in the path
          if node in path:
              # Cycle detected - return the cycle path for better reporting
              cycle_start = path.index(node)
              return path[cycle_start:] + [node]
          
          # Add current node to path and check all neighbors
          new_path = path + [node]
          for neighbor in dependency_graph.get(node, []):
              cycle = detect_cycle(neighbor, new_path)
              if cycle:
                  return cycle
          
          return None
      
      # Check for cycles starting from each node
      for test_name in dependency_graph:
          cycle = detect_cycle(test_name)
          if cycle:
              cycle_str = " -> ".join(cycle)
              warnings.append(f"Warning: Circular dependency detected: {cycle_str}")
              break
      
      return warnings
  ```

### 3.5 Coder Agent

- **Setup:** Configured with Structured Outputs and enhanced error handling.
- **Sub-Agents (Agents as Tools):**  
  - **PostmanCoder:** Generates Postman collections.  
  - **PlaywrightCoder:** Generates Playwright test scripts.  
- **Input (from Triage Agent or User Review):**  
  - `blueprint: dict`  
  - `targets: List[str]` (e.g., ["postman", "playwright"])  
- **Behavior:**  
  - Uses the appropriate model based on complexity (e.g., `gpt-4o` for complex blueprints).
  - For each target, uses the corresponding sub-agent to generate the script.
- **Dynamic Model Selection:**
  ```python
  def calculate_complexity(blueprint: Blueprint) -> float:
      """Calculate the complexity of a blueprint to determine the appropriate model."""
      # Count the total number of tests
      test_count = len(blueprint.suite.tests)
      
      # Count the number of dependencies
      dependency_count = sum(1 for test in blueprint.suite.tests if test.dependencies)
      
      # Count the number of business rules
      business_rule_count = sum(len(test.businessRules or []) for test in blueprint.suite.tests)
      
      # Count setup and teardown steps
      setup_count = len(blueprint.suite.setup or [])
      teardown_count = len(blueprint.suite.teardown or [])
      
      # Calculate a complexity score (0-1) based on these factors
      max_score = 100  # Arbitrary maximum for normalization
      complexity_score = min(1.0, (
          test_count * 2 + 
          dependency_count * 3 + 
          business_rule_count * 2 + 
          setup_count + 
          teardown_count
      ) / max_score)
      
      return complexity_score
  ```
- **Enhanced Error Handling:**
  ```python
  async def generate_scripts_with_error_handling(
      blueprint: Blueprint,
      targets: List[str],
      max_retries: int = 3
  ) -> Dict[str, Dict[str, str]]:
      results = {}
      
      for target in targets:
          tool_name = f"generate_{target}"
          results[target] = {}
          
          for attempt in range(max_retries):
              try:
                  # Determine the appropriate model based on blueprint complexity
                  blueprint_complexity = calculate_complexity(blueprint)
                  model = "gpt-4o" if blueprint_complexity > 0.7 else "gpt-4o-mini"
                  
                  # Update the coder agent model dynamically
                  coder_agent.model = model
                  
                  # Call the agent with the appropriate tool
                  result = await Runner.run(
                      coder_agent,
                      json.dumps({
                          "blueprint": blueprint.model_dump(),
                          "target": target
                      }),
                      timeout=600  # 10-minute timeout for complex generations
                  )
                  
                  script_output = result.final_output_as(ScriptOutput)
                  results[target] = script_output.scripts.get(target, {})
                  break  # Success, exit retry loop
                  
              except Exception as e:
                  logger.error(f"Script generation for {target} failed (attempt {attempt+1}/{max_retries}): {str(e)}")
                  if attempt == max_retries - 1:  # Last attempt
                      results[target] = {
                          "error.txt": f"Failed to generate {target} scripts after {max_retries} attempts: {str(e)}"
                      }
                  else:
                      # Exponential backoff with jitter
                      await asyncio.sleep(2 ** attempt + random.uniform(0, 1))
      
      return results
  ```
- **Streaming Support:**
  ```python
  async def generate_scripts_with_streaming(
      blueprint: Blueprint,
      targets: List[str]
  ) -> AsyncIterator[Tuple[str, str, str]]:
      """Generate scripts with streaming progress updates."""
      for target in targets:
          tool_name = f"generate_{target}"
          
          # Determine the appropriate model based on blueprint complexity
          blueprint_complexity = calculate_complexity(blueprint)
          model = "gpt-4o" if blueprint_complexity > 0.7 else "gpt-4o-mini"
          
          # Update the coder agent model dynamically
          coder_agent.model = model
          
          # Stream the generation process
          result = Runner.run_streamed(
              coder_agent,
              json.dumps({
                  "blueprint": blueprint.model_dump(),
                  "target": target
              })
          )
          
          # Process streaming updates
          current_file = None
          current_content = ""
          async for event in result.stream_events():
              if hasattr(event, 'delta') and event.delta:
                  # Extract file information from the delta if available
                  if "current_file" in event.delta:
                      if current_file and current_content:
                          # Yield the previous file completion
                          yield (target, current_file, current_content)
                      current_file = event.delta["current_file"]
                      current_content = ""
                  elif current_file and "content" in event.delta:
                      current_content += event.delta["content"]
                      # Yield progress update
                      yield (target, current_file, "progress", len(current_content))
          
          # Yield the final file when done
          if current_file and current_content:
              yield (target, current_file, current_content)
  ```
- **Output:**  
  - A `ScriptOutput` instance with:  
    - `scripts: Dict[str, Dict[str, str]]` (e.g., `{"postman": {"collection.json": "..."}, "playwright": {"test1.js": "..."}}`)  
- **Error Handling:**  
  - If a sub-agent fails, includes an error entry in `scripts` for that target.

### 3.6 Export Module

- **REST API Endpoints:**  
  - **`POST /generate`**  
    - **Request:**  
      ```json
      {
          "input_type": "spec|blueprint",
          "spec": "string",
          "blueprint": { ... },
          "mode": "basic|advanced",
          "targets": ["postman", "playwright"]
      }
      ```
    - **Response:**  
      ```json
      { "jobId": "uuid-string" }
      ```
  - **`GET /status/{jobId}`**  
    - **Response:**  
      ```json
      {
          "status": "processing|completed|failed",
          "progress": {
              "stage": "planning|coding",
              "percent": 75,
              "currentFile": "example.test.js"
          },
          "result": { "blueprint": { ... }, "scripts": { ... } }
      }
      ```
- **Download Options:**  
  - UI: Individual files or ZIP archive.  
  - API: Script contents or download URLs.

---

## 4. Structured Output Models

### 4.1 Blueprint Model

```python
from pydantic import BaseModel, Field, validator, root_validator
from typing import List, Optional, Dict, Set, Any
import re

class Step(BaseModel):
    endpoint: str
    method: str
    payload: Optional[Dict[str, Any]] = None
    saveAs: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    
    @validator('method')
    def validate_method(cls, v):
        valid_methods = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'}
        if v.upper() not in valid_methods:
            raise ValueError(f'Method must be one of {valid_methods}')
        return v.upper()
    
    @validator('endpoint')
    def validate_endpoint(cls, v):
        if not v.startswith('/'):
            return '/' + v
        return v
    
    @validator('saveAs')
    def validate_save_as(cls, v):
        if v is not None:
            # Ensure it's a valid variable name
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', v):
                raise ValueError(f'saveAs must be a valid variable name: {v}')
        return v

class Test(BaseModel):
    name: str
    endpoint: str
    method: str
    expectedStatus: int
    assertions: Optional[List[str]] = None
    businessRules: Optional[List[str]] = None
    dependencies: Optional[List[str]] = None
    payload: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    
    @validator('expectedStatus')
    def validate_status(cls, v):
        if not (100 <= v <= 599):
            raise ValueError('HTTP status code must be between 100 and 599')
        return v
    
    @validator('method')
    def validate_method(cls, v):
        valid_methods = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'}
        if v.upper() not in valid_methods:
            raise ValueError(f'Method must be one of {valid_methods}')
        return v.upper()
    
    @validator('endpoint')
    def validate_endpoint(cls, v):
        if not v.startswith('/'):
            return '/' + v
        return v
    
    @validator('name')
    def validate_name(cls, v):
        if not v:
            raise ValueError('Test name cannot be empty')
        if len(v) > 100:
            raise ValueError('Test name too long (max 100 characters)')
        return v
    
    @root_validator
    def validate_payload_for_methods(cls, values):
        method = values.get('method')
        payload = values.get('payload')
        
        if method in ['GET', 'HEAD', 'DELETE'] and payload:
            values['payload'] = None  # Remove payload for methods that shouldn't have one
        
        return values

class Suite(BaseModel):
    setup: Optional[List[Step]] = None
    tests: List[Test]
    teardown: Optional[List[Step]] = None
    variables: Optional[Dict[str, str]] = Field(default_factory=dict, description="Environment variables")
    
    @validator('tests')
    def validate_tests(cls, v):
        if not v:
            raise ValueError('Suite must contain at least one test')
        
        # Check for duplicate test names
        names = [test.name for test in v]
        duplicates = set([name for name in names if names.count(name) > 1])
        if duplicates:
            raise ValueError(f'Duplicate test names found: {duplicates}')
        
        return v
    
    @validator('setup', 'teardown')
    def validate_steps(cls, v):
        if v is not None:
            for step in v:
                # Check if saveAs is provided and valid
                if step.saveAs and not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', step.saveAs):
                    raise ValueError(f'Step saveAs must be a valid variable name: {step.saveAs}')
        return v

class Blueprint(BaseModel):
    schemaVersion: str = "1.0"
    suite: Suite
    warnings: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata about the blueprint")
    
    @validator('schemaVersion')
    def validate_schema_version(cls, v):
        if v != "1.0":
            raise ValueError(f"Unsupported schema version: {v}")
        return v
    
    @validator('suite')
    def validate_suite(cls, v):
        # Additional suite validation beyond what's in the Suite class
        if not v.tests:
            raise ValueError("Suite must contain at least one test")
        
        # Check for duplicate endpoints with same method
        endpoint_methods = {}
        for test in v.tests:
            key = f"{test.method}:{test.endpoint}"
            if key in endpoint_methods:
                raise ValueError(f"Duplicate endpoint/method combination: {key}")
            endpoint_methods[key] = True
        
        return v
    
    def validate_dependencies(self) -> List[str]:
        """Validate test dependencies and return any warnings."""
        warnings = []
        
        # Get all test names
        test_names = {test.name for test in self.suite.tests}
        
        # Check for missing dependencies
        for test in self.suite.tests:
            if test.dependencies:
                for dep in test.dependencies:
                    if dep not in test_names:
                        warnings.append(f"Test '{test.name}' depends on non-existent test '{dep}'")
        
        # Check for circular dependencies with improved reporting
        dependency_graph = {}
        for test in self.suite.tests:
            dependency_graph[test.name] = test.dependencies or []
        
        # Improved cycle detection with path tracking
        def detect_cycle(node, path=None):
            if path is None:
                path = []
            
            # Check if the current node is already in the path
            if node in path:
                # Cycle detected - return the cycle path for better reporting
                cycle_start = path.index(node)
                return path[cycle_start:] + [node]
            
            # Add current node to path and check all neighbors
            new_path = path + [node]
            for neighbor in dependency_graph.get(node, []):
                cycle = detect_cycle(neighbor, new_path)
                if cycle:
                    return cycle
            
            return None
        
        # Check for cycles starting from each node
        for test_name in dependency_graph:
            cycle = detect_cycle(test_name)
            if cycle:
                cycle_str = " -> ".join(cycle)
                warnings.append(f"Circular dependency detected: {cycle_str}")
                break
        
        return warnings
```

### 4.2 ScriptOutput Model

```python
from pydantic import BaseModel, Field, validator, root_validator
from typing import Dict, Optional, List, Any

class ScriptFile(BaseModel):
    filename: str
    content: str
    
    @validator('filename')
    def validate_filename(cls, v):
        # Basic filename validation
        forbidden_chars = '<>:"/\\|?*'
        if any(c in v for c in forbidden_chars):
            raise ValueError(f"Filename contains invalid characters. Avoid: {forbidden_chars}")
        return v
    
    @validator('content')
    def validate_content(cls, v):
        # Check if content is empty
        if not v.strip():
            raise ValueError("File content cannot be empty")
        return v

class TargetOutput(BaseModel):
    files: Dict[str, ScriptFile]
    validation_warnings: Optional[List[str]] = None
    
    @root_validator
    def check_files_exist(cls, values):
        files = values.get('files', {})
        if not files:
            raise ValueError("At least one output file must be provided")
        return values

class ScriptOutput(BaseModel):
    scripts: Dict[str, TargetOutput] = Field(
        ..., 
        description="Scripts for each target, e.g., {'postman': {'files': {'collection.json": {...}}}}"
    )
    overall_warnings: Optional[List[str]] = None
    
    def validate_scripts(self) -> List[str]:
        """Validate the generated scripts for common issues."""
        warnings = []
        
        # Check for empty script files
        for target, output in self.scripts.items():
            for filename, file in output.files.items():
                if not file.content.strip():
                    warnings.append(f"Empty file generated for {target}: {filename}")
                
                # Check for potential unsupported features in Postman
                if target.lower() == "postman" and filename.endswith(".json"):
                    if "pm.sendRequest" in file.content and "callback" in file.content:
                        warnings.append(f"Potential unsupported feature in Postman: Using callbacks with pm.sendRequest")
                
                # Check for potentially missing imports in Playwright
                if target.lower() == "playwright" and filename.endswith((".js", ".ts")):
                    if "test(" in file.content and "import { test } from " not in file.content:
                        warnings.append(f"Potential missing import in Playwright file: 'test' is used but not imported")
                    
                    if "expect(" in file.content and "import { expect } from " not in file.content:
                        warnings.append(f"Potential missing import in Playwright file: 'expect' is used but not imported")
        
        return warnings
```

---

## 5. Agent Setup and Execution

### 5.1 Agent Setup with Model Optimization

```python
import os
import asyncio
import json
import random
from typing import List, Dict, Optional, Tuple, AsyncIterator
import logging

from agents import Agent, handoff, function_tool, trace, gen_trace_id, Runner, Item, ItemHelpers
from pydantic import BaseModel

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load models and schemas
from models import Blueprint, ScriptOutput, Suite, Test, Step, ScriptFile, TargetOutput

# Define model selection based on task complexity
def select_model(task: str, complexity: float) -> str:
    """
    Select the appropriate model based on task complexity and available models.
    
    Args:
        task: The type of task being performed
        complexity: Task complexity score from 0-1
        
    Returns:
        The selected model name
    """
    # Default model if something goes wrong
    default_model = "gpt-4o-mini"
    
    # Get preferred models from environment if available
    planning_model = os.environ.get("PLANNING_MODEL", "gpt-4o")
    coding_model = os.environ.get("CODING_MODEL", "gpt-4o")
    triage_model = os.environ.get("TRIAGE_MODEL", "gpt-3.5-turbo")
    
    try:
        if task == "triage":
            return triage_model
        elif task == "planning":
            if complexity > 0.7:
                return planning_model
            else:
                return "gpt-4o-mini"
        elif task == "coding":
            if complexity > 0.8:
                return coding_model
            elif complexity > 0.5:
                return "gpt-4o-mini"
            else:
                return "gpt-3.5-turbo"
        else:
            logger.warning(f"Unknown task type: {task}, using default model")
            return default_model
    except Exception as e:
        logger.error(f"Error in model selection: {str(e)}, using default model")
        return default_model

# Create sub-agents for code generation
postman_coder = Agent(
    name="PostmanCoder",
    instructions="""
    You are a Postman collection generator. You create Postman collections from test blueprints.
    Follow these guidelines:
    1. Create a collection with folders for each logical group of tests
    2. Include pre-request scripts for setup when needed
    3. Add appropriate assertions based on expectedStatus and assertions
    4. Handle dependencies by using environment variables for data sharing
    5. Implement any businessRules provided in the tests
    """,
    model="gpt-4o-mini"  # Will be dynamically updated based on complexity
)

playwright_coder = Agent(
    name="PlaywrightCoder",
    instructions="""
    You are a Playwright test script generator. You create Playwright API tests from test blueprints.
    Follow these guidelines:
    1. Use the Playwright test framework with appropriate fixtures
    2. Organize tests by logical grouping
    3. Implement proper assertions based on expectedStatus and assertions
    4. Handle dependencies through proper test ordering and data sharing
    5. Implement any businessRules provided in the tests
    """,
    model="gpt-4o-mini"  # Will be dynamically updated based on complexity
)

# Create the main agents
test_planner_agent = Agent(
    name="TestPlanner",
    instructions="""
    You are a test planning specialist. Your job is to analyze OpenAPI specifications and generate
    comprehensive test blueprints. Consider:
    
    1. Basic Mode:
       - All endpoints should be tested with valid inputs
       - Include appropriate status code checks
       - Add schema validation when response schemas are provided
    
    2. Advanced Mode:
       - Include all basic mode tests
       - Implement business rules as custom assertions
       - Set up test data according to provided guidelines
       - Handle test dependencies and sequencing based on the test flow
    
    Generate a detailed Blueprint that follows the specified schema exactly. Be thorough but concise.
    """,
    output_type=Blueprint,
    model="gpt-4o-mini"  # Will be dynamically updated based on complexity
)

coder_agent = Agent(
    name="CoderAgent",
    instructions="""
    You are a test code generator. Your job is to convert test blueprints into executable test code.
    Use the appropriate sub-agent based on the target framework.
    
    Generate well-structured, idiomatic code for each target framework. Ensure tests are:
    1. Well-organized and maintainable
    2. Handle dependencies correctly
    3. Include proper assertions
    4. Implement all specified business rules
    
    Return the complete, runnable test files without omitting any code.
    """,
    tools=[
        postman_coder.as_tool(
            tool_name="generate_postman", 
            tool_description="Generate Postman collection from blueprint"
        ),
        playwright_coder.as_tool(
            tool_name="generate_playwright", 
            tool_description="Generate Playwright test scripts from blueprint"
        )
    ],
    output_type=ScriptOutput,
    model="gpt-4o-mini"  # Will be dynamically updated based on complexity
)

# Create triage agent with handoffs
triage_agent = Agent(
    name="TriageAgent",
    instructions="""
    You are the coordinator for an API test generation system. Your job is to:
    
    1. Determine if the user provided an OpenAPI spec or a test blueprint
    2. For OpenAPI specs, hand off to the TestPlanner agent
    3. For blueprints, hand off to the CoderAgent
    
    Be diligent in checking the input_type and ensuring all necessary data is present before handoff.
    """,
    handoffs=[
        handoff(
            test_planner_agent, 
            input_filter=lambda data: data if any(item for item in data.pre_handoff_items if hasattr(item, 'content') and isinstance(item.content, dict) and item.content.get("input_type") == "spec") else None
        ),
        handoff(
            coder_agent, 
            input_filter=lambda data: data if any(item for item in data.pre_handoff_items if hasattr(item, 'content') and isinstance(item.content, dict) and item.content.get("input_type") == "blueprint") else None
        )
    ],
    model="gpt-3.5-turbo"  # Simple routing task doesn't need a complex model
)
```

### 5.2 Agent Execution with Enhanced Error Handling and Streaming

```python
async def run_agent_with_retry(
    agent: Agent, 
    input_data: str | dict, 
    max_retries: int = 3,
    base_timeout: int = 300,
    complexity: float = 0.5,
    task: str = "general"
) -> Tuple[BaseModel, str]:
    """
    Run an agent with retry logic and error handling.
    
    Args:
        agent: The agent to run
        input_data: The input data (string or dict)
        max_retries: Maximum number of retry attempts
        base_timeout: Base timeout in seconds
        complexity: Task complexity (0-1) to determine model and timeout
        task: Task type for model selection
        
    Returns:
        Tuple of (result, trace_id)
    """
    # Convert dict to JSON string if needed
    if isinstance(input_data, dict):
        input_data = json.dumps(input_data)
    
    # Select model based on task and complexity
    original_model = agent.model
    selected_model = select_model(task, complexity)
    agent.model = selected_model
    
    # Update tool choice based on complexity if needed
    update_tool_choice(agent, complexity)
    
    # Log model selection for debugging
    logger.info(f"Selected model {selected_model} for task {task} with complexity {complexity}")
    
    # Adjust timeout based on complexity
    timeout = int(base_timeout * (1 + complexity))
    
    # Generate trace ID
    trace_id = gen_trace_id()
    
    with trace(f"{agent.name} Execution", trace_id=trace_id):
        for attempt in range(max_retries):
            try:
                logger.info(f"Running {agent.name} (attempt {attempt+1}/{max_retries}, model={agent.model})")
                result = await Runner.run(agent, input=input_data, timeout=timeout)
                logger.info(f"Agent {agent.name} completed successfully")
                
                # Restore original model
                agent.model = original_model
                return result, trace_id
                
            except Exception as e:
                error_type = type(e).__name__
                logger.error(f"Agent {agent.name} failed with {error_type}: {str(e)}")
                
                if attempt == max_retries - 1:  # Last attempt
                    logger.error(f"All {max_retries} attempts failed for {agent.name}")
                    # Restore original model
                    agent.model = original_model
                    raise
                
                # Exponential backoff with jitter
                wait_time = min(30, (2 ** attempt) + random.uniform(0, 1))  # Cap at 30 seconds
                logger.info(f"Retrying in {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)

def run_agent_sync(
    agent: Agent,
    input_data: str | dict,
    complexity: float = 0.5,
    task: str = "general"
) -> BaseModel:
    """
    Synchronous version of agent execution for simpler integration contexts.
    
    Args:
        agent: The agent to run
        input_data: The input data (string or dict)
        complexity: Task complexity (0-1) to determine model
        task: Task type for model selection
        
    Returns:
        The agent's result
    """
    # Convert dict to JSON string if needed
    if isinstance(input_data, dict):
        input_data = json.dumps(input_data)
    
    # Select model based on task and complexity
    original_model = agent.model
    selected_model = select_model(task, complexity)
    agent.model = selected_model
    
    # Update tool choice based on complexity if needed
    update_tool_choice(agent, complexity)
    
    logger.info(f"Running {agent.name} synchronously with model {selected_model}")
    
    try:
        # Generate trace ID for logging
        trace_id = gen_trace_id()
        
        # Use trace for consistent tracing
        with trace(f"{agent.name} Sync", trace_id=trace_id):
            # Run the agent synchronously
            result = Runner.run_sync(agent, input=input_data)
            logger.info(f"Agent {agent.name} completed successfully (sync)")
            return result
    finally:
        # Restore original model
        agent.model = original_model

async def run_agent_with_streaming(
    agent: Agent,
    input_data: str | dict,
    progress_callback: callable,
    complexity: float = 0.5,
    task: str = "general"
) -> BaseModel:
    """
    Run an agent with streaming updates for real-time progress.
    
    Args:
        agent: The agent to run
        input_data: The input data (string or dict)
        progress_callback: Callback function for progress updates (delta, item_type, content)
        complexity: Task complexity (0-1) to determine model
        task: Task type for model selection
        
    Returns:
        The agent's result
    """
    # Convert dict to JSON string if needed
    if isinstance(input_data, dict):
        input_data = json.dumps(input_data)
    
    # Select model based on task and complexity
    original_model = agent.model
    selected_model = select_model(task, complexity)
    agent.model = selected_model
    
    # Update tool choice based on complexity
    update_tool_choice(agent, complexity)
    
    logger.info(f"Running streaming agent {agent.name} with model {selected_model}")
    
    # Generate trace ID for monitoring
    trace_id = gen_trace_id()
    
    with trace(f"{agent.name} Streaming", trace_id=trace_id):
        try:
            # Start streaming run with timeout based on complexity
            timeout = int(300 * (1 + complexity))  # Base timeout adjusted for complexity
            result = Runner.run_streamed(agent, input=input_data, timeout=timeout)
            
            # Process streaming events with proper error handling
            async for event in result.stream_events():
                try:
                    # Extract streaming information
                    if hasattr(event, 'delta') and event.delta:
                        # Send progress update
                        await progress_callback(
                            agent.name, 
                            getattr(event, 'item_type', 'unknown'),
                            event.delta
                        )
                    elif isinstance(event, Item):
                        # Process completed items
                        item_type = type(event).__name__
                        content = None
                        
                        if hasattr(event, 'content'):
                            if isinstance(event.content, list):
                                # Extract text from MessageContentItem
                                text_blocks = [
                                    item.text for item in event.content 
                                    if hasattr(item, 'text') and item.text
                                ]
                                content = "\n".join(text_blocks)
                            else:
                                content = str(event.content)
                        
                        # Send item completion
                        await progress_callback(agent.name, item_type, content)
                except Exception as stream_event_error:
                    # Log but continue processing other events
                    logger.error(f"Error processing stream event: {str(stream_event_error)}")
            
            logger.info(f"Agent {agent.name} streaming completed")
            
            # Restore original model
            agent.model = original_model
            return result.final_output
            
        except asyncio.TimeoutError:
            error_msg = f"Agent {agent.name} streaming timed out after {timeout} seconds"
            logger.error(error_msg)
            agent.model = original_model
            raise TimeoutError(error_msg)
        except Exception as e:
            error_type = type(e).__name__
            logger.error(f"Agent {agent.name} streaming failed with {error_type}: {str(e)}")
            # Restore original model
            agent.model = original_model
            raise

def update_tool_choice(agent: Agent, complexity: float):
    """
    Update tool choice based on complexity to ensure proper tool usage.
    
    Args:
        agent: The agent to update
        complexity: Task complexity score from 0-1
    """
    if complexity > 0.8:
        # Force tool use for very complex scenarios
        agent.model_kwargs = {"tool_choice": "required"}
    elif complexity > 0.6:
        # Specify that tools are available for moderately complex scenarios
        agent.model_kwargs = {"tool_choice": "auto"}
    else:
        # No special tool choice for simpler scenarios
        agent.model_kwargs = {}

def create_run_context(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a run context with standardized metadata for consistent agent operation.
    
    Args:
        request_data: The request data containing optional metadata
        
    Returns:
        A context dictionary with standardized fields
    """
    return {
        "request_id": gen_trace_id(),
        "timestamp": datetime.datetime.now().isoformat(),
        "source": request_data.get("source", "api"),
        "user_id": request_data.get("user_id", "anonymous"),
        "metadata": request_data.get("metadata", {})
    }

### 5.3 Blueprint Validation and Script Generation

```python
async def validate_and_clean_blueprint(blueprint: Blueprint) -> Tuple[Blueprint, List[str]]:
    """
    Validate a blueprint and clean it up if possible.
    
    Args:
        blueprint: The blueprint to validate
        
    Returns:
        Tuple of (cleaned_blueprint, warnings)
    """
    warnings = []
    
    # Run pydantic validation
    try:
        # Re-instantiate to trigger validators
        blueprint = Blueprint(**blueprint.model_dump())
    except Exception as e:
        warnings.append(f"Blueprint validation error: {str(e)}")
        # Try to recover by fixing the most common issues
        try:
            blueprint_dict = blueprint.model_dump()
            
            # Fix missing fields
            if 'suite' not in blueprint_dict or not blueprint_dict['suite']:
                blueprint_dict['suite'] = {'tests': []}
            
            if 'tests' not in blueprint_dict['suite'] or not blueprint_dict['suite']['tests']:
                blueprint_dict['suite']['tests'] = [{
                    'name': 'Default Test',
                    'endpoint': '/',
                    'method': 'GET',
                    'expectedStatus': 200
                }]
                warnings.append("Added a default test because no tests were found")
            
            # Try to re-instantiate with fixes
            blueprint = Blueprint(**blueprint_dict)
        except Exception as nested_e:
            warnings.append(f"Could not recover from validation errors: {str(nested_e)}")
            raise
    
    # Run dependency validation with improved cycle detection
    dependency_warnings = validate_dependencies(blueprint)
    warnings.extend(dependency_warnings)
    
    # Check for security issues
    security_warnings = check_blueprint_security(blueprint)
    warnings.extend(security_warnings)
    
    # Add warnings to the blueprint
    if warnings:
        if blueprint.warnings:
            blueprint.warnings.extend(warnings)
        else:
            blueprint.warnings = warnings
    
    return blueprint, warnings

def validate_dependencies(blueprint: Blueprint) -> List[str]:
    """
    Enhanced validation for test dependencies with improved cycle detection.
    
    Args:
        blueprint: Blueprint to validate
        
    Returns:
        List of warnings
    """
    warnings = []
    
    # Get all test names
    test_names = {test.name for test in blueprint.suite.tests}
    
    # Check for missing dependencies
    for test in blueprint.suite.tests:
        if test.dependencies:
            for dep in test.dependencies:
                if dep not in test_names:
                    warnings.append(f"Test '{test.name}' depends on non-existent test '{dep}'")
    
    # Build dependency graph
    dependency_graph = {}
    for test in blueprint.suite.tests:
        dependency_graph[test.name] = test.dependencies or []
    
    # Improved cycle detection with path tracking
    def detect_cycle(node, path=None):
        if path is None:
            path = []
        
        # Check if the current node is already in the path
        if node in path:
            # Cycle detected - return the cycle path for better reporting
            cycle_start = path.index(node)
            return path[cycle_start:] + [node]
        
        # Add current node to path and check all neighbors
        path = path + [node]
        for neighbor in dependency_graph.get(node, []):
            cycle = detect_cycle(neighbor, path)
            if cycle:
                return cycle
        
        return None
    
    # Check for cycles starting from each node
    for test_name in dependency_graph:
        cycle = detect_cycle(test_name)
        if cycle:
            cycle_str = " -> ".join(cycle)
            warnings.append(f"Circular dependency detected: {cycle_str}")
            break
    
    # Check for dependency chains that are too long (potential performance issue)
    max_chain_length = 10  # Reasonable limit
    
    def get_chain_length(node, visited=None):
        if visited is None:
            visited = set()
        
        if node in visited:
            return 0  # Already counted
        
        visited.add(node)
        
        if not dependency_graph.get(node, []):
            return 1  # Leaf node
        
        return 1 + max(get_chain_length(dep, visited.copy()) for dep in dependency_graph.get(node, []))
    
    for test_name in dependency_graph:
        chain_length = get_chain_length(test_name)
        if chain_length > max_chain_length:
            warnings.append(f"Test '{test_name}' has a dependency chain of length {chain_length}, " 
                            f"which exceeds the recommended maximum of {max_chain_length}")
    
    return warnings

def check_blueprint_security(blueprint: Blueprint) -> List[str]:
    """
    Check blueprint for potential security issues.
    
    This function analyzes the blueprint to identify potential security risks:
    1. Sensitive endpoints that might expose protected resources
    2. Security-sensitive payload data (credentials, tokens, etc.)
    3. Potential injection risks in test assertions
    
    Implementation Notes:
    - Uses pattern matching against a known set of security-sensitive keywords
    - Examines test endpoints, payloads, and assertions for security issues
    - Provides specific warnings with context (test name, location) for easier remediation
    
    Args:
        blueprint: Blueprint to check for security issues
        
    Returns:
        List of security warning messages, each describing a specific issue and its location
    """
    warnings = []
    
    # Check for potentially harmful endpoints or payloads
    sensitive_patterns = [
        'token', 'password', 'secret', 'key', 'auth', 'cred', 
        'admin', 'root', 'sudo', 'shell', 'exec', 'eval'
    ]
    
    # Check sensitive endpoints
    for test in blueprint.suite.tests:
        for pattern in sensitive_patterns:
            if pattern in test.endpoint.lower():
                warnings.append(f"Test '{test.name}' uses potentially sensitive endpoint '{test.endpoint}'")
    
    # Check for setup steps that might expose sensitive data
    if blueprint.suite.setup:
        for i, step in enumerate(blueprint.suite.setup):
            # Check payload for sensitive fields
            if step.payload:
                for key in step.payload:
                    for pattern in sensitive_patterns:
                        if pattern in key.lower():
                            warnings.append(f"Setup step #{i+1} contains potentially sensitive data in field '{key}'")
    
    # Check for potential injection risks in test assertions
    for test in blueprint.suite.tests:
        if test.assertions:
            for i, assertion in enumerate(test.assertions):
                if "'" in assertion or '"' in assertion:
                    warnings.append(f"Test '{test.name}' assertion #{i+1} contains quotes, "
                                    f"which might indicate string injection risks")
    
    return warnings

async def process_openapi_spec(
    spec_text: str, 
    mode: str,
    business_rules: Optional[str] = None,
    test_data: Optional[str] = None,
    test_flow: Optional[str] = None,
    progress_callback: callable = None
) -> Tuple[Blueprint, str]:
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
        spec_size = len(json.dumps(parsed_spec))
        path_count = len(parsed_spec.get("paths", {}))
        endpoint_count = sum(len(methods) for methods in parsed_spec.get("paths", {}).values())
        
        # Calculate a complexity score (0-1)
        max_size = 1_000_000  # 1MB max size
        max_endpoints = 500   # reasonable upper limit
        
        complexity = min(1.0, (
            (spec_size / max_size) * 0.4 +
            (endpoint_count / max_endpoints) * 0.6 +
            (0.2 if mode == "advanced" else 0)
        ))
        
        # Construct message for the test planner
        message = construct_planner_message(
            json.dumps(parsed_spec) if spec_size < 100000 else spec_text,
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
                blueprint = await run_agent_with_streaming(
                    test_planner_agent,
                    message,
                    report_progress,
                    complexity=complexity,
                    task="planning"
                )
                trace_id = gen_trace_id()  # Generate a new trace ID for logging
            except Exception as e:
                logger.error(f"Streaming execution failed: {str(e)}, falling back to non-streaming mode")
                # Fall back to non-streaming mode
                result, trace_id = await run_agent_with_retry(
                    test_planner_agent,
                    message,
                    complexity=complexity,
                    task="planning"
                )
                blueprint = result.final_output_as(Blueprint)
        else:
            # Run without streaming
            result, trace_id = await run_agent_with_retry(
                test_planner_agent,
                message,
                complexity=complexity,
                task="planning"
            )
            blueprint = result.final_output_as(Blueprint)
        
        # Validate and clean up the blueprint
        blueprint, validation_warnings = await validate_and_clean_blueprint(blueprint)
        
        # Log trace ID for debugging
        logger.info(f"Blueprint generation completed with trace_id: {trace_id}")
        if validation_warnings:
            logger.info(f"Blueprint validation produced {len(validation_warnings)} warnings")
        
        return blueprint, trace_id
        
    except SpecValidationError as e:
        logger.error(f"Spec validation error: {e.message}")
        raise
    except Exception as e:
        error_message = f"Blueprint generation error: {str(e)}"
        logger.error(error_message)
        raise BlueprintGenerationError(error_message, trace_id=gen_trace_id())

### 5.4 Custom Model Provider Support
```

---

## 6. Error Handling and Validation

```python
class APITestGenerationError(Exception):
    """Base class for API test generation errors."""
    def __init__(self, message, details=None, trace_id=None):
        self.message = message
        self.details = details or {}
        self.trace_id = trace_id
        super().__init__(self.message)

class SpecValidationError(APITestGenerationError):
    """Error validating OpenAPI spec."""
    pass

class BlueprintGenerationError(APITestGenerationError):
    """Error generating blueprint from spec."""
    pass

class BlueprintValidationError(APITestGenerationError):
    """Error validating blueprint."""
    pass

class ScriptGenerationError(APITestGenerationError):
    """Error generating test scripts."""
    pass

class ModelUnavailableError(APITestGenerationError):
    """Error when required model is unavailable."""
    pass

async def validate_openapi_spec(spec_text: str) -> Tuple[dict, List[str]]:
    """
    Validate an OpenAPI spec and return parsed object and warnings.
    
    Args:
        spec_text: Raw OpenAPI spec text (YAML or JSON)
        
    Returns:
        Tuple of (parsed_spec, warnings)
    """
    warnings = []
    parsed_spec = None
    
    # Check for empty input
    if not spec_text or not spec_text.strip():
        raise SpecValidationError("Empty specification provided", {"spec": "empty"})
    
    # Check for excessive size to prevent DOS
    if len(spec_text) > 2_000_000:  # 2MB limit
        raise SpecValidationError(
            "Specification too large", 
            {"size": len(spec_text), "max_size": 2_000_000}
        )
    
    # Try parsing as JSON first
    try:
        parsed_spec = json.loads(spec_text)
    except json.JSONDecodeError:
        warnings.append("JSON parsing failed, trying YAML")
        try:
            import yaml
            parsed_spec = yaml.safe_load(spec_text)
        except Exception as e:
            error_message = f"YAML parsing failed: {str(e)}"
            warnings.append(error_message)
            raise SpecValidationError(error_message, {"spec": spec_text[:100] + "..."})
    
    # Basic spec validation
    if not parsed_spec:
        raise SpecValidationError("Empty or invalid spec", {"spec": spec_text[:100] + "..."})
    
    if not isinstance(parsed_spec, dict):
        raise SpecValidationError("Specification must be a JSON/YAML object", {"type": type(parsed_spec).__name__})
    
    # Check for required OpenAPI fields with more detailed warnings
    if "openapi" not in parsed_spec:
        warnings.append("Missing 'openapi' version field. This field should specify the OpenAPI version (e.g., '3.0.0').")
    else:
        # Validate version format
        version = str(parsed_spec["openapi"])
        if not re.match(r'^\d+\.\d+\.\d+$', version):
            warnings.append(f"Invalid 'openapi' version format: {version}. Expected format: X.Y.Z")
    
    if "info" not in parsed_spec:
        warnings.append("Missing 'info' section. This should contain API metadata like title and version.")
    else:
        if "title" not in parsed_spec["info"]:
            warnings.append("Missing 'title' in info section")
        if "version" not in parsed_spec["info"]:
            warnings.append("Missing 'version' in info section")
    
    if "paths" not in parsed_spec:
        warnings.append("Critical error: Missing 'paths' section. This section defines the API endpoints.")
        # Create an empty paths object to allow processing to continue
        parsed_spec["paths"] = {}
    elif not parsed_spec["paths"]:
        warnings.append("Warning: 'paths' section is empty. No endpoints are defined.")
    
    # Validate path formats
    for path in parsed_spec.get("paths", {}):
        if not path.startswith('/'):
            warnings.append(f"Path '{path}' does not start with '/'")
        
        # Check for path parameters
        path_params = re.findall(r'\{([^}]+)\}', path)
        for param in path_params:
            # Check if path parameters are defined
            param_defined = False
            for method, operation in parsed_spec["paths"][path].items():
                if method not in ["get", "put", "post", "delete", "options", "head", "patch"]:
                    continue
                
                for op_param in operation.get("parameters", []):
                    if op_param.get("name") == param and op_param.get("in") == "path":
                        param_defined = True
                        break
            
            if not param_defined:
                warnings.append(f"Path parameter '{param}' in '{path}' is not defined in any operation")
    
    return parsed_spec, warnings
```

---

## 7. Security and Performance

- **Security:**  
  - Sanitize inputs: Escape special characters in pasted text, validate file uploads.  
  - Restrict file types to `.yaml`, `.yml`, `.json` (max 1MB).  
  - Use HTTPS for all API communications.
  - Implement proper error handling to prevent leaking sensitive information.
  - Validate all inputs against detailed schemas with proper validators.
  - Sanitize blueprint and script outputs to remove any potential harmful content.
  - Automatically detect and flag sensitive endpoints, credentials, or data patterns in both input and output.
  - Implement rate limiting and request size limitations to prevent DOS attacks.
- **Performance:**  
  - Optimize parsing for large specs (up to 1MB) with streaming support for progress updates.
  - Set agent timeouts dynamically based on task complexity.
  - Implement intelligent retry logic with exponential backoff for increased reliability.
  - Select the optimal model automatically based on task complexity:
    - Use lightweight models (e.g., gpt-3.5-turbo) for simple tasks
    - Use mid-range models (e.g., gpt-4o-mini) for moderate complexity
    - Reserve high-end models (e.g., gpt-4o) for the most complex tasks
  - Implement asynchronous processing for parallel test generation when multiple targets are selected.
  - Support synchronous operation mode for simpler integration contexts.
  - Enable custom model provider configuration for cost-optimization and vendor flexibility.
  - Implement worker pool management for high-volume processing.

---

## 8. Implementation Notes

- **Agent Prompts:**  
  - `TriageAgent`: Clear instructions for handoff based on input type.
  - `TestPlanner`: Guides the LLM to generate a blueprint matching the `Blueprint` schema.
  - `CoderAgent`: Selects the appropriate sub-agent based on the target.
  - All prompts should focus on the specific task and avoid unnecessary instructions that might confuse the model.
- **Tracing:**  
  - Enable tracing for all agents to log key steps and provide trace IDs for debugging.
  - Use custom spans to track specific stages of the pipeline:
    ```python
    with custom_span("Blueprint Generation"):
        blueprint, trace_id = await process_openapi_spec(spec_text, mode)
    ```
  - Add structured logging for important events and errors.
- **Frontend Integration:**  
  - Use Monaco Editor with `blueprint_schema` for validation.
  - Implement WebSockets for real-time progress updates during test generation.
  - Add a progress indicator that shows the current stage and file being generated:
    ```javascript
    const socket = new WebSocket('ws://localhost:8000/ws/job/' + jobId);
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'progress') {
        updateProgressBar(data.stage, data.percent);
        if (data.currentFile) {
          updateCurrentFileIndicator(data.currentFile);
        }
      }
    };
    ```
- **Error Recovery:**
  - Implement robust error handling at each stage of the pipeline.
  - For non-critical errors, continue processing with appropriate warnings.
  - For critical errors, provide detailed error messages and suggestions for resolution.
  - Use a combination of try/except blocks and validators to catch issues early.

---

## 9. Modular Code Organization

To improve maintainability, testability, and scalability, the codebase should be organized into the following modular structure:

### 9.1 Module Organization

```
src/
├── api/                       # API endpoints
│   ├── __init__.py
│   ├── generate.py            # Generation endpoints
│   └── export.py              # Export endpoints
├── agents/                    # Agent definitions and execution
│   ├── __init__.py
│   ├── triage.py              # Triage agent
│   ├── planner.py             # Test planner agent  
│   └── coder.py               # Coder agent with sub-agents
├── blueprint/                 # Blueprint handling
│   ├── __init__.py
│   ├── models.py              # Pydantic models for Blueprint
│   ├── validation.py          # Blueprint validation logic
│   └── security.py            # Security validation for blueprints
├── models/                    # Other data models
│   ├── __init__.py
│   └── script_output.py       # Script output models
├── utils/                     # Utilities
│   ├── __init__.py
│   ├── model_selection.py     # Model selection logic
│   ├── execution.py           # Agent execution helpers
│   ├── streaming.py           # Streaming support
│   └── tracing.py             # Tracing utilities
├── config/                    # Configuration
│   ├── __init__.py
│   └── settings.py            # App settings
└── errors/                    # Error definitions
    ├── __init__.py
    └── exceptions.py          # Custom exceptions
```

### 9.2 Module Responsibilities

1. **Blueprint Module**
   - Contains all blueprint-related logic including models, validation, and security checks
   - Validation logic is separated into dedicated functions for each validation type:
     ```python
     # validation.py
     
     def validate_dependencies(blueprint: Blueprint) -> List[str]:
         """
         Validate test dependencies and check for cycle errors.
         
         This function identifies:
         1. Missing dependencies (tests referring to non-existent tests)
         2. Circular dependencies (cyclic test dependencies)
         3. Excessively long dependency chains (performance issues)
         
         Args:
             blueprint: Blueprint object to validate
             
         Returns:
             List of warning messages describing any dependency issues found
         """
         # Implementation
     
     def validate_test_naming(blueprint: Blueprint) -> List[str]:
         """
         Validate test naming conventions and uniqueness.
         
         Args:
             blueprint: Blueprint object to validate
             
         Returns:
             List of warning messages about naming issues
         """
         # Implementation
     
     def validate_blueprint(blueprint: Blueprint) -> Tuple[Blueprint, List[str]]:
         """
         Comprehensive validation of a blueprint, applying all validators.
         
         This is the main entry point for blueprint validation, which:
         1. Re-instantiates the blueprint to trigger Pydantic validators
         2. Applies all specialized validators (dependencies, security, etc.)
         3. Attempts to recover from certain validation errors
         4. Collects and consolidates all warnings
         
         Args:
             blueprint: Blueprint to validate
             
         Returns:
             Tuple of (validated_blueprint, warnings)
         """
         # Implementation calling specialized validators
     ```

2. **Execution Module**
   - Contains clearly separated functions for different execution modes:
     ```python
     # execution.py
     
     async def run_with_retry(
         agent: Agent, 
         input_data: str | dict,
         config: RetryConfig
     ) -> Tuple[BaseModel, str]:
         """
         Run an agent with intelligent retry logic.
         
         This function:
         1. Configures the agent with appropriate model and settings
         2. Executes the agent with retry logic for resilience
         3. Implements exponential backoff with jitter for stability
         4. Provides detailed logs for debugging failed attempts
         
         Args:
             agent: Agent to execute
             input_data: Input for the agent
             config: Retry configuration including max_retries, timeout settings
             
         Returns:
             Tuple of (result, trace_id)
         """
         # Implementation
     
     def run_sync(
         agent: Agent,
         input_data: str | dict,
         config: RunConfig
     ) -> BaseModel:
         """
         Run an agent synchronously for simpler integrations.
         
         This is a simplified synchronous wrapper around the asynchronous agent
         execution, designed for contexts where async/await isn't available.
         
         Args:
             agent: Agent to execute
             input_data: Input for the agent
             config: Configuration including timeout and model settings
             
         Returns:
             The agent's result
         """
         # Implementation
     ```

3. **Model Selection**
   - Dedicated module for model selection logic:
     ```python
     # model_selection.py
     
     class ModelSelectionStrategy:
         """
         Strategy for selecting the optimal model based on task and complexity.
         
         This class encapsulates the logic for selecting the most appropriate
         model for a given task, considering factors like:
         - Task type (planning, coding, triage)
         - Task complexity (0-1 scale)
         - Environment configuration
         - Fallback options
         
         The strategy can be configured via environment variables or directly.
         """
         
         def __init__(self, 
                     default_model: str = "gpt-4o-mini",
                     env_prefix: str = "MODEL_"):
             """Initialize with defaults and load env configuration."""
             # Implementation
         
         def select_model(self, task: str, complexity: float) -> str:
             """
             Select the appropriate model based on task type and complexity.
             
             Args:
                 task: Type of task (planning, coding, triage)
                 complexity: Complexity score (0-1)
                 
             Returns:
                 Model name to use
             """
             # Implementation with detailed logging
     ```

### 9.3 Documentation Improvements

Every module, class, and function should have detailed documentation following this template:

```python
def function_name(param1: Type1, param2: Type2) -> ReturnType:
    """
    Short description of the function's purpose.
    
    Detailed description explaining:
    - What the function does in more detail
    - Key algorithms or approaches used
    - Side effects or state changes
    - Error handling behavior
    
    Args:
        param1: Description of first parameter
        param2: Description of second parameter
    
    Returns:
        Description of return value
        
    Raises:
        ErrorType1: When this error occurs
        ErrorType2: When that error occurs
        
    Example:
        ```python
        result = function_name("example", 42)
        # result now contains...
        ```
    """
    # Implementation
```

Each module should also include module-level documentation:

```python
"""
Module Name - Brief description

This module handles [primary responsibility].

Key components:
- ComponentA: Handles X functionality
- ComponentB: Manages Y process

Usage:
    import module_name
    
    result = module_name.function(...)
"""
```

For complex classes and functions, include implementation notes or design rationale:

```python
def complex_function():
    """
    Function documentation...
    
    Implementation Notes:
        - Uses algorithm X for better performance with large datasets
        - Maintains O(log n) complexity by using binary search
        - Avoids recursive approach due to stack overflow concerns
    """
    # Implementation
```

### 9.4 Testing Strategy

To ensure reliability, each module should be tested independently:

1. **Unit Tests**
   - Blueprint validation
   - Model selection logic
   - Individual agent functions

2. **Integration Tests**
   - Agent handoffs
   - End-to-end generation flow

3. **Mock Tests**
   - Agent execution with mocked OpenAI API responses

Testing modules should mirror the source code structure:

```
tests/
├── unit/
│   ├── blueprint/
│   │   ├── test_validation.py
│   │   └── test_security.py
│   ├── models/
│   │   └── test_script_output.py
│   └── utils/
│       ├── test_model_selection.py
│       └── test_execution.py
├── integration/
│   ├── test_agent_handoffs.py
│   └── test_generation_flow.py
└── mock/
    └── test_agent_execution.py
```

---

This enhanced plan integrates **Agent Handoffs** (via the Triage Agent), **Structured Outputs** (using Pydantic models with validators), **Tracing** (for debugging and monitoring), **Streaming Support** (for real-time updates), **Model Optimization** (for cost efficiency), and **Enhanced Error Handling** (for reliability) to create a scalable, robust, and efficient API Test Automation Tool.