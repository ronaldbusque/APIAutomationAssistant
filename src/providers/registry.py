"""Registry for model providers."""

from typing import Dict
from agents.models.interface import ModelProvider

_model_providers: Dict[str, ModelProvider] = {}

def register_model_provider(name: str, provider: ModelProvider) -> None:
    """Register a model provider.
    
    Args:
        name: The name to register the provider under.
        provider: The provider instance to register.
        
    Raises:
        ValueError: If a provider is already registered with the given name.
    """
    if name in _model_providers:
        raise ValueError(f"A provider is already registered with name '{name}'")
    _model_providers[name] = provider

def get_model_provider(name: str) -> ModelProvider:
    """Get a registered model provider.
    
    Args:
        name: The name of the provider to get.
        
    Returns:
        The registered provider.
        
    Raises:
        KeyError: If no provider is registered with the given name.
    """
    if name not in _model_providers:
        raise KeyError(f"No provider registered with name '{name}'")
    return _model_providers[name] 