# Setting Up Agents with OpenAI Agents SDK

This guide provides a comprehensive walkthrough for setting up agents using the OpenAI Agents SDK, based on working examples from existing projects.

## Table of Contents

1. [Installation](#installation)
2. [Basic Agent Setup](#basic-agent-setup)
3. [Working with Tools](#working-with-tools)
4. [Agent Handoffs](#agent-handoffs)
5. [Structured Output](#structured-output)
6. [Guardrails](#guardrails)
7. [Tracing and Debugging](#tracing-and-debugging)
8. [Voice Capabilities](#voice-capabilities)
9. [Custom Model Providers](#custom-model-providers)
10. [Advanced Patterns](#advanced-patterns)
11. [Best Practices](#best-practices)

## Installation

Start by setting up your Python environment and installing the OpenAI Agents SDK:

```bash
# Create and activate a virtual environment
python -m venv agents-env
source agents-env/bin/activate  # On Windows: agents-env\Scripts\activate

# Install the SDK
pip install openai-agents

# For voice capabilities (optional)
pip install 'openai-agents[voice]'
```

Ensure you have your OpenAI API key set up as an environment variable:

```bash
# Set API key in your environment
export OPENAI_API_KEY='your-api-key'

# Or in your .env file
OPENAI_API_KEY=your-api-key
```

## Basic Agent Setup

The simplest way to create an agent is as follows:

```python
import asyncio
from agents import Agent, Runner

async def main():
    # Create a basic agent
    agent = Agent(
        name="Assistant",
        instructions="You are a helpful assistant that responds in haikus.",
    )

    # Run the agent with input
    result = await Runner.run(agent, "Tell me about machine learning.")
    
    # Access the agent's response
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())
```

For synchronous code, you can use `run_sync`:

```python
from agents import Agent, Runner

agent = Agent(name="Assistant", instructions="You are a helpful assistant")

result = Runner.run_sync(agent, "Write a haiku about recursion in programming.")
print(result.final_output)
```

Key components:
- `name`: A unique identifier for the agent
- `instructions`: Detailed guidance for how the agent should behave
- `Runner.run()`: Execute the agent with your input asynchronously
- `Runner.run_sync()`: Execute the agent synchronously (for non-async code)
- `result.final_output`: Access the agent's response

## Working with Tools

Tools give agents the ability to perform specific functions:

### Function Tools

```python
import asyncio
from agents import Agent, Runner, function_tool

@function_tool
def get_weather(city: str) -> str:
    """Return the weather for a specified city."""
    # In a real implementation, this would call a weather API
    return f"The weather in {city} is sunny and 75°F."

async def main():
    agent = Agent(
        name="Weather Assistant",
        instructions="You help users check the weather in different cities.",
        tools=[get_weather],
    )

    result = await Runner.run(agent, "What's the weather like in San Francisco?")
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())
```

### Built-in Tools

The SDK provides built-in tools like web search:

```python
import asyncio
from agents import Agent, Runner, WebSearchTool

async def main():
    agent = Agent(
        name="Web Researcher",
        instructions="You are a helpful agent that searches the web for information.",
        tools=[WebSearchTool(user_location={"type": "approximate", "city": "New York"})],
    )

    result = await Runner.run(
        agent,
        "Find the latest news about AI advancements and summarize one key development."
    )
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())
```

## Agent Handoffs

Handoffs allow one agent to transfer control to another agent:

```python
import asyncio
from agents import Agent, Runner, handoff, HandoffInputData
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

# Create specialized agents
spanish_agent = Agent(
    name="Spanish Assistant",
    instructions="You only speak Spanish and are very helpful.",
    handoff_description="A Spanish-speaking assistant."
)

english_agent = Agent(
    name="English Assistant", 
    instructions="You only speak English and are very helpful.",
    handoff_description="An English-speaking assistant."
)

# Create message filter for handoff (optional)
def language_handoff_filter(handoff_message_data: HandoffInputData) -> HandoffInputData:
    # Customize what message history is passed to the handoff agent
    return handoff_message_data

# Create a triage agent that can hand off to specialized agents
triage_agent = Agent(
    name="Language Triage",
    instructions=prompt_with_handoff_instructions(
        "You are a language detector. If a user speaks Spanish, hand off to the Spanish assistant. "
        "If a user speaks English, hand off to the English assistant."
    ),
    handoffs=[
        handoff(spanish_agent, input_filter=language_handoff_filter),
        handoff(english_agent)
    ],
)

async def main():
    # When Spanish is detected, this will hand off to the Spanish agent
    result = await Runner.run(triage_agent, "Hola, ¿cómo estás?")
    print(result.final_output)
    
    # When English is detected, this will hand off to the English agent
    result = await Runner.run(triage_agent, "Hello, how are you?")
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())
```

## Structured Output

You can define specific output structures using Pydantic models:

```python
import asyncio
from pydantic import BaseModel, Field
from agents import Agent, Runner

class ResearchReport(BaseModel):
    title: str = Field(description="The title of the research report")
    summary: str = Field(description="A brief summary of the findings")
    key_points: list[str] = Field(description="List of key points from the research")
    follow_up_questions: list[str] = Field(description="Suggested follow-up questions")

async def main():
    research_agent = Agent(
        name="Research Agent",
        instructions="You create detailed research reports on topics.",
        model="gpt-4o",  # Specify a more capable model for complex tasks
        output_type=ResearchReport,  # Define the expected output structure
    )

    result = await Runner.run(research_agent, "Research the impact of AI on healthcare")
    
    # Access structured data
    report = result.final_output_as(ResearchReport)
    print(f"Title: {report.title}")
    print(f"Summary: {report.summary}")
    print("Key Points:")
    for point in report.key_points:
        print(f"- {point}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Guardrails

Guardrails help ensure the agent's inputs and outputs meet specific criteria:

### Output Guardrails

```python
import asyncio
from pydantic import BaseModel, Field
from agents import (
    Agent, 
    RunContextWrapper, 
    Runner, 
    GuardrailFunctionOutput, 
    output_guardrail
)

class MessageOutput(BaseModel):
    response: str = Field(description="The response to the user's message")

@output_guardrail
async def content_safety_check(
    context: RunContextWrapper, 
    agent: Agent, 
    output: MessageOutput
) -> GuardrailFunctionOutput:
    # Check if response contains sensitive information
    contains_sensitive_info = "credit card" in output.response.lower()
    
    return GuardrailFunctionOutput(
        output_info={"contains_sensitive_info": contains_sensitive_info},
        tripwire_triggered=contains_sensitive_info,
    )

agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant.",
    output_type=MessageOutput,
    output_guardrails=[content_safety_check],
)

async def main():
    try:
        result = await Runner.run(agent, "What should I do with my credit card information?")
        print(result.final_output.response)
    except Exception as e:
        print(f"Guardrail triggered: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Input Guardrails

```python
import asyncio
from agents import (
    Agent, 
    Runner, 
    GuardrailFunctionOutput, 
    input_guardrail,
    TriggeredGuardrail,
)

@input_guardrail
async def profanity_check(input_text: str) -> GuardrailFunctionOutput:
    # Check for inappropriate content
    contains_profanity = "inappropriate_word" in input_text.lower()
    
    return GuardrailFunctionOutput(
        output_info={"contains_profanity": contains_profanity},
        tripwire_triggered=contains_profanity,
    )

agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant.",
    input_guardrails=[profanity_check],
)

async def main():
    try:
        result = await Runner.run(agent, "Tell me about inappropriate_word.")
        print(result.final_output)
    except TriggeredGuardrail as e:
        print(f"Input guardrail triggered: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Tracing and Debugging

The SDK provides built-in tracing capabilities:

```python
import asyncio
from agents import Agent, Runner, trace, gen_trace_id, custom_span

async def main():
    agent = Agent(
        name="Assistant",
        instructions="You are a helpful assistant.",
    )
    
    # Generate a trace ID to track this specific run
    trace_id = gen_trace_id()
    
    # Use the trace context manager to capture the full workflow
    with trace("My Agent Workflow", trace_id=trace_id):
        # Use custom span to track specific parts of your workflow
        with custom_span("User Query Processing"):
            result = await Runner.run(agent, "Tell me about quantum computing")
            print(result.final_output)
        
    print(f"Trace ID: {trace_id}")
    print(f"View trace: https://platform.openai.com/traces/{trace_id}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Disabling Tracing

In development environments, you may want to disable tracing:

```python
from agents import set_tracing_disabled

# Disable tracing for all agents in this session
set_tracing_disabled(disabled=True)
```

## Voice Capabilities

The Agents SDK now supports voice interactions, allowing you to build voice-enabled applications with agents. First, install the voice dependencies:

```bash
pip install 'openai-agents[voice]'
```

### Basic Voice Pipeline

```python
import asyncio
import numpy as np
import sounddevice as sd

from agents import Agent, function_tool
from agents.voice import (
    AudioInput,
    SingleAgentVoiceWorkflow,
    VoicePipeline,
)

# Define a function tool for the agent
@function_tool
def get_weather(city: str) -> str:
    """Get the weather for a given city."""
    return f"The weather in {city} is sunny."

# Create an agent
agent = Agent(
    name="Voice Assistant",
    instructions="You're speaking to a human, so be polite and concise.",
    model="gpt-4o-mini",
    tools=[get_weather],
)

async def main():
    # Create a voice pipeline with the agent
    pipeline = VoicePipeline(workflow=SingleAgentVoiceWorkflow(agent))
    
    # Normally you'd capture real audio, but for this example we'll use silence
    buffer = np.zeros(24000 * 3, dtype=np.int16)  # 3 seconds of silence at 24kHz
    audio_input = AudioInput(buffer=buffer)

    # Run the pipeline
    result = await pipeline.run(audio_input)

    # Set up audio playback
    player = sd.OutputStream(samplerate=24000, channels=1, dtype=np.int16)
    player.start()

    # Stream audio responses
    async for event in result.stream():
        if event.type == "voice_stream_event_audio":
            player.write(event.data)

if __name__ == "__main__":
    asyncio.run(main())
```

### Voice with Handoffs

You can combine voice capabilities with agent handoffs for multilingual voice assistants:

```python
import asyncio
from agents import Agent
from agents.voice import VoicePipeline, SingleAgentVoiceWorkflow
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

# Create specialized language agents
spanish_agent = Agent(
    name="Spanish",
    handoff_description="A spanish speaking agent.",
    instructions=prompt_with_handoff_instructions(
        "You're speaking to a human, so be polite and concise. Speak in Spanish.",
    ),
    model="gpt-4o-mini",
)

# Create main agent with handoff capability
main_agent = Agent(
    name="Assistant",
    instructions=prompt_with_handoff_instructions(
        "You're speaking to a human, so be polite and concise. "
        "If the user speaks in Spanish, handoff to the spanish agent.",
    ),
    model="gpt-4o-mini",
    handoffs=[spanish_agent],
)

# Create voice pipeline
pipeline = VoicePipeline(workflow=SingleAgentVoiceWorkflow(main_agent))

# Usage with audio input and output would be similar to the previous example
```

## Custom Model Providers

The OpenAI Agents SDK now supports custom model providers, enabling you to use compatible models from other providers or your own implementations.

### Using Custom Providers

```python
import asyncio
from agents import Agent, Runner

# Configure a custom model provider
from agents.models import CustomModel, ModelProvider

# Example of setting up a provider for Anthropic models
custom_provider = ModelProvider(
    # Provider-specific configuration
    api_key="your-provider-api-key",
    base_url="https://your-provider-endpoint.com/v1",
)

async def main():
    # Create an agent with a custom model
    agent = Agent(
        name="Assistant",
        instructions="You are a helpful assistant.",
        model=CustomModel(
            provider=custom_provider,
            model="your-provider-model-name"
        )
    )

    result = await Runner.run(agent, "Tell me about quantum computing")
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())
```

### Implementing a Custom Provider

For more advanced customization, you can implement your own model provider:

```python
from agents.models import ModelProvider, ChatCompletionsModel
from pydantic import SecretStr

class MyCustomProvider(ModelProvider):
    api_key: SecretStr
    
    def get_chat_completions_model(self, model_name: str) -> ChatCompletionsModel:
        # Return your custom model implementation
        return MyCustomChatCompletionsModel(provider=self, model=model_name)

# Register your custom provider (optional but recommended)
from agents.models import register_model_provider
register_model_provider("my-provider", MyCustomProvider)

# Usage
agent = Agent(
    name="Custom Model Agent",
    instructions="You are a helpful assistant.",
    model="my-provider/my-custom-model"
)
```

## Advanced Patterns

### Multi-Agent Research System

Here's how to build a more complex research system with multiple agents:

```python
import asyncio
from pydantic import BaseModel, Field
from agents import Agent, Runner, trace, gen_trace_id, function_tool, custom_span

# Define data models
class SearchQuery(BaseModel):
    query: str = Field(description="The search term to use")
    reason: str = Field(description="Why this search is relevant")

class SearchPlan(BaseModel):
    searches: list[SearchQuery] = Field(description="List of searches to perform")

class ResearchReport(BaseModel):
    title: str = Field(description="Report title")
    summary: str = Field(description="Executive summary")
    key_findings: list[str] = Field(description="Key findings from research")
    follow_up_questions: list[str] = Field(description="Suggested follow-up questions")

# Create specialized agents
planner_agent = Agent(
    name="Research Planner",
    instructions="You plan search queries to thoroughly research a topic.",
    model="gpt-4o",
    output_type=SearchPlan,
)

@function_tool
def web_search(query: str) -> str:
    """Perform a web search and return results."""
    # In a real implementation, this would call a search API
    return f"Search results for: {query}..."

search_agent = Agent(
    name="Search Agent",
    instructions="You search the web to find information.",
    tools=[web_search],
)

report_agent = Agent(
    name="Report Writer",
    instructions="You create comprehensive research reports based on search results.",
    model="gpt-4o",
    output_type=ResearchReport,
)

async def main():
    query = "What are the latest developments in quantum computing?"
    trace_id = gen_trace_id()
    
    with trace("Research Workflow", trace_id=trace_id):
        print(f"Starting research on: {query}")
        
        # Step 1: Plan searches
        with custom_span("Planning Search Queries"):
            plan_result = await Runner.run(planner_agent, f"Research topic: {query}")
            search_plan = plan_result.final_output_as(SearchPlan)
            print(f"Generated {len(search_plan.searches)} search queries")
        
        # Step 2: Execute searches
        with custom_span("Executing Searches"):
            search_results = []
            for search_item in search_plan.searches:
                result = await Runner.run(
                    search_agent, 
                    f"Search query: {search_item.query}\nReason: {search_item.reason}"
                )
                search_results.append(result.final_output)
        
        # Step 3: Generate report
        with custom_span("Generating Report"):
            input_text = f"Original query: {query}\n\nSearch results:\n"
            for i, result in enumerate(search_results, 1):
                input_text += f"Result {i}: {result}\n\n"
                
            report_result = await Runner.run(report_agent, input_text)
            report = report_result.final_output_as(ResearchReport)
        
        # Print results
        print(f"\nRESEARCH REPORT: {report.title}")
        print(f"\nSummary: {report.summary}")
        print("\nKey Findings:")
        for finding in report.key_findings:
            print(f"- {finding}")
        
        print(f"\nView trace: https://platform.openai.com/traces/{trace_id}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Agents as Tools

You can also use agents as tools for other agents:

```python
import asyncio
from agents import Agent, Runner

# Create specialized agents
spanish_translator = Agent(
    name="Spanish Translator",
    instructions="You translate text from English to Spanish accurately.",
)

french_translator = Agent(
    name="French Translator",
    instructions="You translate text from English to French accurately.",
)

# Create an orchestrator agent that uses other agents as tools
orchestrator = Agent(
    name="Translation Orchestrator",
    instructions=(
        "You are a translation service. Use the appropriate translation tool "
        "based on the user's request."
    ),
    tools=[
        spanish_translator.as_tool(
            tool_name="translate_to_spanish",
            tool_description="Translate English text to Spanish"
        ),
        french_translator.as_tool(
            tool_name="translate_to_french",
            tool_description="Translate English text to French"
        )
    ]
)

async def main():
    result = await Runner.run(
        orchestrator, 
        "Please translate 'Hello, how are you?' to both Spanish and French."
    )
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())
```

### Forcing Tool Use

You can guide agents to use specific tools when needed:

```python
import asyncio
from agents import Agent, Runner, function_tool

@function_tool
def analyze_sentiment(text: str) -> str:
    """Analyze the sentiment of the provided text."""
    # In a real implementation, this would use a sentiment analysis API
    return "The sentiment is positive."

agent = Agent(
    name="Sentiment Analyzer",
    instructions=(
        "You are a sentiment analysis assistant. "
        "Always use the analyze_sentiment tool to analyze sentiment."
    ),
    tools=[analyze_sentiment],
    force_tool_use=True,  # Force the agent to use tools
)

async def main():
    result = await Runner.run(agent, "What do you think of this product review: 'I love it!'")
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())
```

## Best Practices

1. **Be Specific with Instructions**: Provide clear, detailed instructions to guide agent behavior.

2. **Use Appropriate Models**: Choose models based on task complexity (e.g., gpt-4o for complex tasks, gpt-3.5-turbo for simpler tasks).

3. **Implement Guardrails**: Add input and output guardrails to ensure safety and quality.

4. **Enable Tracing**: Use the tracing system for debugging and performance monitoring.

5. **Structure Complex Systems**: Break complex tasks into smaller, specialized agents.

6. **Handle Errors Gracefully**: Implement proper error handling, especially around guardrails.

7. **Test Thoroughly**: Test agents with various inputs to ensure they behave as expected.

8. **Monitor Performance**: Use traces to monitor agent performance in production.

9. **Manage Costs**: Be mindful of API usage, especially with more advanced models.

10. **Consider Security**: Be careful with sensitive data and implement proper authentication.

11. **Optimize Voice Interactions**: For voice applications, keep prompts concise and design for natural conversation flow.

12. **Customize Model Providers**: Use the most appropriate models for your specific use case, taking advantage of custom model providers when needed.

## Conclusion

The OpenAI Agents SDK provides a powerful framework for building sophisticated agent systems. By following the patterns and examples in this guide, you can create reliable, scalable, and safe agent applications for a wide range of use cases, including text-based and voice-enabled applications.

For the latest information, refer to the [official OpenAI Agents SDK documentation](https://openai.github.io/openai-agents-python/). 