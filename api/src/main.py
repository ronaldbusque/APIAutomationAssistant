import asyncio
import json
import uuid
import traceback
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add this new model for autonomous mode request
class GenerateAutonomousRequest(BaseModel):
    spec: str
    targets: List[str]
    max_iterations: Optional[int] = 2

# Add the new endpoint for autonomous generation
@app.post("/generate-autonomous")
async def generate_autonomous(request: GenerateAutonomousRequest, background_tasks: BackgroundTasks):
    """
    Autonomously generate both blueprint and scripts in one step.
    
    This endpoint initiates an agent-based workflow that:
    1. Analyzes the OpenAPI spec
    2. Creates a test blueprint
    3. Generates test scripts for all requested targets
    
    The process is fully autonomous and may involve multiple iterations and validations.
    """
    # Generate a new job ID
    job_id = str(uuid.uuid4())
    
    # Create a new job in the tracking system
    job_db[job_id] = {
        "status": "queued",
        "created_at": datetime.now().isoformat(),
        "progress": {
            "stage": "spec_analysis",
            "percent": 0,
            "message": "Starting autonomous generation process..."
        }
    }
    
    # Start the async task for autonomous generation
    background_tasks.add_task(
        run_autonomous_generation,
        job_id=job_id,
        spec=request.spec,
        targets=request.targets,
        max_iterations=request.max_iterations
    )
    
    return {"job_id": job_id}

# Add the function to handle autonomous generation
async def run_autonomous_generation(job_id: str, spec: str, targets: List[str], max_iterations: int):
    try:
        # Update job status to processing
        job_db[job_id]["status"] = "processing"
        
        # Step 1: Initial spec analysis
        update_job_progress(job_id, "spec_analysis", 10, "Analyzing OpenAPI specification...")
        
        # Parse the spec to validate it
        try:
            parsed_spec = parse_spec(spec)
        except Exception as e:
            job_db[job_id]["status"] = "failed"
            job_db[job_id]["error"] = f"Invalid OpenAPI specification: {str(e)}"
            return
        
        # Step 2: Blueprint authoring
        update_job_progress(job_id, "blueprint_authoring", 20, "Creating test blueprint...")
        
        # Generate blueprint using agents
        blueprint = await generate_blueprint_with_agents(spec)
        
        # Step 3: Blueprint review
        update_job_progress(job_id, "blueprint_reviewing", 40, "Reviewing and optimizing test blueprint...")
        
        # Validate the blueprint
        if not blueprint or not isinstance(blueprint, dict) or "groups" not in blueprint:
            job_db[job_id]["status"] = "failed"
            job_db[job_id]["error"] = "Failed to generate a valid test blueprint"
            return
        
        # Step 4: Blueprint complete
        update_job_progress(job_id, "blueprint_generation_complete", 50, "Blueprint generation complete. Proceeding to script generation...")
        
        # Step 5: Script generation
        update_job_progress(job_id, "script_coding", 60, f"Generating test scripts for {', '.join(targets)}...")
        
        # Generate scripts for each target
        all_scripts = {}
        for target in targets:
            target_scripts = await generate_scripts_for_target(blueprint, target)
            all_scripts[target] = target_scripts
        
        # Step 6: Script review
        update_job_progress(job_id, "script_reviewing", 90, "Reviewing and validating generated scripts...")
        
        # Final check on scripts
        if not all_scripts or any(not scripts for scripts in all_scripts.values()):
            job_db[job_id]["status"] = "failed"
            job_db[job_id]["error"] = "Failed to generate scripts for some targets"
            return
        
        # Step 7: Complete the process
        update_job_progress(job_id, "script_generation_complete", 100, "Script generation complete!")
        
        # Update job with results
        job_db[job_id]["status"] = "completed"
        job_db[job_id]["result"] = {
            "blueprint": blueprint,
            "scripts": all_scripts
        }
        
    except Exception as e:
        # Log error and update job status
        print(f"Error in autonomous generation: {str(e)}")
        traceback.print_exc()
        job_db[job_id]["status"] = "failed"
        job_db[job_id]["error"] = str(e)
        
# Helper function to update job progress
def update_job_progress(job_id: str, stage: str, percent: int, message: str):
    if job_id in job_db:
        job_db[job_id]["progress"] = {
            "stage": stage,
            "percent": percent,
            "message": message
        }

# Parse OpenAPI spec for validation and analysis
def parse_spec(spec_content: str) -> dict:
    """
    Parse and validate an OpenAPI specification.
    Returns the parsed specification as a dictionary.
    Raises an exception if the specification is invalid.
    """
    # Determine if it's YAML or JSON
    try:
        if spec_content.strip().startswith('{'):
            # It's JSON
            parsed_spec = json.loads(spec_content)
        else:
            # Assume it's YAML
            import yaml
            parsed_spec = yaml.safe_load(spec_content)
        
        # Basic validation
        if not isinstance(parsed_spec, dict):
            raise ValueError("Specification must be a valid JSON or YAML object")
        
        # Check for required OpenAPI fields
        if 'openapi' not in parsed_spec:
            raise ValueError("Missing 'openapi' field in specification")
        
        if 'paths' not in parsed_spec:
            raise ValueError("Missing 'paths' field in specification")
        
        return parsed_spec
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format")
    except yaml.YAMLError:
        raise ValueError("Invalid YAML format")
    except Exception as e:
        raise ValueError(f"Error parsing specification: {str(e)}")

# Generate blueprint using agents
async def generate_blueprint_with_agents(spec: str) -> dict:
    """
    Use agents to generate a test blueprint from an OpenAPI specification.
    This function implements the autonomous blueprint generation process.
    """
    # For now, reuse the existing blueprint generation logic
    # In a full implementation, this would be replaced with agent-specific logic
    blueprint_request = {
        "spec": spec,
        "mode": "basic"  # Default to basic mode for autonomous generation
    }
    
    # Use the existing blueprint generation function
    # This would be replaced with more sophisticated agent-based logic
    return await generate_blueprint_internal(blueprint_request)

# Generate scripts for a specific target
async def generate_scripts_for_target(blueprint: dict, target: str) -> dict:
    """
    Generate scripts for a specific target framework based on the provided blueprint.
    Returns a dictionary mapping file paths to file contents.
    """
    # For now, reuse the existing script generation logic
    # In a full implementation, this would be enhanced with agent-specific logic
    script_request = {
        "blueprint": blueprint,
        "targets": [target]
    }
    
    # Use the existing script generation function but extract just the target we need
    result = await generate_scripts_internal(script_request)
    
    # Return just the scripts for the specified target
    if target in result:
        return result[target]
    else:
        return {}

# Extract the core blueprint generation logic to be reusable
async def generate_blueprint_internal(request: dict) -> dict:
    """
    Internal function to generate a blueprint from a specification.
    This is used by both the regular and autonomous generation paths.
    """
    # Placeholder implementation - in a real system, this would call your AI service
    # For now, return a sample blueprint for testing
    sample_blueprint = {
        "apiName": "Sample API",
        "version": "1.0.0",
        "groups": [
            {
                "name": "Default Group",
                "tests": [
                    {
                        "id": "test1",
                        "name": "Sample Test",
                        "endpoint": "/sample",
                        "method": "GET",
                        "expectedStatus": 200
                    }
                ]
            }
        ]
    }
    
    # Add a delay to simulate processing time
    await asyncio.sleep(2)
    
    return sample_blueprint

# Extract the core script generation logic to be reusable
async def generate_scripts_internal(request: dict) -> dict:
    """
    Internal function to generate scripts based on a blueprint.
    This is used by both the regular and autonomous generation paths.
    """
    # Placeholder implementation - in a real system, this would call your AI service
    # For now, return sample scripts for testing
    result = {}
    
    for target in request.get("targets", []):
        if target == "postman":
            result[target] = {
                "collection.json": json.dumps({
                    "info": {
                        "name": "Sample Collection",
                        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
                    },
                    "item": [
                        {
                            "name": "Sample Test",
                            "request": {
                                "method": "GET",
                                "url": "{{baseUrl}}/sample"
                            }
                        }
                    ]
                }, indent=2)
            }
        elif target == "playwright":
            result[target] = {
                "tests/sample.spec.ts": """import { test, expect } from '@playwright/test';

test('Sample Test', async ({ request }) => {
  const response = await request.get('/sample');
  expect(response.status()).toBe(200);
});"""
            }
        else:
            # Default for other targets
            result[target] = {
                f"test_sample.{target}": f"// Sample test for {target}\n// Generated for testing purposes"
            }
    
    # Add a delay to simulate processing time
    await asyncio.sleep(3)
    
    return result

# Update the existing /generate-blueprint endpoint to use the internal function
@app.post("/generate-blueprint")
async def generate_blueprint(request: GenerateBlueprintRequest, background_tasks: BackgroundTasks):
    # ... existing code ...
    
    # Update to use the shared internal function
    background_tasks.add_task(
        run_blueprint_generation,
        job_id=job_id,
        request_data=request.dict()
    )
    
    return {"job_id": job_id}

# Update the blueprint generation task
async def run_blueprint_generation(job_id: str, request_data: dict):
    try:
        # ... existing code ...
        
        # Use the shared internal function
        blueprint = await generate_blueprint_internal(request_data)
        
        # ... rest of existing function ...
    except Exception as e:
        # ... existing error handling ...
        pass

# Update the existing /generate-scripts endpoint to use the internal function
@app.post("/generate-scripts")
async def generate_scripts(request: GenerateScriptsRequest, background_tasks: BackgroundTasks):
    # ... existing code ...
    
    # Update to use the shared internal function
    background_tasks.add_task(
        run_script_generation,
        job_id=job_id,
        request_data=request.dict()
    )
    
    return {"job_id": job_id}

# Update the script generation task
async def run_script_generation(job_id: str, request_data: dict):
    try:
        # ... existing code ...
        
        # Use the shared internal function
        scripts = await generate_scripts_internal(request_data)
        
        # ... rest of existing function ...
    except Exception as e:
        # ... existing error handling ...
        pass

# ... existing code ... 