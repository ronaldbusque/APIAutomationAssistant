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