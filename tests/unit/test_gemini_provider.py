import pytest
from unittest.mock import MagicMock, patch
import google.genai as genai

from src.providers.google import GeminiProvider, GeminiModel
from agents.model_settings import ModelSettings
from openai.types.responses import ResponseOutputMessage, ResponseOutputRefusal
from agents.tool import FunctionTool

@pytest.fixture
def mock_genai():
    with patch('google.genai') as mock:
        yield mock

@pytest.fixture
def provider():
    return GeminiProvider(api_key="test-key")

@pytest.fixture
def model(provider):
    return provider.get_model("gemini-1.5-pro")

@pytest.fixture
def mock_function_tool():
    # Create a test tool with openai_schema mocked
    tool = MagicMock(spec=FunctionTool)
    tool.name = "test_tool"
    tool.description = "A test tool"
    tool.openai_schema.return_value = {
        "name": "test_tool",
        "description": "A test tool",
        "parameters": {
            "type": "object",
            "properties": {
                "arg1": {"type": "string"}
            }
        }
    }
    return tool

def test_provider_initialization():
    provider = GeminiProvider(api_key="test-key")
    assert provider.api_key == "test-key"

def test_provider_get_model():
    provider = GeminiProvider(api_key="test-key")
    model = provider.get_model("gemini-1.5-pro")
    assert isinstance(model, GeminiModel)
    assert model.full_model_name == "gemini-1.5-pro"

def test_model_initialization(model):
    assert model.full_model_name == "gemini-1.5-pro"
    # Client is now set at initialization time
    assert model.client is not None

@pytest.mark.asyncio
async def test_get_response_basic(model, mock_genai):
    # Mock response
    mock_response = MagicMock()
    mock_response.text = "Test response"
    mock_response.parts = []
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content = MagicMock()
    mock_response.candidates[0].content.parts = []
    mock_response.candidates[0].finish_reason = MagicMock()
    mock_response.candidates[0].finish_reason.name = "STOP"
    
    # Setup mock
    model.client = MagicMock()
    model.models = MagicMock()
    model.models.generate_content_async.return_value = mock_response

    # Test
    messages = [{"role": "user", "content": "Hello"}]
    response = await model.get_response(input=messages)
    
    assert response.output  # Check that we have output

@pytest.mark.asyncio
async def test_get_response_with_tool_calls(model, mock_genai):
    # Mock response with function call
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content = MagicMock()
    
    mock_part = MagicMock()
    mock_part.function_call = MagicMock()
    mock_part.function_call.name = "test_tool"
    mock_part.function_call.args = {"arg1": "value1"}
    
    mock_response.candidates[0].content.parts = [mock_part]
    mock_response.candidates[0].finish_reason = MagicMock()
    mock_response.candidates[0].finish_reason.name = "TOOL_CALL"
    
    # Setup mock
    model.client = MagicMock()
    model.models = MagicMock()
    model.models.generate_content_async.return_value = mock_response

    # Create a mock tool directly in the test
    mock_tool = MagicMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "A test tool"
    
    # Define openai_schema as a function
    def openai_schema():
        return {
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {
                "type": "object",
                "properties": {
                    "arg1": {"type": "string"}
                }
            }
        }
    mock_tool.openai_schema = openai_schema

    # Test
    messages = [{"role": "user", "content": "Use the tool"}]
    response = await model.get_response(input=messages, tools=[mock_tool])
    
    # Check that tool call was included in output
    assert response.output

@pytest.mark.asyncio
async def test_get_response_with_safety_block(model, mock_genai):
    # Setup mock to raise safety error
    mock_response = MagicMock()
    mock_response.candidates = []
    mock_response.prompt_feedback = MagicMock()
    mock_response.prompt_feedback.block_reason = MagicMock()
    mock_response.prompt_feedback.block_reason.name = "SAFETY"
    
    model.client = MagicMock()
    model.models = MagicMock()
    model.models.generate_content_async.return_value = mock_response

    # Test
    messages = [{"role": "user", "content": "Unsafe content"}]
    response = await model.get_response(input=messages)
    
    # Check that refusal was included in output
    assert response.output
    assert any("refusal" in str(item) for item in response.output)

@pytest.mark.asyncio
async def test_get_response_with_system_prompt(model, mock_genai):
    # Mock response
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content = MagicMock()
    mock_response.candidates[0].content.parts = []
    mock_response.candidates[0].finish_reason = MagicMock()
    mock_response.candidates[0].finish_reason.name = "STOP"
    
    # Setup mock
    model.client = MagicMock()
    model.models = MagicMock()
    model.models.generate_content_async.return_value = mock_response

    # Test messages with system prompt
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello"}
    ]
    
    response = await model.get_response(input=messages)
    
    # Verify the call to generate_content
    generated_content_call = model.models.generate_content_async.call_args
    assert generated_content_call is not None

@pytest.mark.asyncio
async def test_get_response_with_tool_result(model, mock_genai):
    # Mock response
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content = MagicMock()
    mock_response.candidates[0].content.parts = []
    mock_response.candidates[0].finish_reason = MagicMock()
    mock_response.candidates[0].finish_reason.name = "STOP"
    
    # Setup mock
    model.client = MagicMock()
    model.models = MagicMock()
    model.models.generate_content_async.return_value = mock_response

    # Test messages with tool result
    messages = [
        {"role": "user", "content": "Use the tool"},
        {"role": "assistant", "content": [{"type": "tool_calls", "tool_calls": [{"function": {"name": "test_tool", "arguments": "{}"}}]}]},
        {"role": "tool", "tool_call_id": "test_tool", "content": "Tool execution result"}
    ]
    
    response = await model.get_response(input=messages)
    
    # Verify a call was made
    assert model.models.generate_content_async.called

@pytest.mark.asyncio
async def test_get_response_with_model_settings(model, mock_genai):
    # Mock response
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content = MagicMock() 
    mock_response.candidates[0].content.parts = []
    mock_response.candidates[0].finish_reason = MagicMock()
    mock_response.candidates[0].finish_reason.name = "STOP"
    
    # Setup mock
    model.client = MagicMock()
    model.models = MagicMock()
    model.models.generate_content_async.return_value = mock_response

    # Test with model settings
    messages = [{"role": "user", "content": "Hello"}]
    settings = ModelSettings(temperature=0.5)
    
    response = await model.get_response(input=messages, model_settings=settings)
    
    # Verify a call was made with correct parameters
    generation_params = model.models.generate_content_async.call_args[1]['generation_config']
    assert generation_params.get('temperature') == 0.5 