#!/usr/bin/env python
"""
Script to inspect Pydantic model schemas for debugging.
"""

import json
import logging
from typing import Any, Dict

from src.config.settings import load_settings
from src.blueprint.models import Blueprint, Parameter, Test, TestGroup

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def print_model_schemas():
    """Generates and prints JSON schemas for Blueprint and Parameter.value."""
    try:
        print("\n--- Generating Schemas for Debugging ---")

        # First, examine the Parameter model
        print("\n--- Parameter Schema ---")
        param_schema = Parameter.model_json_schema()
        print(json.dumps(param_schema, indent=2))

        # Specifically examine the 'value' field within Parameter
        print("\n--- Schema for Parameter.value ---")
        param_value_def = param_schema.get("properties", {}).get("value", {})
        # If it uses $ref, try to resolve it from $defs
        if "$ref" in param_value_def:
            ref_path = param_value_def["$ref"]
            def_key = ref_path.split('/')[-1] # Get the key from '#/$defs/...'
            resolved_def = param_schema.get("$defs", {}).get(def_key, "Reference not found in $defs")
            print(f"Reference ({ref_path}):")
            print(json.dumps(resolved_def, indent=2))
        else:
            print(json.dumps(param_value_def, indent=2))

        # Generate schema for Test model
        print("\n--- Test Schema (Parameter container) ---")
        test_schema = Test.model_json_schema()
        param_list_def = test_schema.get("properties", {}).get("parameters", {})
        print(json.dumps(param_list_def, indent=2))

        # Generate schema for the main Blueprint model top level properties
        blueprint_schema = Blueprint.model_json_schema()
        print("\n--- Blueprint Schema (Top Level Properties) ---")
        # Print only top-level properties for brevity
        print(json.dumps(blueprint_schema.get('properties', {}), indent=2))

        # Create a Parameter instance and print its JSON representation
        # Note: in_ is mapped to 'in' in the schema but needs to be used as in_ in Python code
        print("\n--- Parameter Instance as Dict ---")
        param = Parameter(
            name="testParam",
            value="string_value", 
            **{"in": "query"}  # Use this trick to set the 'in' field without using in_
        )
        print(json.dumps(param.model_dump(by_alias=True), indent=2))  # Use by_alias to show the field as 'in'

        # Try with different types
        print("\n--- Parameter with array value ---")
        param_array = Parameter(
            name="arrayParam",
            value=["item1", "item2"], 
            **{"in": "query"}
        )
        print(json.dumps(param_array.model_dump(by_alias=True), indent=2))

        print("\n--- Parameter with object value ---")
        param_object = Parameter(
            name="objectParam",
            value={"key1": "value1", "key2": 123}, 
            **{"in": "body"}
        )
        print(json.dumps(param_object.model_dump(by_alias=True), indent=2))

        print("\n--- Parameter with number value ---")
        param_number = Parameter(
            name="numberParam",
            value=42.5, 
            **{"in": "query"}
        )
        print(json.dumps(param_number.model_dump(by_alias=True), indent=2))
        
        # Create a full Blueprint example
        print("\n--- Blueprint Simple Instance ---")
        group = TestGroup(
            name="Test Group",
            description="A test group",
            tests=[
                Test(
                    id="test1",
                    name="Test 1",
                    description="Test case 1",
                    endpoint="/api/test",
                    method="GET",
                    parameters=[
                        Parameter(name="param1", value="value1", **{"in": "query"}),
                        Parameter(name="param2", value=123, **{"in": "query"})
                    ]
                )
            ]
        )
        
        blueprint = Blueprint(
            apiName="Test API",
            version="1.0",
            groups=[group]
        )
        
        print(json.dumps(blueprint.model_dump(by_alias=True), indent=2))

    except Exception as e:
        print(f"\nError generating/printing schemas: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function to run the script."""
    print("\n=== Inspecting Model Schemas ===")
    
    # Load settings
    try:
        load_settings()
        print("Settings loaded successfully")
    except Exception as e:
        print(f"Error loading settings: {e}")
    
    # Print schemas
    print_model_schemas()
    
    print("\n=== Inspection complete ===")

if __name__ == "__main__":
    main() 