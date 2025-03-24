class APITestGenerationError(Exception):
    """Base class for API test generation errors."""
    def __init__(self, message, details=None, trace_id=None):
        self.message = message
        self.details = details or {}
        self.trace_id = trace_id
        super().__init__(self.message)

class SpecValidationError(APITestGenerationError):
    """Error validating OpenAPI spec."""
    pass

class BlueprintGenerationError(APITestGenerationError):
    """Error generating blueprint from spec."""
    pass

class BlueprintValidationError(APITestGenerationError):
    """Error validating blueprint."""
    pass

class ScriptGenerationError(APITestGenerationError):
    """Error generating test scripts."""
    pass

class ModelUnavailableError(APITestGenerationError):
    """Error when required model is unavailable."""
    pass 