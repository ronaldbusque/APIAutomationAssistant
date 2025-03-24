#!/usr/bin/env python
"""
Test script for API Automation Assistant
"""

import requests
import json
import time
import sys
import os

# Simple OpenAPI specification for testing
SIMPLE_OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "Simple API",
        "description": "A simple API for testing",
        "version": "1.0.0"
    },
    "servers": [
        {
            "url": "https://api.example.com/v1"
        }
    ],
    "paths": {
        "/users": {
            "get": {
                "summary": "Get all users",
                "description": "Returns a list of users",
                "operationId": "getUsers",
                "responses": {
                    "200": {
                        "description": "Successful operation",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "$ref": "#/components/schemas/User"
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid status value"
                    }
                }
            },
            "post": {
                "summary": "Create a user",
                "description": "Creates a new user",
                "operationId": "createUser",
                "requestBody": {
                    "description": "User object to be created",
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/User"
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "User created",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/User"
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid request"
                    }
                }
            }
        },
        "/users/{userId}": {
            "get": {
                "summary": "Get user by ID",
                "description": "Returns a user by ID",
                "operationId": "getUserById",
                "parameters": [
                    {
                        "name": "userId",
                        "in": "path",
                        "description": "ID of the user to retrieve",
                        "required": True,
                        "schema": {
                            "type": "integer",
                            "format": "int64"
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful operation",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/User"
                                }
                            }
                        }
                    },
                    "404": {
                        "description": "User not found"
                    }
                }
            }
        }
    },
    "components": {
        "schemas": {
            "User": {
                "type": "object",
                "required": [
                    "id",
                    "name",
                    "email"
                ],
                "properties": {
                    "id": {
                        "type": "integer",
                        "format": "int64"
                    },
                    "name": {
                        "type": "string"
                    },
                    "email": {
                        "type": "string",
                        "format": "email"
                    },
                    "age": {
                        "type": "integer",
                        "format": "int32",
                        "minimum": 0
                    }
                }
            }
        }
    }
}

def wait_for_job_completion(base_url: str, job_id: str, max_attempts: int = 30) -> dict:
    """
    Wait for a job to complete and return its result.
    
    Args:
        base_url: Base URL of the API
        job_id: Job ID to wait for
        max_attempts: Maximum number of polling attempts
        
    Returns:
        Job result dictionary
    """
    print(f"\nPolling for job {job_id} completion...")
    last_stage = None
    last_percent = 0
    
    for attempt in range(max_attempts):
        try:
            job_response = requests.get(f"{base_url}/status/{job_id}")
            job_response.raise_for_status()
            job_result = job_response.json()
            
            status = job_result.get("status")
            progress = job_result.get("progress", {})
            
            # Only print if there's a change in stage or progress
            current_stage = progress.get("stage", "unknown")
            current_percent = progress.get("percent", 0)
            
            if current_stage != last_stage or current_percent != last_percent:
                if progress:
                    stage = current_stage
                    percent = current_percent
                    message = progress.get("message", "")
                    print(f"Job status: {status} | Stage: {stage} | Progress: {percent}% | {message}")
                else:
                    print(f"Job status: {status}")
                
                last_stage = current_stage
                last_percent = current_percent
            
            if status == "completed":
                print("\nJob completed successfully!")
                return job_result.get("result", {})
            elif status == "failed":
                error = job_result.get("error")
                print(f"\nJob failed: {error}")
                raise Exception(f"Job failed: {error}")
            elif attempt == max_attempts - 1:
                print("\nTimed out waiting for job completion")
                raise Exception("Timed out waiting for job completion")
            
            time.sleep(10)  # Wait 10 seconds before polling again
        except Exception as e:
            print(f"\nError checking job status: {e}")
            raise

def test_blueprint_generation():
    """Test the blueprint generation endpoint."""
    base_url = "http://localhost:8000"
    
    # First, check if the API is healthy
    try:
        health_response = requests.get(f"{base_url}/health")
        health_response.raise_for_status()
        print(f"API Health: {health_response.json()}")
    except Exception as e:
        print(f"Error checking API health: {e}")
        sys.exit(1)
    
    # Prepare the request data for blueprint generation
    blueprint_request = {
        "spec": json.dumps(SIMPLE_OPENAPI_SPEC),
        "mode": "basic"
    }
    
    # Submit the request to generate blueprint
    try:
        print("Submitting blueprint generation request...")
        response = requests.post(f"{base_url}/generate-blueprint", json=blueprint_request)
        response.raise_for_status()
        result = response.json()
        job_id = result.get("job_id")
        print(f"Blueprint generation job submitted successfully. Job ID: {job_id}")
    except Exception as e:
        print(f"Error submitting blueprint generation job: {e}")
        sys.exit(1)
    
    # Wait for blueprint generation to complete
    try:
        blueprint_result = wait_for_job_completion(base_url, job_id)
        print("Blueprint generation result:")
        print(json.dumps(blueprint_result, indent=2))
        return blueprint_result.get("blueprint")
    except Exception as e:
        print(f"Blueprint generation failed: {e}")
        sys.exit(1)

def test_script_generation(blueprint: dict):
    """Test the script generation endpoint."""
    base_url = "http://localhost:8000"
    
    # Prepare the request data for script generation
    script_request = {
        "blueprint": blueprint,
        "targets": ["playwright"]  # Only generate Playwright tests
    }
    
    # Log blueprint details
    print("\nBlueprint Details:")
    print(f"Number of test groups: {len(blueprint.get('groups', []))}")
    total_tests = sum(len(group.get('tests', [])) for group in blueprint.get('groups', []))
    print(f"Total number of tests: {total_tests}")
    print(f"Target framework: {script_request['targets'][0]}")
    
    # Submit the request to generate scripts
    try:
        print("\nSubmitting script generation request...")
        response = requests.post(f"{base_url}/generate-scripts", json=script_request)
        response.raise_for_status()
        result = response.json()
        job_id = result.get("job_id")
        print(f"Script generation job submitted successfully. Job ID: {job_id}")
    except Exception as e:
        print(f"\nError submitting script generation job: {e}")
        sys.exit(1)
    
    # Wait for script generation to complete
    try:
        print("\nWaiting for script generation to complete...")
        script_result = wait_for_job_completion(base_url, job_id)
        
        print("\nScript Generation Result:")
        print("Generated files:")
        
        # Create output directory
        output_dir = "generated_tests"
        os.makedirs(output_dir, exist_ok=True)
        
        # Save generated files
        for target, files in script_result.get("scripts", {}).items():
            print(f"\n{target.upper()}:")
            for filename, content in files.items():
                # Create necessary subdirectories
                filepath = os.path.join(output_dir, filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                # Save the file
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  - {filename} (saved to {filepath})")
        
        print(f"\nAll files have been saved to the '{output_dir}' directory")
        return script_result
    except Exception as e:
        print(f"\nScript generation failed: {e}")
        sys.exit(1)

def test_api_automation():
    """Test the complete API automation workflow."""
    print("\n=== Testing Blueprint Generation ===")
    blueprint = test_blueprint_generation()
    
    print("\n=== Testing Script Generation ===")
    test_script_generation(blueprint)
    
    print("\n=== All tests completed successfully ===")

if __name__ == "__main__":
    test_api_automation() 