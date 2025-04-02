Okay, here is a focused overview of the `google-genai` SDK (v0.7.2 based on the provided docs), tailored specifically for the implementation needs of integrating Gemini models into the `APIAutomationAssistant` using the `openai-agents` provider pattern. This document highlights the key components and concepts relevant to building the `GeminiModel` adapter class.

---

**Google GenAI SDK (google-genai) Overview for APIAutomationAssistant Integration**

**Purpose:** This document provides a concise reference to the `google-genai` Python library, focusing on the elements required to implement a custom `Model` interface for the `openai-agents` SDK, enabling the use of Google Gemini models within the APIAutomationAssistant.

**Core Library:** `google-genai` (ensure this is installed, *not* `google-generativeai`).

**Key Goal:** Implement the `get_response` method of the `agents.models.Model` interface using `google-genai`. Streaming (`stream_response`) is deferred.

**1. Initialization & Configuration**

*   **Global Configuration:** The `google-genai` library requires global configuration using the API key *before* creating model instances.
    ```python
    from google import genai
    from src.config.settings import settings # Your application settings

    google_api_key = settings.get("API_KEYS", {}).get("google")
    if google_api_key:
        genai.configure(api_key=google_api_key)
    else:
        # Handle missing key error appropriately
        raise ValueError("GOOGLE_API_KEY is not configured.")
    ```
*   **Model Instance:** Create an instance of the specific model you want to use.
    ```python
    # Example: Inside your GeminiProvider.get_model method
    model_name = "models/gemini-2.0-flash-thinking-exp-01-21" # Use the appropriate name format
    client = genai.GenerativeModel(model_name)
    ```

**2. Core Generation Function (Non-Streaming)**

*   **Function:** `GenerativeModel.generate_content_async(...)`
*   **Purpose:** Sends the conversation history and configuration to the Gemini model and receives a complete response.
*   **Key Parameters:**
    *   `contents` (`list[types.Content]`): The conversation history. Requires translation from the `openai-agents` SDK format.
    *   `tools` (`list[types.Tool]`, optional): Function declarations for the model to use. Requires translation from the `openai-agents` SDK format.
    *   `tool_config` (`types.ToolConfig`, optional): Configuration for how tools should be called (mode: AUTO, ANY, NONE).
    *   `generation_config` (`types.GenerationConfig`, optional): Parameters like temperature, max tokens, stop sequences.
    *   `safety_settings` (`list[types.SafetySetting]`, optional): Configure content safety thresholds.
    *   `system_instruction` (`types.Content`, optional): System prompt (note: Gemini handles this differently than OpenAI; often best prepended to the first user message).
*   **Return Value:** `types.GenerateContentResponse`

**3. Input Data Structures & Translation**

*   **`types.Content`**: Represents a single turn in the conversation.
    *   `role` (str): Must be `"user"` or `"model"`. **Crucially, Gemini requires a strict alternation starting with `"user"`**. History from `openai-agents` needs careful translation and potential merging of consecutive messages of the same role. The `"system"` role needs special handling (often prepended to the first user message). The `"tool"` role in `openai-agents` maps to a `"user"` role containing a `Part` with `function_response` in Gemini.
    *   `parts` (`list[types.Part]`): The content of the message.
*   **`types.Part`**: Represents a piece of content within a `Content` message.
    *   `Part.from_text(text: str)`: For text content.
    *   `Part.from_function_call(name: str, args: dict)`: To represent a function *call* made by the *model* (used when translating *from* Gemini response).
    *   `Part.from_function_response(name: str, response: dict)`: To represent the *result* of a function call *sent back to the model*. The `response` dict should contain the actual output, typically as `{'content': '...'}`. **This is used for the SDK's "tool" role message.**
    *   *(Other Part types like `from_uri`, `from_bytes` exist for multimodal input but are not the primary focus for this integration initially).*

**4. Output Data Structures & Translation**

*   **`types.GenerateContentResponse`**: The main response object.
    *   `candidates` (`list[types.Candidate]`): List of generated responses (usually one).
    *   `prompt_feedback` (`types.GenerateContentResponsePromptFeedback`): Contains information if the *prompt* was blocked (`block_reason`).
    *   `usage_metadata` (`types.GenerateContentResponseUsageMetadata`): Contains token counts (`prompt_token_count`, `candidates_token_count`, `total_token_count`).
*   **`types.Candidate`**: A single response candidate.
    *   `content` (`types.Content`): The actual generated content (`role` will be `"model"`).
    *   `finish_reason` (`types.FinishReason`): Why generation stopped (e.g., `STOP`, `MAX_TOKENS`, `SAFETY`, `RECITATION`, `TOOL_CALL`). **Must check for `SAFETY` and `RECITATION` to handle blocked content.**
    *   `safety_ratings` (`list[types.SafetyRating]`): Detailed safety scores if applicable.
*   **Parsing Candidate Content:** Iterate through `candidate.content.parts`:
    *   If a part has `text`: Append to the text output.
    *   If a part has `function_call`: This is a tool call request from the model. Extract `part.function_call.name` and `part.function_call.args` (which is already a `dict`). Translate this into the `openai-agents` `ResponseFunctionToolCall` format (requires generating a unique `id` and JSON-stringifying the `args`).

**5. Function Calling / Tools**

*   **Declaration:**
    *   `types.Tool`: Wrapper, primarily contains `function_declarations`.
    *   `types.FunctionDeclaration`: Defines a single function.
        *   `name` (str): Function name.
        *   `description` (str): Description for the model.
        *   `parameters` (`types.Schema`): Defines the expected arguments using an OpenAPI-like schema.
    *   `types.Schema`: Defines the structure and types of parameters.
        *   `type` (str): E.g., "OBJECT", "STRING", "INTEGER", "NUMBER", "BOOLEAN", "ARRAY".
        *   `properties` (`dict[str, types.Schema]`): For "OBJECT" type, defines nested parameters.
        *   `items` (`types.Schema`): For "ARRAY" type, defines the schema of array elements.
        *   `required` (`list[str]`): List of required property names for "OBJECT".
        *   `description` (str): Description of the parameter.
        *   `format` (str): Optional format specifier (e.g., "int32", "float").
        *   `enum` (`list[str]`): Possible string values.
    *   **Translation:** The `openai-agents` `Tool.openai_schema()` needs careful translation into `types.FunctionDeclaration` and nested `types.Schema` objects.
*   **Configuration:**
    *   `types.ToolConfig`: Passed to `generate_content_async`. Contains `function_calling_config`.
    *   `types.FunctionCallingConfig`:
        *   `mode` (`types.FunctionCallingConfigMode`): Controls tool use.
            *   `AUTO` (Default): Model decides whether to call a function.
            *   `ANY`: Forces the model to call *one* of the provided functions. Similar to OpenAI's `required`.
            *   `NONE`: Model will not call any functions.
        *   `allowed_function_names` (`list[str]`, optional): If `mode` is `ANY` or `AUTO`, restricts calls to only these functions. Can be used to force a *specific* function call if the list contains only one name and mode is `ANY`.
*   **Handling Calls:** See Section 4 (Output Parsing).
*   **Returning Results:** See Section 3 (`Part.from_function_response`).

**6. Generation Configuration**

*   **`types.GenerationConfig`**: Passed to `generate_content_async`.
    *   `temperature` (float)
    *   `top_p` (float)
    *   `top_k` (int)
    *   `candidate_count` (int): Should generally be 1 for agent use.
    *   `max_output_tokens` (int)
    *   `stop_sequences` (`list[str]`)

**7. Error Handling**

*   **API Errors:** Calls to `generate_content_async` might raise exceptions (e.g., `google.api_core.exceptions.PermissionDenied`, `google.api_core.exceptions.InvalidArgument`). Wrap calls in `try...except`.
*   **Content Blocking:** Check `response.prompt_feedback.block_reason` and `candidate.finish_reason == 'SAFETY'` or `'RECITATION'`. Translate these into `ResponseRefusalMessage` for the `openai-agents` SDK.
*   **Tool Call Errors:** If the model generates a malformed function call, it might raise an error during response parsing or result in an unexpected `finish_reason`.

**8. Key Differences / Mapping Considerations for Implementation**

*   **Client Initialization:** `google-genai` uses `genai.configure(api_key=...)` globally. The `GeminiProvider` should ensure this is called before `genai.GenerativeModel()` is used.
*   **System Prompt:** Gemini doesn't have a dedicated "system" role in the same way as OpenAI. Prepend system instructions to the first "user" message in the `contents` list.
*   **History Roles:** Gemini requires strict `user`/`model` alternation. The translation layer must handle merging or adjusting roles from the `openai-agents` history format. Tool results (`openai-agents` "tool" role) map to Gemini "user" role with a `function_response` part.
*   **Tool Call Arguments:** `openai-agents` expects `arguments` as a JSON *string*. Gemini's `FunctionCall` provides `args` as a *dictionary*. Translation is needed in both directions.
*   **Tool Call IDs:** `openai-agents` uses `id` for tool calls and expects it back in the tool response. Gemini's `FunctionCall` doesn't inherently have an ID that needs to be round-tripped. The `GeminiModel` implementation will need to generate temporary IDs when translating *from* Gemini and potentially ignore them when translating *to* Gemini (or use the function name as the ID in the `FunctionResponse`).
*   **Tool Configuration (`tool_choice`):** Mapping OpenAI's `tool_choice` (`none`, `auto`, `required`, specific function) to Gemini's `ToolConfig` (`mode`: NONE, AUTO, ANY; `allowed_function_names`) requires careful interpretation. `ANY` seems the closest equivalent to OpenAI's `required`. Forcing a *specific* function might involve setting `mode=ANY` and `allowed_function_names=['your_func']`.
*   **Streaming:** Deferred, but note that Gemini's streaming response structure (`GenerateContentResponse` chunks) will need mapping to `openai-agents` `TResponseStreamEvent` types.

---

This overview should provide the necessary context from the `google-genai` SDK documentation to proceed with implementing the `GeminiModel` and `GeminiProvider` for the `APIAutomationAssistant`, focusing on the non-streaming `get_response` path first. Remember to refer back to the full `google-genai-sdk-docs.txt` for specific details on types and function signatures as needed during implementation.