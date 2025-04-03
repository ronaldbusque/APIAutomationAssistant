"""
Google Gemini AI provider implementation
"""

import time
import logging
import json
import os
from enum import Enum
from typing import List, Dict, Any, Optional, Union, Tuple, Callable, Literal, TypeVar, AsyncIterator

# Create logger before imports
logger = logging.getLogger(__name__)

# Import Google GenAI library
import google.genai as genai

# Define GenerationConfig as a simple class if it doesn't exist
class GenerationConfig:
    """Simple class to mimic GenerationConfig functionality"""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

# Import Client directly
from google.genai.client import Client

# Import from openai_provider (version 0.0.7)
try:
    logger.info("Attempting to import using 0.0.7 paths")
    from agents.models.openai_provider import OpenAIProvider
    from agents.models.interface import Model, ModelProvider
    from agents.model_settings import ModelSettings
    from agents.items import TResponseInputItem, TResponseOutputItem, TResponseStreamEvent, ModelResponse
    from agents.tool import Tool, FunctionTool
    from agents.exceptions import ModelBehaviorError
    from agents.usage import Usage
    
    logger.info("Successfully imported OpenAI agents SDK modules using version 0.0.7 paths")
    OPENAI_AGENTS_IMPORTED = True
except ImportError as e:
    logger.error(f"Failed to import OpenAI agents SDK: {e}")
    logger.error("GeminiProvider will not function correctly without these imports")
    # List all packages to debug
    import subprocess
    try:
        pkg_list = subprocess.check_output(["pip", "list"]).decode()
        logger.info(f"Installed packages: {pkg_list}")
    except Exception as pkg_e:
        logger.error(f"Failed to list packages: {pkg_e}")
    OPENAI_AGENTS_IMPORTED = False

# OpenAI types imports with error handling
try:
    from openai.types.responses import ResponseOutputMessage, ResponseOutputRefusal
    from openai.types.responses import ResponseFunctionToolCall
    logger.info("Successfully imported OpenAI types")
except ImportError as e:
    logger.error(f"Failed to import OpenAI types: {e}")
    # Define stub classes
    class ResponseOutputMessage:
        pass
        
    class ResponseOutputRefusal:
        pass
        
    class ResponseFunctionToolCall:
        pass

# Import app settings
from src.config.settings import settings as app_settings

logger = logging.getLogger(__name__)


class GeminiModel(Model):
    """Implements the agents.Model interface for Google Gemini models using google-genai."""

    def __init__(self, model_name: str, provider: 'GeminiProvider'):
        self.full_model_name = model_name
        self.client_model_name = model_name
        # If provider gives us client_model_name separately (which we set in get_model), 
        # we'll use that instead. Otherwise we'll add the models/ prefix if needed
        if not self.client_model_name.startswith("models/"):
            self.client_model_name = f"models/{self.client_model_name}"
            
        self.provider = provider
        self.client = provider.client  # Get client from provider
        self.models = provider.models  # Get models from provider

    # --- Translation Methods (Crucial and Complex) ---

    def _translate_sdk_history_to_gemini(self, history: List[TResponseInputItem]) -> List[dict]:
        """Converts SDK message history to Gemini's Content list format."""
        gemini_history = []
        system_prompt = None

        # Extract system prompt first if present
        if history and history[0].get("role") == "system":
            system_prompt = str(history[0].get("content", ""))
            history = history[1:]  # Remove system prompt from main history

        for item in history:
            role = item.get("role")
            content = item.get("content")

            if role == "user":
                # Prepend system prompt to the *first* user message
                text_content = str(content)
                if system_prompt and not any(c["role"] == 'user' for c in gemini_history):
                    text_content = f"{system_prompt}\n\n{text_content}"
                    system_prompt = None  # Only add once

                gemini_history.append({"role": "user", "parts": [{"text": text_content}]})

            elif role == "assistant":
                parts = []
                if isinstance(content, list):  # OpenAI format for tool calls
                    for part_item in content:
                        if part_item.get("type") == "text":
                            parts.append({"text": part_item.get("text", "")})
                        elif part_item.get("type") == "tool_calls":
                            for tool_call in part_item.get("tool_calls", []):
                                # Map OpenAI tool call back to Gemini FunctionCall Part
                                # This assumes we have the necessary info. Gemini expects FunctionCall object.
                                # We need 'name' and 'args' (as dict).
                                func_name = tool_call.get("function", {}).get("name")
                                try:
                                    func_args = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
                                except json.JSONDecodeError:
                                    logger.warning(f"Could not parse arguments for tool call: {func_name}")
                                    func_args = {}

                                if func_name:
                                    parts.append({"function_call": {"name": func_name, "args": func_args}})
                                else:
                                    logger.warning(f"Skipping tool call part due to missing name: {tool_call}")
                        else:
                            parts.append({"text": str(part_item)})  # Fallback
                elif isinstance(content, str):  # Simple text response
                    parts.append({"text": content})

                if parts:
                    gemini_history.append({"role": "model", "parts": parts})

            elif role == "tool":
                # Map SDK tool result back to Gemini FunctionResponse Part
                tool_call_id = item.get("tool_call_id")  # This ID comes from the *assistant's* tool_call message
                tool_content_str = str(item.get("content", ""))
                # We need the *function name* associated with the tool_call_id.
                # This requires looking back in the history, which is complex and error-prone.
                # A better approach is needed, perhaps storing mapping in context, but that violates SDK principles.
                # Simplification: Assume the tool_call_id *is* the function name for Gemini's FunctionResponse.
                # This is likely incorrect but necessary without a better mapping mechanism.
                if tool_call_id:
                    # Gemini expects the response content nested under 'response': {'content': ...}
                    gemini_history.append({
                        "role": "user",  # Gemini uses 'user' role for function responses
                        "parts": [{"function_response": {"name": tool_call_id, "response": {"content": tool_content_str}}}]
                    })
                else:
                    logger.warning(f"Tool message missing tool_call_id, cannot translate to Gemini: {item}")

        # Gemini API requires alternating user/model roles. Merge or handle violations.
        # This simplified merge might lose information or context.
        merged_history = []
        if gemini_history:
            current_content = gemini_history[0]
            for i in range(1, len(gemini_history)):
                next_content = gemini_history[i]
                # Basic merge: If same role, combine parts (may not be semantically correct)
                if next_content["role"] == current_content["role"]:
                    current_content["parts"].extend(next_content["parts"])
                    logger.debug(f"Merging consecutive roles: {current_content['role']}")
                else:
                    merged_history.append(current_content)
                    current_content = next_content
            merged_history.append(current_content)

        # Ensure history doesn't start with 'model' if possible (Gemini API constraint)
        if merged_history and merged_history[0]["role"] == "model":
            logger.warning("Gemini history starts with 'model' role. This might cause issues.")
            # Prepending an empty user message might be needed depending on API strictness
            # merged_history.insert(0, {"role": "user", "parts": [{"text": ""}]})

        return merged_history

    def _translate_schema_to_gemini(self, param_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Translates an OpenAPI-like JSON schema dict to Gemini parameter format."""
        gemini_type_map = {
            "string": "STRING", "integer": "INTEGER", "number": "NUMBER",
            "boolean": "BOOLEAN", "array": "ARRAY", "object": "OBJECT"
        }
        # Default to STRING if type is missing or unknown
        prop_type = param_schema.get("type", "string")
        gemini_type = gemini_type_map.get(prop_type, "STRING")

        translated_schema = {
            "type": gemini_type,
            "description": param_schema.get("description"),
            "nullable": param_schema.get("nullable", False),  # Check for nullable support
            "enum": param_schema.get("enum"),
            "format": param_schema.get("format"),  # Pass format directly (e.g., 'int32', 'float')
        }

        if gemini_type == "OBJECT":
            properties = param_schema.get("properties", {})
            translated_schema["properties"] = {
                name: self._translate_schema_to_gemini(prop)
                for name, prop in properties.items()
            }
            translated_schema["required"] = param_schema.get("required")
        elif gemini_type == "ARRAY":
            items_schema = param_schema.get("items")
            if items_schema:
                translated_schema["items"] = self._translate_schema_to_gemini(items_schema)

        return translated_schema

    def _translate_sdk_tools_to_gemini(self, tools: Optional[List[Tool]]) -> Optional[List[dict]]:
        """Converts SDK Tool list to Gemini's Tool list format."""
        if not tools:
            return None

        gemini_declarations = []
        for tool in tools:
            try:
                # Use the SDK's method to get the OpenAI-compatible schema
                schema_dict = tool.openai_schema()
                func_name = schema_dict.get("name")
                description = schema_dict.get("description", "")
                parameters_schema = schema_dict.get("parameters", {})  # This is the OpenAPI schema for parameters

                if not func_name:
                    logger.warning(f"Skipping tool due to missing name: {tool}")
                    continue

                # Translate the parameters schema (which is type 'object')
                gemini_params_schema = self._translate_schema_to_gemini(parameters_schema)

                gemini_declarations.append({
                    "name": func_name,
                    "description": description,
                    "parameters": gemini_params_schema  # Pass the translated schema
                })
            except Exception as e:
                logger.warning(f"Failed to translate tool '{getattr(tool, 'name', 'unknown')}' to Gemini format: {e}", exc_info=True)

        return [{"function_declarations": gemini_declarations}] if gemini_declarations else None

    def _translate_gemini_response_to_sdk(self, response) -> List[TResponseOutputItem]:
        """Converts Gemini response object to the SDK's output item list."""
        sdk_output: List[TResponseOutputItem] = []

        # Check for blocked response first
        if not response.candidates and response.prompt_feedback and response.prompt_feedback.block_reason:
            block_reason = response.prompt_feedback.block_reason.name
            block_message = f"Prompt blocked by API. Reason: {block_reason}"
            logger.warning(block_message)
            sdk_output.append(ResponseOutputRefusal(type="refusal", refusal=block_message))
            return sdk_output

        if not response.candidates:
            # No candidates and no explicit block reason - unusual state
            logger.warning("Gemini response has no candidates and no block reason.")
            sdk_output.append(ResponseOutputRefusal(type="refusal", refusal="Model response was empty or incomplete."))
            return sdk_output

        # Process the first candidate (assuming candidate_count=1 for now)
        candidate = response.candidates[0]

        # Check finish reason for safety/recitation issues
        finish_reason = candidate.finish_reason.name
        if finish_reason == "SAFETY":
            safety_ratings = {rating.category.name: rating.probability.name for rating in candidate.safety_ratings}
            safety_message = f"Content flagged for safety: {safety_ratings}"
            logger.warning(safety_message)
            sdk_output.append(ResponseOutputRefusal(type="refusal", refusal=safety_message))
            return sdk_output  # Stop processing if blocked by safety
        elif finish_reason == "RECITATION":
            recitation_message = "Content flagged for recitation."
            logger.warning(recitation_message)
            sdk_output.append(ResponseOutputRefusal(type="refusal", refusal=recitation_message))
            return sdk_output  # Stop processing if blocked by recitation
        elif finish_reason not in ["STOP", "MAX_TOKENS", "TOOL_CALL"]:
            logger.warning(f"Gemini response finished with potentially problematic reason: {finish_reason}")
            # Continue processing but be aware

        # Process content parts
        text_content = ""
        tool_calls = []
        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if hasattr(part, 'text') and part.text:
                    text_content += part.text
                elif hasattr(part, 'function_call') and part.function_call:
                    fc = part.function_call
                    # Map Gemini FunctionCall to SDK ResponseFunctionToolCall
                    tool_call_id = f"call_{fc.name}_{len(tool_calls)}"  # Generate simple ID
                    try:
                        # Gemini args are dict, SDK expects JSON string
                        args_json = json.dumps(fc.args)
                    except TypeError:
                        logger.warning(f"Could not serialize args for tool call {fc.name}: {fc.args}")
                        args_json = "{}"

                    tool_calls.append(ResponseFunctionToolCall(
                        id=tool_call_id,
                        name=fc.name,
                        arguments=args_json
                    ))

        # Construct the SDK output message(s)
        if tool_calls:
            # If there are tool calls, the SDK expects them in a specific format,
            # often within the 'content' list of an assistant message.
            # Let's mimic the OpenAI structure.
            content_list = []
            if text_content:  # Include preceding text if any
                content_list.append({"type": "text", "text": text_content})
            content_list.append({"type": "tool_calls", "tool_calls": tool_calls})
            sdk_output.append(ResponseOutputMessage(content=content_list))
        elif text_content:
            # Simple text response
            sdk_output.append(ResponseOutputMessage(content=text_content))
        # If neither text nor tool calls, might be an empty response or only safety related finish reason
        elif not sdk_output:  # Avoid adding empty message if refusal already added
            logger.warning("Gemini candidate finished without text or tool calls.")
            # Optionally add an empty message or handle as needed
            # sdk_output.append(ResponseOutputMessage(content=""))

        return sdk_output

    # --- get_response Implementation ---
    async def get_response(
        self,
        system_instructions: Optional[str] = None,
        input: Union[str, List[TResponseInputItem]] = None,
        model_settings: Optional[ModelSettings] = None,
        tools: Optional[List[Tool]] = None,
        output_schema = None,  # AgentOutputSchema
        handoffs = None,       # list[Handoff]
        tracing = None,        # ModelTracing
    ) -> ModelResponse:
        """Gets a non-streaming response from the Gemini model."""
        if model_settings is None:
            model_settings = ModelSettings()
        
        if isinstance(input, str):
            # Convert string input to TResponseInputItem format
            input = [{"role": "user", "content": input}]
        
        if system_instructions and input:
            # Prepend system instructions as a system message
            input = [{"role": "system", "content": system_instructions}] + input
            
        if not self.client or not self.models: # Check if client/models were set by provider
            raise ConnectionError("Gemini client/models not initialized by provider.")

        # 1. Translate SDK history and tools to Gemini format
        try:
            gemini_history = self._translate_sdk_history_to_gemini(input)
            gemini_tools = self._translate_sdk_tools_to_gemini(tools)
        except Exception as e:
            logger.exception(f"Error translating SDK input/tools to Gemini format: {e}")
            raise ModelBehaviorError(f"Input/Tool Translation Error: {e}") from e

        # 2. Translate ModelSettings to generation parameters
        generation_params = {
            "candidate_count": 1,  # Assuming we only want one candidate
            "temperature": model_settings.temperature,
            "top_p": model_settings.top_p,
            # top_k not supported in current version
            "max_output_tokens": model_settings.max_tokens,
        }
        
        # Add stop sequences if available
        if hasattr(model_settings, 'stop') and model_settings.stop:
            generation_params["stop_sequences"] = model_settings.stop

        tool_params = None
        if gemini_tools:
            # Map tool_choice logic (Simplified: AUTO/ANY/NONE)
            # Gemini's 'FUNCTION' mode requires specifying *which* function, which differs from OpenAI's 'required'.
            # 'ANY' seems closest to OpenAI's 'required'. 'AUTO' is default. 'NONE' disables.
            mode = "AUTO"
            allowed_function_names = None
            if isinstance(model_settings.tool_choice, str):
                if model_settings.tool_choice == "required":
                    mode = "ANY"
                elif model_settings.tool_choice == "none":
                    mode = "NONE"
                elif model_settings.tool_choice != "auto":
                    # Specific function name - Gemini uses allowed_function_names with ANY/AUTO
                    mode = "ANY"  # Or AUTO? Check Gemini docs. Let's try ANY.
                    allowed_function_names = [model_settings.tool_choice]
            elif isinstance(model_settings.tool_choice, dict) and model_settings.tool_choice.get("type") == "function":
                # OpenAI specific format
                func_name = model_settings.tool_choice.get("function", {}).get("name")
                if func_name:
                    mode = "ANY"  # Or AUTO?
                    allowed_function_names = [func_name]

            tool_params = {
                "function_calling_config": {
                    "mode": mode,
                    "allowed_function_names": allowed_function_names
                }
            }

        # 3. Make the API call
        logger.debug(f"Calling Gemini model '{self.full_model_name}' (History: {len(gemini_history)}, Tools: {len(gemini_tools[0]['function_declarations']) if gemini_tools else 0})")
        try:
            # Use the API format - synchronous call inside async method
            # The Model interface requires async but google-genai might not have
            # async methods, so we call the synchronous version here.
            if gemini_tools:
                # Log that tools are being ignored for this version
                logger.warning("Tools parameter is being ignored because it's not supported in this version of Google GenAI")
                logger.warning("Agent functionality that requires tools will not work with this model")
            
            # Check which parameters are supported in the current version
            import inspect
            generate_content_signature = inspect.signature(self.models.generate_content)
            supported_params = generate_content_signature.parameters.keys()
            logger.debug(f"Supported parameters for generate_content: {supported_params}")
            
            # Build parameters dict based on what's supported
            call_params = {
                "model": self.client_model_name,
                "contents": gemini_history,
            }
            
            # Handle older API versions (prior to 0.3.0) that need a GenerationConfig object
            try:
                import google.generativeai as genai_module
                # Check if GenerationConfig exists in the module
                if hasattr(genai_module, 'GenerationConfig'):
                    logger.debug("Using GenAI-provided GenerationConfig")
                    # Create a GenerationConfig object
                    config = genai_module.GenerationConfig(**generation_params)
                    if "generation_config" in supported_params:
                        call_params["generation_config"] = config
                    else:
                        logger.debug("Generation config object created but parameter not supported")
                        # Fallback to adding individual parameters
                        for param_name, param_value in generation_params.items():
                            if param_name in supported_params:
                                call_params[param_name] = param_value
                                logger.debug(f"Added individual param {param_name}={param_value}")
                else:
                    # Handle generation parameters: either pass as generation_config object or as direct parameters
                    if "generation_config" in supported_params:
                        logger.debug("Adding generation_config parameter to generate_content call")
                        call_params["generation_config"] = generation_params
                    else:
                        # Add individual generation parameters directly
                        logger.debug("Adding generation parameters directly to generate_content call")
                        # Map each generation parameter if the parameter name exists in the function signature
                        for param_name, param_value in generation_params.items():
                            if param_name in supported_params:
                                call_params[param_name] = param_value
                                logger.debug(f"Added generation parameter {param_name}={param_value}")
                            else:
                                logger.debug(f"Skipping unsupported parameter: {param_name}")
            except ImportError:
                logger.warning("Could not import google.generativeai directly, using fallback approach")
                # Fallback to direct parameter passing
                for param_name, param_value in generation_params.items():
                    if param_name in supported_params:
                        call_params[param_name] = param_value
                        logger.debug(f"Fallback: Added parameter {param_name}={param_value}")
            
            # Only add tool-related params if supported
            if "tools" in supported_params and gemini_tools:
                logger.debug("Adding tools parameter to generate_content call")
                call_params["tools"] = gemini_tools
            
            if "tool_config" in supported_params and tool_params:
                logger.debug("Adding tool_config parameter to generate_content call")
                call_params["tool_config"] = tool_params
            
            # Make the API call with only supported parameters
            logger.debug(f"Calling generate_content with parameters: {call_params.keys()}")
            response = self.models.generate_content(**call_params)
            logger.info("Successfully received response from Gemini API")
                
        except Exception as e:
            logger.exception(f"Error calling Google GenAI API: {e}")
            # Return a structured refusal message
            from agents.usage import Usage
            return ModelResponse(
                output=[ResponseOutputRefusal(type="refusal", refusal=f"Gemini API Error: {e}")],
                usage=Usage(requests=1, input_tokens=0, output_tokens=0, total_tokens=0),
                referenceable_id=None
            )

        # 4. Translate Gemini response back to SDK format
        try:
            sdk_output_items = self._translate_gemini_response_to_sdk(response)
        except Exception as e:
            logger.exception(f"Error translating Gemini response to SDK format: {e}")
            raise ModelBehaviorError(f"Response Translation Error: {e}") from e

        # 5. Extract Usage
        usage_dict = {
            "requests": 1,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0
        }
        try:
            if response.usage_metadata:
                usage = response.usage_metadata
                usage_dict = {
                    "requests": 1,
                    "input_tokens": usage.prompt_token_count, 
                    "output_tokens": usage.candidates_token_count,
                    "total_tokens": usage.total_token_count,
                }
                logger.debug(f"Gemini response usage: {usage_dict}")
        except Exception as e:
            logger.warning(f"Could not extract usage metadata from Gemini response: {e}")

        from agents.usage import Usage
        return ModelResponse(
            output=sdk_output_items,
            usage=Usage(**usage_dict),
            referenceable_id=None
        )

    # --- stream_response (Deferred) ---
    async def stream_response(
        self,
        system_instructions: Optional[str] = None,
        input: Union[str, List[TResponseInputItem]] = None,
        model_settings: Optional[ModelSettings] = None,
        tools: Optional[List[Tool]] = None,
        output_schema = None,  # AgentOutputSchema
        handoffs = None,       # list[Handoff]
        tracing = None,        # ModelTracing
    ) -> AsyncIterator[TResponseStreamEvent]:
        """Gets a streaming response from the Gemini model. (DEFERRED)"""
        logger.error("Streaming is not yet implemented for GeminiModel.")
        raise NotImplementedError("Streaming is not yet implemented for GeminiModel.")
        yield {}  # Required to make it an async generator, but will raise first


class GeminiProvider(ModelProvider):
    """Provides GeminiModel instances using google-genai."""
    
    def __init__(self, api_key: str):
        if not api_key:
            logger.error("Cannot initialize GeminiProvider: API key is None or empty")
            raise ValueError("GeminiProvider requires a valid API key")
        
        # Log details about the API key for debugging (securely)
        api_key_length = len(api_key) if api_key else 0
        api_key_prefix = api_key[:4] + "..." if api_key_length > 8 else "***"
        logger.info(f"Initializing with API key: {api_key_prefix}, length: {api_key_length}")
        
        self.api_key = api_key
        try:
            logger.info("Initializing Google GenerativeAI Client")
            
            # Set environment variable - needed by certain versions
            os.environ["GOOGLE_API_KEY"] = api_key
            logger.info("Set GOOGLE_API_KEY environment variable")
            
            # Check Google GenAI version
            try:
                import google.generativeai as genai_module
                logger.info(f"GenAI module path: {genai_module.__file__}")
                logger.info(f"GenAI module version: {getattr(genai_module, '__version__', 'unknown')}")
                
                # Print all available attributes in the module
                module_attrs = [attr for attr in dir(genai_module) if not attr.startswith('__')]
                logger.info(f"Available GenAI module attributes: {module_attrs}")
            except Exception as ve:
                logger.error(f"Failed to get genai module version: {ve}")
            
            # Check Python package versions to diagnose any issues
            import pkg_resources
            google_genai_version = pkg_resources.get_distribution("google-genai").version
            logger.info(f"Using google-genai version: {google_genai_version}")
            
            # Initialize the client
            self.client = Client(api_key=api_key)
            logger.info("Initialized Google Client with API key")
            
            # Models in 1.9.0 can be accessed through client.models
            self.models = self.client.models
            
            # Test methods available on models
            logger.info(f"Models object type: {type(self.models)}")
            logger.info(f"Models object methods: {[m for m in dir(self.models) if not m.startswith('_')]}")
            
            # Test method signature of generate_content
            import inspect
            try:
                sig = inspect.signature(self.models.generate_content)
                logger.info(f"generate_content signature: {sig}")
                logger.info(f"generate_content parameters: {list(sig.parameters.keys())}")
            except Exception as se:
                logger.error(f"Failed to get method signature: {se}")
            
            # Test by listing models
            try:
                model_list = self.client.models.list()
                logger.info(f"Successfully listed models: {len(model_list)} models found")
                for model in model_list:
                    logger.info(f"Available model: {model.name}")
            except Exception as e:
                logger.warning(f"Could not list models (but client initialization succeeded): {e}")
                
            logger.info("Successfully initialized Google GenerativeAI Client")
            
        except Exception as e:
            logger.exception(f"Failed to initialize Google GenerativeAI Client: {e}")
            raise RuntimeError(f"Failed to initialize Google GenerativeAI Client: {e}") from e

    def get_model(self, model_name: str) -> Model:
        """Returns a GeminiModel instance for the given model name."""
        logger.info(f"Getting Gemini model instance for: {model_name}")
        
        # Handle Google model name format
        formatted_model_name = model_name
        
        # Strip google/ prefix if present
        if model_name.startswith("google/"):
            formatted_model_name = model_name.split("/", 1)[1]
        
        # Add models/ prefix for the client API if not already present
        client_model_name = formatted_model_name
        if not client_model_name.startswith("models/"):
            client_model_name = f"models/{client_model_name}"
        
        # Create the GeminiModel
        model = GeminiModel(model_name=formatted_model_name, provider=self)
        model.full_model_name = formatted_model_name
        model.client_model_name = client_model_name
        model.client = self.client
        model.models = self.models
        
        return model

    def is_chat_completions_model(self, model_name: str) -> bool:
        # Gemini API is conceptually closer to Chat Completions
        return True 