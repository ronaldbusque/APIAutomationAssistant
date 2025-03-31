**Revised Goal:** Start from the original codebase again, implement multi-provider support by configuring the *underlying `openai` library* globally at startup, and let the `Agent` definitions simply use the model name string.

---

**New Foolproof Implementation Plan (From Original Codebase)**

**Phase 1: Configuration (`src/config/settings.py`)**

*   **Objective:** Add support for provider/model strings and API keys for different providers in the configuration.
*   **File:** `src/config/settings.py` (Based on Original Code)
*   **Actions:**
    1.  **Update `BASE_CONFIG`:**
        *   Change default model strings to `provider/model-name` format (defaulting to `openai`).
        *   Add `GOOGLE_API_KEY: None`.
        ```python
        # src/config/settings.py
        # ... (imports) ...
        logger = logging.getLogger(__name__)

        BASE_CONFIG = {
            # ... (HOST, PORT, RELOAD, LOG_LEVEL, LOG_FILE) ...

            # Model selection settings (PROVIDER/MODEL format)
            "MODEL_PLANNING": "openai/o3-mini", # Assuming this was the working original default
            "MODEL_CODING": "openai/gpt-4o-mini",
            "MODEL_TRIAGE": "openai/gpt-4o-mini",
            "MODEL_DEFAULT": "openai/gpt-4o-mini",

            # API Keys
            "GOOGLE_API_KEY": None,
            # Add others if needed

            # ... (Complexity thresholds, Performance settings) ...
        }

        # --- ADD PROVIDER_CONFIG Dictionary ---
        # Define provider base URLs and API key env var names
        GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/" # Verify URL

        PROVIDER_CONFIG = {
            "openai": {
                "api_key_env": "OPENAI_API_KEY",
                "base_url": None # Use library default
            },
            "google": {
                "api_key_env": "GOOGLE_API_KEY",
                "base_url": GOOGLE_BASE_URL
            },
            # Add other providers if needed
        }
        # --- END ADD ---

        # --- REPLACE load_settings function ---
        def load_settings() -> Dict[str, Any]:
            """Load settings from environment variables with defaults."""
            settings_dict = {}
            logger.info("Loading application settings...")

            # Load general settings
            for key, default in BASE_CONFIG.items():
                if "_API_KEY" in key: continue
                env_value = os.environ.get(key)
                settings_dict[key] = env_value if env_value is not None else default
                if key.startswith("MODEL_"):
                    logger.info(f"Setting {key} = '{settings_dict[key]}' (Source: {'Environment' if env_value is not None else 'Default'})")

            # Load API keys into nested dict
            settings_dict["API_KEYS"] = {}
            # Load the primary OpenAI key first (required by SDK implicitly often)
            openai_api_key = os.environ.get("OPENAI_API_KEY")
            if openai_api_key:
                settings_dict["API_KEYS"]["openai"] = openai_api_key
                logger.info("Loaded API key for provider: openai (from OPENAI_API_KEY)")
            else:
                logger.warning("OPENAI_API_KEY environment variable not found. OpenAI models may fail.")

            # Load keys for other configured providers
            for provider, config in PROVIDER_CONFIG.items():
                 if provider == "openai": continue # Already handled
                 api_key_env_var = config["api_key_env"]
                 api_key = os.environ.get(api_key_env_var)
                 if api_key:
                     settings_dict["API_KEYS"][provider.lower()] = api_key
                     logger.info(f"Loaded API key for provider: {provider.lower()} (from {api_key_env_var})")
                 else:
                     logger.debug(f"API key environment variable '{api_key_env_var}' not found for provider: {provider.lower()}")


            # Keep numeric/boolean conversions from original file
            numeric_settings = [
                "PORT", "MAX_RETRIES", "BASE_TIMEOUT", "MAX_JITTER",
                "MODEL_PLANNING_HIGH_THRESHOLD", "MODEL_PLANNING_MEDIUM_THRESHOLD",
                "MODEL_CODING_HIGH_THRESHOLD", "MODEL_CODING_MEDIUM_THRESHOLD"
            ]
            for key in numeric_settings:
                if key in settings_dict and settings_dict[key] is not None:
                    try:
                        if "." in str(settings_dict[key]): settings_dict[key] = float(settings_dict[key])
                        else: settings_dict[key] = int(settings_dict[key])
                    except (ValueError, TypeError): pass # Keep original if conversion fails

            bool_settings = ["RELOAD"]
            for key in bool_settings:
                 if key in settings_dict and isinstance(settings_dict[key], str):
                      settings_dict[key] = settings_dict[key].lower() in ("true", "yes", "1", "t", "y")

            logger.info("Settings loading complete.")
            return settings_dict
        # --- END REPLACE load_settings ---

        # --- Keep update_settings and initial load ---
        def update_settings():
            global settings
            settings.clear()
            new_settings = load_settings()
            settings.update(new_settings)
            logger.info("Settings have been updated from environment variables")
            return settings

        settings = load_settings()
        ```
*   **Verification:** Run `python -c "from src.config.settings import settings; print(settings)"`. Check `API_KEYS` and model formats.

**Phase 2: Update Utilities (`src/utils/openai_setup.py`, `src/utils/model_selection.py`)**

*   **Objective:** Create helpers to parse identifiers, configure the global `openai` client, and select only the `model_name` string.
*   **File:** `src/utils/openai_setup.py`
*   **Action:** Replace the *entire file content* with:
    ```python
    """
    LLM Client Configuration and Tracing Utility

    Configures the global 'openai' library client based on settings
    and manages conditional tracing.
    """
    import os
    import logging
    import openai # Import the base library
    from typing import Dict, Tuple, Any
    from dotenv import load_dotenv

    from src.config.settings import settings, PROVIDER_CONFIG

    logger = logging.getLogger(__name__)

    # --- Model Identifier Parser ---
    def parse_model_identifier(full_model_name: str) -> Tuple[str, str]:
        """Parses 'provider/model-name' string. Defaults to 'openai'."""
        if not isinstance(full_model_name, str):
            full_model_name = str(full_model_name)
        if "/" in full_model_name:
            provider, model_name = full_model_name.split("/", 1)
            return provider.lower(), model_name
        else:
            return "openai", full_model_name

    # --- Global Client Configuration ---
    def configure_global_llm_client(provider: str):
        """
        Configures the global openai library client attributes (api_key, base_url)
        for the specified provider.

        Args:
            provider: Lowercase name of the provider to configure globally.

        Raises:
            ValueError: If provider config or API key is missing.
        """
        provider_lower = provider.lower()
        logger.info(f"Configuring global 'openai' library client for provider: {provider_lower}")

        if provider_lower not in PROVIDER_CONFIG:
            logger.error(f"Configuration missing for global provider setup: {provider_lower}")
            raise ValueError(f"Unknown LLM provider for global config: {provider_lower}")

        provider_conf = PROVIDER_CONFIG[provider_lower]
        api_key_env_var = provider_conf["api_key_env"]
        api_key = settings.get("API_KEYS", {}).get(provider_lower)

        if not api_key:
            logger.error(f"API key for provider '{provider_lower}' not found for global config. Check env var '{api_key_env_var}'.")
            raise ValueError(f"API key for provider '{provider_lower}' is missing for global config.")

        base_url = provider_conf.get("base_url")

        try:
            openai.api_key = api_key # Set global key
            # Set global base_url ONLY if it's not None (i.e., for non-openai providers)
            if base_url:
                openai.base_url = base_url
                # For openai>=1.0, need to configure the *client* instance,
                # but agents SDK might use the global vars OR a default client.
                # Let's try configuring the default client instance too.
                # This part is slightly uncertain depending on SDK internals.
                try:
                     # Attempt to configure default async client
                     openai.base_url = base_url # This might affect default client in v1+
                     # If using specific client instances later, this might not be needed
                     logger.info(f"Set global openai.base_url for {provider_lower}: {base_url}")
                except Exception as client_config_err:
                     logger.warning(f"Could not configure default client base_url: {client_config_err}")
            else:
                 # Ensure base_url is reset if switching back to openai default
                 if hasattr(openai, 'base_url'):
                      openai.base_url = None # Or openai.api_base for older versions
                 logger.info(f"Using default OpenAI base URL (global config).")

            # Log the key being used (masked)
            masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "..."
            logger.info(f"Global 'openai' client configured for provider '{provider_lower}' using key from {api_key_env_var} (Key: {masked_key})")

        except Exception as e:
            logger.exception(f"Error configuring global openai client for {provider_lower}: {e}")
            raise ValueError(f"Failed to configure global client for {provider_lower}") from e


    # --- Tracing Configuration ---
    def configure_tracing():
        """Disables SDK tracing if primary provider is not 'openai'."""
        try:
            default_model_full = settings.get("MODEL_DEFAULT", "openai/gpt-4o-mini")
            primary_provider, _ = parse_model_identifier(default_model_full)
            from agents import set_tracing_disabled # Dynamic import

            if primary_provider != "openai":
                logger.info(f"Primary provider '{primary_provider}' != 'openai'. Disabling OpenAI tracing.")
                set_tracing_disabled(disabled=True)
            else:
                logger.info("Primary provider is 'openai'. OpenAI tracing enabled.")
                set_tracing_disabled(disabled=False)
        except ImportError:
             logger.warning("Could not import 'set_tracing_disabled'. Tracing config skipped.")
        except Exception as e:
            logger.warning(f"Could not configure tracing: {e}", exc_info=True)

    # --- Deprecated Wrapper (Keep from original, but it's now unused) ---
    def setup_openai_client():
        """DEPRECATED: Global client is configured by configure_global_llm_client."""
        logger.warning("Called deprecated setup_openai_client. Configuration is now global.")
        # Optionally, trigger the global config here if needed as a fallback
        # primary_provider, _ = parse_model_identifier(settings.get("MODEL_DEFAULT"))
        # configure_global_llm_client(primary_provider)
        return None # Return None as it doesn't return a client anymore

    # --- Load .env ---
    load_dotenv()
    ```
*   **File:** `src/utils/model_selection.py`
*   **Action:** Modify `ModelSelectionStrategy.select_model` to return *only* the `model_name` string.
    ```python
    # src/utils/model_selection.py
    # ... (imports, including parse_model_identifier) ...

    class ModelSelectionStrategy:
        def __init__(self, ...): # Keep init as is
            # ...
            pass

        def select_model(self, task: str, complexity: float) -> str: # Return type is now str
            """
            Select the configured model NAME string for a given task.
            Provider is handled globally at startup.

            Args:
                task: Type of task (planning, coding, triage, code_generation).
                complexity: Complexity score (0-1). Used for logging/potential future logic.

            Returns:
                Model name string (e.g., "o3-mini", "gpt-4o")
            """
            try:
                task_map = { "code_generation": "coding" }
                standard_task = task_map.get(task, task)

                full_model_identifier = self.model_config.get(standard_task, self.default_model_full)
                logger.debug(f"Selecting model for task '{task}'. Config: '{full_model_identifier}'. Complexity: {complexity:.2f}")

                # Parse provider and model name
                provider, model_name = parse_model_identifier(full_model_identifier)

                logger.info(f"Selected model name for '{task}': '{model_name}' (from provider '{provider}')")
                return model_name # Return ONLY the name string

            except Exception as e:
                logger.exception(f"Error selecting model for task '{task}'. Falling back.")
                try:
                    _, default_model_name = parse_model_identifier(self.default_model_full)
                    return default_model_name
                except Exception:
                    return "gpt-4o-mini" # Absolute fallback name

        # --- Keep update_tool_choice and calculate_timeout ---
        # ...
    ```
*   **Verification:** Run `python -c "from src.utils.model_selection import ModelSelectionStrategy; s=ModelSelectionStrategy(); print(s.select_model('planning', 0.8))"`. Verify it prints *only* the model name string (e.g., `"gpt-4o"` or `"o3-mini"`).

**Phase 4: Simplify Agent Setup (`src/agents/setup.py`)**

*   **Objective:** Revert agent setup to simply pass the selected model name string, relying on the globally configured client.
*   **File:** `src/agents/setup.py`
*   **Action:**
    1.  **Imports:** Remove imports for `get_llm_client`, `parse_model_identifier`. Keep `ModelSelectionStrategy` and imports for `Agent`, `Blueprint`, `ScriptOutput`, `settings`.
    2.  **Remove `_setup_agent_internal`:** Delete this helper function entirely.
    3.  **Restore `setup_*` Functions:** Revert `setup_test_planner_agent`, `setup_postman_coder`, `setup_playwright_coder`, `setup_coder_agent`, `setup_triage_agent`, and `setup_all_agents` back to their *original* structure from `... (1).zip.xml`, where they directly instantiate `Agent` using the model name string obtained from `settings` or the `model_strategy`. Crucially, ensure `output_type=Blueprint` is passed to `setup_test_planner_agent`.
        ```python
        # src/agents/setup.py - Reverted Example Snippet

        # ... (SDK Imports, Local Imports: Blueprint, ScriptOutput, settings) ...
        from src.utils.model_selection import ModelSelectionStrategy # Keep this

        logger = logging.getLogger(__name__)
        model_strategy = ModelSelectionStrategy() # Keep instance

        # No _setup_agent_internal

        def setup_test_planner_agent(model: Optional[str] = None, complexity: float = 0.7) -> Agent: # Add complexity arg if needed elsewhere
            """Set up the Test Planner agent."""
            # Select ONLY the model name string using the strategy
            selected_model_name = model_strategy.select_model("planning", complexity)
            # Use override if provided, otherwise use selected name
            model_to_use = model if model else selected_model_name # model param is override name

            logger.info(f"Setting up Test Planner agent with model name: {model_to_use}")

            test_planner_agent = Agent(
                name="Test Planner",
                model=model_to_use, # Use the model name string
                instructions="""... [Original Instructions] ...""",
                output_type=Blueprint # Ensure this is passed for structured output
            )
            logger.info(f"Test Planner agent set up with model: {model_to_use}")
            return test_planner_agent

        def setup_postman_coder(model: Optional[str] = None, complexity: float = 0.6) -> Agent: # Add complexity arg if needed elsewhere
            """Set up the Postman Coder agent."""
            selected_model_name = model_strategy.select_model("coding", complexity)
            model_to_use = model if model else selected_model_name
            logger.info(f"Setting up Postman Coder agent with model name: {model_to_use}")
            postman_coder = Agent(
                name="PostmanCoder",
                model=model_to_use, # Use model name string
                instructions="""... [Original Instructions] ...""",
                # No output_type needed if it doesn't generate structured output directly
            )
            logger.info(f"Postman Coder agent set up with model: {model_to_use}")
            return postman_coder

        # ... Revert setup_playwright_coder similarly ...

        def setup_coder_agent(model: Optional[str] = None, complexity: float = 0.7) -> Agent: # Add complexity arg if needed elsewhere
             """Set up the Coder agent."""
             selected_model_name = model_strategy.select_model("coding", complexity)
             model_to_use = model if model else selected_model_name
             logger.info(f"Setting up Coder agent with model name: {model_to_use}")

             # Setup sub-agents (they will also use their configured models implicitly)
             postman_sub_agent = setup_postman_coder(complexity=complexity) # Pass complexity if needed
             playwright_sub_agent = setup_playwright_coder(complexity=complexity) # Pass complexity if needed

             coder_agent = Agent(
                 name="Test Coder",
                 model=model_to_use, # Use model name string
                 instructions="""... [Original Instructions] ...""",
                 output_type=ScriptOutput, # Ensure this is passed
                 tools=[
                     postman_sub_agent.as_tool(...),
                     playwright_sub_agent.as_tool(...)
                 ]
             )
             logger.info(f"Coder agent set up with model: {model_to_use}")
             return coder_agent

        # ... Revert setup_triage_agent similarly ...
        # ... Revert setup_all_agents similarly, calling the reverted setup functions ...
        def setup_all_agents() -> Dict[str, Agent]:
            """Set up all agents using configured models."""
            logger.info("Setting up all agents...")
            agents = {
                # Calls will now use the simplified setup functions above
                "planning": setup_test_planner_agent(complexity=0.7),
                "coding": setup_coder_agent(complexity=0.7),
                "triage": setup_triage_agent(complexity=0.3)
            }
            logger.info(f"Successfully set up agents: {', '.join(agents.keys())}")
            # Module-level assignment (if needed)
            import src.agents as agents_module
            for name, agent in agents.items():
                setattr(agents_module, f"{name}_agent", agent)
            return agents

        ```
*   **Verification:** Run `python -c "from src.agents.setup import setup_all_agents; agents = setup_all_agents(); print(agents)"`. Verify agents are created using only model name strings.

**Phase 5: Correct Agent Execution Calls (`src/agents/test_generation.py`)**

*   **Objective:** Ensure the setup functions are called correctly and pass the agent instances to runners.
*   **File:** `src/agents/test_generation.py`
*   **Action:**
    1.  **In `process_openapi_spec`:**
        *   Remove the line `model=model_strategy.select_model(...)`.
        *   Modify the call to `setup_test_planner_agent` to pass only `complexity` (and potentially the `model` override string if that feature is desired later, but not the tuple). The `setup_test_planner_agent` function now internally uses the strategy to get the *name*.
            ```python
            # Corrected call inside process_openapi_spec
            test_planner = setup_test_planner_agent(complexity=complexity)
            ```
        *   Ensure `trace_id` is handled correctly (generated early).
    2.  **In `generate_test_scripts`:**
        *   Remove the line `model = model_strategy.select_model(...)`.
        *   Modify the call to `setup_coder_agent` similarly:
            ```python
            # Corrected call inside generate_test_scripts
            coder_agent = setup_coder_agent(complexity=complexity)
            ```
        *   Ensure `trace_id` is handled correctly.
*   **Verification:** Run `test_api.py`. Verify logs show the correct model *name* being passed during agent setup, and that execution proceeds without errors related to model arguments.

**Phase 6: Configure Global Client and Tracing on Startup (`src/main.py`)**

*   **Objective:** Configure the global `openai` library client and tracing based on `MODEL_DEFAULT`.
*   **File:** `src/main.py`
*   **Action:**
    1.  **Imports:** Add `from .utils.openai_setup import configure_global_llm_client, configure_tracing, parse_model_identifier` and `from .config.settings import settings`. Remove the old `setup_openai_client` import if it was used directly.
    2.  **Add Startup Logic:** *After* `logger = configure_logging()` and *before* `app = FastAPI(...)` or `setup_all_agents()`:
        ```python
        # src/main.py

        # ... (dotenv load, imports) ...
        logger = configure_logging()

        # --- ADD GLOBAL CONFIGURATION ---
        try:
            # Determine the primary provider from default model setting
            default_model_full = settings.get("MODEL_DEFAULT", "openai/gpt-4o-mini")
            primary_provider, _ = parse_model_identifier(default_model_full)

            # Configure the global openai client for the primary provider
            configure_global_llm_client(primary_provider)

            # Configure tracing based on the primary provider
            configure_tracing()

            logger.info(f"Global client and tracing configured for primary provider: {primary_provider}")

        except Exception as config_err:
             logger.error(f"CRITICAL: Failed during global client/tracing configuration: {config_err}", exc_info=True)
             # Optionally exit if this configuration is essential
             # sys.exit(1)
        # --- END GLOBAL CONFIGURATION ---


        # Create FastAPI application
        app = FastAPI(...)
        # ... (middleware, exception handlers) ...

        # Initialize agents (they will now implicitly use the globally configured client)
        try:
            agents = setup_all_agents()
            logger.info("Agents initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing agents: {str(e)}", exc_info=True)
            agents = None

        # ... (rest of app setup, routes, main function) ...
        ```
*   **Verification:** Start the app with `MODEL_DEFAULT=openai/...` and check logs for OpenAI client config + tracing enabled. Restart with `MODEL_DEFAULT=google/...` and check logs for Google client config (base URL) + tracing disabled.

**Phase 7: Final Testing**

*   **Objective:** Validate end-to-end functionality with different providers.
*   **Actions:** Repeat the testing steps from **Phase 10** of the previous plan. Crucially:
    *   Verify `o3-mini` works for `MODEL_PLANNING`.
    *   Verify `gpt-4o` works for `MODEL_PLANNING`.
    *   Verify `google/gemini-1.5-flash` works for `MODEL_PLANNING` (if key/endpoint valid).
    *   Verify `MODEL_CODING` and `MODEL_TRIAGE` work with different providers.
    *   Check logs to ensure the correct client config (base URL) and tracing status align with the configured primary provider.

This revised plan simplifies the integration by configuring the underlying `openai` library globally, which seems to be how the SDK implicitly worked with `o3-mini` + structured output in your original codebase. It avoids complex agent instantiation logic and should restore the previous behavior while enabling provider switching via `.env`. Remember to ensure your Pydantic models (`src/blueprint/models.py`) are fully reverted to the state in the original `(1).zip.xml` file before starting this plan, except for the `schema_extra` -> `json_schema_extra` rename.