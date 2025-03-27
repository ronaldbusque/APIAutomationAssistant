"""
Generation API - Endpoints for generating API tests

This module provides API endpoints for test generation from OpenAPI specs.
"""

import asyncio
import json
import uuid
import logging
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..agents.test_generation import process_openapi_spec, generate_test_scripts
from ..blueprint.validation import validate_and_clean_blueprint as validate_blueprint
from ..errors.exceptions import (
    APITestGenerationError, SpecValidationError, 
    BlueprintGenerationError, ScriptGenerationError
)
from ..utils.execution import create_run_context

# Create the logger
logger = logging.getLogger(__name__)

# Define request and response models
class GenerateBlueprintRequest(BaseModel):
    """Request model for blueprint generation."""
    spec: str = Field(..., description="OpenAPI spec (YAML or JSON format)")
    mode: str = Field("basic", description="Mode ('basic' or 'advanced')")
    business_rules: Optional[str] = Field(None, description="Business rules (for advanced mode)")
    test_data: Optional[str] = Field(None, description="Test data setup (for advanced mode)")
    test_flow: Optional[str] = Field(None, description="Test flow (for advanced mode)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "spec": "openapi: 3.0.0\ninfo:\n  title: Example API\n  version: 1.0.0\npaths:\n  /users:\n    get:\n      summary: Get users\n      responses:\n        '200':\n          description: Successful response",
                "mode": "basic"
            }
        }

class GenerateScriptsRequest(BaseModel):
    """Request model for script generation."""
    blueprint: Dict[str, Any] = Field(..., description="Test blueprint to generate scripts from")
    targets: List[str] = Field(..., description="Target frameworks (e.g., ['postman', 'playwright'])")
    
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
                "targets": ["postman", "playwright"]
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
    request: GenerateBlueprintRequest
):
    """
    Background task for blueprint generation.
    
    Args:
        job_id: Job ID
        request: Blueprint generation request
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
        
        # Set up progress callback with more granular updates
        async def progress_callback(stage, progress, agent):
            # Extract trace_id if available
            trace_id = None
            if isinstance(progress, dict) and "trace_id" in progress:
                trace_id = progress.get("trace_id")
            
            # Create a more descriptive message
            message = progress.get("message", "Processing") if isinstance(progress, dict) else str(progress)[:150]
            
            # Determine percentage based on stage and content
            percent = 0
            if stage == "initializing":
                percent = 10
                message = "Setting up blueprint generation environment..."
            elif stage == "planning":
                # Increment percent gradually during planning stage
                old_percent = job_progress[job_id].get("percent", 10)
                # Ensure we're always making forward progress but not jumping to 100%
                percent = min(90, old_percent + 5)
                
                if not message.startswith("Planning"):
                    message = f"Analyzing API endpoints: {message}"
            
            # Update progress
            job_progress[job_id] = {
                "stage": stage,
                "percent": percent,
                "message": message,
                "agent": agent,
                "trace_id": trace_id
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
        
        # Generate blueprint
        blueprint, trace_id = await process_openapi_spec(
            request.spec,
            request.mode,
            request.business_rules,
            request.test_data,
            request.test_flow,
            progress_callback
        )
        
        # Store result
        job_results[job_id] = {
            "blueprint": blueprint,
            "trace_id": trace_id
        }
        
        # Update job status
        active_jobs[job_id] = "completed"
        job_progress[job_id] = {
            "stage": "completed",
            "percent": 100,
            "message": "Blueprint generation successfully completed. Ready for review!",
            "agent": "system"
        }
        
        # Send completion to WebSocket if connected
        if job_id in websocket_connections:
            try:
                await websocket_connections[job_id].send_json({
                    "type": "completed",
                    "job_id": job_id,
                    "result": job_results[job_id]
                })
            except Exception as ws_error:
                logger.error(f"WebSocket error: {str(ws_error)}")
            
    except Exception as e:
        # Log the error
        logger.error(f"Job {job_id} failed: {str(e)}")
        
        # Update job status
        active_jobs[job_id] = "failed"
        job_progress[job_id] = {
            "stage": "failed",
            "percent": 0,
            "message": f"Error: {str(e)}"
        }
        
        # Store error
        job_results[job_id] = {
            "error": str(e),
            "error_type": type(e).__name__,
            "trace_id": getattr(e, "trace_id", None)
        }
        
        # Send error to WebSocket if connected
        if job_id in websocket_connections:
            try:
                await websocket_connections[job_id].send_json({
                    "type": "error",
                    "job_id": job_id,
                    "error": str(e)
                })
            except Exception as ws_error:
                logger.error(f"WebSocket error: {str(ws_error)}")

async def generate_scripts_background(
    job_id: str,
    request: GenerateScriptsRequest
):
    """
    Background task for script generation.
    
    Args:
        job_id: Job ID
        request: Script generation request
    """
    try:
        # Update job status
        active_jobs[job_id] = "processing"
        
        # Initialize progress
        job_progress[job_id] = {
            "stage": "initializing",
            "percent": 0,
            "message": "Starting script generation for your API endpoints...",
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
        
        # Set up progress callback with more granular updates
        async def progress_callback(stage, progress, agent):
            # Extract trace_id if available
            trace_id = None
            if isinstance(progress, dict) and "trace_id" in progress:
                trace_id = progress.get("trace_id")
            
            # Create a more descriptive message
            message = progress.get("message", "Processing") if isinstance(progress, dict) else str(progress)[:150]
            
            # Determine percentage based on stage and content
            percent = 0
            if stage == "initializing":
                percent = 10
                message = "Setting up test generation environment..."
            elif stage == "planning":
                # During planning stage (40% of progress)
                old_percent = job_progress[job_id].get("percent", 10)
                # Ensure we're making forward progress but not jumping too far
                percent = min(40, old_percent + 5)
                
                if not message.startswith("Planning"):
                    message = f"Planning test structure: {message}"
            elif stage == "coding":
                # During coding stage (41-90% of progress)
                old_percent = job_progress[job_id].get("percent", 40)
                # Ensure we're making forward progress
                percent = min(90, max(41, old_percent + 5))
                
                if not message.startswith("Generating"):
                    message = f"Generating test code: {message}"
            
            # Update progress
            job_progress[job_id] = {
                "stage": stage,
                "percent": percent,
                "message": message,
                "agent": agent,
                "trace_id": trace_id
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
        
        # Generate scripts - use try/except to ensure we always get some output
        try:
            scripts, trace_id = await generate_test_scripts(
                request.blueprint,
                request.targets,
                progress_callback
            )
            
            # Log success
            logger.info(f"Script generation completed successfully for job {job_id}")
            
        except Exception as gen_error:
            logger.error(f"Error during script generation for job {job_id}: {str(gen_error)}")
            
            # Try to generate minimal scripts as fallback
            logger.info(f"Attempting to generate minimal scripts as fallback for job {job_id}")
            
            # Create minimal outputs for each target
            scripts = {}
            for target in request.targets:
                scripts[target] = {
                    f"minimal_{target}_tests.txt": f"// Minimal tests for {target}\n// Error occurred: {str(gen_error)}\n\n// Original blueprint API name: {request.blueprint.get('apiName', 'Unknown')}"
                }
            
            # Generate a trace ID for tracking
            trace_id = f"error-{uuid.uuid4()}"
        
        # Log script structure before storing
        logger.info(f"Scripts generated with types: {list(scripts.keys())}")
        for script_type, files in scripts.items():
            logger.info(f"Script type {script_type} contains {len(files)} files:")
            for filename in files.keys():
                file_size = len(files[filename]) if isinstance(files[filename], str) else 'Non-string content'
                logger.info(f"  - {filename} (size: {file_size})")
        
        # Store result
        job_results[job_id] = {
            "blueprint": request.blueprint,
            "scripts": scripts,
            "trace_id": trace_id
        }
        
        # Log result structure sent to client
        logger.info(f"Result keys: {list(job_results[job_id].keys())}")
        logger.info(f"Scripts result structure: {json.dumps({k: list(v.keys()) for k, v in scripts.items()})}")
        
        # Update job status
        active_jobs[job_id] = "completed"
        job_progress[job_id] = {
            "stage": "completed",
            "percent": 100,
            "message": "Script generation successfully completed. Your test scripts are ready!",
            "agent": "system",
            "trace_id": trace_id
        }
        
        # Send completion to WebSocket if connected
        if job_id in websocket_connections:
            try:
                await websocket_connections[job_id].send_json({
                    "type": "completed",
                    "job_id": job_id,
                    "result": job_results[job_id]
                })
            except Exception as ws_error:
                logger.error(f"WebSocket error: {str(ws_error)}")
            
    except Exception as e:
        # Log the error
        logger.error(f"Job {job_id} failed: {str(e)}")
        
        # Update job status
        active_jobs[job_id] = "failed"
        job_progress[job_id] = {
            "stage": "failed",
            "percent": 0,
            "message": f"Error: {str(e)}"
        }
        
        # Store error
        job_results[job_id] = {
            "error": str(e),
            "error_type": type(e).__name__,
            "trace_id": getattr(e, "trace_id", None),
            "blueprint": request.blueprint  # Include the blueprint for reference
        }
        
        # Send error to WebSocket if connected
        if job_id in websocket_connections:
            try:
                await websocket_connections[job_id].send_json({
                    "type": "error",
                    "job_id": job_id,
                    "error": str(e)
                })
            except Exception as ws_error:
                logger.error(f"WebSocket error: {str(ws_error)}")

def create_api_router(app: FastAPI = None):
    """
    Create the API router for test generation.
    
    Args:
        app: Optional FastAPI app to add routes to
        
    Returns:
        FastAPI router or app with routes added
    """
    if app is None:
        from fastapi import APIRouter
        app = APIRouter()
    
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
        # Validate request
        if not request.spec:
            raise HTTPException(status_code=400, detail="OpenAPI spec is required")
        
        # Create job ID
        job_id = str(uuid.uuid4())
        
        # Add job to active jobs
        active_jobs[job_id] = "queued"
        
        # Create run context
        context = create_run_context({"source": "api", "operation": "blueprint"})
        logger.info(f"Starting blueprint generation job {job_id} with context: {context}")
        
        # Start background task
        background_tasks.add_task(generate_blueprint_background, job_id, request)
        
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
        # Validate request
        if not request.blueprint:
            raise HTTPException(status_code=400, detail="Blueprint is required")
        if not request.targets:
            raise HTTPException(status_code=400, detail="At least one target is required")
        
        # Create job ID
        job_id = str(uuid.uuid4())
        
        # Add job to active jobs
        active_jobs[job_id] = "queued"
        
        # Create run context
        context = create_run_context({"source": "api", "operation": "scripts"})
        logger.info(f"Starting script generation job {job_id} with context: {context}")
        
        # Start background task
        background_tasks.add_task(generate_scripts_background, job_id, request)
        
        return {"job_id": job_id}
    
    @app.get("/status/{job_id}", response_model=JobStatusResponse)
    async def get_job_status(job_id: str):
        """
        Get the status of a generation job.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job status response
        """
        # Check if job exists
        if job_id not in active_jobs:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        # Get job status
        status = active_jobs[job_id]
        progress = job_progress.get(job_id)
        result = job_results.get(job_id)
        
        # Build response
        response = JobStatusResponse(
            job_id=job_id,
            status=status,
            progress=progress,
            result=result if status == "completed" else None,
            error=result.get("error") if status == "failed" and result else None
        )
        
        return response
    
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
    
    return app 