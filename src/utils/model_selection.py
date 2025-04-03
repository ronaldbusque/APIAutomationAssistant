import os
import logging
from typing import Dict, Any, Optional

# Add path adjustment for imports
import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from src.config.settings import settings, GEMINI_FLASH
from src.utils.openai_setup import parse_model_identifier

logger = logging.getLogger(__name__)

class ModelSelectionStrategy:
    """
    Strategy for selecting the optimal model based on task and complexity.
    
    This class encapsulates the logic for selecting the most appropriate
    model for a given task, considering factors like:
    - Task type (planning, coding, triage)
    - Task complexity (0-1 scale)
    - Environment configuration
    - Fallback options
    
    The strategy can be configured via environment variables or directly.
    """
    
    def __init__(self, 
                default_model: str = None,
                env_prefix: str = "MODEL_"):
        """
        Initialize with defaults and load configuration from settings.
        
        Args:
            default_model: Fallback model if no specific model is configured
            env_prefix: Prefix for model settings (e.g., MODEL_PLANNING)
        """
        # Import settings freshly to ensure we get the latest values
        from src.config.settings import settings as fresh_settings
        
        # Use settings from the centralized settings module
        self.default_model = default_model or fresh_settings.get("MODEL_DEFAULT", "gemini-2.0-flash-thinking-exp-01-21")
        self.env_prefix = env_prefix
        
        # Load model configuration from settings
        self.model_config = {
            "planning": fresh_settings.get("MODEL_PLANNING", "openai/gpt-4o"),
            "coding": fresh_settings.get("MODEL_CODING", "openai/gpt-4o"),
            "triage": fresh_settings.get("MODEL_TRIAGE", "openai/gpt-3.5-turbo"),
            "default": fresh_settings.get("MODEL_DEFAULT", self.default_model),
            # Add new autonomous agent model configurations
            "blueprint_authoring": fresh_settings.get("MODEL_BP_AUTHOR", "openai/gpt-4o"),
            "blueprint_reviewing": fresh_settings.get("MODEL_BP_REVIEWER", "openai/gpt-4o"),
            "script_coding": fresh_settings.get("MODEL_SCRIPT_CODER", "openai/gpt-4o"),
            "script_reviewing": fresh_settings.get("MODEL_SCRIPT_REVIEWER", "openai/gpt-4o"),
        }
        
        # Configure complexity thresholds from settings
        self.complexity_thresholds = {
            "planning": {
                "high": float(fresh_settings.get("MODEL_PLANNING_HIGH_THRESHOLD", 0.7)),
                "medium": float(fresh_settings.get("MODEL_PLANNING_MEDIUM_THRESHOLD", 0.4))
            },
            "coding": {
                "high": float(fresh_settings.get("MODEL_CODING_HIGH_THRESHOLD", 0.8)),
                "medium": float(fresh_settings.get("MODEL_CODING_MEDIUM_THRESHOLD", 0.5))
            }
        }
        
        logger.debug(f"Initialized ModelSelectionStrategy with config: {self.model_config}")
        logger.info(f"Using models: planning={self.model_config['planning']}, coding={self.model_config['coding']}, triage={self.model_config['triage']}")
    
    def select_model(self, task_type: str, task_complexity: float = 0.5) -> str:
        """
        Select a model based on task type and complexity.
        
        Args:
            task_type: Type of task (planning, coding, triage, etc.)
            task_complexity: Complexity score from 0-1
            
        Returns:
            Model name with provider prefix
        """
        logger.info(f"Selecting model for task type: {task_type}, complexity: {task_complexity:.2f}")
        model_name = None
        
        # Handle blueprint and script task types
        if task_type == "blueprint_authoring":
            model_name = self.model_config.get("blueprint_authoring")
            logger.info(f"Selected model for blueprint authoring: {model_name}")
        elif task_type == "blueprint_reviewing":
            model_name = self.model_config.get("blueprint_reviewing")
            logger.info(f"Selected model for blueprint reviewing: {model_name}")
        elif task_type == "script_coding":
            model_name = self.model_config.get("script_coding")
            logger.info(f"Selected model for script coding: {model_name}")
        elif task_type == "script_reviewing":
            model_name = self.model_config.get("script_reviewing")
            logger.info(f"Selected model for script reviewing: {model_name}")
        # Handle classic task types
        elif task_type == "planning":
            model_name = self.model_config.get("planning")
            logger.info(f"Selected model for planning: {model_name}")
        elif task_type == "coding":
            model_name = self.model_config.get("coding")
            logger.info(f"Selected model for coding: {model_name}")
        elif task_type == "triage":
            model_name = self.model_config.get("triage")
            logger.info(f"Selected model for triage: {model_name}")
        # Handle specialized task types
        elif task_type == "code_generation":
            model_name = self.model_config.get("coding")
            logger.info(f"Selected model for code generation: {model_name}")
        elif task_type == "code_review":
            model_name = self.model_config.get("coding")
            logger.info(f"Selected model for code review: {model_name}")
        elif task_type == "documentation":
            model_name = self.model_config.get("planning")
            logger.info(f"Selected model for documentation: {model_name}")
        elif task_type == "testing":
            model_name = self.model_config.get("coding")
            logger.info(f"Selected model for testing: {model_name}")
        # Default case
        else:
            logger.warning(f"Unknown task type: {task_type}, falling back to default model")
            model_name = self.model_config.get("default")
            
        # If no model selected or model is None, use default
        if not model_name:
            logger.warning(f"No model configured for task type: {task_type}, using default")
            model_name = self.model_config.get("default", "google/gemini-2.0-flash-thinking-exp-01-21")
            
        # Apply provider formatting and return
        formatted_model = self._format_model_name(model_name)
        logger.info(f"Final selected model: {formatted_model}")
        return formatted_model

    def _format_model_name(self, model_name: str) -> str:
        """
        Format model name to ensure it has the correct provider prefix.
        
        Args:
            model_name: The model name, which may or may not include a provider prefix
            
        Returns:
            Properly formatted model name with provider prefix
        """
        if not model_name:
            logger.warning("Model name is None or empty, using default model")
            model_name = self.model_config.get("default", "google/gemini-2.0-flash-thinking-exp-01-21")
            
        logger.debug(f"Formatting model name: {model_name}")
        
        # If model_name already has a provider prefix (like "openai/" or "google/"), keep it
        if "/" in model_name:
            provider, model = model_name.split("/", 1)
            
            # Handle the case where the model name starts with "models/"
            model = model.replace("models/", "")
            formatted_name = f"{provider}/{model}"
            logger.debug(f"Model name already has provider '{provider}', formatted to: {formatted_name}")
            return formatted_name
        
        # If there's no provider prefix, add the default "google/" prefix
        model_name = model_name.replace("models/", "")
        default_provider = "google"
        
        # Special case: OpenAI models should get the openai/ prefix if not already included
        if model_name.startswith(("gpt-3", "gpt-4")):
            logger.debug(f"Model {model_name} appears to be an OpenAI model, adding 'openai/' prefix")
            return f"openai/{model_name}"
            
        # Special case: Anthropic models
        if model_name.startswith("claude-"):
            logger.debug(f"Model {model_name} appears to be an Anthropic model, adding 'anthropic/' prefix")
            return f"anthropic/{model_name}"
            
        # Default case: add google/ prefix for all other models
        formatted_name = f"{default_provider}/{model_name}"
        logger.debug(f"Added default provider '{default_provider}' to model name: {formatted_name}")
        return formatted_name

    def update_tool_choice(self, agent_config: Dict[str, Any], complexity: float) -> Dict[str, Any]:
        """
        Update tool choice based on complexity to ensure proper tool usage.
        
        Args:
            agent_config: Agent configuration dictionary
            complexity: Task complexity score from 0-1
            
        Returns:
            Updated agent configuration
        """
        if complexity > 0.8:
            # Force tool use for very complex scenarios
            agent_config["model_kwargs"] = {"tool_choice": "required"}
        elif complexity > 0.6:
            # Specify that tools are available for moderately complex scenarios
            agent_config["model_kwargs"] = {"tool_choice": "auto"}
        else:
            # No special tool choice for simpler scenarios
            agent_config["model_kwargs"] = {}
            
        return agent_config

    def calculate_timeout(self, base_timeout: int, complexity: float) -> int:
        """
        Calculate appropriate timeout based on task complexity.
        
        Args:
            base_timeout: Base timeout in seconds
            complexity: Task complexity score (0-1)
            
        Returns:
            Adjusted timeout in seconds
        """
        # Scale timeout based on complexity, with a minimum
        min_timeout = 60  # Minimum 60 seconds
        scaling_factor = 1 + 2 * complexity  # Up to 3x for most complex tasks
        
        timeout = max(min_timeout, int(base_timeout * scaling_factor))
        logger.debug(f"Calculated timeout: {timeout}s (base: {base_timeout}s, complexity: {complexity:.2f})")
        return timeout 