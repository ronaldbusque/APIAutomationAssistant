
## **Implementation Plan: Autonomous Agent Workflow (Revised & Detailed)**

**(Based on Feedback - Restored Detail)**

**Goal:** Introduce an optional "Autonomous Mode" using iterative Author-Reviewer agent loops for robust blueprint and script generation.

**Core Changes:**
*   Implement Author-Reviewer loops for blueprint and script generation.
*   Agents communicate primarily via JSON *strings*.
*   Pipeline code handles parsing, control flow (keywords), and context.
*   Integrate into existing background task infrastructure.
*   Modify `run_agent_with_retry` to pass context and return `RunResult`.

---

**Phase 0: Setup & Configuration**

1.  **Create New Directories and Files:** (As planned)
    *   `src/agents/autonomous/`
    *   `__init__.py`, `agents.py`, `pipeline.py`, `context.py`.

2.  **Update Configuration (`src/config/settings.py`):** (As planned)
    *   Add `MODEL_BP_AUTHOR`, `MODEL_BP_REVIEWER`, `MODEL_SCRIPT_CODER`, `MODEL_SCRIPT_REVIEWER`, `AUTONOMOUS_MAX_ITERATIONS` to `BASE_CONFIG`.
    *   Add `"AUTONOMOUS_MAX_ITERATIONS"` to `numeric_settings`.

3.  **Update `.env.example`:** (As planned)
    *   Add new optional model overrides and `AUTONOMOUS_MAX_ITERATIONS=3`.

4.  **Update Model Selection (`src/utils/model_selection.py`):** (As planned)
    *   Modify `ModelSelectionStrategy.__init__` to load new models with fallbacks.
    *   Modify `ModelSelectionStrategy.select_model` to handle new task names (`blueprint_authoring`, etc.).

5.  **Modify `run_agent_with_retry` (`src/utils/execution.py`) (CRITICAL):**
    *   **Update Signature & Return Type:**
        ```python
        # src/utils/execution.py
        from agents import RunResult # Make sure RunResult is imported if not already
        from typing import Tuple, Union, Any # Add Any for context

        async def run_agent_with_retry(
            agent: Agent,
            input_data: Union[str, dict],
            config: RetryConfig = None,
            run_config: RunConfig = None,
            context: Any = None, # ADDED: Allow passing context
            model_selection: ModelSelectionStrategy = None
        ) -> Tuple[RunResult, str]: # MODIFIED: Return RunResult, not BaseModel
            # ... (Keep existing setup logic using run_config) ...

            # Ensure model selection happens based on run_config.task and run_config.complexity
            if run_config:
                 selected_model = model_selection.select_model(run_config.task, run_config.complexity)
                 agent.model = selected_model # Update agent's model for this run
                 agent_config = {"model_kwargs": getattr(agent, "model_kwargs", {})} # Get current kwargs
                 agent_config = model_selection.update_tool_choice(agent_config, run_config.complexity) # Update tool choice based on complexity
                 agent.model_kwargs = agent_config["model_kwargs"] # Apply updated kwargs
                 timeout = model_selection.calculate_timeout(config.base_timeout if config else 300, run_config.complexity) # Calculate timeout
                 logger.info(f"Running {agent.name} with model {selected_model}, timeout {timeout}s, complexity {run_config.complexity:.2f}")


            trace_id = gen_trace_id()
            with trace(f"{agent.name} Execution", trace_id=trace_id):
                for attempt in range(config.max_retries if config else 3):
                    try:
                        # ... (Logging for attempt) ...

                        # MODIFIED: Pass context to Runner.run
                        result: RunResult = await Runner.run(agent, input=input_data, context=context)
                        logger.info(f"Agent {agent.name} completed successfully")

                        # Restore original model configuration AFTER use (if modified temporarily)
                        # Note: Model selection logic already handles this if done correctly per-run
                        # agent.model = original_model
                        # agent.model_kwargs = original_model_kwargs

                        # MODIFIED: Return the full RunResult object
                        return result, trace_id

                    except Exception as e:
                        # ... (Existing error handling and retry logic) ...
                        if attempt == (config.max_retries if config else 3) - 1:
                            # Restore model config before raising
                            # agent.model = original_model
                            # agent.model_kwargs = original_model_kwargs
                            raise
                        # ... (Wait logic) ...
        ```
    *   **Review Call Sites:** Ensure all existing calls to `run_agent_with_retry` are updated to handle the `(RunResult, str)` tuple return and access `.final_output` if needed, e.g., `result_tuple[0].final_output`.

---

**Phase 1: Blueprint Generation Loop**

1.  **Implement Planner Context (`src/agents/autonomous/context.py`):** (As planned)
    ```python
    from typing import Dict, Any, Optional
    from pydantic import BaseModel

    class PlannerContext(BaseModel):
        """Context object holding data for the blueprint generation phase."""
        spec_analysis: Dict[str, Any] | None = None
    ```

2.  **Implement Spec Analysis Helper (`src/agents/autonomous/pipeline.py`):** (As planned, now `async`)
    ```python
    # src/agents/autonomous/pipeline.py
    import asyncio
    import json
    import yaml
    import logging
    from typing import Dict, Any, Tuple, List, Callable, Coroutine # Added Callable, Coroutine
    from src.utils.spec_validation import validate_openapi_spec
    from src.errors.exceptions import SpecValidationError, BlueprintGenerationError, ScriptGenerationError # Import errors
    from src.agents.autonomous.context import PlannerContext # Import context
    from src.agents.autonomous.agents import ( # Import agent setups
        setup_blueprint_author_agent, setup_blueprint_reviewer_agent,
        setup_script_coder_agent, setup_script_reviewer_agent
    )
    from src.utils.execution import run_agent_with_retry, RunConfig, RetryConfig # Import execution utils
    from src.config.settings import settings
    from agents import RunResult # Import RunResult

    logger = logging.getLogger(__name__)

    # Keyword constants
    BLUEPRINT_APPROVED_KEYWORD = "[[BLUEPRINT_APPROVED]]"
    REVISION_NEEDED_KEYWORD = "[[REVISION_NEEDED]]"
    CODE_APPROVED_KEYWORD = "[[CODE_APPROVED]]" # Add for phase 2

    async def analyze_initial_spec(spec_text: str) -> Tuple[Dict[str, Any], List[str]]:
        """Parses spec, returns analysis dict {endpoints, schemas, raw_spec_for_context} and warnings."""
        logger.info("Analyzing initial OpenAPI spec...")
        try:
            parsed_spec, warnings = await validate_openapi_spec(spec_text) # Await async validator
            analysis_result = {
                "endpoints": list(parsed_spec.get("paths", {}).keys()),
                "schemas": list(parsed_spec.get("components", {}).get("schemas", {}).keys()),
                "raw_spec_for_context": parsed_spec # Crucial for reviewer
            }
            logger.info(f"Spec analysis complete. Found {len(analysis_result['endpoints'])} endpoints, {len(analysis_result['schemas'])} schemas.")
            return analysis_result, warnings
        except SpecValidationError as e:
            logger.error(f"Initial spec validation failed: {e.message}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during spec analysis: {str(e)}")
            raise SpecValidationError(f"Failed to analyze spec: {str(e)}") from e

    # ... (pipeline functions below) ...
    ```

3.  **Implement Blueprint Agents Setup (`src/agents/autonomous/agents.py`):**
    *   Implement `setup_blueprint_author_agent` and `setup_blueprint_reviewer_agent` as planned.
    *   **Include Full Prompts:**
        ```python
        # src/agents/autonomous/agents.py
        import logging
        from agents import Agent
        from src.config.settings import settings
        from src.utils.model_selection import ModelSelectionStrategy

        logger = logging.getLogger(__name__)
        model_strategy = ModelSelectionStrategy()

        def setup_blueprint_author_agent() -> Agent:
            model_name = model_strategy.select_model("blueprint_authoring", complexity=0.6) # Example complexity
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
- Follow the feedback immediately with a single newline character (`\n`).
- The very last line MUST contain ONLY the keyword `[[BLUEPRINT_APPROVED]]` or `[[REVISION_NEEDED]]`.
- Do NOT add any text after the keyword.
""",
                output_type=str,
                tools=[],
            )

        # ... (Placeholders for script agents - keep as is for Phase 1) ...
        def setup_script_coder_agent(framework: str) -> Agent:
            logger.warning(f"Script Coder Agent setup called for {framework} - Placeholder.")
            return Agent(name=f"ScriptCoderAgent_{framework}", instructions="Placeholder Coder", output_type=str)
        def setup_script_reviewer_agent(framework: str) -> Agent:
            logger.warning(f"Script Reviewer Agent setup called for {framework} - Placeholder.")
            return Agent(name=f"ScriptReviewerAgent_{framework}", instructions="Placeholder Reviewer", output_type=str)
        ```

4.  **Implement Blueprint Pipeline (`src/agents/autonomous/pipeline.py`):**
    *   Implement `run_autonomous_blueprint_pipeline` as planned.
    *   **Use Correct Return Handling:** Ensure calls to `run_agent_with_retry` correctly unpack the `(RunResult, str)` tuple and use `result_tuple[0].final_output` to get the raw string.
    *   **Pass Context:** Add the `context=planner_context` argument to the `run_agent_with_retry` call, especially for the reviewer agent.
    *   **Implement Robust Parsing:** Include the planned robust parsing for the reviewer's output (checking last line for keywords).
    *   **Add TODOs for Complexity:** Add `# TODO: Calculate or estimate blueprint complexity` before calls to `run_agent_with_retry` for Author and Reviewer. For now, you can pass a default `complexity` in `RunConfig` (e.g., `RunConfig(complexity=0.6, task="blueprint_authoring")`).

5.  **Integrate into API Background Task (`src/api/generate.py`):**
    *   Add `POST /generate-autonomous` endpoint and `run_autonomous_pipeline_background` task function as planned.
    *   Ensure `analyze_initial_spec` is awaited correctly.
    *   Implement the basic progress callback mapping.
    *   Include detailed error logging in `except` blocks (`logger.exception(...)`).

6.  **Testing (Phase 1):** (As planned)
    *   Focus on unit tests for the pipeline logic (mocking agents and their string outputs).
    *   Perform manual end-to-end tests via the API.
    *   Iteratively refine prompts based on agent outputs in logs.

---

**Phase 2: Script Generation Loop**

1.  **Implement Script Agents Setup (`src/agents/autonomous/agents.py`):**
    *   Replace placeholders for `setup_script_coder_agent` and `setup_script_reviewer_agent`.
    *   **Include Full Prompts:** Write detailed instructions similar to the blueprint agents, emphasizing:
        *   **Coder:** Takes framework, blueprint JSON, feedback, previous code JSON list string. Outputs ONLY JSON string list `[{"filename": ..., "content": ...}]`. Mention framework best practices.
        *   **Reviewer:** Takes framework, blueprint JSON, code files JSON list string. Compares code to blueprint and framework standards. Outputs feedback + `[[CODE_APPROVED]]` or `[[REVISION_NEEDED]]` on a new line.

2.  **Implement Script Pipeline (`src/agents/autonomous/pipeline.py`):**
    *   Replace the placeholder `run_autonomous_script_pipeline`.
    *   **Pass Context (If Needed):** While the script reviewer primarily compares code to the blueprint (provided as input), you *could* pass the `PlannerContext` containing the original `spec_analysis` if the reviewer needs deeper spec context. Decide based on prompt effectiveness during testing.
    *   **Use Correct Return Handling:** Unpack `(RunResult, str)`.
    *   **Implement Robust Parsing:** Parse coder output as a JSON list, validate item structure. Parse reviewer output for keywords.
    *   **Add TODOs for Complexity:** Add complexity calculation/defaults for Coder and Reviewer agent runs.

3.  **Update Background Task (`src/api/generate.py`):**
    *   Replace placeholder script generation call with `await run_autonomous_script_pipeline(...)`.
    *   Implement the script assembly logic robustly as planned.

4.  **Testing (Phase 2):** (As planned)
    *   Unit test the script pipeline logic.
    *   Manually test end-to-end via API, focusing on one framework first.
    *   Iteratively refine script agent prompts.

---

**Phase 3: Integration & Cleanup**

1.  **End-to-End Testing:** (As planned)
2.  **API Tests (`test_api.py`):** Add `test_autonomous_generation`.
3.  **Code Review & Cleanup:** (As planned)
4.  **Documentation:** (As planned)

---

## **UI Update Plan: Autonomous Mode Toggle**

1.  **State Management (`src/context/AppContext.tsx`):**
    *   Add a new boolean state variable to `AppState`:
        ```typescript
        export interface AppState {
          // ... existing state ...
          isAutonomousMode: boolean; // Add this
        }
        ```
    *   Update `initialState`:
        ```typescript
        const initialState: AppState = {
          // ... existing initial state ...
          isAutonomousMode: false, // Default to false
        };
        ```
    *   Add a setter function to `AppContextType`:
        ```typescript
        interface AppContextType {
          // ... existing setters ...
          setIsAutonomousMode: (enabled: boolean) => void; // Add this
        }
        ```
    *   Implement the setter function in `AppProvider`:
        ```typescript
        export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
          // ... existing state and setters ...
          const setIsAutonomousMode = (enabled: boolean) => {
            setState(prev => ({ ...prev, isAutonomousMode: enabled }));
          };

          const value = {
            // ... existing value ...
            setIsAutonomousMode, // Add this
          };
          // ... rest of provider ...
        };
        ```

2.  **Add Toggle Component (`src/components/ModeSelection.tsx`):**
    *   Import `useAppContext` and `Switch` from Headless UI.
    *   Get `state.isAutonomousMode` and `setIsAutonomousMode` from context.
    *   Add the toggle switch UI element, placed logically near the action buttons or mode selection area. Example using Headless UI `Switch`:
        ```typescript
        import { Switch } from '@headlessui/react';
        // ... other imports ...

        const ModeSelection: React.FC<Props> = ({ onBack, onNext }) => {
          const {
            state,
            setMode,
            // ... other setters ...
            setIsAutonomousMode, // Get the setter
            setBlueprintJobId // Needed to store the single autonomous job ID
          } = useAppContext();

          // ... existing state (isGenerating, error) ...

          // Rename mutation hook if needed, or reuse useGenerateBlueprint but call different endpoint
          const generateAutonomousMutation = useGenerateBlueprint(); // Reuse or create specific hook

          const handleGenerate = async () => {
             setIsGenerating(true);
             setError(null);

             try {
                 if (state.isAutonomousMode) {
                     // *** AUTONOMOUS MODE TRIGGER ***
                     console.log("Starting Autonomous Generation...");
                     const autonomousRequest = {
                         spec: state.openApiSpec, // Assuming openApiSpec holds the raw spec
                         targets: state.targets,
                         // max_iterations is handled by backend default or can be added here
                     };

                     // Make POST request to the new /generate-autonomous endpoint
                     // IMPORTANT: Adapt useApi hook or use fetch directly if hook isn't generic
                     const response = await fetch(`${API_BASE_URL}/generate-autonomous`, { // Use new endpoint
                         method: 'POST',
                         headers: { 'Content-Type': 'application/json' },
                         body: JSON.stringify(autonomousRequest),
                     });
                     if (!response.ok) throw new Error(`Autonomous job submission failed: ${response.statusText}`);
                     const result = await response.json();

                     setBlueprintJobId(result.job_id); // Store the SINGLE job ID
                     // **SKIP BlueprintView, go directly to ScriptOutput to monitor the single job**
                     setCurrentStep('scripts'); // Assuming setCurrentStep is available via context

                 } else {
                     // *** STANDARD MODE TRIGGER (Existing Logic) ***
                     console.log("Starting Standard Blueprint Generation...");
                     const blueprintRequest = {
                         spec: state.openApiSpec,
                         mode: state.mode as 'basic' | 'advanced',
                         // ... include advanced inputs if state.mode === 'advanced' ...
                         business_rules: state.mode === 'advanced' ? state.businessRules || undefined : undefined,
                         test_data: state.mode === 'advanced' ? state.testData || undefined : undefined,
                         test_flow: state.mode === 'advanced' ? state.testFlow || undefined : undefined,
                     };
                     // Use existing mutation hook for /generate-blueprint
                     const result = await generateBlueprintMutation.mutateAsync(blueprintRequest);
                     setBlueprintJobId(result.job_id);
                     onNext(); // Go to BlueprintView for standard mode
                 }
             } catch (err) {
                 setError(err instanceof Error ? err.message : 'Failed to start generation');
                 setIsGenerating(false); // Ensure loading state is reset on error
             } finally {
                 // Only set generating false if NOT autonomous, as autonomous has its own monitoring
                 if (!state.isAutonomousMode) {
                     setIsGenerating(false);
                 }
             }
          };


          return (
            <div className="space-y-8">
              {/* ... existing Mode Selection and Advanced Options ... */}

              {/* --- Add Autonomous Toggle --- */}
              <div className="flex items-center justify-between p-4 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700/30">
                 <div>
                    <span className="font-medium text-gray-900 dark:text-white">Enable Autonomous Mode</span>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Let AI agents iteratively refine the blueprint and scripts.</p>
                 </div>
                 <Switch
                    checked={state.isAutonomousMode}
                    onChange={setIsAutonomousMode}
                    className={`${
                      state.isAutonomousMode ? 'bg-primary-600' : 'bg-gray-200 dark:bg-gray-600'
                    } relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800`}
                  >
                    <span className="sr-only">Enable Autonomous Mode</span>
                    <span
                      className={`${
                        state.isAutonomousMode ? 'translate-x-6' : 'translate-x-1'
                      } inline-block h-4 w-4 transform rounded-full bg-white transition-transform`}
                    />
                  </Switch>
              </div>
              {/* --- End Autonomous Toggle --- */}


              {/* ... existing Error Display ... */}

              {/* Action Buttons */}
              <div className="flex justify-between">
                <button onClick={onBack} /* ... existing ... */ > Back </button>
                <button
                  onClick={handleGenerate}
                  disabled={isGenerating || !state.openApiSpec} // Disable if no spec
                  className="px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white font-medium rounded-md disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                >
                  {isGenerating ? (
                     <> /* ... spinner ... */ Generating... </>
                  ) : state.isAutonomousMode ? (
                     'Start Autonomous Generation' // Change button text
                  ) : (
                     'Generate Blueprint'
                  )}
                </button>
              </div>
            </div>
          );
        };
        ```

3.  **Modify `ScriptOutput.tsx`:**
    *   Import `useAppContext`.
    *   Get `state.isAutonomousMode`.
    *   **Conditional Rendering/Behavior:**
        *   Check if `state.scriptJobId` (now used for *both* standard script generation *and* the single autonomous job) exists.
        *   The `useJobStatus` and `useWebSocket` hooks will automatically work with this single ID.
        *   **Progress Display:** Modify `renderProgress` to interpret the new autonomous stages (`spec_analysis`, `blueprint_authoring`, `blueprint_reviewing`, `script_coding`, etc.) coming from the `progress_callback` in the backend. Map these stages to user-friendly text and adjust the percentage calculation logic (it will span 0-100% across the *entire* autonomous run).
        *   **Initial State:** If entering this component via Autonomous Mode (`state.isAutonomousMode` is true), it should immediately start polling the job ID passed via `state.scriptJobId` (which was set in `ModeSelection`). It should *not* show the target selection or "Generate Scripts" button initially.
        *   **Final Display:** Once the autonomous job status is "completed", the component should:
            *   Retrieve the final `blueprint` and `scripts` from `jobStatus.data.result`.
            *   Update the app context using `setBlueprint(...)` and `setScripts(...)`.
            *   Render the target selection tabs and file viewer as it does now, allowing the user to browse the *final* generated artifacts.
        *   **Hide Generate Button:** If `state.isAutonomousMode` is true, hide or disable the manual "Generate Scripts" button/logic.

4.  **Modify `Layout.tsx` (Optional but Recommended):**
    *   If `isAutonomousMode` is true, perhaps visually indicate this on the stepper or disable clicking previous steps like Blueprint review, as the loop handles it internally. This is a UX refinement.

5.  **Testing (UI):**
    *   Test toggling Autonomous Mode on/off on the `ModeSelection` page.
    *   Verify the correct API endpoint (`/generate-autonomous` or `/generate-blueprint`) is called.
    *   If Autonomous Mode is ON, verify the app navigates directly to the `ScriptOutput` page.
    *   Verify the `ScriptOutput` page polls the correct job ID and displays progress reflecting the autonomous stages.
    *   Verify the final blueprint and scripts are displayed correctly after the autonomous job completes.
    *   Verify standard mode still works as before.

---

This revised plan restores the code detail while incorporating the essential feedback, especially regarding context handling in `run_agent_with_retry` and adding robust parsing. The UI plan provides a clear path for integrating the autonomous mode toggle. Remember that iterative testing and prompt refinement will be key to the success of the autonomous loops.