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
    max_iterations: int = None
) -> Dict[str, Any]:
    """
    Run autonomous pipeline for blueprint generation
    
    Args:
        spec_analysis: Dictionary containing spec analysis data
        progress_callback: Optional callback for progress updates
        max_iterations: Maximum iterations for the pipeline, defaults to AUTONOMOUS_MAX_ITERATIONS
        
    Returns:
        Dictionary containing the final generated blueprint
    """
    # Get max iterations from settings if not provided
    if max_iterations is None:
        from ...config.settings import AUTONOMOUS_MAX_ITERATIONS
        max_iterations = AUTONOMOUS_MAX_ITERATIONS
    
    logger.info(f"Starting autonomous blueprint pipeline with max {max_iterations} iterations")
    
    # Set up context structure to hold spec information and user inputs
    planner_context = PlannerContext(spec_analysis=spec_analysis)
    
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
        # Prepare spec analysis summary for the prompt
        spec_for_prompt = json.dumps(spec_analysis, indent=2)
        # Limit size if too large
        MAX_SPEC_PROMPT_LEN = 10000 # Adjust as needed
        if len(spec_for_prompt) > MAX_SPEC_PROMPT_LEN:
            spec_for_prompt = spec_for_prompt[:MAX_SPEC_PROMPT_LEN] + "\n... (spec truncated) ..."
            logger.warning("Spec analysis truncated for Author/Reviewer prompt due to size.")

        # Modify author_input_data
        if blueprint_json:
            author_input_data = {
                "spec_analysis_summary": spec_for_prompt, # ADDED
                "reviewer_feedback": reviewer_feedback,
                "previous_blueprint": blueprint_json
            }
        else:
            author_input_data = {
                "spec_analysis_summary": spec_for_prompt, # ADDED
                "reviewer_feedback": reviewer_feedback
            }

        # Log Author Input (limit blueprint length if too long)
        log_author_input = author_input_data.copy()
        log_author_input["spec_analysis_summary"] = log_author_input["spec_analysis_summary"][:300] + "..."
        if "previous_blueprint" in log_author_input:
            log_author_input["previous_blueprint"] = log_author_input["previous_blueprint"][:300] + "..."
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
                
                # Validate the blueprint structure
                validation_result = validate_blueprint(blueprint_dict)
                if not validation_result["valid"]:
                    # If validation fails, log issues but continue with the JSON
                    logger.warning(f"Blueprint validation issues: {validation_result['errors']}")
                
                # Use the proposed blueprint for the next iteration
                blueprint_json = proposed_blueprint_json
                logger.info(f"Blueprint author proposed valid JSON blueprint (iteration {iteration})")
                
            except json.JSONDecodeError as e:
                logger.error(f"Blueprint author produced invalid JSON (iteration {iteration}): {e}")
                raise BlueprintGenerationError(f"Blueprint author produced invalid JSON: {e}")
                
        except Exception as e:
            logger.error(f"Blueprint author failed (iteration {iteration}): {str(e)}")
            raise BlueprintGenerationError(f"Blueprint author failed: {str(e)}") from e
        
        # --- Reviewer Step ---
        # Modify reviewer_input_data
        reviewer_input_data = {
            "spec_analysis_summary": spec_for_prompt, # ADDED
            "blueprint_to_review": blueprint_json
        }
        
        # Log Reviewer Input
        log_reviewer_input = reviewer_input_data.copy()
        log_reviewer_input["spec_analysis_summary"] = log_reviewer_input["spec_analysis_summary"][:300] + "..."
        log_reviewer_input["blueprint_to_review"] = log_reviewer_input["blueprint_to_review"][:300] + "..."
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
            
            # Extract feedback and check for approval keyword
            reviewer_output = review_output_raw
            
            # Find the last line to check for keywords
            lines = reviewer_output.strip().split('\n')
            last_line = lines[-1].strip() if lines else ""
            
            if last_line == BLUEPRINT_APPROVED_KEYWORD:
                approved = True
                logger.info(f"Blueprint approved by reviewer on iteration {iteration}")
                # Remove the keyword from the feedback
                reviewer_feedback = '\n'.join(lines[:-1])
            elif last_line == REVISION_NEEDED_KEYWORD:
                # Remove the keyword from the feedback
                reviewer_feedback = '\n'.join(lines[:-1])
                logger.info(f"Blueprint revision needed (iteration {iteration})")
            else:
                # No recognized keyword, use entire output as feedback
                reviewer_feedback = reviewer_output
                logger.warning(f"No recognized keyword found in reviewer output (iteration {iteration})")
            
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
    
    # Return the final blueprint as a dictionary
    try:
        return json.loads(blueprint_json)
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
        from ...config.settings import AUTONOMOUS_MAX_ITERATIONS
        max_iterations = AUTONOMOUS_MAX_ITERATIONS
    
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
            
            try:
                # Validate JSON structure
                script_files_list = json.loads(proposed_script_files_json)
                
                # Basic validation of structure
                if not isinstance(script_files_list, list):
                    raise ScriptGenerationError(f"Invalid script files format: expected list, got {type(script_files_list)}")
                
                # Check each file has filename and content
                for i, file_obj in enumerate(script_files_list):
                    if not isinstance(file_obj, dict):
                        raise ScriptGenerationError(f"Invalid file object at index {i}: expected dict, got {type(file_obj)}")
                    
                    if "filename" not in file_obj or "content" not in file_obj:
                        raise ScriptGenerationError(f"Invalid file object at index {i}: missing required keys (filename, content)")
                
                # Use the proposed script files JSON for the next iteration
                script_files_json = proposed_script_files_json
                script_files = script_files_list
                logger.info(f"Script coder proposed valid files for {framework} (iteration {iteration}): {len(script_files)} files")
                
            except json.JSONDecodeError as e:
                logger.error(f"Script coder produced invalid JSON for {framework} (iteration {iteration}): {e}")
                raise ScriptGenerationError(f"Script coder produced invalid JSON: {e}")
                
        except Exception as e:
            logger.error(f"Script coder failed for {framework} (iteration {iteration}): {str(e)}")
            raise ScriptGenerationError(f"Script coder failed: {str(e)}") from e
        
        # --- Reviewer Step ---
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
            
            # Extract feedback and check for approval keyword
            reviewer_output = review_output_raw
            
            # Find the last line to check for keywords
            lines = reviewer_output.strip().split('\n')
            last_line = lines[-1].strip() if lines else ""
            
            if last_line == CODE_APPROVED_KEYWORD:
                approved = True
                logger.info(f"Scripts approved by reviewer on iteration {iteration}")
                # Remove the keyword from the feedback
                reviewer_feedback = '\n'.join(lines[:-1])
            elif last_line == REVISION_NEEDED_KEYWORD:
                # Remove the keyword from the feedback
                reviewer_feedback = '\n'.join(lines[:-1])
                logger.info(f"Script revision needed (iteration {iteration})")
            else:
                # No recognized keyword, use entire output as feedback
                reviewer_feedback = reviewer_output
                logger.warning(f"No recognized keyword found in reviewer output (iteration {iteration})")
            
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