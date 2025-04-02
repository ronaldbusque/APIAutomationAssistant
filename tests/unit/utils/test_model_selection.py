import pytest
from unittest.mock import patch
from src.utils.model_selection import ModelSelectionStrategy
from src.config.settings import GEMINI_FLASH

def test_model_selection_with_gemini():
    """Test model selection with Gemini model configuration."""
    strategy = ModelSelectionStrategy()
    
    # Test blueprint authoring with Gemini
    model = strategy.select_model("blueprint_authoring", 0.7)
    assert model.startswith("models/")
    
    # Test script reviewing with Gemini
    model = strategy.select_model("script_reviewing", 0.6)
    assert model.startswith("models/")

def test_model_selection_with_explicit_gemini_config():
    """Test model selection with explicit Gemini model configuration."""
    with patch('src.utils.model_selection.settings') as mock_settings:
        # Configure mock settings to use Gemini
        mock_settings.get.return_value = f"models/{GEMINI_FLASH}"
        
        strategy = ModelSelectionStrategy()
        
        # Test with explicit Gemini configuration
        model = strategy.select_model("blueprint_authoring", 0.7)
        assert model == f"models/{GEMINI_FLASH}"
        
        # Test with another task
        model = strategy.select_model("script_reviewing", 0.6)
        assert model == f"models/{GEMINI_FLASH}"

def test_model_selection_fallback():
    """Test model selection fallback behavior."""
    strategy = ModelSelectionStrategy()
    
    # Test with unknown task
    model = strategy.select_model("unknown_task", 0.5)
    assert model.startswith("models/")  # Should use default model
    
    # Test with invalid complexity
    model = strategy.select_model("blueprint_authoring", 1.5)
    assert model.startswith("models/")  # Should handle invalid complexity gracefully

def test_tool_choice_update():
    """Test tool choice updates with Gemini compatibility."""
    strategy = ModelSelectionStrategy()
    
    # Test high complexity
    config = strategy.update_tool_choice({"model_kwargs": {}}, 0.9)
    assert config["model_kwargs"]["tool_choice"] == "required"
    
    # Test medium complexity
    config = strategy.update_tool_choice({"model_kwargs": {}}, 0.7)
    assert config["model_kwargs"]["tool_choice"] == "auto"
    
    # Test low complexity
    config = strategy.update_tool_choice({"model_kwargs": {}}, 0.3)
    assert config["model_kwargs"] == {} 