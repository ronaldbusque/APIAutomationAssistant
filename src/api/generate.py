"""
Generation API - Endpoints for generating API tests

This module provides API endpoints for test generation from OpenAPI specs.
"""

import asyncio
import json
import uuid
import logging
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends, Request, Query
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
from .auth import get_current_identifier, AUTH_EXCEPTION

# Create the logger
logger = logging.getLogger(__name__)
# Create audit logger
audit_logger = logging.getLogger("audit")

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
    Create and return API router with all endpoints.
    
    Args:
        app: Optional FastAPI app to configure
    
    Returns:
        FastAPI router
    """
    from fastapi import APIRouter
    
    # Create router with prefix
    router = APIRouter(
        prefix="/api/v1",
        tags=["Generation"]
    )

    @router.post("/generate-blueprint", response_model=Dict[str, str])
    async def generate_blueprint(
        request: GenerateBlueprintRequest, 
        background_tasks: BackgroundTasks,
        identifier: str = Depends(get_current_identifier)  # Add authentication dependency
    ):
        """
        Generate a test blueprint from an OpenAPI specification.
        
        This endpoint accepts an OpenAPI spec and additional parameters to
        generate a comprehensive test blueprint. The generation process
        runs asynchronously and returns a job ID for status tracking.
        """
        try:
            job_id = str(uuid.uuid4())
            active_jobs[job_id] = "queued"
            
            # Log the audit event BEFORE starting the task
            log_details = {"job_id": job_id, "type": "blueprint"}
            audit_logger.info(
                f"Action='generate_start' Details={json.dumps(log_details)}",
                extra={'identifier': identifier}
            )
            
            # Add job to background tasks
            background_tasks.add_task(
                generate_blueprint_background,
                job_id=job_id,
                request=request,
                max_blueprint_iterations=request.max_iterations,
                business_rules=request.business_rules,
                test_data=request.test_data,
                test_flow=request.test_flow
            )
            
            logger.info(f"Blueprint generation job queued with ID: {job_id}")
            return {"job_id": job_id}
            
        except Exception as e:
            logger.error(f"Failed to queue blueprint generation job: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to queue job: {str(e)}")

    @router.post("/generate-scripts", response_model=Dict[str, str])
    async def generate_scripts(
        request: GenerateScriptsRequest, 
        background_tasks: BackgroundTasks,
        identifier: str = Depends(get_current_identifier)  # Add authentication dependency
    ):
        """
        Generate test scripts from a test blueprint.
        
        This endpoint accepts a test blueprint and generates executable test scripts
        in the specified target frameworks. The generation process runs asynchronously
        and returns a job ID for status tracking.
        """
        try:
            job_id = str(uuid.uuid4())
            active_jobs[job_id] = "queued"
            
            # Log the audit event
            log_details = {"job_id": job_id, "type": "scripts", "targets": request.targets}
            audit_logger.info(
                f"Action='generate_start' Details={json.dumps(log_details)}",
                extra={'identifier': identifier}
            )
            
            # Add job to background tasks
            background_tasks.add_task(
                generate_scripts_background,
                job_id=job_id,
                request=request,
                max_script_iterations=request.max_iterations
            )
            
            logger.info(f"Script generation job queued with ID: {job_id}")
            return {"job_id": job_id}
            
        except Exception as e:
            logger.error(f"Failed to queue script generation job: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to queue job: {str(e)}")

    @router.get("/status/{job_id}", response_model=JobStatusResponse)
    async def get_job_status(job_id: str, identifier: str = Depends(get_current_identifier)):
        """
        Get the status of a generation job.
        
        This endpoint returns the current status of a job, including progress
        information and results if the job is completed.
        """
        if job_id not in active_jobs and job_id not in job_results:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
            
        if job_id in job_results:
            result = job_results[job_id]
            status_response = JobStatusResponse(
                job_id=job_id, 
                status="completed" if "error" not in result else "failed",
                result=result if "error" not in result else None,
                error=result.get("error") if "error" in result else None
            )
        else:
            status = active_jobs.get(job_id, "unknown")
            status_response = JobStatusResponse(
                job_id=job_id,
                status=status,
                progress=job_progress.get(job_id)
            )
            
        return status_response

    @router.websocket("/ws/job/{job_id}")
    async def websocket_job_status(
        websocket: WebSocket, 
        job_id: str,
        token: Optional[str] = Query(None)
    ):
        """
        WebSocket endpoint for real-time job status updates.
        
        This endpoint allows clients to receive real-time updates on job progress.
        """
        # Try to get identifier from token parameter
        identifier = None
        from ..config.settings import settings
        access_token_map = settings.get('ACCESS_TOKENS_DICT', {})

        if token:
            for id, valid_token in access_token_map.items():
                if token == valid_token:
                    identifier = id
                    break

        if not identifier:
            logger.warning(f"WebSocket connection denied for job {job_id}: Invalid or missing token.")
            # Close the connection BEFORE accepting if auth fails
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return # Important to stop processing
            
        logger.info(f"WebSocket connection established for job {job_id} by identifier: {identifier}")
        await websocket.accept()
        
        # Store websocket connection for sending updates
        websocket_connections[job_id] = websocket
        
        try:
            # Send initial status if available
            if job_id in job_progress:
                await websocket.send_json({
                    "type": "progress",
                    "job_id": job_id,
                    "progress": job_progress[job_id]
                })
            elif job_id in job_results:
                await websocket.send_json({
                    "type": "result",
                    "job_id": job_id,
                    "result": job_results[job_id]
                })
                
            # Keep connection alive and handle client messages if needed
            while True:
                data = await websocket.receive_text()
                # Handle any client commands if needed
                await asyncio.sleep(0.1) # Small delay to prevent tight loop
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected from job {job_id}")
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")
        finally:
            if job_id in websocket_connections:
                del websocket_connections[job_id]

    @router.get("/file-content/{job_id}/{target}/{filename:path}")
    async def get_file_content(job_id: str, target: str, filename: str, identifier: str = Depends(get_current_identifier)):
        """
        Get the content of a generated file.
        
        This endpoint returns the content of a generated file for a specific job,
        target, and filename.
        """
        if job_id not in job_results:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found or not completed")
            
        job_result = job_results[job_id]
        if "error" in job_result:
            raise HTTPException(status_code=400, detail=f"Job {job_id} failed: {job_result['error']}")
            
        if "files" not in job_result:
            raise HTTPException(status_code=404, detail=f"No files found for job {job_id}")
            
        target_files = job_result["files"].get(target)
        if not target_files:
            raise HTTPException(status_code=404, detail=f"No files found for target {target} in job {job_id}")
            
        file_content = None
        for file_info in target_files:
            if file_info["path"] == filename or file_info["path"].endswith(f"/{filename}"):
                file_content = file_info["content"]
                break
                
        if file_content is None:
            raise HTTPException(status_code=404, detail=f"File {filename} not found for target {target} in job {job_id}")
            
        return {"content": file_content}
        
    return router 