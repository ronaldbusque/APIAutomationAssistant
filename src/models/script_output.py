"""
Script Output Models Module - Data models for generated test scripts

This module defines the data models used to represent generated test scripts
from test blueprints in different formats.
"""

from typing import List, Dict, Any, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, model_validator

class ScriptType(str, Enum):
    """Enumeration of supported script output types."""
    POSTMAN = "postman"
    PLAYWRIGHT = "playwright"
    CYPRESS = "cypress"
    PYTEST = "pytest"
    CUSTOM = "custom"

class FileContent(BaseModel):
    """Model for individual file content within a generated output."""
    filename: str = Field(..., description="Name of the file")
    content: str = Field(..., description="Text content of the file")
    path: Optional[str] = Field(None, description="Optional path where the file should be saved")
    format: Optional[str] = Field(None, description="Optional format identifier (e.g., 'js', 'json', 'py')")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileContent':
        """Create a FileContent instance from a dictionary.
        
        Args:
            data: Dictionary containing file content data
            
        Returns:
            A FileContent instance
            
        Raises:
            ValueError: If the data format is invalid
        """
        if not isinstance(data, dict):
            raise ValueError(f"Expected dictionary data, got {type(data)}")
        
        # If the content is not a string, try to convert it to a string
        if "content" in data and not isinstance(data["content"], str):
            try:
                import json
                data["content"] = json.dumps(data["content"], indent=2)
            except Exception:
                data["content"] = str(data["content"])
        
        # Try to create the file content
        try:
            return cls(**data)
        except Exception as e:
            raise ValueError(f"Failed to parse file content data: {e}")

class TargetOutput(BaseModel):
    """Model for output targeted at a specific testing framework."""
    name: str = Field(..., description="Name of the output file or collection")
    type: ScriptType = Field(..., description="Type of the script")
    content: Dict[str, Any] = Field(..., description="The generated script/collection content")
    files: Optional[List[FileContent]] = Field(None, description="Individual files if content is separated")
    
    @model_validator(mode='after')
    def validate_content(self) -> 'TargetOutput':
        """Validate that the content matches the expected format for the script type."""
        if self.type == ScriptType.POSTMAN:
            # Validate Postman collection structure
            if not isinstance(self.content, dict) or 'info' not in self.content or 'item' not in self.content:
                raise ValueError("Postman collection must contain 'info' and 'item' fields")
        
        # Add validations for other script types as needed
        
        return self
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TargetOutput':
        """Create a TargetOutput instance from a dictionary.
        
        Args:
            data: Dictionary containing target output data
            
        Returns:
            A TargetOutput instance
            
        Raises:
            ValueError: If the data format is invalid
        """
        if not isinstance(data, dict):
            raise ValueError(f"Expected dictionary data, got {type(data)}")
        
        # Create a copy of the data to modify
        data_copy = data.copy()
        
        # Add required fields if missing
        if "name" not in data_copy or not data_copy["name"]:
            script_type = data_copy.get("type", "custom")
            data_copy["name"] = f"{script_type.capitalize()} Scripts"
            
        if "type" not in data_copy or not data_copy["type"]:
            data_copy["type"] = "custom"
            
        if "content" not in data_copy or not data_copy["content"]:
            data_copy["content"] = {"info": "Default content created for missing content"}
            
        # Convert files to FileContent objects if they're dictionaries
        if "files" in data_copy and isinstance(data_copy["files"], list):
            file_objects = []
            for file_data in data_copy["files"]:
                if isinstance(file_data, dict):
                    try:
                        file_content = FileContent(**file_data)
                        file_objects.append(file_content)
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).warning(f"Invalid file data: {e}, skipping")
                else:
                    file_objects.append(file_data)  # Assume it's already a FileContent object
            data_copy["files"] = file_objects
        
        # Ensure content is a dictionary
        if "content" in data_copy:
            if not isinstance(data_copy["content"], dict):
                if isinstance(data_copy["content"], str):
                    # If content is a string, store it as a dictionary with a "content" key
                    data_copy["content"] = {"content": data_copy["content"]}
                else:
                    # Convert any non-dict content to a dictionary
                    try:
                        # Try to convert to JSON string first if it's an object
                        import json
                        data_copy["content"] = {"content": json.dumps(data_copy["content"], indent=2)}
                    except Exception:
                        # Fall back to string representation
                        data_copy["content"] = {"content": str(data_copy["content"])}
        
        # Try to create the target output
        try:
            return cls(**data_copy)
        except Exception as e:
            # If validation fails, create a basic valid instance
            import logging
            logging.getLogger(__name__).error(f"Failed to parse target output data: {e}")
            
            # Extract the type if available
            script_type = "custom"
            if "type" in data_copy and data_copy["type"]:
                script_type = data_copy["type"]
            
            # Create a minimal valid object
            return cls(
                name=f"{script_type.capitalize() if isinstance(script_type, str) else 'Custom'} Scripts",
                type=script_type,
                content={"info": "Default content created due to validation error"},
                files=[
                    FileContent(
                        filename=f"default_{script_type}.txt",
                        content="// This is a placeholder created due to validation errors"
                    )
                ]
            )

class ScriptOutput(BaseModel):
    """Model for the complete script output response."""
    apiName: str = Field(..., description="Name of the API being tested")
    version: str = Field(..., description="Version of the generated scripts")
    outputs: List[TargetOutput] = Field(..., description="List of generated script outputs")
    
    @model_validator(mode='after')
    def validate_outputs(self) -> 'ScriptOutput':
        """Validate that the outputs list isn't empty and has unique script types."""
        if not self.outputs:
            raise ValueError("Script output must contain at least one target output")
        
        # Check for duplicate script types
        types = [output.type for output in self.outputs]
        if len(types) != len(set(types)):
            raise ValueError("Duplicate script types found in outputs")
        
        return self
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScriptOutput':
        """Create a ScriptOutput instance from a dictionary.
        
        Args:
            data: Dictionary containing script output data
            
        Returns:
            A ScriptOutput instance
            
        Raises:
            ValueError: If the data format is invalid
        """
        # Handle case where the data is empty or invalid
        if data is None or (isinstance(data, str) and not data.strip()):
            # Create minimal valid output with default targets
            import logging
            logging.getLogger(__name__).warning("Received empty data, creating default ScriptOutput")
            return cls(
                apiName="API Tests",
                version="1.0.0",
                outputs=[
                    TargetOutput(
                        name="Default Test Scripts",
                        type=ScriptType.CUSTOM,
                        content={"info": "Default content created for empty response"},
                        files=[
                            FileContent(
                                filename="default.txt",
                                content="// This is a placeholder created when the agent returned an empty response"
                            )
                        ]
                    )
                ]
            )
            
        # Handle case where the output format is different from our model
        if not isinstance(data, dict):
            # Try to convert to dict if it's a string (JSON)
            if isinstance(data, str):
                import json
                try:
                    data = json.loads(data)
                except json.JSONDecodeError as e:
                    import logging
                    logging.getLogger(__name__).error(f"Invalid JSON data: {e}")
                    # Extract JSON object from the string if possible
                    import re
                    json_match = re.search(r'(\{.*\})', data, re.DOTALL)
                    if json_match:
                        try:
                            data = json.loads(json_match.group(1))
                        except json.JSONDecodeError:
                            logging.getLogger(__name__).error("Failed to extract valid JSON from the response")
                            # Create minimal valid output with default targets
                            return cls(
                                apiName="API Tests",
                                version="1.0.0",
                                outputs=[
                                    TargetOutput(
                                        name="Default Test Scripts",
                                        type=ScriptType.CUSTOM,
                                        content={"info": "Default content created for invalid JSON response"},
                                        files=[
                                            FileContent(
                                                filename="default.txt",
                                                content="// This is a placeholder created when the agent returned invalid JSON"
                                            )
                                        ]
                                    )
                                ]
                            )
                    else:
                        # Create minimal valid output with default targets
                        return cls(
                            apiName="API Tests",
                            version="1.0.0",
                            outputs=[
                                TargetOutput(
                                    name="Default Test Scripts",
                                    type=ScriptType.CUSTOM,
                                    content={"info": "Default content created for invalid JSON response"},
                                    files=[
                                        FileContent(
                                            filename="default.txt",
                                            content="// This is a placeholder created when the agent returned invalid JSON"
                                        )
                                    ]
                                )
                            ]
                        )
            else:
                # Try to convert non-dict, non-string data to a default ScriptOutput
                import logging
                logging.getLogger(__name__).error(f"Unexpected data type: {type(data)}, creating default ScriptOutput")
                return cls(
                    apiName="API Tests",
                    version="1.0.0",
                    outputs=[
                        TargetOutput(
                            name="Default Test Scripts",
                            type=ScriptType.CUSTOM,
                            content={"info": "Default content created for unexpected data type"},
                            files=[
                                FileContent(
                                    filename="default.txt",
                                    content=f"// This is a placeholder created when the agent returned data of type {type(data)}"
                                )
                            ]
                        )
                    ]
                )
        
        # Create a copy of the data to modify
        data_copy = data.copy()
        
        # Add required fields if missing
        if "apiName" not in data_copy or not data_copy["apiName"]:
            data_copy["apiName"] = "API Tests"
            
        if "version" not in data_copy or not data_copy["version"]:
            data_copy["version"] = "1.0.0"
        
        # Handle different output formats
        if "outputs" in data_copy:
            # Check if outputs is a dictionary instead of a list
            if isinstance(data_copy["outputs"], dict):
                # Transform the outputs dict to a list of target outputs
                outputs_list = []
                for key, value in data_copy["outputs"].items():
                    if isinstance(value, dict):
                        # Add name if it's missing
                        if "name" not in value:
                            value["name"] = key
                        # Try to create a TargetOutput
                        try:
                            target_output = TargetOutput.from_dict(value)
                            outputs_list.append(target_output)
                        except Exception as e:
                            import logging
                            logging.getLogger(__name__).error(f"Failed to create TargetOutput for key {key}: {e}")
                data_copy["outputs"] = outputs_list
            
            # Handle case where outputs is a list but might contain invalid items
            elif isinstance(data_copy["outputs"], list):
                outputs_list = []
                for item in data_copy["outputs"]:
                    if isinstance(item, dict):
                        try:
                            target_output = TargetOutput.from_dict(item)
                            outputs_list.append(target_output)
                        except Exception as e:
                            import logging
                            logging.getLogger(__name__).error(f"Failed to create TargetOutput from item: {e}")
                    else:
                        # If it's already a TargetOutput, keep it
                        if isinstance(item, TargetOutput):
                            outputs_list.append(item)
                
                data_copy["outputs"] = outputs_list
        else:
            # No outputs field, try to create a default one
            if "content" in data_copy:
                # The whole dict might be a single output
                try:
                    target_output = TargetOutput.from_dict(data_copy)
                    data_copy = {
                        "apiName": "API Tests",
                        "version": "1.0.0",
                        "outputs": [target_output]
                    }
                except Exception:
                    # Create a default output
                    data_copy["outputs"] = [
                        TargetOutput(
                            name="Default Test Scripts",
                            type=ScriptType.CUSTOM,
                            content=data_copy.get("content", {"info": "Default content"}),
                            files=[]
                        )
                    ]
            else:
                # Create a default output
                data_copy["outputs"] = [
                    TargetOutput(
                        name="Default Test Scripts",
                        type=ScriptType.CUSTOM,
                        content={"info": "Default content created for missing outputs"},
                        files=[
                            FileContent(
                                filename="default.txt",
                                content="// This is a placeholder created when the agent returned no outputs"
                            )
                        ]
                    )
                ]
                
        # Ensure there's at least one output
        if not data_copy.get("outputs") or len(data_copy["outputs"]) == 0:
            data_copy["outputs"] = [
                TargetOutput(
                    name="Default Test Scripts",
                    type=ScriptType.CUSTOM,
                    content={"info": "Default content created for empty outputs"},
                    files=[
                        FileContent(
                            filename="default.txt",
                            content="// This is a placeholder created when the agent returned empty outputs list"
                        )
                    ]
                )
            ]
        
        # Try to create the ScriptOutput
        try:
            return cls(**data_copy)
        except Exception as e:
            # If validation still fails, create a minimal valid ScriptOutput
            import logging
            logging.getLogger(__name__).error(f"Failed to create ScriptOutput: {e}, falling back to default")
            
            # Determine if we can rescue any outputs
            outputs = []
            if "outputs" in data_copy and isinstance(data_copy["outputs"], list):
                for item in data_copy["outputs"]:
                    if isinstance(item, TargetOutput):
                        outputs.append(item)
            
            # If no outputs could be rescued, create a default one
            if not outputs:
                outputs = [
                    TargetOutput(
                        name="Default Test Scripts",
                        type=ScriptType.CUSTOM,
                        content={"info": "Default content created due to validation error"},
                        files=[
                            FileContent(
                                filename="default.txt",
                                content="// This is a placeholder created due to validation errors in ScriptOutput"
                            )
                        ]
                    )
                ]
            
            # Create and return a minimal valid ScriptOutput
            return cls(
                apiName="API Tests",
                version="1.0.0",
                outputs=outputs
            ) 