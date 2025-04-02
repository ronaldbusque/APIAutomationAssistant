"""
Agent Execution Module - Utilities for running agents with enhanced features

This module provides functions for executing agents with retry logic,
streaming support, and error handling.
"""

import asyncio
import json
import random
import logging
import datetime
from typing import Tuple, Dict, List, Any, Optional, AsyncIterator, Callable, Union

from agents import Agent, Runner, gen_trace_id, trace
from agents.items import RunItem
from agents import RunResult  # Import RunResult explicitly
from pydantic import BaseModel

from .model_selection import ModelSelectionStrategy

# Create the logger
logger = logging.getLogger(__name__)

class RetryConfig:
    """Configuration for agent execution with retry logic."""
    def __init__(self, 
                 max_retries: int = 3,
                 base_timeout: int = 300,
                 max_jitter: float = 1.0):
        self.max_retries = max_retries
        self.base_timeout = base_timeout
        self.max_jitter = max_jitter

class RunConfig:
    """Configuration for agent execution."""
    def __init__(self,
                 timeout: int = 300,
                 complexity: float = 0.5,
                 task: str = "general",
                 input_data: Optional[Dict[str, Any]] = None):
        self.timeout = timeout
        self.complexity = complexity
        self.task = task
        self.input_data = input_data

async def run_agent_with_retry(
    agent: Agent, 
    input_data: Union[str, dict], 
    config: RetryConfig = None,
    run_config: RunConfig = None,
    context: Any = None,  # Add context parameter
    complexity: float = 0.5,
    task: str = "general",
    model_selection: ModelSelectionStrategy = None
) -> Tuple[RunResult, str]:  # Return RunResult instead of Any
    """
    Run an agent with retry logic and error handling.
    
    Args:
        agent: The agent to run
        input_data: The input data (string or dict)
        config: Retry configuration
        run_config: Run configuration (takes precedence over complexity/task)
        context: Optional context data to pass to the agent
        complexity: Task complexity (0-1) to determine model
        task: Task type for model selection
        model_selection: Optional model selection strategy
        
    Returns:
        Tuple of (RunResult, trace_id)
    """
    # Use default config if not provided
    config = config or RetryConfig()
    
    # Extract settings from run_config if provided
    if run_config:
        complexity = run_config.complexity
        task = run_config.task
        # Handle input_data from run_config if provided and not directly supplied
        if run_config.input_data is not None and input_data is None:
            input_data = run_config.input_data
    
    # Convert dict to JSON string if needed
    if isinstance(input_data, dict):
        input_data = json.dumps(input_data)
    
    # Create model selection strategy if not provided
    model_selection = model_selection or ModelSelectionStrategy()
    
    # Update agent configuration based on complexity
    original_model_kwargs = getattr(agent, "model_kwargs", {})
    agent_config = {"model_kwargs": original_model_kwargs}
    agent_config = model_selection.update_tool_choice(agent_config, complexity)
    agent.model_kwargs = agent_config["model_kwargs"]
    
    # Calculate timeout based on complexity
    timeout = model_selection.calculate_timeout(config.base_timeout, complexity)
    
    # Generate trace ID
    trace_id = gen_trace_id()
    
    # Log the model instance details from the agent object
    model_info = "Unknown Model"
    if agent.model:
        if hasattr(agent.model, 'full_model_name'):
            model_info = f"{type(agent.model).__name__}({agent.model.full_model_name})"
        elif hasattr(agent.model, 'model_name'):
            model_info = f"{type(agent.model).__name__}({agent.model.model_name})"
        else:
            model_info = type(agent.model).__name__
    
    logger.info(f"Running {agent.name} with model {model_info}, timeout {timeout}s, complexity {complexity:.2f}")
    
    with trace(f"{agent.name} Execution", trace_id=trace_id):
        for attempt in range(config.max_retries):
            try:
                logger.info(f"Attempt {attempt+1}/{config.max_retries} for {agent.name}")
                
                # Run the agent with context parameter
                result: RunResult = await Runner.run(agent, input=input_data, context=context)
                logger.info(f"Agent {agent.name} completed successfully")
                
                # Restore model_kwargs only - no need to restore model anymore
                agent.model_kwargs = original_model_kwargs
                
                return result, trace_id
                
            except Exception as e:
                error_type = type(e).__name__
                logger.error(f"Agent {agent.name} failed with {error_type}: {str(e)}")
                
                if attempt == config.max_retries - 1:  # Last attempt
                    logger.error(f"All {config.max_retries} attempts failed for {agent.name}")
                    # Restore model_kwargs only
                    agent.model_kwargs = original_model_kwargs
                    raise
                
                # Exponential backoff with jitter
                wait_time = min(30, (2 ** attempt) + random.uniform(0, config.max_jitter))
                logger.info(f"Retrying in {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)

def run_agent_sync(
    agent: Agent,
    input_data: Union[str, dict],
    config: RunConfig = None,
    model_selection: ModelSelectionStrategy = None
) -> Any:
    """
    Synchronous version of agent execution for simpler integration contexts.
    
    Args:
        agent: The agent to run
        input_data: The input data (string or dict)
        config: Run configuration
        model_selection: Optional model selection strategy
        
    Returns:
        The agent's result
    """
    # Use default config if not provided
    config = config or RunConfig()
    
    # Convert dict to JSON string if needed
    if isinstance(input_data, dict):
        input_data = json.dumps(input_data)
    
    # Create model selection strategy if not provided
    model_selection = model_selection or ModelSelectionStrategy()
    
    # Update agent configuration based on complexity
    original_model_kwargs = getattr(agent, "model_kwargs", {})
    agent_config = {"model_kwargs": original_model_kwargs}
    agent_config = model_selection.update_tool_choice(agent_config, config.complexity)
    agent.model_kwargs = agent_config["model_kwargs"]
    
    # Calculate timeout based on complexity
    timeout = model_selection.calculate_timeout(config.timeout, config.complexity)
    
    # Log the model instance details from the agent object
    model_info = "Unknown Model"
    if agent.model:
        if hasattr(agent.model, 'full_model_name'):
            model_info = f"{type(agent.model).__name__}({agent.model.full_model_name})"
        elif hasattr(agent.model, 'model_name'):
            model_info = f"{type(agent.model).__name__}({agent.model.model_name})"
        else:
            model_info = type(agent.model).__name__
    
    logger.info(f"Running {agent.name} synchronously with model {model_info}, timeout {timeout}s")
    
    try:
        # Generate trace ID for logging
        trace_id = gen_trace_id()
        
        # Use trace for consistent tracing
        with trace(f"{agent.name} Sync", trace_id=trace_id):
            # Run the agent synchronously without timeout parameter
            result = Runner.run_sync(agent, input=input_data)
            logger.info(f"Agent {agent.name} completed successfully (sync)")
            return result
    finally:
        # Restore only model_kwargs
        agent.model_kwargs = original_model_kwargs

async def run_agent_with_streaming(
    agent: Agent,
    input_data: Union[str, dict],
    progress_callback: Callable[[str, str, Any], None],
    config: RunConfig = None,
    model_selection: ModelSelectionStrategy = None
) -> Any:
    """
    Run an agent with streaming support for real-time feedback.
    
    Args:
        agent: The agent to run
        input_data: The input data (string or dict)
        progress_callback: Callback function for progress updates with parameters:
                          (stage, status, data)
        config: Run configuration
        model_selection: Optional model selection strategy
        
    Returns:
        The agent's final result
    """
    # Use default config if not provided
    config = config or RunConfig()
    
    # Convert dict to JSON string if needed
    if isinstance(input_data, dict):
        input_data = json.dumps(input_data)
    
    # Create model selection strategy if not provided
    model_selection = model_selection or ModelSelectionStrategy()
    
    # Store original kwargs
    original_model_kwargs = getattr(agent, "model_kwargs", {})
    
    # Update agent configuration based on complexity
    agent_config = {"model_kwargs": original_model_kwargs}
    agent_config = model_selection.update_tool_choice(agent_config, config.complexity)
    agent.model_kwargs = agent_config["model_kwargs"]
    
    # Calculate timeout based on complexity
    timeout = model_selection.calculate_timeout(config.timeout, config.complexity)
    
    # Log the model instance details from the agent object
    model_info = "Unknown Model"
    if agent.model:
        if hasattr(agent.model, 'full_model_name'):
            model_info = f"{type(agent.model).__name__}({agent.model.full_model_name})"
        elif hasattr(agent.model, 'model_name'):
            model_info = f"{type(agent.model).__name__}({agent.model.model_name})"
        else:
            model_info = type(agent.model).__name__
    
    logger.info(f"Running {agent.name} with streaming using model {model_info}, timeout {timeout}s")
    
    # Generate trace ID for consistent correlation
    trace_id = gen_trace_id()
    
    # Call progress callback with initialized state
    progress_callback("initialize", "starting", {
        "agent": agent.name,
        "model": model_info,
        "trace_id": trace_id,
        "timestamp": datetime.datetime.now().isoformat(),
    })
    
    try:
        # Use trace for consistent tracing
        with trace(f"{agent.name} Streaming", trace_id=trace_id):
            # Create a run iterator
            run = Runner.run_stream(agent, input=input_data)
            
            # Initialize result to None, will be updated on completion
            result = None
            
            # Process streaming items as they arrive
            async for event in run:
                # Extract message type and data
                event_type = "unknown"
                event_data = None
                
                if isinstance(event, RunItem):
                    event_type = event.item_type
                    event_data = event.content
                    
                    # Handle Thought events with special parsing
                    if event_type == "thought":
                        # Progress callback for thought events
                        progress_callback("thinking", "in_progress", {
                            "thought": event_data,
                            "timestamp": datetime.datetime.now().isoformat(),
                        })
                    
                    # Handle Action events
                    elif event_type == "action":
                        # Progress callback for action events
                        progress_callback("action", "in_progress", {
                            "action": event_data,
                            "timestamp": datetime.datetime.now().isoformat(),
                        })
                        
                    # Handle ActionOutput events
                    elif event_type == "action_output":
                        # Progress callback for action output events
                        progress_callback("action_output", "in_progress", {
                            "output": event_data,
                            "timestamp": datetime.datetime.now().isoformat(),
                        })
                        
                    # Handle other item types
                    else:
                        # Generic progress callback
                        progress_callback(event_type, "in_progress", {
                            "content": event_data,
                            "timestamp": datetime.datetime.now().isoformat(),
                        })
                
                # Handle final result
                elif isinstance(event, RunResult):
                    result = event
                    # Save result for return
                    logger.info(f"Agent {agent.name} completed with streaming result")
                    
                    # Progress callback for completion
                    progress_callback("complete", "success", {
                        "result": str(result.final_output)[:1000],  # First 1000 chars
                        "timestamp": datetime.datetime.now().isoformat(),
                    })
            
            return result
            
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(f"Agent {agent.name} streaming failed: {error_type}: {error_msg}")
        
        # Progress callback for error
        progress_callback("error", "failed", {
            "error_type": error_type,
            "error_message": error_msg,
            "timestamp": datetime.datetime.now().isoformat(),
        })
        
        # Re-raise the exception
        raise
        
    finally:
        # Restore original settings in finally block for safety
        agent.model_kwargs = original_model_kwargs

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