import json
import yaml
import re
from typing import Tuple, Dict, List, Any, Optional
import logging

from ..errors.exceptions import SpecValidationError

logger = logging.getLogger(__name__)

async def validate_openapi_spec(spec_text: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Validate an OpenAPI spec and return parsed object and warnings.
    
    Args:
        spec_text: Raw OpenAPI spec text (YAML or JSON)
        
    Returns:
        Tuple of (parsed_spec, warnings)
        
    Raises:
        SpecValidationError: If the spec is invalid or cannot be parsed
    """
    warnings = []
    parsed_spec = None
    
    # Check for empty input
    if not spec_text or not spec_text.strip():
        raise SpecValidationError("Empty specification provided", {"spec": "empty"})
    
    # Check for excessive size to prevent DOS
    if len(spec_text) > 2_000_000:  # 2MB limit
        raise SpecValidationError(
            "Specification too large", 
            {"size": len(spec_text), "max_size": 2_000_000}
        )
    
    # Try parsing as JSON first
    try:
        parsed_spec = json.loads(spec_text)
        logger.debug("Successfully parsed spec as JSON")
    except json.JSONDecodeError:
        warnings.append("JSON parsing failed, trying YAML")
        try:
            parsed_spec = yaml.safe_load(spec_text)
            logger.debug("Successfully parsed spec as YAML")
        except Exception as e:
            error_message = f"YAML parsing failed: {str(e)}"
            warnings.append(error_message)
            logger.error(error_message)
            raise SpecValidationError(error_message, {"spec": spec_text[:100] + "..."})
    
    # Basic spec validation
    if not parsed_spec:
        raise SpecValidationError("Empty or invalid spec", {"spec": spec_text[:100] + "..."})
    
    if not isinstance(parsed_spec, dict):
        raise SpecValidationError("Specification must be a JSON/YAML object", {"type": type(parsed_spec).__name__})
    
    # Check for required OpenAPI fields with more detailed warnings
    if "openapi" not in parsed_spec:
        warnings.append("Missing 'openapi' version field. This field should specify the OpenAPI version (e.g., '3.0.0').")
    else:
        # Validate version format
        version = str(parsed_spec["openapi"])
        if not re.match(r'^\d+\.\d+\.\d+$', version):
            warnings.append(f"Invalid 'openapi' version format: {version}. Expected format: X.Y.Z")
    
    if "info" not in parsed_spec:
        warnings.append("Missing 'info' section. This should contain API metadata like title and version.")
    else:
        if "title" not in parsed_spec["info"]:
            warnings.append("Missing 'title' in info section")
        if "version" not in parsed_spec["info"]:
            warnings.append("Missing 'version' in info section")
    
    if "paths" not in parsed_spec:
        warnings.append("Critical error: Missing 'paths' section. This section defines the API endpoints.")
        # Create an empty paths object to allow processing to continue
        parsed_spec["paths"] = {}
    elif not parsed_spec["paths"]:
        warnings.append("Warning: 'paths' section is empty. No endpoints are defined.")
    
    # Validate path formats
    for path in parsed_spec.get("paths", {}):
        if not path.startswith('/'):
            warnings.append(f"Path '{path}' does not start with '/'")
        
        # Check for path parameters
        path_params = re.findall(r'\{([^}]+)\}', path)
        for param in path_params:
            # Check if path parameters are defined
            param_defined = False
            for method, operation in parsed_spec["paths"][path].items():
                if method not in ["get", "put", "post", "delete", "options", "head", "patch"]:
                    continue
                
                for op_param in operation.get("parameters", []):
                    if op_param.get("name") == param and op_param.get("in") == "path":
                        param_defined = True
                        break
            
            if not param_defined:
                warnings.append(f"Path parameter '{param}' in '{path}' is not defined in any operation")
    
    return parsed_spec, warnings 