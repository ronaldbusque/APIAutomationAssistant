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

logger = logging.getLogger(__name__)

# Keyword constants
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
    progress_callback: Callable[[str, Any, str], Coroutine] = None,
    max_iterations: int = None
) -> Dict[str, Any]:
    """
    Run the autonomous blueprint generation pipeline with Author-Reviewer loop.
    
    Args:
        spec_analysis: The result from analyze_initial_spec
        progress_callback: Async function for progress updates (stage, progress, agent)
        max_iterations: Maximum iterations for the Author-Reviewer loop
        
    Returns:
        Generated blueprint dict
        
    Raises:
        BlueprintGenerationError: If blueprint generation fails
    """
    if max_iterations is None:
        max_iterations = settings.get("AUTONOMOUS_MAX_ITERATIONS", 3)
    
    logger.info(f"Starting autonomous blueprint pipeline with max {max_iterations} iterations")
    
    # Create the planner context with spec analysis
    planner_context = PlannerContext(spec_analysis=spec_analysis)
    
    # Initialize blueprint author agent
    blueprint_author = setup_blueprint_author_agent()
    
    # Initialize blueprint reviewer agent
    blueprint_reviewer = setup_blueprint_reviewer_agent()
    
    # Initialize variables for the loop
    blueprint_json = None
    reviewer_feedback = "No feedback yet. Please create an initial blueprint based on the specification analysis."
    approved = False
    iteration = 0
    
    # Author-Reviewer loop
    while not approved and iteration < max_iterations:
        iteration += 1
        logger.info(f"Starting blueprint iteration {iteration}/{max_iterations}")
        
        # Prepare input for blueprint author
        if blueprint_json:
            author_input = {
                "reviewer_feedback": reviewer_feedback,
                "previous_blueprint": blueprint_json
            }
        else:
            author_input = {
                "reviewer_feedback": reviewer_feedback
            }
        
        # Call progress callback if provided
        if progress_callback:
            await progress_callback(
                "blueprint_authoring", 
                {"percent": 20 * iteration, "message": f"Creating blueprint (iteration {iteration}/{max_iterations})..."}, 
                "BlueprintAuthorAgent"
            )
        
        # TODO: Calculate or estimate blueprint complexity
        complexity = 0.6
        
        # Run blueprint author agent
        try:
            # Pass context to run_agent_with_retry
            run_config = RunConfig(complexity=complexity, task="blueprint_authoring")
            author_result, author_trace = await run_agent_with_retry(
                blueprint_author, 
                author_input, 
                run_config=run_config,
                context=planner_context
            )
            blueprint_json = author_result.final_output
            
            # Basic validation of author output
            if not blueprint_json or not blueprint_json.strip().startswith("{"):
                raise BlueprintGenerationError("Invalid blueprint format from author agent")
            
            logger.info(f"Blueprint author completed successfully (iteration {iteration})")
            
        except Exception as e:
            logger.error(f"Blueprint author failed (iteration {iteration}): {str(e)}")
            raise BlueprintGenerationError(f"Blueprint author failed: {str(e)}") from e
        
        # Call progress callback if provided
        if progress_callback:
            await progress_callback(
                "blueprint_reviewing", 
                {"percent": 20 * iteration + 10, "message": f"Reviewing blueprint (iteration {iteration}/{max_iterations})..."}, 
                "BlueprintReviewerAgent"
            )
        
        # Run blueprint reviewer agent
        try:
            # Pass context to run_agent_with_retry
            run_config = RunConfig(complexity=0.5, task="blueprint_reviewing")
            reviewer_result, reviewer_trace = await run_agent_with_retry(
                blueprint_reviewer, 
                {"blueprint": blueprint_json},
                run_config=run_config,
                context=planner_context
            )
            
            # Extract feedback and check for approval keyword
            reviewer_output = reviewer_result.final_output
            
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
    
    # Parse the blueprint JSON
    try:
        blueprint = json.loads(blueprint_json)
        
        # Call progress callback if provided
        if progress_callback:
            await progress_callback(
                "blueprint_generation_complete", 
                {"percent": 100, "message": "Blueprint generation complete."}, 
                "system"
            )
        
        return blueprint
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse blueprint JSON: {str(e)}")
        raise BlueprintGenerationError(f"Invalid blueprint JSON: {str(e)}") from e

async def run_autonomous_script_pipeline(
    blueprint: Dict[str, Any],
    framework: str,
    progress_callback: Callable[[str, Any, str], Coroutine] = None,
    max_iterations: int = None
) -> List[Dict[str, str]]:
    """
    Run the autonomous script generation pipeline with Coder-Reviewer loop.
    
    Args:
        blueprint: The blueprint dictionary
        framework: Target framework (e.g., 'postman', 'playwright')
        progress_callback: Async function for progress updates (stage, progress, agent)
        max_iterations: Maximum iterations for the Coder-Reviewer loop
        
    Returns:
        List of file objects [{"filename": str, "content": str}, ...]
        
    Raises:
        ScriptGenerationError: If script generation fails
    """
    if max_iterations is None:
        max_iterations = settings.get("AUTONOMOUS_MAX_ITERATIONS", 3)
    
    logger.info(f"Starting autonomous script pipeline for {framework} with max {max_iterations} iterations")
    
    # Initialize script coder agent for the specified framework
    script_coder = setup_script_coder_agent(framework)
    
    # Initialize script reviewer agent for the specified framework
    script_reviewer = setup_script_reviewer_agent(framework)
    
    # Initialize variables for the loop
    script_files_json = None
    script_files = None
    reviewer_feedback = "No feedback yet. Please create initial test scripts based on the blueprint."
    approved = False
    iteration = 0
    
    # Convert blueprint to JSON string for agent input
    blueprint_json = json.dumps(blueprint)
    
    # Coder-Reviewer loop
    while not approved and iteration < max_iterations:
        iteration += 1
        logger.info(f"Starting script generation iteration {iteration}/{max_iterations}")
        
        # Prepare input for script coder
        if script_files_json:
            coder_input = {
                "framework": framework,
                "blueprint": blueprint_json,
                "reviewer_feedback": reviewer_feedback,
                "previous_code_files": script_files_json
            }
        else:
            coder_input = {
                "framework": framework,
                "blueprint": blueprint_json,
                "reviewer_feedback": reviewer_feedback
            }
        
        # Call progress callback if provided
        if progress_callback:
            await progress_callback(
                "script_coding", 
                {"percent": 60 + (40/max_iterations) * (iteration-1), "message": f"Creating {framework} scripts (iteration {iteration}/{max_iterations})..."}, 
                f"ScriptCoderAgent_{framework}"
            )
        
        # TODO: Calculate or estimate script coding complexity
        complexity = 0.7
        
        # Run script coder agent
        try:
            run_config = RunConfig(complexity=complexity, task="script_coding")
            coder_result, coder_trace = await run_agent_with_retry(
                script_coder, 
                coder_input, 
                run_config=run_config
            )
            script_files_json = coder_result.final_output
            
            # Parse and validate script files output
            try:
                script_files = json.loads(script_files_json)
                if not isinstance(script_files, list):
                    raise ScriptGenerationError("Script coder did not return a list of files")
                
                # Validate structure of each file object
                for file in script_files:
                    if not isinstance(file, dict) or "filename" not in file or "content" not in file:
                        raise ScriptGenerationError("Invalid file object in script coder output")
                
                logger.info(f"Script coder completed successfully with {len(script_files)} files (iteration {iteration})")
                
            except json.JSONDecodeError as e:
                raise ScriptGenerationError(f"Failed to parse script files JSON: {str(e)}") from e
            
        except Exception as e:
            logger.error(f"Script coder failed (iteration {iteration}): {str(e)}")
            raise ScriptGenerationError(f"Script coder failed: {str(e)}") from e
        
        # Call progress callback if provided
        if progress_callback:
            await progress_callback(
                "script_reviewing", 
                {"percent": 60 + (40/max_iterations) * (iteration-0.5), "message": f"Reviewing {framework} scripts (iteration {iteration}/{max_iterations})..."}, 
                f"ScriptReviewerAgent_{framework}"
            )
        
        # Run script reviewer agent
        try:
            # Prepare input for script reviewer
            reviewer_input = {
                "framework": framework,
                "blueprint": blueprint_json,
                "code_files": script_files_json
            }
            
            run_config = RunConfig(complexity=0.6, task="script_reviewing")
            reviewer_result, reviewer_trace = await run_agent_with_retry(
                script_reviewer, 
                reviewer_input,
                run_config=run_config
            )
            
            # Extract feedback and check for approval keyword
            reviewer_output = reviewer_result.final_output
            
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
            logger.error(f"Script reviewer failed (iteration {iteration}): {str(e)}")
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