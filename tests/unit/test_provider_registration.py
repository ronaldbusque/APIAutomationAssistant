import pytest
from unittest.mock import patch, MagicMock
from google.genai.client import Client
from src.providers.google import GeminiProvider
from src.providers.registry import register_model_provider, get_model_provider

@pytest.fixture
def mock_client():
    with patch('src.providers.google.Client') as mock:
        yield mock

def test_provider_registration():
    """Test registering the GeminiProvider."""
    provider = GeminiProvider(api_key="test-key")
    register_model_provider("google", provider)
    # Re-registering should raise ValueError
    with pytest.raises(ValueError):
        register_model_provider("google", provider)
    
    # Getting the provider should work
    assert get_model_provider("google") is provider
    
    # Getting a non-existent provider should raise KeyError
    with pytest.raises(KeyError):
        get_model_provider("non-existent")

def test_provider_api_key_configuration(mock_client):
    """Test that the provider configures the API key correctly."""
    provider = GeminiProvider(api_key="test-key")
    assert provider.api_key == "test-key"
    mock_client.assert_called_once_with(api_key="test-key")

def test_provider_model_configuration(mock_client):
    """Test that the provider configures models correctly."""
    mock_client_instance = MagicMock()
    mock_client.return_value = mock_client_instance
    
    provider = GeminiProvider(api_key="test-key")
    model = provider.get_model("gemini-1.5-pro")
    
    # Initial state
    assert model.client is mock_client_instance
    
    # Verify configuration
    mock_client.assert_called_with(api_key="test-key")
    assert model.client_model_name == "models/gemini-1.5-pro" 