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
        schema_extra = {
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
        schema_extra = {
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
            "message": "Starting blueprint generation"
        }
        
        # Set up progress callback
        async def progress_callback(stage, progress, agent):
            job_progress[job_id] = {
                "stage": stage,
                "percent": progress.get("percent", 0) if isinstance(progress, dict) else 0,
                "message": progress.get("message", "Processing") if isinstance(progress, dict) else str(progress)[:100]
            }
            
            # Send progress to WebSocket if connected
            if job_id in websocket_connections:
                try:
                    await websocket_connections[job_id].send_json({
                        "type": "progress",
                        "job_id": job_id,
                        "progress": job_progress[job_id]
                    })
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
            "message": "Blueprint generation completed"
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
            "message": "Starting script generation"
        }
        
        # Set up progress callback
        async def progress_callback(stage, progress, agent):
            job_progress[job_id] = {
                "stage": stage,
                "percent": progress.get("percent", 0) if isinstance(progress, dict) else 0,
                "message": progress.get("message", "Processing") if isinstance(progress, dict) else str(progress)[:100]
            }
            
            # Send progress to WebSocket if connected
            if job_id in websocket_connections:
                try:
                    await websocket_connections[job_id].send_json({
                        "type": "progress",
                        "job_id": job_id,
                        "progress": job_progress[job_id]
                    })
                except Exception as ws_error:
                    logger.error(f"WebSocket error: {str(ws_error)}")
        
        # Generate scripts
        scripts = await generate_test_scripts(
            request.blueprint,
            request.targets,
            progress_callback
        )
        
        # Store result
        job_results[job_id] = {
            "blueprint": request.blueprint,
            "scripts": scripts
        }
        
        # Update job status
        active_jobs[job_id] = "completed"
        job_progress[job_id] = {
            "stage": "completed",
            "percent": 100,
            "message": "Script generation completed"
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
    
    return app 