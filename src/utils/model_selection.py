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

from src.config.settings import settings

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
        self.default_model = default_model or fresh_settings.get("MODEL_DEFAULT", "gpt-4o-mini")
        self.env_prefix = env_prefix
        
        # Load model configuration from settings
        self.model_config = {
            "planning": fresh_settings.get("MODEL_PLANNING", "gpt-4o"),
            "coding": fresh_settings.get("MODEL_CODING", "gpt-4o"),
            "triage": fresh_settings.get("MODEL_TRIAGE", "gpt-3.5-turbo"),
            "default": fresh_settings.get("MODEL_DEFAULT", self.default_model)
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
    
    def select_model(self, task: str, complexity: float) -> str:
        """
        Select the appropriate model based on task type and complexity.
        
        Args:
            task: Type of task (planning, coding, triage)
            complexity: Complexity score (0-1)
            
        Returns:
            Model name to use
        """
        try:
            logger.debug(f"Original task requested: {task} with complexity {complexity}")
            
            # Map task aliases to standard task types
            task_mapping = {
                "code_generation": "coding",
                "planning": "planning",
                "triage": "triage",
                "coding": "coding"
            }
            
            # Standardize the task name
            standard_task = task_mapping.get(task)
            if standard_task:
                logger.debug(f"Mapped task {task} to standard task {standard_task}")
                task = standard_task
            else:
                logger.warning(f"Unknown task type: {task}, will try to use as-is or fall back to default")
            
            # Always respect the task-specific model from config if it exists
            if task in self.model_config and self.model_config.get(task):
                selected_model = self.model_config.get(task)
                logger.info(f"Using configured model {selected_model} for {task} task with complexity {complexity:.2f}")
                return selected_model
            
            # If no task-specific model is configured, select based on complexity
            logger.debug(f"No direct model config for task '{task}', selecting based on complexity")
            if task == "triage":
                # Triage is a simple routing task, use lightweight model
                selected_model = self.model_config.get("triage", "gpt-3.5-turbo")
                
            elif task == "planning":
                thresholds = self.complexity_thresholds.get("planning", {"high": 0.7, "medium": 0.4})
                
                if complexity > thresholds["high"]:
                    # High complexity planning - use the most capable model
                    selected_model = "gpt-4o"
                elif complexity > thresholds["medium"]:
                    # Medium complexity - balance capability and cost
                    selected_model = "gpt-4o-mini"
                else:
                    # Low complexity - use cost-effective model
                    selected_model = "gpt-3.5-turbo"
                    
            elif task == "coding":
                thresholds = self.complexity_thresholds.get("coding", {"high": 0.8, "medium": 0.5})
                
                if complexity > thresholds["high"]:
                    # High complexity coding - use the most capable model
                    selected_model = "gpt-4o"
                elif complexity > thresholds["medium"]:
                    # Medium complexity - balance capability and cost
                    selected_model = "gpt-4o-mini"
                else:
                    # Low complexity - use cost-effective model
                    selected_model = "gpt-3.5-turbo"
            else:
                logger.warning(f"Unrecognized task type: {task}, using default model")
                selected_model = self.model_config.get("default", self.default_model)
                
            logger.info(f"Selected model {selected_model} for {task} task with complexity {complexity:.2f} (based on complexity)")
            return selected_model
            
        except Exception as e:
            logger.error(f"Error in model selection: {str(e)}, using default model {self.default_model}")
            # Return the default model as a fallback
            return self.model_config.get("default", self.default_model)
            
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