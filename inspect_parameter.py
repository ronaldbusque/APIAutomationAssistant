#!/usr/bin/env python
"""
Focused script to inspect the Parameter model issue
"""

import json
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

# Simplified Parameter model for testing
class TestParameter(BaseModel):
    """Test implementation of Parameter model"""
    name: str = Field(description="Parameter name")
    value: Any = Field(description="Parameter value (can be any type)")
    in_: str = Field(description="Parameter location", alias="in")
    required: Optional[bool] = Field(True, description="Whether the parameter is required")
    description: Optional[str] = Field(None, description="Description of the parameter")
    
    model_config = {
        "populate_by_name": True,  # Allow using either alias or field name
        "json_schema_extra": {
            "required": ["name", "value", "in"]
        }
    }

def inspect_parameter_model():
    """Test the Parameter model schema and JSON serialization"""
    
    print("\n=== Testing Parameter Model ===")
    
    # Print the Parameter schema
    schema = TestParameter.model_json_schema()
    print("\nParameter Schema:")
    print(json.dumps(schema, indent=2))
    
    # Focus on the value field
    value_schema = schema.get("properties", {}).get("value", {})
    print("\nValue Field Schema:")
    print(json.dumps(value_schema, indent=2))
    
    # Try to create parameters with different value types
    try:
        # String value - using direct property assignment
        print("\nAttempting to create parameters...")
        param1 = TestParameter(name="param1", value="string_value", in_="query")
        print("\nString Value Parameter:")
        print(json.dumps(param1.model_dump(by_alias=True), indent=2))
        
        # Integer value - using dictionary unpacking
        param2 = TestParameter(**{"name": "param2", "value": 123, "in": "path"})
        print("\nInteger Value Parameter:")
        print(json.dumps(param2.model_dump(by_alias=True), indent=2))
        
        # List value
        param3 = TestParameter(name="param3", value=["item1", "item2"], in_="query")
        print("\nList Value Parameter:")
        print(json.dumps(param3.model_dump(by_alias=True), indent=2))
        
        # Dict value
        param4 = TestParameter(name="param4", value={"key1": "val1", "key2": 123}, in_="body")
        print("\nDict Value Parameter:")
        print(json.dumps(param4.model_dump(by_alias=True), indent=2))
        
        # Bool value
        param5 = TestParameter(name="param5", value=True, in_="query")
        print("\nBool Value Parameter:")
        print(json.dumps(param5.model_dump(by_alias=True), indent=2))
        
        # None value
        param6 = TestParameter(name="param6", value=None, in_="query")
        print("\nNone Value Parameter:")
        print(json.dumps(param6.model_dump(by_alias=True), indent=2))
        
    except Exception as e:
        print(f"\nError creating parameters: {e}")
        import traceback
        traceback.print_exc()
    
    # Generate JSON Schema for different values
    print("\n=== Testing JSON Schema Generation for Different Values ===")
    
    # Create a test model with various value types
    class TestValues(BaseModel):
        string_val: str = "test"
        int_val: int = 123
        float_val: float = 3.14
        bool_val: bool = True
        list_val: List[str] = ["a", "b", "c"]
        dict_val: Dict[str, Any] = {"a": 1, "b": "test"}
        any_val: Any = {"complex": ["nested", {"structure": True}]}
    
    test_schema = TestValues.model_json_schema()
    print("\nTest Values Schema:")
    print(json.dumps(test_schema, indent=2))
    
    # Focus on the any_val field
    any_val_schema = test_schema.get("properties", {}).get("any_val", {})
    print("\nAny Field Schema:")
    print(json.dumps(any_val_schema, indent=2))
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    inspect_parameter_model() 