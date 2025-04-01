"""
Autonomous Pipeline - Main pipeline for autonomous agent workflows

This module implements the core pipeline for running the autonomous agent loops
for blueprint and script generation.
"""

import asyncio
import json
import yaml
import logging
from typing import Dict, Any, Tuple, List, Callable, Coroutine, Optional
from src.utils.spec_validation import validate_openapi_spec
from src.errors.exceptions import SpecValidationError, BlueprintGenerationError, ScriptGenerationError
from src.agents.autonomous.context import PlannerContext
from src.agents.autonomous.agents import (
    setup_blueprint_author_agent, setup_blueprint_reviewer_agent,
    setup_script_coder_agent, setup_script_reviewer_agent
)
from src.utils.execution import run_agent_with_retry, RunConfig, RetryConfig
from src.config.settings import settings
from agents import RunResult
from src.blueprint.validation import validate_and_clean_blueprint as validate_blueprint

logger = logging.getLogger(__name__)

# Define keyword constants at the top level
BLUEPRINT_APPROVED_KEYWORD = "[[BLUEPRINT_APPROVED]]"
REVISION_NEEDED_KEYWORD = "[[REVISION_NEEDED]]"
CODE_APPROVED_KEYWORD = "[[CODE_APPROVED]]"

async def analyze_initial_spec(spec_text: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Parses spec, returns analysis dict {endpoints, schemas, raw_spec_for_context} and warnings.
    
    Args:
        spec_text: The raw OpenAPI spec text
        
    Returns:
        Tuple of (analysis_result, warnings)
        
    Raises:
        SpecValidationError: If spec validation fails
    """
    logger.info("Analyzing initial OpenAPI spec...")
    try:
        parsed_spec, warnings = await validate_openapi_spec(spec_text)
        analysis_result = {
            "endpoints": list(parsed_spec.get("paths", {}).keys()),
            "schemas": list(parsed_spec.get("components", {}).get("schemas", {}).keys()),
            "raw_spec_for_context": parsed_spec
        }
        logger.info(f"Spec analysis complete. Found {len(analysis_result['endpoints'])} endpoints, {len(analysis_result['schemas'])} schemas.")
        return analysis_result, warnings
    except SpecValidationError as e:
        logger.error(f"Initial spec validation failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during spec analysis: {str(e)}")
        raise SpecValidationError(f"Failed to analyze spec: {str(e)}") from e

async def run_autonomous_blueprint_pipeline(
    spec_analysis: Dict[str, Any],
    progress_callback = None,
    max_iterations: int = None,
    business_rules: Optional[str] = None,
    test_data: Optional[str] = None,
    test_flow: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run autonomous pipeline for blueprint generation
    
    Args:
        spec_analysis: Dictionary containing spec analysis data
        progress_callback: Optional callback for progress updates
        max_iterations: Maximum iterations for the pipeline, defaults to AUTONOMOUS_MAX_ITERATIONS
        business_rules: Optional business rules to consider during generation
        test_data: Optional test data setup considerations
        test_flow: Optional high-level desired test flow overview
        
    Returns:
        Dictionary containing the final generated blueprint and status flags
    """
    # Get max iterations from settings if not provided
    if max_iterations is None:
        from ...config.settings import settings
        max_iterations = settings.get("AUTONOMOUS_MAX_ITERATIONS", 3)
    
    logger.info(f"Starting autonomous blueprint pipeline with max {max_iterations} iterations")
    
    # Log advanced context details
    logger.debug(f"Received business rules: {'Yes' if business_rules else 'No'}")
    logger.debug(f"Received test data guidance: {'Yes' if test_data else 'No'}")
    logger.debug(f"Received test flow guidance: {'Yes' if test_flow else 'No'}")
    
    # Set up context structure to hold spec information and user inputs
    planner_context = PlannerContext(
        spec_analysis=spec_analysis,
        business_rules=business_rules,
        test_data=test_data,
        test_flow=test_flow
    )
    
    # Set up agents
    blueprint_author = setup_blueprint_author_agent()
    blueprint_reviewer = setup_blueprint_reviewer_agent()
    
    # Track current state
    blueprint_json = None
    approved = False
    reviewer_feedback = "No feedback yet. This is the first iteration."
    iteration = 0
    
    # Main iteration loop
    while not approved and iteration < max_iterations:
        iteration += 1
        logger.info(f"Starting blueprint iteration {iteration}/{max_iterations}")
        
        # --- Author Step ---
        # Prepare spec analysis summary for the prompt - MODIFIED TO REMOVE INDENTATION
        spec_for_prompt = json.dumps(spec_analysis)  # NO INDENTATION for more compact representation
        
        # Limit size if too large
        MAX_SPEC_PROMPT_LEN = 80000
        if len(spec_for_prompt) > MAX_SPEC_PROMPT_LEN:
            # Ensure we truncate to valid JSON by finding a safe ending position
            truncate_pos = MAX_SPEC_PROMPT_LEN
            # Look back to find a safer truncation point at a comma or closing brace
            for i in range(truncate_pos-1, max(0, truncate_pos-100), -1):
                if spec_for_prompt[i] in [',', '}', ']']:
                    truncate_pos = i + 1
                    break
            
            spec_for_prompt = spec_for_prompt[:truncate_pos] + '..."}}' # Add closing JSON suffix
            logger.warning(f"Spec analysis (compact) truncated (limit: {MAX_SPEC_PROMPT_LEN}) for Author/Reviewer prompt due to size.")

        # Modify author_input_data
        author_input_data = {
            "spec_analysis_summary": spec_for_prompt,  # Use compact version
            "reviewer_feedback": reviewer_feedback,
        }
        if blueprint_json:
            author_input_data["previous_blueprint"] = blueprint_json
        # Explicitly add context fields if they exist
        if business_rules:
            author_input_data["business_rules"] = business_rules
        if test_data:
            author_input_data["test_data_guidance"] = test_data # Use descriptive key
        if test_flow:
            author_input_data["test_flow_guidance"] = test_flow   # Use descriptive key

        # Log Author Input (limit length for readability)
        log_author_input = {k: (v[:300] + "..." if isinstance(v, str) and len(v) > 300 else v)
                            for k, v in author_input_data.items()}
        logger.debug(f"AUTHOR Input (Iter {iteration}):\n{json.dumps(log_author_input, indent=2)}")
        
        if progress_callback:
            await progress_callback(
                "blueprint_authoring", 
                {"message": f"Creating API test blueprint (iteration {iteration})"}, 
                "blueprint_author"
            )
        
        try:
            # TODO: Calculate complexity
            complexity = 0.6
            run_config = RunConfig(complexity=complexity, task="blueprint_authoring")
            author_result = await run_agent_with_retry(
                blueprint_author,
                author_input_data, # Pass the dict WITH spec analysis
                run_config=run_config,
                context=planner_context
            )
            # Properly unpack the tuple result
            author_run_result, author_trace_id = author_result
            # Access raw output string from the RunResult object
            proposed_blueprint_json = author_run_result.final_output
            if not isinstance(proposed_blueprint_json, str):
                proposed_blueprint_json = str(proposed_blueprint_json)
            
            # Log Author Output
            logger.debug(f"AUTHOR Output (Iter {iteration}):\n{proposed_blueprint_json[:1000]}...")
            
            try:
                # Validate the JSON structure
                blueprint_dict = json.loads(proposed_blueprint_json)
                
                # Validate the blueprint structure (await the async function)
                # Note: validate_and_clean_blueprint returns a tuple (dict, warnings)
                cleaned_blueprint_dict, validation_warnings = await validate_blueprint(blueprint_dict)
                if validation_warnings:
                    logger.warning(f"Blueprint validation issues (iteration {iteration}): {validation_warnings}")
                
                # Use the proposed blueprint for the next iteration
                blueprint_json = proposed_blueprint_json
                logger.info(f"Blueprint author proposed valid JSON blueprint (iteration {iteration})")
                
            except json.JSONDecodeError as e:
                logger.error(f"Blueprint author produced invalid JSON (iteration {iteration}): {e}")
                # Provide feedback for next iteration
                reviewer_feedback = f"[[REVISION_NEEDED]]\nYour previous output was not valid JSON. Please output only a single, valid JSON string representing the blueprint. Error: {e}"
                # If last iteration, raise error, otherwise continue
                if iteration == max_iterations:
                    raise BlueprintGenerationError(f"Author failed to produce valid JSON after {max_iterations} iterations.") from e
                continue # Skip reviewer for this iteration
                
        except Exception as e:
            logger.error(f"Blueprint author failed (iteration {iteration}): {str(e)}")
            raise BlueprintGenerationError(f"Blueprint author failed: {str(e)}") from e
        
        # --- Reviewer Step ---
        # Modify reviewer_input_data
        reviewer_input_data = {
            "spec_analysis_summary": spec_for_prompt,  # Use compact version
            "blueprint_to_review": blueprint_json,
        }
        # Explicitly add context fields if they exist
        if business_rules:
            reviewer_input_data["business_rules"] = business_rules
        if test_data:
            reviewer_input_data["test_data_guidance"] = test_data
        if test_flow:
            reviewer_input_data["test_flow_guidance"] = test_flow

        # Log Reviewer Input (limit length)
        log_reviewer_input = {k: (v[:300] + "..." if isinstance(v, str) and len(v) > 300 else v)
                              for k, v in reviewer_input_data.items()}
        logger.debug(f"REVIEWER Input (Iter {iteration}):\n{json.dumps(log_reviewer_input, indent=2)}")
        
        if progress_callback:
            await progress_callback(
                "blueprint_reviewing", 
                {"message": f"Reviewing API test blueprint (iteration {iteration})"}, 
                "blueprint_reviewer"
            )
        
        try:
            # TODO: Calculate complexity
            complexity = 0.5
            run_config = RunConfig(complexity=complexity, task="blueprint_reviewing")
            reviewer_result = await run_agent_with_retry(
                blueprint_reviewer,
                reviewer_input_data, # Pass the dict WITH spec analysis
                run_config=run_config,
                context=planner_context
            )
            # Properly unpack the tuple result
            reviewer_run_result, reviewer_trace_id = reviewer_result
            # Access raw output string from the RunResult object
            review_output_raw = reviewer_run_result.final_output
            if not isinstance(review_output_raw, str):
                review_output_raw = str(review_output_raw)
            
            # Log Reviewer Output
            logger.debug(f"REVIEWER Output (Iter {iteration}):\n{review_output_raw}")
            
            # --- MODIFIED Keyword Parsing ---
            approved = False
            revision_needed = False
            feedback_lines = []
            keyword_found = False

            lines = review_output_raw.strip().split('\n')
            # Iterate backwards to find the last non-empty line for the keyword
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i].strip()
                if line == BLUEPRINT_APPROVED_KEYWORD:
                    approved = True
                    keyword_found = True
                    feedback_lines = lines[:i] # Get lines before the keyword line
                    break
                elif line == REVISION_NEEDED_KEYWORD:
                    revision_needed = True
                    keyword_found = True
                    feedback_lines = lines[:i] # Get lines before the keyword line
                    break
                elif line: # Stop searching if we hit a non-empty line that isn't a keyword
                    break

            if approved:
                logger.info(f"Blueprint approved by reviewer on iteration {iteration}")
                reviewer_feedback = '\n'.join(feedback_lines).strip()
            elif revision_needed:
                logger.info(f"Blueprint revision needed (iteration {iteration})")
                reviewer_feedback = '\n'.join(feedback_lines).strip()
            else:
                # No recognized keyword found, use entire output as feedback
                logger.warning(f"No recognized keyword found in reviewer output (iteration {iteration})")
                reviewer_feedback = review_output_raw # Keep original raw output as feedback
            # --- END MODIFIED Keyword Parsing ---
            
        except Exception as e:
            logger.error(f"Blueprint reviewer failed (iteration {iteration}): {str(e)}")
            raise BlueprintGenerationError(f"Blueprint reviewer failed: {str(e)}") from e
    
    # After the loop, check if blueprint was approved
    if not approved:
        logger.warning(f"Max iterations ({max_iterations}) reached without blueprint approval")
    
    # Call progress callback if provided
    if progress_callback:
        await progress_callback(
            "blueprint_complete", 
            {"percent": 100, "message": "Blueprint generation complete"}, 
            "system"
        )
    
    # Return the final blueprint as a dictionary with status flags
    try:
        final_blueprint_dict = json.loads(blueprint_json)
        # ... (code to add metadata like description, baseUrl - keep this) ...
        return {
            "blueprint": final_blueprint_dict,
            "approved": approved,
            "max_iterations_reached": (iteration == max_iterations and not approved),
            "final_feedback": reviewer_feedback # Last feedback given
        }
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing final blueprint JSON: {e}")
        raise BlueprintGenerationError(f"Error parsing final blueprint JSON: {e}")

async def run_autonomous_script_pipeline(
    blueprint: Dict[str, Any],
    framework: str,
    progress_callback = None,
    max_iterations: int = None
) -> List[Dict[str, str]]:
    """
    Run autonomous pipeline for script generation
    
    Args:
        blueprint: Blueprint dictionary
        framework: Target framework (e.g., 'postman', 'playwright')
        progress_callback: Optional callback for progress updates
        max_iterations: Maximum iterations for the pipeline, defaults to AUTONOMOUS_MAX_ITERATIONS
        
    Returns:
        List of dictionaries with filename and content pairs
    """
    # Get max iterations from settings if not provided
    if max_iterations is None:
        from ...config.settings import settings
        max_iterations = settings.get("AUTONOMOUS_MAX_ITERATIONS", 3)
    
    logger.info(f"Starting autonomous script pipeline for {framework} with max {max_iterations} iterations")
    
    # Set up agents for the target framework
    script_coder = setup_script_coder_agent(framework)
    script_reviewer = setup_script_reviewer_agent(framework)
    
    # Track current state
    script_files = []
    script_files_json = None
    approved = False
    reviewer_feedback = "No feedback yet. This is the first iteration."
    iteration = 0
    
    # Convert blueprint to a JSON string for the prompts
    blueprint_json_str = json.dumps(blueprint, indent=2)
    
    # Main iteration loop
    while not approved and iteration < max_iterations:
        iteration += 1
        logger.info(f"Starting script iteration {iteration}/{max_iterations} for {framework}")
        
        # --- Coder Step ---
        # Modify coder_input_data
        if script_files_json:
            coder_input_data = {
                "framework": framework,
                "blueprint_json": blueprint_json_str, # Pass blueprint as string
                "reviewer_feedback": reviewer_feedback,
                "previous_code_files": script_files_json
            }
        else:
            coder_input_data = {
                "framework": framework,
                "blueprint_json": blueprint_json_str, # Pass blueprint as string
                "reviewer_feedback": reviewer_feedback
            }
        
        # Log Coder Input (limit blueprint/code)
        log_coder_input = coder_input_data.copy()
        log_coder_input["blueprint_json"] = log_coder_input["blueprint_json"][:500] + "..."
        if "previous_code_files" in log_coder_input:
            log_coder_input["previous_code_files"] = log_coder_input["previous_code_files"][:500] + "..."
        logger.debug(f"CODER Input for {framework} (Iter {iteration}):\n{json.dumps(log_coder_input, indent=2)}")
        
        if progress_callback:
            await progress_callback(
                "script_coding", 
                {"message": f"Creating {framework} test scripts (iteration {iteration})"}, 
                f"script_coder_{framework}"
            )
        
        coder_failed_json = False # Flag to track if coder failed JSON validation
        try:
            # TODO: Calculate complexity
            complexity = 0.7
            run_config = RunConfig(complexity=complexity, task="script_coding")
            coder_result = await run_agent_with_retry(
                script_coder,
                coder_input_data, # Pass dict WITH blueprint
                run_config=run_config
            )
            # Properly unpack the tuple result
            coder_run_result, coder_trace_id = coder_result
            # Access raw output string from the RunResult object
            proposed_script_files_json = coder_run_result.final_output
            if not isinstance(proposed_script_files_json, str):
                proposed_script_files_json = str(proposed_script_files_json)
            
            # Log Coder Output
            logger.debug(f"CODER Output for {framework} (Iter {iteration}):\n{proposed_script_files_json[:1000]}...")
            
            # --- ENHANCED JSON VALIDATION ---
            try:
                # 1. Validate the outer array structure
                script_files_list = json.loads(proposed_script_files_json)

                if not isinstance(script_files_list, list):
                    raise ScriptGenerationError(f"Coder output is not a JSON list (Iter {iteration}). Got type: {type(script_files_list)}")

                # 2. Validate individual file objects and inner JSON content
                validated_files = []
                for i, file_obj in enumerate(script_files_list):
                    if not isinstance(file_obj, dict) or "filename" not in file_obj or "content" not in file_obj:
                        raise ScriptGenerationError(f"Invalid file object structure at index {i} (Iter {iteration}).")

                    filename = file_obj["filename"]
                    content_str = file_obj["content"]

                    # Ensure content is a string
                    if not isinstance(content_str, str):
                         logger.warning(f"Content for file '{filename}' is not a string (type: {type(content_str)}). Attempting conversion.")
                         content_str = str(content_str)
                         file_obj["content"] = content_str # Update the object

                    # 3. If it's a JSON file, validate its content string
                    if filename.lower().endswith('.json'):
                        try:
                            # Attempt to parse the inner JSON content
                            json.loads(content_str)
                            logger.debug(f"Successfully validated inner JSON for: {filename}")
                        except json.JSONDecodeError as inner_json_err:
                            # Raise specific error if inner JSON is invalid
                            raise ScriptGenerationError(
                                f"Coder produced invalid JSON content within file '{filename}' (Iter {iteration}): {inner_json_err}"
                            ) from inner_json_err

                    validated_files.append(file_obj) # Add validated file object

                # All validations passed
                script_files_json = proposed_script_files_json # Store the original valid outer JSON string
                script_files = validated_files # Store the list of validated file objects
                logger.info(f"Script coder proposed valid JSON structure and content for {framework} (iteration {iteration}): {len(script_files)} files")

            except (json.JSONDecodeError, ScriptGenerationError) as json_validation_err:
                # Catch errors specifically from JSON parsing or our structure checks
                logger.error(f"Script coder JSON validation failed (Iter {iteration}): {json_validation_err}")
                coder_failed_json = True # Set the flag
                # Prepare feedback for the *next* coder iteration
                reviewer_feedback = (
                    f"{REVISION_NEEDED_KEYWORD}\n" # Ensure keyword is present for loop logic
                    f"Error: Your previous output was not valid JSON or had an invalid structure.\n"
                    f"Validation Error: {json_validation_err}\n"
                    f"Please carefully review your entire output, ensuring it's a single, valid JSON array `[{{\"filename\": ..., \"content\": ...}}]` "
                    f"and that all `content` strings (especially for .json files) have correctly escaped internal quotes (`\\\"`) and backslashes (`\\\\`). Fix the JSON syntax and structure."
                )
                # If it's the last iteration, raise the error anyway
                if iteration >= max_iterations: # Use >= for safety
                     logger.error(f"Coder failed JSON validation on final attempt ({iteration}). Raising error.")
                     # Raise the original error for better context
                     raise ScriptGenerationError(f"Coder failed JSON validation on final attempt: {json_validation_err}") from json_validation_err
                else:
                    # Allow loop to continue to give coder a chance to fix it
                    logger.info(f"Coder failed JSON validation on attempt {iteration}. Feeding error back for retry.")
            # --- END ENHANCED JSON VALIDATION ---
                
        except ScriptGenerationError as sge: # Catch our specific errors raised during validation
            logger.error(str(sge))
            # If validation fails, we want to retry if possible (handled above),
            # but if it failed on the last iteration, re-raise.
            if iteration >= max_iterations:
                raise
            else:
                # Ensure the flag is set and feedback is prepared if not already
                coder_failed_json = True
                if not reviewer_feedback.startswith(REVISION_NEEDED_KEYWORD): # Avoid double-prepending
                    reviewer_feedback = f"{REVISION_NEEDED_KEYWORD}\n{str(sge)}"
        except Exception as e:
            # Handle other unexpected errors during coder execution
            logger.error(f"Script coder failed for {framework} (iteration {iteration}): {str(e)}")
            # If coder fails execution (not just validation), we should probably raise
            raise ScriptGenerationError(f"Script coder failed: {str(e)}") from e
        
        # --- Reviewer Step ---
        # Skip reviewer step if the coder failed JSON validation in this iteration
        if coder_failed_json:
            logger.warning(f"Skipping reviewer step for iteration {iteration} due to coder JSON validation failure.")
            continue # Go to the next iteration of the loop
        
        # Modify reviewer_input_data
        reviewer_input_data = {
            "framework": framework,
            "blueprint_json": blueprint_json_str, # Pass blueprint string
            "generated_script_files_json": script_files_json # Pass current scripts string
        }
        
        # Log Reviewer Input (limit blueprint/code)
        log_reviewer_input = reviewer_input_data.copy()
        log_reviewer_input["blueprint_json"] = log_reviewer_input["blueprint_json"][:500] + "..."
        log_reviewer_input["generated_script_files_json"] = log_reviewer_input["generated_script_files_json"][:500] + "..."
        logger.debug(f"REVIEWER Input for {framework} (Iter {iteration}):\n{json.dumps(log_reviewer_input, indent=2)}")
        
        if progress_callback:
            await progress_callback(
                "script_reviewing", 
                {"message": f"Reviewing {framework} test scripts (iteration {iteration})"}, 
                f"script_reviewer_{framework}"
            )
        
        try:
            # TODO: Calculate complexity
            complexity = 0.6
            run_config = RunConfig(complexity=complexity, task="script_reviewing")
            reviewer_result = await run_agent_with_retry(
                script_reviewer,
                reviewer_input_data, # Pass dict WITH blueprint AND code
                run_config=run_config
            )
            # Properly unpack the tuple result
            reviewer_run_result, reviewer_trace_id = reviewer_result
            # Access raw output string from the RunResult object
            review_output_raw = reviewer_run_result.final_output
            if not isinstance(review_output_raw, str):
                review_output_raw = str(review_output_raw)
            
            # Log Reviewer Output
            logger.debug(f"REVIEWER Output for {framework} (Iter {iteration}):\n{review_output_raw}")
            
            # --- MODIFIED Keyword Parsing ---
            approved = False
            revision_needed = False
            feedback_lines = []
            keyword_found = False

            lines = review_output_raw.strip().split('\n')
            # Iterate backwards to find the last non-empty line for the keyword
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i].strip()
                if line == CODE_APPROVED_KEYWORD:
                    approved = True
                    keyword_found = True
                    feedback_lines = lines[:i] # Get lines before the keyword line
                    break
                elif line == REVISION_NEEDED_KEYWORD:
                    revision_needed = True
                    keyword_found = True
                    feedback_lines = lines[:i] # Get lines before the keyword line
                    break
                elif line: # Stop searching if we hit a non-empty line that isn't a keyword
                    break

            if approved:
                logger.info(f"Scripts approved by reviewer on iteration {iteration}")
                reviewer_feedback = '\n'.join(feedback_lines).strip()
            elif revision_needed:
                logger.info(f"Script revision needed (iteration {iteration})")
                reviewer_feedback = '\n'.join(feedback_lines).strip()
            else:
                # No recognized keyword found, use entire output as feedback
                logger.warning(f"No recognized keyword found in reviewer output (iteration {iteration})")
                reviewer_feedback = review_output_raw # Keep original raw output as feedback
            # --- END MODIFIED Keyword Parsing ---
            
        except Exception as e:
            logger.error(f"Script reviewer failed for {framework} (iteration {iteration}): {str(e)}")
            raise ScriptGenerationError(f"Script reviewer failed: {str(e)}") from e
    
    # After the loop, check if scripts were approved
    if not approved:
        logger.warning(f"Max iterations ({max_iterations}) reached without script approval")
    
    # Call progress callback if provided
    if progress_callback:
        await progress_callback(
            "script_generation_complete", 
            {"percent": 100, "message": f"{framework} script generation complete."}, 
            "system"
        )
    
    return script_files 