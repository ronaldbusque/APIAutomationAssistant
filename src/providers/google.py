"""
Google Gemini AI provider implementation
"""

import time
import logging
import json
import os
import uuid
from enum import Enum
from typing import List, Dict, Any, Optional, Union, Tuple, Callable, Literal, TypeVar, AsyncIterator
import inspect

# Create logger before imports
logger = logging.getLogger(__name__)

# Import Google GenAI library
import google.genai as genai
from google.genai.client import Client
from google.genai.types import GenerationConfig, ToolConfig  # Import specific types

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
    
    # Define the type we need - these aren't in the 0.0.7 version but match the expected shape
    TRequestHistoryItem = TResponseInputItem
    TResponseToolDefinition = Tool
    
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
    
    # Define stub types for error handling
    class TRequestHistoryItem:
        role: str
        content: Any
        tool_calls: list = []
        tool_call_id: str = ""
        
    class TResponseToolDefinition:
        pass

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

    def _translate_sdk_history_to_gemini(self, history: List[TRequestHistoryItem]):
        """
        Translate the SDK history format to Gemini's format.
        This includes extracting system prompt and handling tool responses.
        """
        logger.info(f"Translating SDK history to Gemini format, {len(history)} items")
        gemini_history = []
        system_prompt = None
        tool_call_map = {}  # Maps tool_call_id to function_name
        
        # First pass to extract system prompt and create tool call mapping
        for i, item in enumerate(history):
            if item.role == "system" and i == 0:
                system_prompt = item.content
                continue
                
            # If assistant message has tool_calls, store the mapping
            if item.role == "assistant" and hasattr(item, "tool_calls") and item.tool_calls:
                for tool_call in item.tool_calls:
                    if hasattr(tool_call, "id") and hasattr(tool_call, "function"):
                        tool_call_map[tool_call.id] = tool_call.function.name
                        logger.info(f"Mapped tool call ID {tool_call.id} to function {tool_call.function.name}")
        
        # Second pass to build the conversation
        for i, item in enumerate(history):
            # Skip system message as it's handled separately
            if item.role == "system" and i == 0:
                continue
                
            # Handle user messages
            if item.role == "user":
                content = self._extract_content_text(item.content)
                gemini_history.append({"role": "user", "parts": [{"text": content}]})
                logger.info(f"Added user message: {content[:50]}...")
                
            # Handle assistant messages
            elif item.role == "assistant":
                # If message has tool calls
                if hasattr(item, "tool_calls") and item.tool_calls:
                    parts = []
                    
                    # Add text content if any
                    if item.content:
                        text_content = self._extract_content_text(item.content)
                        if text_content:
                            parts.append({"text": text_content})
                    
                    # Add function calls
                    for tool_call in item.tool_calls:
                        if hasattr(tool_call, "function"):
                            function_part = {
                                "function_call": {
                                    "name": tool_call.function.name,
                                    "args": json.loads(tool_call.function.arguments)
                                }
                            }
                            parts.append(function_part)
                            logger.info(f"Added function call: {tool_call.function.name}")
                    
                    gemini_history.append({"role": "model", "parts": parts})
                
                # Simple text message
                else:
                    content = self._extract_content_text(item.content)
                    gemini_history.append({"role": "model", "parts": [{"text": content}]})
                    logger.info(f"Added assistant message: {content[:50]}...")
            
            # Handle tool messages (function responses)
            elif item.role == "tool":
                # Get the parent function name from the tool_call_id if available
                parent_function = None
                if hasattr(item, "tool_call_id") and item.tool_call_id in tool_call_map:
                    parent_function = tool_call_map[item.tool_call_id]
                    
                # If we know which function this response belongs to
                if parent_function:
                    content = self._extract_content_text(item.content)
                    function_response = {
                        "role": "function",
                        "parts": [{
                            "function_response": {
                                "name": parent_function,
                                "response": {"content": content}
                            }
                        }]
                    }
                    gemini_history.append(function_response)
                    logger.info(f"Added function response for {parent_function}")
                else:
                    # Fall back to treating it as a user message if we can't associate with a function
                    content = self._extract_content_text(item.content)
                    gemini_history.append({"role": "user", "parts": [{"text": f"Tool response: {content}"}]})
                    logger.warning(f"Added tool response as user message (no tool_call_id mapping found)")
        
        logger.info(f"Translated to {len(gemini_history)} Gemini history items")
        return gemini_history, system_prompt
    
    def _extract_content_text(self, content):
        """Extract text from content which may be in different formats."""
        if isinstance(content, str):
            return content
        
        if isinstance(content, list):
            text = ""
            for item in content:
                if isinstance(item, str):
                    text += item
                elif isinstance(item, dict):
                    if "text" in item:
                        text += item["text"]
                    elif "content" in item and isinstance(item["content"], str):
                        text += item["content"]
            return text
            
        logger.warning(f"Unknown content format: {type(content)}")
        return str(content)

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

    def _translate_gemini_response_to_sdk(self, response):
        """
        Convert a Gemini response to SDK format.
        """
        logger.info(f"Translating Gemini response to SDK: {type(response)}")
        
        if hasattr(response, 'prompt_feedback'):
            prompt_feedback = response.prompt_feedback
            logger.info(f"Prompt feedback: {prompt_feedback}")
            if prompt_feedback and hasattr(prompt_feedback, 'block_reason'):
                logger.warning(f"Response was blocked. Reason: {prompt_feedback.block_reason}")
                return ResponseOutputMessage(
                    id=str(uuid.uuid4()),
                    role="assistant",
                    content=[{"text": "I'm unable to respond to that request."}],
                    status="completed",
                    type="message"
                )
        
        # Check if the response has candidates
        candidates = getattr(response, 'candidates', None)
        if not candidates:
            logger.warning("Response has no candidates")
            return ResponseOutputMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=[{"text": "No response generated."}],
                status="completed",
                type="message"
            )
        
        # Get the first candidate
        candidate = candidates[0]
        content = getattr(candidate, 'content', None)
        
        if not content:
            logger.warning("Candidate has no content")
            return ResponseOutputMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=[{"text": "Empty response received."}],
                status="completed",
                type="message"
            )
        
        # Extract parts from the content
        parts = getattr(content, 'parts', [])
        logger.info(f"Content parts: {parts}")
        
        # Check for function calls if using tools
        function_calls = []
        text_content = ""
        
        # Generate a unique ID for this response
        response_id = str(uuid.uuid4())
        
        for part in parts:
            # Check if part is a dict with a function_call
            if isinstance(part, dict) and 'function_call' in part:
                function_call = part['function_call']
                tool_call_id = str(uuid.uuid4())
                
                function_calls.append({
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": function_call.get('name', ''),
                        "arguments": function_call.get('arguments', '{}')
                    }
                })
                logger.info(f"Found function call: {function_call.get('name', '')}")
            # Text content
            elif isinstance(part, str):
                text_content += part
            # Object with text
            elif hasattr(part, 'text'):
                text_content += part.text
            # If it's an unknown type, log it
            else:
                logger.warning(f"Unknown part type: {type(part)}")
        
        # If we have function calls, format as tool calls
        if function_calls:
            logger.info(f"Returning response with {len(function_calls)} function calls")
            return ResponseOutputMessage(
                id=response_id,
                role="assistant",
                content=[],
                tool_calls=function_calls,
                status="completed",
                type="message"
            )
        # Otherwise return the text content
        else:
            logger.info("Returning response with text content")
            return ResponseOutputMessage(
                id=response_id,
                role="assistant",
                content=[{"text": text_content}],
                status="completed",
                type="message"
            )

    # --- get_response Implementation ---
    
    # This implementation has been replaced by a newer version below
    # The new version handles system prompts correctly and has better error handling

    # --- stream_response (Deferred) ---
    async def stream_response(
        self,
        system_instructions: Optional[str] = None,
        input: Union[str, List[TRequestHistoryItem]] = None,
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
    
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-pro"):
        if not api_key:
            logger.error("Cannot initialize GeminiProvider: API key is None or empty")
            raise ValueError("GeminiProvider requires a valid API key")
        
        # Store the model name for use in get_model
        self.model_name = model_name
        logger.info(f"Initializing GeminiProvider with model: {model_name}")
        
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
                logger.info(f"GenAI module path: {genai.__file__}")
                logger.info(f"GenAI module version: {getattr(genai, '__version__', 'unknown')}")
                
                # Print all available attributes in the module
                module_attrs = [attr for attr in dir(genai) if not attr.startswith('__')]
                logger.info(f"Available GenAI module attributes: {module_attrs}")
                
                # Test if GenerationConfig is available
                if hasattr(genai, 'GenerationConfig'):
                    logger.info("GenerationConfig is available in this version")
                elif hasattr(genai.types, 'GenerationConfig'):
                    logger.info("GenerationConfig is available in genai.types")
                else:
                    logger.warning("GenerationConfig not found in genai module structure")
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

    def get_model(self, model_name: Optional[str] = None) -> Any:
        """
        Get a Gemini model from the client.
        
        Args:
            model_name: Optional model name override. If not provided, the default is used.
            
        Returns:
            A GenAI model instance that can be used for inference.
        """
        if not model_name:
            model_name = self.model_name
            
        logger.info(f"Getting Gemini model: {model_name}")
        
        # Strip google/ prefix if present
        if model_name.startswith("google/"):
            model_name = model_name.replace("google/", "", 1)
            logger.debug(f"Stripped 'google/' prefix from model name: {model_name}")
        
        # Ensure model name has "models/" prefix for the Google API
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
            logger.debug(f"Added 'models/' prefix to model name: {model_name}")
            
        try:
            logger.info(f"Retrieving model: {model_name}")
            model = self.client.models.get(model_name)
            logger.info(f"Successfully retrieved model: {model_name}")
            return model
        except Exception as e:
            logger.exception(f"Failed to get model {model_name}: {e}")
            # Fallback to gemini-1.5-pro if available
            try:
                fallback_model = "models/gemini-1.5-pro"
                logger.warning(f"Attempting fallback to {fallback_model}")
                return self.client.models.get(fallback_model)
            except Exception as fallback_err:
                logger.error(f"Fallback to {fallback_model} also failed: {fallback_err}")
                raise ValueError(f"Could not initialize model {model_name} or fallback model: {str(e)}")

    def is_chat_completions_model(self, model_name: str) -> bool:
        # Gemini API is conceptually closer to Chat Completions
        return True 

    async def get_response(self, input: List[TRequestHistoryItem], tools: Optional[List[TResponseToolDefinition]] = None) -> Union[TResponseOutputItem, List[TResponseOutputItem]]:
        """
        Process a request and return a response. This is the main entry point for the provider.
        """
        logger.info(f"Processing request with {len(input)} history items and {len(tools) if tools else 0} tools")
        model = self.get_model()
        
        try:
            # 1. Translate SDK history and tools to Gemini format
            gemini_history, system_prompt = self._translate_sdk_history_to_gemini(input)
            gemini_tools = self._translate_sdk_tools_to_gemini(tools)
            
            # Log what we're sending to Gemini
            logger.info(f"Sending {len(gemini_history)} history items to Gemini")
            logger.info(f"System prompt: {system_prompt[:50]}..." if system_prompt else "No system prompt")
            logger.info(f"Tools: {len(gemini_tools) if gemini_tools else 0}")
            
            # 2. Setup generation config and safety settings
            try:
                generation_config = genai.GenerationConfig(
                    temperature=0.7,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=4096,
                    response_mime_type="application/json",
                )
                logger.info("Created generation config")
            except Exception as config_err:
                logger.warning(f"Failed to create generation config: {config_err}, using default")
                generation_config = None
                
            # 3. Make the API call with proper error handling
            try:
                # If we have system prompt, add it to the first user message
                if system_prompt and gemini_history and gemini_history[0]["role"] == "user":
                    prompt_text = gemini_history[0]["parts"][0]["text"]
                    gemini_history[0]["parts"][0]["text"] = f"{system_prompt}\n\n{prompt_text}"
                    logger.info("Added system prompt to first user message")
                
                # Ensure we have at least one conversation turn
                if not gemini_history:
                    logger.warning("No history items to send, creating empty user message")
                    gemini_history.append({"role": "user", "parts": [{"text": "Hello"}]})
                
                # Check that history starts with user message (Gemini requirement)
                if gemini_history[0]["role"] != "user":
                    logger.warning(f"First message role is {gemini_history[0]['role']}, not user. Adding empty user message.")
                    gemini_history.insert(0, {"role": "user", "parts": [{"text": "Hello"}]})
                
                logger.info(f"Making API call to Gemini with {len(gemini_history)} items")
                
                # Synchronous call to the Gemini API
                response = model.generate_content(
                    contents=gemini_history,
                    generation_config=generation_config,
                    tools=gemini_tools,
                    safety_settings=None  # Use defaults
                )
                logger.info(f"Received response from Gemini: {type(response)}")
                
                # 4. Translate the response back to SDK format
                sdk_response = self._translate_gemini_response_to_sdk(response)
                return sdk_response
                
            except Exception as api_err:
                logger.exception(f"Error making API call to Gemini: {api_err}")
                # Return refusal message with the error details
                error_msg = f"The AI model encountered an error: {str(api_err)}"
                return ResponseOutputMessage(
                    id=str(uuid.uuid4()),
                    role="assistant",
                    content=[{"text": error_msg}],
                    status="completed",
                    type="message"
                )
                
        except Exception as e:
            logger.exception(f"Error in GeminiProvider.get_response: {e}")
            # Return a generic error message
            error_msg = "I encountered an error processing your request."
            return ResponseOutputMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=[{"text": error_msg}],
                status="completed",
                type="message"
            ) 