from typing import List, Tuple, Set, Dict, Any, Union
import re
import json

from ..errors.exceptions import BlueprintValidationError
from .models import Blueprint

def validate_dependencies(blueprint_dict: Dict[str, Any]) -> List[str]:
    """
    Enhanced validation for test dependencies with dictionary input.
    
    Args:
        blueprint_dict: Blueprint dictionary to validate
        
    Returns:
        List of warnings
    """
    warnings = []
    
    # Check if blueprint_dict or groups is None
    if not blueprint_dict or 'groups' not in blueprint_dict or not blueprint_dict.get('groups'):
        warnings.append("Blueprint has no groups defined")
        return warnings
    
    # Get all test IDs
    test_ids = []
    for group in blueprint_dict.get('groups', []):
        if not group or 'tests' not in group or not group.get('tests'):
            warnings.append(f"Group '{group.get('name', 'unnamed')}' has no tests defined")
            continue
            
        for test in group.get('tests', []):
            if 'id' in test:
                test_ids.append(test['id'])
            else:
                warnings.append(f"Test in group '{group.get('name', 'unnamed')}' is missing an ID")
    
    # Check for missing dependencies
    for group in blueprint_dict.get('groups', []):
        if not group or 'tests' not in group:
            continue
            
        for test in group.get('tests', []):
            if not test:
                continue
                
            if 'id' not in test:
                continue
                
            dependencies = test.get('dependencies', [])
            if dependencies is None:
                continue
                
            for dep_id in dependencies:
                if dep_id not in test_ids:
                    warnings.append(f"Test '{test['id']}' depends on non-existent test '{dep_id}'")
    
    # Build dependency graph
    dependency_graph = {}
    for group in blueprint_dict.get('groups', []):
        if not group or 'tests' not in group:
            continue
            
        for test in group.get('tests', []):
            if not test or 'id' not in test:
                continue
                
            dependencies = test.get('dependencies', [])
            if dependencies is None:
                dependencies = []
                
            dependency_graph[test['id']] = dependencies
    
    # No dependencies to check
    if not dependency_graph:
        return warnings
    
    # Improved cycle detection with path tracking
    def detect_cycle(node, path=None):
        if path is None:
            path = []
        
        # Check if the current node is already in the path
        if node in path:
            # Cycle detected - return the cycle path for better reporting
            cycle_start = path.index(node)
            return path[cycle_start:] + [node]
        
        # Add current node to path and check all neighbors
        path = path + [node]
        for neighbor in dependency_graph.get(node, []):
            cycle = detect_cycle(neighbor, path)
            if cycle:
                return cycle
        
        return None
    
    # Check for cycles starting from each node
    for test_id in dependency_graph:
        cycle = detect_cycle(test_id)
        if cycle:
            cycle_str = " -> ".join(cycle)
            warnings.append(f"Circular dependency detected: {cycle_str}")
            break
    
    return warnings

def check_blueprint_security(blueprint_dict: Dict[str, Any]) -> List[str]:
    """
    Check blueprint for potential security issues.
    
    Args:
        blueprint_dict: Blueprint dictionary to check for security issues
        
    Returns:
        List of security warning messages
    """
    warnings = []
    
    # Check for potentially harmful endpoints or payloads
    sensitive_patterns = [
        'token', 'password', 'secret', 'key', 'auth', 'cred', 
        'admin', 'root', 'sudo', 'shell', 'exec', 'eval'
    ]
    
    # Check sensitive endpoints
    for group in blueprint_dict.get('groups', []):
        for test in group.get('tests', []):
            if 'endpoint' in test:
                for pattern in sensitive_patterns:
                    if pattern in test['endpoint'].lower():
                        test_id = test.get('id', 'unknown')
                        warnings.append(f"Test '{test_id}' uses potentially sensitive endpoint '{test['endpoint']}'")
    
    # Check for potential injection risks in test assertions
    for group in blueprint_dict.get('groups', []):
        for test in group.get('tests', []):
            if test.get('assertions'):
                for i, assertion in enumerate(test['assertions']):
                    if "'" in assertion or '"' in assertion:
                        test_id = test.get('id', 'unknown')
                        warnings.append(f"Test '{test_id}' assertion #{i+1} contains quotes, "
                                       f"which might indicate string injection risks")
    
    return warnings

async def validate_and_clean_blueprint(blueprint_data: Union[Blueprint, Dict[str, Any]]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Validate a blueprint and clean it up if possible.
    
    Args:
        blueprint_data: The blueprint to validate (can be a model instance or dictionary)
        
    Returns:
        Tuple of (cleaned_blueprint_dict, warnings)
    """
    warnings = []
    
    # Convert to dictionary if it's a model instance
    if isinstance(blueprint_data, Blueprint):
        try:
            blueprint_dict = blueprint_data.model_dump()
        except Exception as e:
            warnings.append(f"Failed to convert blueprint model to dictionary: {str(e)}")
            # Try to convert to dict another way
            blueprint_dict = {k: v for k, v in blueprint_data.__dict__.items() if not k.startswith('_')}
    else:
        blueprint_dict = blueprint_data
    
    # Ensure blueprint_dict is not None
    if not blueprint_dict:
        warnings.append("Blueprint dictionary is empty, using a minimal default structure")
        blueprint_dict = {
            "apiName": "Default API",
            "version": "1.0.0",
            "groups": []
        }
    
    # Run dependency validation
    try:
        dependency_warnings = validate_dependencies(blueprint_dict)
        warnings.extend(dependency_warnings)
        
        # Check for security issues
        security_warnings = check_blueprint_security(blueprint_dict)
        warnings.extend(security_warnings)
    except Exception as e:
        warnings.append(f"Warning during blueprint validation: {str(e)}")
    
    # Ensure the blueprint has required fields
    if "apiName" not in blueprint_dict:
        blueprint_dict["apiName"] = "Unknown API"
        warnings.append("Blueprint missing apiName, using 'Unknown API'")
        
    if "version" not in blueprint_dict:
        blueprint_dict["version"] = "1.0.0"
        warnings.append("Blueprint missing version, using '1.0.0'")
        
    if "groups" not in blueprint_dict:
        blueprint_dict["groups"] = []
        warnings.append("Blueprint missing groups, using empty list")
    
    return blueprint_dict, warnings 