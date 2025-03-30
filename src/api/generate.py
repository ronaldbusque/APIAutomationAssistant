"""
Generation API - Endpoints for generating API tests

This module provides API endpoints for test generation from OpenAPI specs.
"""

import asyncio
import json
import uuid
import logging
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..errors.exceptions import (
    APITestGenerationError, SpecValidationError, 
    BlueprintGenerationError, ScriptGenerationError
)
from ..utils.execution import create_run_context
from ..agents.autonomous import (
    analyze_initial_spec, run_autonomous_blueprint_pipeline,
    run_autonomous_script_pipeline
)

# Create the logger
logger = logging.getLogger(__name__)

# Define request and response models
class GenerateBlueprintRequest(BaseModel):
    """Request model for blueprint generation."""
    spec: str = Field(..., description="OpenAPI spec (YAML or JSON format)")
    business_rules: Optional[str] = Field(None, description="Optional: Business rules to consider during generation")
    test_data: Optional[str] = Field(None, description="Optional: Test data setup considerations")
    test_flow: Optional[str] = Field(None, description="Optional: High-level desired test flow overview/sequence")
    max_iterations: Optional[int] = Field(3, description="Max refinement iterations for blueprint (default: 3)", ge=1, le=10)
    
    class Config:
        json_schema_extra = {
            "example": {
                "spec": "openapi: 3.0.0\ninfo:\n  title: Example API\n  version: 1.0.0\npaths:\n  /users:\n    get:\n      summary: Get users\n      responses:\n        '200':\n          description: Successful response",
                "max_iterations": 2,
                "business_rules": "Users under 18 should not be allowed to create premium orders."
            }
        }

class GenerateScriptsRequest(BaseModel):
    """Request model for script generation."""
    blueprint: Dict[str, Any] = Field(..., description="Test blueprint to generate scripts from")
    targets: List[str] = Field(..., description="Target frameworks (e.g., ['postman', 'playwright'])")
    max_iterations: Optional[int] = Field(None, description="Max refinement iterations for script generation (default: 3)", ge=1, le=10)
    
    class Config:
        json_schema_extra = {
            "example": {
                "blueprint": {
                    "apiName": "Example API",
                    "version": "1.0.0",
                    "groups": [
                        {
                            "name": "Users",
                            "tests": [
                                {
                                    "id": "get-users",
                                    "name": "Get users",
                                    "endpoint": "/users",
                                    "method": "GET",
                                    "expectedStatus": 200
                                }
                            ]
                        }
                    ]
                },
                "targets": ["postman", "playwright"],
                "max_iterations": 3
            }
        }

class JobStatusResponse(BaseModel):
    """Response model for job status."""
    job_id: str
    status: str = Field(..., description="Job status ('queued', 'processing', 'completed', 'failed')")
    progress: Optional[Dict[str, Any]] = Field(None, description="Job progress information")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result (when completed)")
    error: Optional[str] = Field(None, description="Error message (when failed)")

# Job storage
active_jobs = {}
job_results = {}
job_progress = {}
websocket_connections = {}

async def generate_blueprint_background(
    job_id: str,
    request: GenerateBlueprintRequest,
    max_blueprint_iterations: Optional[int] = None,
    business_rules: Optional[str] = None,
    test_data: Optional[str] = None,
    test_flow: Optional[str] = None
):
    """
    Background task for blueprint generation.
    
    Args:
        job_id: Job ID
        request: Blueprint generation request
        max_blueprint_iterations: Maximum iterations for blueprint generation
        business_rules: Business rules to consider during generation
        test_data: Test data setup considerations
        test_flow: High-level desired test flow overview/sequence
    """
    try:
        # Update job status
        active_jobs[job_id] = "processing"
        
        # Initialize progress
        job_progress[job_id] = {
            "stage": "initializing",
            "percent": 0,
            "message": "Analyzing OpenAPI specification and preparing test blueprint...",
            "agent": "system"
        }
        
        # Send initial progress update via WebSocket if connected
        if job_id in websocket_connections:
            try:
                await websocket_connections[job_id].send_json({
                    "type": "progress",
                    "job_id": job_id,
                    "progress": job_progress[job_id]
                })
            except Exception as ws_error:
                logger.error(f"WebSocket error: {str(ws_error)}")
        
        # Set up progress callback wrapper
        async def progress_callback_wrapper(stage, progress, agent):
            # Extract trace_id if available
            trace_id = None
            if isinstance(progress, dict) and "trace_id" in progress:
                trace_id = progress.get("trace_id")
            
            # Create a more descriptive message
            message = progress.get("message", "Processing") if isinstance(progress, dict) else str(progress)[:150]
            
            # Determine percentage based on stage and content
            percent = 0
            if stage == "spec_analysis":
                percent = 10
                message = f"Analyzing spec: {message}"
            elif stage == "blueprint_authoring":
                old_percent = job_progress[job_id].get("percent", 10)
                percent = min(50, old_percent + 5)
                message = f"Authoring blueprint: {message}"
            elif stage == "blueprint_reviewing":
                old_percent = job_progress[job_id].get("percent", 50)
                percent = min(90, old_percent + 5)
                message = f"Reviewing blueprint: {message}"
            elif stage == "blueprint_complete":
                percent = 100
                message = "Blueprint generation complete!"
            
            # For reporting to the UI, use a consistent stage name
            reported_stage = "planning"
            
            # Update progress
            job_progress[job_id] = {
                "stage": reported_stage,
                "percent": percent,
                "message": message,
                "agent": agent,
                "trace_id": trace_id,
                "autonomous_stage": stage
            }
            
            # Send progress to WebSocket if connected
            if job_id in websocket_connections:
                try:
                    await websocket_connections[job_id].send_json({
                        "type": "progress",
                        "job_id": job_id,
                        "progress": job_progress[job_id]
                    })
                    # Add a small delay to prevent message flooding
                    await asyncio.sleep(0.1)
                except Exception as ws_error:
                    logger.error(f"WebSocket error: {str(ws_error)}")
        
        # Generate blueprint using autonomous pipeline
        logger.info(f"Starting blueprint generation for job {job_id}")
        
        # First analyze the spec
        await progress_callback_wrapper("spec_analysis", {"percent": 5, "message": "Analyzing specification..."}, "System")
        spec_analysis, spec_warnings = await analyze_initial_spec(request.spec)
        
        # Start the autonomous pipeline
        await progress_callback_wrapper("blueprint_authoring", {"percent": 10, "message": "Starting generation loop..."}, "System")
        from ..config.settings import settings
        
        # Use max_iterations from request or settings
        iterations_to_use = max_blueprint_iterations or request.max_iterations or settings.get("AUTONOMOUS_MAX_ITERATIONS", 3)
        
        # Log debug info for advanced context
        logger.debug(f"Received business rules: {'Yes' if business_rules else 'No'}")
        logger.debug(f"Received test data guidance: {'Yes' if test_data else 'No'}")
        logger.debug(f"Received test flow guidance: {'Yes' if test_flow else 'No'}")
        
        blueprint_dict = await run_autonomous_blueprint_pipeline(
            spec_analysis=spec_analysis,
            progress_callback=progress_callback_wrapper,
            max_iterations=iterations_to_use,
            # Pass the advanced context arguments
            business_rules=business_rules,
            test_data=test_data,
            test_flow=test_flow
        )
        
        trace_id = f"autonomous_bp_{job_id}"
        logger.info(f"Blueprint generation complete for job {job_id}")
        
        # Store result
        job_results[job_id] = {
            "blueprint": blueprint_dict.get("blueprint"),
            "trace_id": trace_id,
            "final_status": {
                "approved": blueprint_dict.get("approved"),
                "max_iterations_reached": blueprint_dict.get("max_iterations_reached"),
                "final_feedback": blueprint_dict.get("final_feedback")
            }
        }
        
        # Update job status
        active_jobs[job_id] = "completed"
        
        # Send final progress update
        job_progress[job_id] = {
            "stage": "planning",
            "percent": 100,
            "message": "Blueprint generation complete!",
            "agent": "system",
            "trace_id": trace_id
        }
        
        # Send final progress update via WebSocket if connected
        if job_id in websocket_connections:
            try:
                await websocket_connections[job_id].send_json({
                    "type": "progress",
                    "job_id": job_id,
                    "progress": job_progress[job_id]
                })
                
                # Also send a result update
                await websocket_connections[job_id].send_json({
                    "type": "result",
                    "job_id": job_id,
                    "result": job_results[job_id]
                })
            except Exception as ws_error:
                logger.error(f"WebSocket error: {str(ws_error)}")
    
    except SpecValidationError as e:
        logger.error(f"Spec validation error for job {job_id}: {str(e)}")
        active_jobs[job_id] = "failed"
        job_results[job_id] = {"error": f"Spec validation error: {str(e)}"}
    except BlueprintGenerationError as e:
        logger.error(f"Blueprint generation error for job {job_id}: {str(e)}")
        active_jobs[job_id] = "failed"
        job_results[job_id] = {"error": f"Blueprint generation error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error for job {job_id}: {str(e)}", exc_info=True)
        active_jobs[job_id] = "failed"
        job_results[job_id] = {"error": f"Unexpected error: {str(e)}"}

async def generate_scripts_background(
    job_id: str,
    request: GenerateScriptsRequest,
    max_script_iterations: Optional[int] = None
):
    """
    Background task for script generation.
    
    Args:
        job_id: Job ID
        request: Scripts generation request
        max_script_iterations: Maximum iterations for script generation
    """
    try:
        # Update job status
        active_jobs[job_id] = "processing"
        
        # Initialize progress
        job_progress[job_id] = {
            "stage": "initializing",
            "percent": 0,
            "message": "Preparing to generate test scripts...",
            "agent": "system"
        }
        
        # Send initial progress update via WebSocket if connected
        if job_id in websocket_connections:
            try:
                await websocket_connections[job_id].send_json({
                    "type": "progress",
                    "job_id": job_id,
                    "progress": job_progress[job_id]
                })
            except Exception as ws_error:
                logger.error(f"WebSocket error: {str(ws_error)}")
        
        # Set up progress callback wrapper
        async def progress_callback_wrapper(stage, progress, agent):
            # Extract trace_id if available
            trace_id = None
            if isinstance(progress, dict) and "trace_id" in progress:
                trace_id = progress.get("trace_id")
            
            # Create a more descriptive message
            message = progress.get("message", "Processing") if isinstance(progress, dict) else str(progress)[:150]
            
            # Determine percentage based on stage and content
            percent = 0
            if stage == "script_coding":
                old_percent = job_progress[job_id].get("percent", 10)
                percent = min(50, old_percent + 5)
                message = f"Generating code: {message}"
            elif stage == "script_reviewing":
                old_percent = job_progress[job_id].get("percent", 50)
                percent = min(90, old_percent + 5)
                message = f"Reviewing code: {message}"
            elif stage == "script_complete":
                percent = 100
                message = "Code generation complete!"
            else:
                # For other stages, just increment
                old_percent = job_progress[job_id].get("percent", 0)
                percent = min(95, old_percent + 5)
            
            # For reporting to the UI, use a consistent stage name
            reported_stage = "coding"
            
            # Update progress
            job_progress[job_id] = {
                "stage": reported_stage,
                "percent": percent,
                "message": message,
                "agent": agent,
                "trace_id": trace_id,
                "autonomous_stage": stage,
                "target": getattr(progress, "target", None)
            }
            
            # Send progress to WebSocket if connected
            if job_id in websocket_connections:
                try:
                    await websocket_connections[job_id].send_json({
                        "type": "progress",
                        "job_id": job_id,
                        "progress": job_progress[job_id]
                    })
                    # Add a small delay to prevent message flooding
                    await asyncio.sleep(0.1)
                except Exception as ws_error:
                    logger.error(f"WebSocket error: {str(ws_error)}")
        
        # Generate scripts for each target using the autonomous pipeline
        logger.info(f"Starting script generation for job {job_id}")
        
        # Use max_iterations from request or settings
        from ..config.settings import settings
        iterations_to_use = max_script_iterations or request.max_iterations or settings.get("AUTONOMOUS_MAX_ITERATIONS", 3)
        
        # Store results for each target
        results = {}
        trace_ids = {}
        
        # Check if blueprint is valid
        import json
        if isinstance(request.blueprint, str):
            try:
                blueprint_dict = json.loads(request.blueprint)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid blueprint JSON: {str(e)}")
        else:
            blueprint_dict = request.blueprint
        
        # Process each target
        for target in request.targets:
            logger.info(f"Generating scripts for target {target}")
            
            try:
                # Update progress for this target
                await progress_callback_wrapper("initializing", {
                    "message": f"Initializing script generation for {target}",
                    "target": target
                }, "system")
                
                # Run the autonomous script pipeline
                script_files_list = await run_autonomous_script_pipeline(
                    blueprint=blueprint_dict,
                    framework=target,
                    progress_callback=progress_callback_wrapper,
                    max_iterations=iterations_to_use
                )
                
                # Convert the list of file objects into an object map {filename: content}
                script_files_map = {
                    file_obj["filename"]: file_obj["content"]
                    for file_obj in script_files_list
                    if "filename" in file_obj and "content" in file_obj # Basic validation
                }
                
                # Store result for this target
                trace_id = f"autonomous_script_{job_id}_{target}"
                results[target] = script_files_map
                trace_ids[target] = trace_id
                
                logger.info(f"Script generation for target {target} complete: {len(script_files_map)} files generated")
            except Exception as e:
                logger.error(f"Error generating scripts for target {target}: {str(e)}")
                results[target] = {"error": str(e)}
                trace_ids[target] = f"error_{job_id}_{target}"
        
        # Store overall results
        job_results[job_id] = {
            "scripts": results,
            "trace_ids": trace_ids
        }
        
        # Update job status
        active_jobs[job_id] = "completed"
        
        # Send final progress update
        job_progress[job_id] = {
            "stage": "coding",
            "percent": 100,
            "message": "Script generation complete!",
            "agent": "system"
        }
        
        # Send final progress update via WebSocket if connected
        if job_id in websocket_connections:
            try:
                await websocket_connections[job_id].send_json({
                    "type": "progress",
                    "job_id": job_id,
                    "progress": job_progress[job_id]
                })
                
                # Also send a result update
                await websocket_connections[job_id].send_json({
                    "type": "result",
                    "job_id": job_id,
                    "result": job_results[job_id]
                })
            except Exception as ws_error:
                logger.error(f"WebSocket error: {str(ws_error)}")
    
    except Exception as e:
        logger.error(f"Script generation error for job {job_id}: {str(e)}", exc_info=True)
        active_jobs[job_id] = "failed"
        job_results[job_id] = {"error": f"Script generation error: {str(e)}"}

def create_api_router(app: FastAPI = None):
    """
    Create API router and add all routes.
    
    Args:
        app: FastAPI application
        
    Returns:
        Created API router
    """
    if app is None:
        from fastapi import APIRouter
        router = APIRouter()
    else:
        router = app
    
    @app.middleware("http")
    async def suppress_status_logging(request: Request, call_next):
        """Middleware to prevent logging for status poll endpoints."""
        response = await call_next(request)
        return response
    
    @app.post("/generate-blueprint", response_model=Dict[str, str])
    async def generate_blueprint(request: GenerateBlueprintRequest, background_tasks: BackgroundTasks):
        """
        Generate a test blueprint from an OpenAPI spec.
        
        Args:
            request: Blueprint generation request
            background_tasks: FastAPI background tasks
            
        Returns:
            Dictionary with job ID
        """
        job_id = str(uuid.uuid4())
        active_jobs[job_id] = "queued"
        
        # Start background task
        background_tasks.add_task(
            generate_blueprint_background,
            job_id=job_id,
            request=request,
            max_blueprint_iterations=request.max_iterations,
            business_rules=request.business_rules,
            test_data=request.test_data,
            test_flow=request.test_flow
        )
        
        return {"job_id": job_id}
    
    @app.post("/generate-scripts", response_model=Dict[str, str])
    async def generate_scripts(request: GenerateScriptsRequest, background_tasks: BackgroundTasks):
        """
        Generate test scripts from a blueprint.
        
        Args:
            request: Script generation request
            background_tasks: FastAPI background tasks
            
        Returns:
            Dictionary with job ID
        """
        job_id = str(uuid.uuid4())
        active_jobs[job_id] = "queued"
        
        # Start background task
        background_tasks.add_task(
            generate_scripts_background,
            job_id=job_id,
            request=request,
            max_script_iterations=request.max_iterations
        )
        
        return {"job_id": job_id}
    
    @app.get("/status/{job_id}", response_model=JobStatusResponse)
    async def get_job_status(job_id: str):
        """Get the status of a job."""
        # This endpoint is polled frequently, so we need to make it efficient
        # If job not found, return 404
        if job_id not in active_jobs:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        # Return job status
        status = active_jobs.get(job_id, "not_found")
        progress = job_progress.get(job_id, {})
        result = job_results.get(job_id, {})
        error = result.get("error") if status == "failed" else None
        
        return {
            "job_id": job_id,
            "status": status,
            "progress": progress,
            "result": result if status == "completed" else None,
            "error": error,
        }
    
    @app.websocket("/ws/job/{job_id}")
    async def websocket_job_status(websocket: WebSocket, job_id: str):
        """
        WebSocket endpoint for real-time job status updates.
        
        Args:
            websocket: WebSocket connection
            job_id: Job ID
        """
        await websocket.accept()
        
        if job_id not in active_jobs:
            await websocket.send_json({"error": f"Job {job_id} not found"})
            await websocket.close()
            return
        
        # Store WebSocket connection
        websocket_connections[job_id] = websocket
        
        try:
            # Send initial status
            status = active_jobs[job_id]
            progress = job_progress.get(job_id)
            
            await websocket.send_json({
                "type": "status",
                "job_id": job_id,
                "status": status,
                "progress": progress
            })
            
            # If job is already completed or failed, send result or error
            if status == "completed":
                await websocket.send_json({
                    "type": "completed",
                    "job_id": job_id,
                    "result": job_results.get(job_id)
                })
            elif status == "failed":
                await websocket.send_json({
                    "type": "error",
                    "job_id": job_id,
                    "error": job_results.get(job_id, {}).get("error")
                })
            
            # Keep connection open
            while True:
                # Ping to keep connection alive
                await websocket.receive_text()
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for job {job_id}")
        finally:
            # Remove WebSocket connection
            if job_id in websocket_connections:
                del websocket_connections[job_id]
    
    @app.get("/file-content/{job_id}/{target}/{filename:path}")
    async def get_file_content(job_id: str, target: str, filename: str):
        """
        Get the content of a specific generated file.
        
        Args:
            job_id: Job ID
            target: Target framework
            filename: File name/path
            
        Returns:
            File content as text
        """
        # Check if job exists
        if job_id not in active_jobs:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        # Check if job is completed
        if active_jobs[job_id] != "completed":
            raise HTTPException(status_code=400, detail=f"Job {job_id} is not completed")
        
        # Get job result
        result = job_results.get(job_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"No results found for job {job_id}")
        
        # Extract scripts
        scripts = result.get("scripts", {})
        if not scripts:
            raise HTTPException(status_code=404, detail=f"No scripts found in job {job_id}")
        
        # Check if target exists
        if target not in scripts:
            raise HTTPException(status_code=404, detail=f"Target {target} not found in job {job_id}")
        
        # Get target scripts
        target_scripts = scripts[target]
        
        # Handle both array and object formats
        if isinstance(target_scripts, list):
            # If it's a list of filenames, check if the file exists in the list
            if filename not in target_scripts:
                raise HTTPException(status_code=404, detail=f"File {filename} not found in target {target}")
            
            # We need to look up the actual content from somewhere
            # This might mean we need to read from disk if files were saved
            try:
                # Try to read from the output directory
                import os
                from pathlib import Path
                
                # Define the output directory pattern
                output_dir = f"output_{job_id}/{target}"
                file_path = Path(output_dir) / filename
                
                if not file_path.exists():
                    raise FileNotFoundError(f"File {file_path} does not exist on disk")
                
                # Read the file content
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                return content
            except Exception as e:
                logger.error(f"Error reading file {filename} for job {job_id}: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")
        else:
            # If it's a dictionary, check if the file exists
            if filename not in target_scripts:
                raise HTTPException(status_code=404, detail=f"File {filename} not found in target {target}")
            
            # Return the file content
            return target_scripts[filename]
    
    return router 