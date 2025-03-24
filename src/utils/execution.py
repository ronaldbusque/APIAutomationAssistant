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
                 task: str = "general"):
        self.timeout = timeout
        self.complexity = complexity
        self.task = task

async def run_agent_with_retry(
    agent: Agent, 
    input_data: Union[str, dict], 
    config: RetryConfig = None,
    complexity: float = 0.5,
    task: str = "general",
    model_selection: ModelSelectionStrategy = None
) -> Tuple[Any, str]:
    """
    Run an agent with retry logic and error handling.
    
    Args:
        agent: The agent to run
        input_data: The input data (string or dict)
        config: Retry configuration
        complexity: Task complexity (0-1) to determine model
        task: Task type for model selection
        model_selection: Optional model selection strategy
        
    Returns:
        Tuple of (result, trace_id)
    """
    # Use default config if not provided
    config = config or RetryConfig()
    
    # Convert dict to JSON string if needed
    if isinstance(input_data, dict):
        input_data = json.dumps(input_data)
    
    # Create model selection strategy if not provided
    model_selection = model_selection or ModelSelectionStrategy()
    
    # Select model based on task and complexity
    original_model = agent.model
    selected_model = model_selection.select_model(task, complexity)
    agent.model = selected_model
    
    # Update agent configuration based on complexity
    original_model_kwargs = getattr(agent, "model_kwargs", {})
    agent_config = {"model_kwargs": original_model_kwargs}
    agent_config = model_selection.update_tool_choice(agent_config, complexity)
    agent.model_kwargs = agent_config["model_kwargs"]
    
    # Calculate timeout based on complexity
    timeout = model_selection.calculate_timeout(config.base_timeout, complexity)
    
    # Generate trace ID
    trace_id = gen_trace_id()
    
    logger.info(f"Running {agent.name} with model {selected_model}, timeout {timeout}s, complexity {complexity:.2f}")
    
    with trace(f"{agent.name} Execution", trace_id=trace_id):
        for attempt in range(config.max_retries):
            try:
                logger.info(f"Attempt {attempt+1}/{config.max_retries} for {agent.name}")
                
                # Run the agent without timeout parameter (removed to fix compatibility issue)
                result = await Runner.run(agent, input=input_data)
                logger.info(f"Agent {agent.name} completed successfully")
                
                # Restore original model and configuration
                agent.model = original_model
                agent.model_kwargs = original_model_kwargs
                
                return result, trace_id
                
            except Exception as e:
                error_type = type(e).__name__
                logger.error(f"Agent {agent.name} failed with {error_type}: {str(e)}")
                
                if attempt == config.max_retries - 1:  # Last attempt
                    logger.error(f"All {config.max_retries} attempts failed for {agent.name}")
                    # Restore original model and configuration
                    agent.model = original_model
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
    
    # Select model based on task and complexity
    original_model = agent.model
    selected_model = model_selection.select_model(config.task, config.complexity)
    agent.model = selected_model
    
    # Update agent configuration based on complexity
    original_model_kwargs = getattr(agent, "model_kwargs", {})
    agent_config = {"model_kwargs": original_model_kwargs}
    agent_config = model_selection.update_tool_choice(agent_config, config.complexity)
    agent.model_kwargs = agent_config["model_kwargs"]
    
    # Calculate timeout based on complexity
    timeout = model_selection.calculate_timeout(config.timeout, config.complexity)
    
    logger.info(f"Running {agent.name} synchronously with model {selected_model}, timeout {timeout}s")
    
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
        # Restore original model and configuration
        agent.model = original_model
        agent.model_kwargs = original_model_kwargs

async def run_agent_with_streaming(
    agent: Agent,
    input_data: Union[str, dict],
    progress_callback: Callable[[str, str, Any], None],
    config: RunConfig = None,
    model_selection: ModelSelectionStrategy = None
) -> Any:
    """
    Run an agent with streaming updates for real-time progress.
    
    Args:
        agent: The agent to run
        input_data: The input data (string or dict)
        progress_callback: Callback function for progress updates (agent_name, item_type, content)
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
    
    # Select model based on task and complexity
    original_model = agent.model
    selected_model = model_selection.select_model(config.task, config.complexity)
    agent.model = selected_model
    
    # Update agent configuration based on complexity
    original_model_kwargs = getattr(agent, "model_kwargs", {})
    agent_config = {"model_kwargs": original_model_kwargs}
    agent_config = model_selection.update_tool_choice(agent_config, config.complexity)
    agent.model_kwargs = agent_config["model_kwargs"]
    
    # Calculate timeout based on complexity
    timeout = model_selection.calculate_timeout(config.timeout, config.complexity)
    
    logger.info(f"Running streaming agent {agent.name} with model {selected_model}, timeout {timeout}s")
    
    # Generate trace ID for monitoring
    trace_id = gen_trace_id()
    
    with trace(f"{agent.name} Streaming", trace_id=trace_id):
        try:
            # Start streaming run (removed timeout parameter that causes errors)
            result = Runner.run_streamed(agent, input=input_data)
            
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
                    elif isinstance(event, RunItem):
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
            
            # Restore original model and configuration
            agent.model = original_model
            agent.model_kwargs = original_model_kwargs
            
            return result.final_output
            
        except asyncio.TimeoutError:
            error_msg = f"Agent {agent.name} streaming timed out after {timeout} seconds"
            logger.error(error_msg)
            agent.model = original_model
            agent.model_kwargs = original_model_kwargs
            raise TimeoutError(error_msg)
        except Exception as e:
            error_type = type(e).__name__
            logger.error(f"Agent {agent.name} streaming failed with {error_type}: {str(e)}")
            # Restore original model and configuration
            agent.model = original_model
            agent.model_kwargs = original_model_kwargs
            raise

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