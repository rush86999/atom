# LLMService API Reference

**Version:** 1.0.0
**Last Updated:** March 22, 2026
**Phase:** 222-llm-service-enhancement

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [API Reference](#api-reference)
5. [Migration Guide](#migration-guide)
6. [Examples](#examples)
7. [Common Patterns](#common-patterns)
8. [Performance Tips](#performance-tips)
9. [Troubleshooting](#troubleshooting)

---

## Overview

### What is LLMService?

`LLMService` is a unified interface for LLM interactions across the Atom platform. It wraps the advanced `BYOKHandler` infrastructure to provide a simplified, consistent API for text generation, streaming responses, structured output, and cognitive tier routing.

**Key Benefits:**
- **Unified Interface**: Single entry point for all LLM operations
- **Cost Optimization**: Intelligent provider routing and cognitive tier selection
- **Structured Output**: Built-in Pydantic model validation with instructor
- **Streaming Support**: Token-by-token streaming for real-time responses
- **Cognitive Tiers**: 5-tier intelligent routing system (MICRO to COMPLEX)
- **Provider Fallback**: Automatic provider fallback on failures
- **Type Safety**: Full type hints for better IDE support

### Architecture

```
┌─────────────────────────────────────────────────────┐
│                   LLMService                        │
│  (Unified Interface for LLM Interactions)           │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│                   BYOKHandler                       │
│  (Provider Selection, Cost Optimization, Routing)    │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│              LLM Providers                          │
│  (OpenAI, Anthropic, DeepSeek, Gemini, MiniMax...)  │
└─────────────────────────────────────────────────────┘
```

### Core Features

1. **Simple Text Generation**: `generate()` for basic completions
2. **Streaming Responses**: `stream_completion()` for real-time token streaming
3. **Structured Output**: `generate_structured()` for Pydantic-validated responses
4. **Cognitive Tier Routing**: `generate_with_tier()` for cost-optimized intelligent routing
5. **Provider Selection**: `get_optimal_provider()` and `get_ranked_providers()` for cost estimation
6. **Routing Info**: `get_routing_info()` for previewing model selection without API calls

---

## Installation

### Requirements

```bash
# Core dependencies
pip install fastapi pydantic openai anthropic

# Optional: For structured output
pip install instructor

# Optional: For token estimation
pip install tiktoken
```

### Import

```python
from core.llm_service import LLMService
from core.llm_service import LLMProvider, LLMModel
```

---

## Quick Start

### Basic Usage

```python
from core.llm_service import LLMService

# Initialize service
service = LLMService(workspace_id="default")

# Simple text generation
response = await service.generate(
    prompt="Explain quantum computing in simple terms",
    model="auto"  # Automatically selects optimal model
)
print(response)
```

### Streaming

```python
# Stream responses token-by-token
async for token in service.stream_completion(
    messages=[{"role": "user", "content": "Tell me a story"}]
):
    print(token, end="", flush=True)
```

### Structured Output

```python
from pydantic import BaseModel

class SentimentAnalysis(BaseModel):
    sentiment: str  # "positive", "negative", "neutral"
    confidence: float
    key_points: list[str]

result = await service.generate_structured(
    prompt="Analyze the sentiment of this review...",
    response_model=SentimentAnalysis
)

print(f"Sentiment: {result.sentiment}")
print(f"Confidence: {result.confidence}")
```

### Cognitive Tier Routing

```python
# Use intelligent 5-tier routing for cost optimization
result = await service.generate_with_tier(
    prompt="Write a Python function to sort a list",
    task_type="code"
)

print(f"Response: {result['response']}")
print(f"Tier: {result['tier']}, Model: {result['model']}")
print(f"Cost: ${result['cost_cents']/100:.4f}")
```

---

## API Reference

### Initialization

#### `LLMService(workspace_id: str = "default", db=None)`

Create a new LLMService instance.

**Parameters:**
- `workspace_id` (str): Workspace identifier for BYOK resolution. Default: `"default"`
- `db` (Session, optional): Database session for usage tracking

**Example:**
```python
service = LLMService(workspace_id="my-workspace", db=db)
```

---

### Core Methods

#### `async generate(prompt, system_instruction, model, temperature, max_tokens, **kwargs) -> str`

Generate simple text completion.

**Parameters:**
- `prompt` (str): The user prompt
- `system_instruction` (str): System prompt for the LLM. Default: `"You are a helpful assistant."`
- `model` (str): Model name or `"auto"` for automatic selection. Default: `"auto"`
- `temperature` (float): Sampling temperature (0.0-1.0). Default: `0.7`
- `max_tokens` (int): Maximum tokens to generate. Default: `1000`
- `**kwargs`: Additional parameters passed to BYOKHandler

**Returns:**
- `str`: Generated text response

**Example:**
```python
response = await service.generate(
    prompt="What is the capital of France?",
    temperature=0.3
)
```

---

#### `async generate_completion(messages, model, temperature, max_tokens, **kwargs) -> Dict[str, Any]`

Generate completion with OpenAI-style messages format.

**Parameters:**
- `messages` (List[Dict[str, str]]): Chat messages in OpenAI format
  - Each message has `role` ("system", "user", "assistant") and `content`
- `model` (str): Model name or `"auto"`. Default: `"auto"`
- `temperature` (float): Sampling temperature. Default: `0.7`
- `max_tokens` (int): Maximum tokens to generate. Default: `1000`
- `**kwargs`: Additional parameters

**Returns:**
- `Dict[str, Any]`: Response with keys:
  - `success` (bool): Whether generation succeeded
  - `content` (str): Generated text
  - `text` (str): Alias for content
  - `usage` (Dict): Token usage
    - `prompt_tokens` (int)
    - `completion_tokens` (int)
    - `total_tokens` (int)
  - `model` (str): Model used
  - `provider` (str): Provider used

**Example:**
```python
messages = [
    {"role": "system", "content": "You are a helpful assistant"},
    {"role": "user", "content": "Hello!"},
    {"role": "assistant", "content": "Hi there! How can I help?"},
    {"role": "user", "content": "What's 2+2?"}
]

response = await service.generate_completion(messages)
print(response["content"])
print(f"Tokens used: {response['usage']['total_tokens']}")
```

---

#### `async stream_completion(messages, model, provider_id, temperature, max_tokens, agent_id, db) -> AsyncGenerator[str, None]`

Stream LLM responses token-by-token with automatic provider fallback.

**Parameters:**
- `messages` (List[Dict[str, str]]): Chat messages in OpenAI format
- `model` (str): Model name or `"auto"` for automatic selection. Default: `"auto"`
- `provider_id` (str): Provider ID or `"auto"` for optimal selection. Default: `"auto"`
- `temperature` (float): Sampling temperature. Default: `0.7`
- `max_tokens` (int): Maximum tokens to generate. Default: `1000`
- `agent_id` (str, optional): Agent ID for governance tracking
- `db` (Session, optional): Database session for governance tracking

**Yields:**
- `str`: Individual tokens as they arrive from the LLM

**Example:**
```python
async for token in service.stream_completion(
    messages=[{"role": "user", "content": "Write a haiku"}],
    model="auto",
    provider_id="auto"
):
    print(token, end="", flush=True)
```

**Note:**
- When `provider_id="auto"`, analyzes query complexity to select optimal provider
- Includes automatic provider fallback on failure
- Integrates with governance tracking when `agent_id` and `db` are provided

---

#### `async generate_structured(prompt, response_model, system_instruction, temperature, model, task_type, agent_id, image_payload) -> Optional[BaseModel]`

Generate structured output using Pydantic model validation.

**Parameters:**
- `prompt` (str): The user prompt
- `response_model` (Type[BaseModel]): Pydantic model class for structured output validation
- `system_instruction` (str): System instruction for the LLM. Default: `"You are a helpful assistant."`
- `temperature` (float): Sampling temperature. Default: `0.2`
- `model` (str): Model name or `"auto"` for optimal selection. Default: `"auto"`
- `task_type` (str, optional): Task type hint (e.g., "summarization", "code_generation")
- `agent_id` (str, optional): Agent ID for cost tracking
- `image_payload` (str, optional): Base64 image string or URL for vision support

**Returns:**
- `Optional[BaseModel]`: Instance of `response_model` with validated data, or `None` if generation fails

**Example:**
```python
from pydantic import BaseModel
from typing import List

class DocumentSummary(BaseModel):
    title: str
    summary: str
    key_points: List[str]
    sentiment: str

result = await service.generate_structured(
    prompt="Summarize this document...",
    response_model=DocumentSummary,
    temperature=0.3
)

if result:
    print(f"Title: {result.title}")
    print(f"Summary: {result.summary}")
```

**Note:**
- Tenant-aware routing: BYOK keys used if available, otherwise Managed AI
- Vision support: Pass `image_payload` (Base64 or URL) for multimodal inputs
- Graceful fallback: Returns `None` if instructor unavailable or generation fails
- Auto model selection: When `model="auto"`, selects optimal model for structured output

---

#### `async generate_with_tier(prompt, system_instruction, task_type, user_tier_override, agent_id, image_payload) -> Dict[str, Any]`

Generate response using cognitive tier routing with intelligent 5-tier system.

**Cognitive Tiers:**
- **MICRO**: Ultra-low cost (<$0.01/M tokens), simple tasks
- **STANDARD**: Balanced cost/quality (~$0.50/M tokens), general tasks
- **VERSATILE**: Advanced capabilities (~$2-5/M tokens), complex tasks
- **HEAVY**: High-performance (~$10-20/M tokens), demanding tasks
- **COMPLEX**: Maximum quality (~$30+/M tokens), critical tasks

**Parameters:**
- `prompt` (str): The user query
- `system_instruction` (str): System prompt for the LLM. Default: `"You are a helpful assistant."`
- `task_type` (str, optional): Task type hint (code, chat, analysis, etc.)
- `user_tier_override` (str, optional): User-specified tier (bypasses classification)
  - Valid values: `"micro"`, `"standard"`, `"versatile"`, `"heavy"`, `"complex"`
- `agent_id` (str, optional): Agent ID for cost tracking and escalation history
- `image_payload` (str, optional): Base64/URL image for multimodal input

**Returns:**
- `Dict[str, Any]`: Response with keys:
  - `response` (str): Generated text response
  - `tier` (str): Cognitive tier used (e.g., "standard", "versatile")
  - `provider` (str): Provider ID used (e.g., "openai", "anthropic")
  - `model` (str): Model name used (e.g., "gpt-4o-mini", "claude-3-5-sonnet")
  - `cost_cents` (float): Estimated cost in cents
  - `escalated` (bool): Whether escalation occurred (True if tier was upgraded)
  - `request_id` (str): Unique request ID for tracking
  - `error` (str, optional): Error message if generation failed

**Example:**
```python
result = await service.generate_with_tier(
    prompt="Explain quantum computing in simple terms",
    task_type="analysis"
)

print(result["response"])
print(f"Tier: {result['tier']}, Model: {result['model']}")
print(f"Cost: ${result['cost_cents']/100:.4f}")

# Force specific tier (bypass classification)
result = await service.generate_with_tier(
    prompt="Write a Python function",
    user_tier_override="versatile"
)
```

---

### Provider Selection Methods

#### `get_optimal_provider(complexity, task_type, prefer_cost, tenant_plan, is_managed_service, requires_tools, requires_structured) -> tuple[str, str]`

Get the optimal provider and model for a given complexity level.

**Parameters:**
- `complexity` (str): Query complexity level. Options: `"simple"`, `"moderate"`, `"complex"`, `"advanced"`. Default: `"moderate"`
- `task_type` (str, optional): Task type hint (e.g., "summarization", "code_generation")
- `prefer_cost` (bool): Whether to prefer cost over quality. Default: `True`
- `tenant_plan` (str): Tenant plan for model restrictions. Default: `"free"`
- `is_managed_service` (bool): Whether this is managed service or BYOK. Default: `True`
- `requires_tools` (bool): Whether model must support tool calling. Default: `False`
- `requires_structured` (bool): Whether model must support structured output. Default: `False`

**Returns:**
- `tuple[str, str]`: (provider_id, model_name)

**Example:**
```python
provider, model = service.get_optimal_provider(
    complexity="moderate",
    prefer_cost=True
)
print(f"Using {provider} with {model}")
```

---

#### `get_ranked_providers(complexity, task_type, prefer_cost, tenant_plan, is_managed_service, requires_tools, requires_structured, estimated_tokens, cognitive_tier) -> List[tuple[str, str]]`

Get a ranked list of providers and models using the BPC (Benchmark-Price-Capability) algorithm.

**Cache-Aware Cost Optimization:**
When `estimated_tokens` is provided, uses cache-aware effective cost calculation to prioritize models with good prompt caching support (e.g., Anthropic).

**Cognitive Tier Filtering:**
When `cognitive_tier` is provided, uses 5-tier quality filtering instead of QueryComplexity for more granular control.

**Parameters:**
- `complexity` (str): Query complexity level. Default: `"moderate"`
- `task_type` (str, optional): Task type hint
- `prefer_cost` (bool): Whether to prefer cost over quality. Default: `True`
- `tenant_plan` (str): Tenant plan for model restrictions. Default: `"free"`
- `is_managed_service` (bool): Whether this is managed service or BYOK. Default: `True`
- `requires_tools` (bool): Whether model must support tool calling. Default: `False`
- `requires_structured` (bool): Whether model must support structured output. Default: `False`
- `estimated_tokens` (int): Estimated input token count (for cache hit prediction). Default: `1000`
- `cognitive_tier` (str, optional): Cognitive tier ("micro", "standard", "versatile", "heavy", "complex")

**Returns:**
- `List[tuple[str, str]]`: List of (provider_id, model_name) tuples ranked by value score

**Example:**
```python
providers = service.get_ranked_providers(
    complexity="complex",
    estimated_tokens=5000,
    cognitive_tier="versatile"
)

for provider, model in providers[:3]:
    print(f"{provider}: {model}")
```

---

#### `get_routing_info(prompt, task_type) -> Dict[str, Any]`

Get routing decision info without making an API call.

Useful for UI preview features - shows users which model will be used and estimated cost before generation.

**Parameters:**
- `prompt` (str): The user prompt to analyze
- `task_type` (str, optional): Task type hint

**Returns:**
- `Dict[str, Any]`: Routing info with keys:
  - `complexity` (str): Complexity level
  - `selected_provider` (str): Provider ID
  - `selected_model` (str): Model name
  - `available_providers` (List[str]): List of available providers
  - `cost_tier` (str): Budget/mid/premium
  - `estimated_cost_usd` (float, optional): Estimated cost
  - `error` (str, optional): Error message if no providers available

**Example:**
```python
info = service.get_routing_info("Explain quantum computing")
print(f"Using {info['selected_model']}")
print(f"Estimated cost: ${info['estimated_cost_usd']:.4f}")
```

---

### Helper Methods

#### `get_provider(model) -> LLMProvider`

Get the provider for a given model.

**Parameters:**
- `model` (str): Model name

**Returns:**
- `LLMProvider`: Provider enum value

**Example:**
```python
provider = service.get_provider("gpt-4o")
print(provider)  # LLMProvider.OPENAI
```

---

#### `estimate_tokens(text, model) -> int`

Estimate token count for text.

**Parameters:**
- `text` (str): Text to estimate
- `model` (str): Model name for tokenization. Default: `"gpt-4o-mini"`

**Returns:**
- `int`: Estimated token count

**Example:**
```python
tokens = service.estimate_tokens("Hello world", model="gpt-4o")
print(f"Estimated tokens: {tokens}")
```

---

#### `estimate_cost(input_tokens, output_tokens, model) -> float`

Estimate cost in USD.

**Parameters:**
- `input_tokens` (int): Input token count
- `output_tokens` (int): Output token count
- `model` (str): Model name

**Returns:**
- `float`: Estimated cost in USD

**Example:**
```python
cost = service.estimate_cost(1000, 500, "gpt-4o-mini")
print(f"Estimated cost: ${cost:.4f}")
```

---

#### `classify_tier(prompt, task_type) -> CognitiveTier`

Classify a prompt into a cognitive tier.

Helper method to understand tier decisions without making API calls.

**Parameters:**
- `prompt` (str): The user prompt to classify
- `task_type` (str, optional): Task type hint (code, chat, analysis, etc.)

**Returns:**
- `CognitiveTier`: CognitiveTier enum value (MICRO, STANDARD, VERSATILE, HEAVY, or COMPLEX)

**Example:**
```python
from core.llm.cognitive_tier_system import CognitiveTier

tier = service.classify_tier("Hi there")
print(tier)  # CognitiveTier.MICRO

tier = service.classify_tier("Write a Python REST API", task_type="code")
print(tier)  # CognitiveTier.VERSATILE or HEAVY
```

---

#### `get_tier_description(tier) -> Dict[str, Any]`

Get human-readable description of a cognitive tier.

**Parameters:**
- `tier` (Union[str, CognitiveTier]): Cognitive tier as string or CognitiveTier enum

**Returns:**
- `Dict[str, Any]`: Tier description with keys:
  - `name` (str): Tier name
  - `cost_range` (str): Cost per million tokens
  - `quality_level` (str): Quality description
  - `use_cases` (List[str]): Typical use cases
  - `example_models` (List[str]): Example models in this tier

**Example:**
```python
desc = service.get_tier_description("versatile")
print(desc["cost_range"])  # "~$2-5/M tokens"
print(desc["use_cases"])   # ["Reasoning", "Analysis", "Code generation"]
```

---

#### `is_available() -> bool`

Check if LLM service is available by checking for any initialized clients.

**Returns:**
- `bool`: True if at least one provider is available

**Example:**
```python
if service.is_available():
    print("LLM service is ready")
```

---

## Migration Guide

### From BYOKHandler to LLMService

LLMService provides a simplified wrapper around BYOKHandler. Most BYOKHandler methods are still available through LLMService, but with a cleaner interface.

#### Before (Direct BYOKHandler Usage)

```python
from core.llm.byok_handler import BYOKHandler

handler = BYOKHandler(workspace_id="my-workspace")

# Generate response
response = await handler.generate_response(
    prompt="Explain quantum computing",
    model_type="auto",
    temperature=0.7
)
```

#### After (LLMService Usage)

```python
from core.llm_service import LLMService

service = LLMService(workspace_id="my-workspace")

# Generate response (simpler interface)
response = await service.generate(
    prompt="Explain quantum computing",
    model="auto",
    temperature=0.7
)
```

---

### Migration Patterns

#### Pattern 1: Simple Text Generation

**Before:**
```python
response = await handler.generate_response(
    prompt=prompt,
    system_instruction=system,
    model_type=model,
    temperature=temperature
)
```

**After:**
```python
response = await service.generate(
    prompt=prompt,
    system_instruction=system,
    model=model,
    temperature=temperature
)
```

**Changes:**
- `model_type` → `model` (more consistent naming)
- Simpler return type (str instead of potential dict)

---

#### Pattern 2: Streaming

**Before:**
```python
async for token in handler.stream_completion(
    messages=messages,
    model=model,
    provider_id=provider_id,
    temperature=temperature,
    max_tokens=max_tokens
):
    print(token, end="")
```

**After:**
```python
async for token in service.stream_completion(
    messages=messages,
    model=model,
    provider_id=provider_id,
    temperature=temperature,
    max_tokens=max_tokens
):
    print(token, end="")
```

**Changes:**
- None! Streaming interface is identical
- Added auto provider selection when `provider_id="auto"`

---

#### Pattern 3: Structured Output

**Before:**
```python
result = await handler.generate_structured_response(
    prompt=prompt,
    system_instruction=system,
    response_model=MyModel,
    temperature=temperature
)
```

**After:**
```python
result = await service.generate_structured(
    prompt=prompt,
    system_instruction=system,
    response_model=MyModel,
    temperature=temperature
)
```

**Changes:**
- Simplified method name (`generate_structured` vs `generate_structured_response`)
- Returns `None` on failure (graceful fallback) instead of raising

---

#### Pattern 4: Provider Selection

**Before:**
```python
complexity = handler.analyze_query_complexity(prompt)
provider, model = handler.get_optimal_provider(complexity)
```

**After:**
```python
provider, model = service.get_optimal_provider(
    complexity="moderate"  # Can also use task_type for auto-detection
)
```

**Changes:**
- Complexity analysis happens automatically when using `"auto"` for generation
- Can pass string complexity levels instead of enum

---

### Backward Compatibility

**Good News:** LLMService maintains full backward compatibility with BYOKHandler. All existing BYOKHandler methods are still available:

```python
# You can still access the underlying handler
service.handler.generate_response(...)
service.handler.analyze_query_complexity(...)
service.handler.get_optimal_provider(...)
```

**Migration Strategy:**
1. **Phase 1**: Use LLMService for new features (streaming, structured output, cognitive tier)
2. **Phase 2**: Gradually migrate existing code to LLMService methods
3. **Phase 3**: Remove direct BYOKHandler usage (optional, as it's still accessible)

---

## Examples

### Example 1: Streaming with Progress Tracking

```python
import asyncio
from core.llm_service import LLMService

service = LLMService()

async def stream_with_progress():
    token_count = 0
    async for token in service.stream_completion(
        messages=[{"role": "user", "content": "Write a short story"}],
        model="auto"
    ):
        token_count += 1
        print(token, end="", flush=True)

        # Optional: Track progress
        if token_count % 10 == 0:
            print(f"\n[Received {token_count} tokens...]")

    print(f"\n\nTotal tokens: {token_count}")

asyncio.run(stream_with_progress())
```

---

### Example 2: Structured Output with Nested Models

```python
from pydantic import BaseModel
from typing import List

class Step(BaseModel):
    step_number: int
    description: str
    command: str

class Tutorial(BaseModel):
    title: str
    difficulty: str  # "beginner", "intermediate", "advanced"
    estimated_time: str
    steps: List[Step]

service = LLMService()

async def generate_tutorial():
    result = await service.generate_structured(
        prompt="Create a tutorial for setting up a Python virtual environment",
        response_model=Tutorial,
        temperature=0.3
    )

    if result:
        print(f"Title: {result.title}")
        print(f"Difficulty: {result.difficulty}")
        print(f"Estimated Time: {result.estimated_time}")
        print("\nSteps:")
        for step in result.steps:
            print(f"{step.step_number}. {step.description}")
            print(f"   Command: {step.command}")

asyncio.run(generate_tutorial())
```

---

### Example 3: Tier-Based Cost Optimization

```python
from core.llm_service import LLMService

service = LLMService()

async def optimize_cost():
    prompts = [
        ("Hi", "chat"),
        ("Explain photosynthesis", "explanation"),
        ("Write a Python REST API", "code"),
        ("Design a microservices architecture", "architecture")
    ]

    total_cost = 0

    for prompt, task_type in prompts:
        result = await service.generate_with_tier(
            prompt=prompt,
            task_type=task_type
        )

        cost_usd = result['cost_cents'] / 100
        total_cost += cost_usd

        print(f"Prompt: {prompt[:50]}...")
        print(f"  Tier: {result['tier']}")
        print(f"  Model: {result['model']}")
        print(f"  Cost: ${cost_usd:.4f}")
        print(f"  Escalated: {result['escalated']}")
        print()

    print(f"Total cost: ${total_cost:.4f}")

asyncio.run(optimize_cost())
```

---

### Example 4: Provider Selection with Cost Estimation

```python
from core.llm_service import LLMService

service = LLMService()

def compare_providers():
    prompt = "Analyze the pros and cons of remote work"

    # Get routing info without making API call
    info = service.get_routing_info(prompt)

    print(f"Selected Provider: {info['selected_provider']}")
    print(f"Selected Model: {info['selected_model']}")
    print(f"Complexity: {info['complexity']}")
    print(f"Estimated Cost: ${info['estimated_cost_usd']:.4f}")

    # Get ranked providers for comparison
    ranked = service.get_ranked_providers(
        complexity=info['complexity'],
        estimated_tokens=1000
    )

    print("\nRanked Providers:")
    for i, (provider, model) in enumerate(ranked[:5], 1):
        print(f"{i}. {provider}: {model}")

compare_providers()
```

---

### Example 5: Migration Example (Before/After)

**Before (BYOKHandler):**
```python
from core.llm.byok_handler import BYOKHandler

handler = BYOKHandler(workspace_id="default")

async def old_way():
    # Analyze complexity
    complexity = handler.analyze_query_complexity("Write Python code")

    # Get optimal provider
    provider, model = handler.get_optimal_provider(complexity)

    # Generate response
    response = await handler.generate_response(
        prompt="Write a Python function to sort a list",
        model_type=model,
        temperature=0.7
    )

    print(response)
```

**After (LLMService):**
```python
from core.llm_service import LLMService

service = LLMService(workspace_id="default")

async def new_way():
    # All-in-one: auto provider selection + generation
    response = await service.generate(
        prompt="Write a Python function to sort a list",
        model="auto",  # Auto-selects optimal provider
        temperature=0.7
    )

    print(response)
```

**Benefits:**
- Simpler, cleaner code
- Automatic provider selection
- Unified interface
- Less boilerplate

---

## Common Patterns

### Pattern 1: Streaming with Progress

```python
async def stream_with_progress(service, prompt):
    token_count = 0
    start_time = time.time()

    async for token in service.stream_completion(
        messages=[{"role": "user", "content": prompt}],
        model="auto"
    ):
        token_count += 1
        print(token, end="", flush=True)

        # Optional: Progress updates every 50 tokens
        if token_count % 50 == 0:
            elapsed = time.time() - start_time
            rate = token_count / elapsed
            print(f"\n[Speed: {rate:.1f} tokens/sec]")

    print(f"\n\nTotal: {token_count} tokens in {elapsed:.1f}s")
```

---

### Pattern 2: Structured Output with Nested Models

```python
class Section(BaseModel):
    title: str
    content: str

class Document(BaseModel):
    title: str
    sections: List[Section]
    summary: str

result = await service.generate_structured(
    prompt="Create a documentation page for REST APIs",
    response_model=Document
)
```

---

### Pattern 3: Tier-Based Cost Optimization

```python
# Automatic tier selection for cost optimization
result = await service.generate_with_tier(
    prompt="Summarize this article",
    task_type="summarization"
)

# Check if escalation occurred (quality issue)
if result['escalated']:
    print(f"Tier escalated due to quality issues")
    print(f"Final tier: {result['tier']}")

# Track costs
cost_usd = result['cost_cents'] / 100
print(f"Generation cost: ${cost_usd:.4f}")
```

---

### Pattern 4: Provider Fallback Handling

```python
async def generate_with_fallback(service, prompt):
    """Generate with automatic provider fallback on failure."""
    try:
        response = await service.generate(
            prompt=prompt,
            model="auto"
        )
        return response
    except Exception as e:
        print(f"Primary generation failed: {e}")
        print("Retrying with different provider...")

        # Retry with explicit provider
        response = await service.generate(
            prompt=prompt,
            model="gpt-4o-mini"
        )
        return response
```

---

## Performance Tips

### 1. Use Appropriate Tiers

**Simple queries → MICRO tier (90% cost savings)**
```python
# Greetings, basic questions
await service.generate_with_tier(
    prompt="Hi there!",
    task_type="chat"  # Will select MICRO tier
)
```

**Code generation → COMPLEX tier (best quality)**
```python
# Critical code generation
await service.generate_with_tier(
    prompt="Write a production-ready authentication system",
    task_type="code",
    user_tier_override="complex"  # Force highest tier
)
```

---

### 2. Enable Caching for Repeated Prompts

```python
# Long prompts benefit from prompt caching (90% discount)
# Use get_ranked_providers with estimated_tokens

ranked = service.get_ranked_providers(
    complexity="moderate",
    estimated_tokens=5000,  # Large prompt → caching enabled
    prefer_cost=True
)

# Ranking will prioritize models with good caching support (e.g., Anthropic)
provider, model = ranked[0]
```

---

### 3. Use Streaming for Real-Time Feedback

```python
# Streaming reduces perceived latency
async for token in service.stream_completion(
    messages=[{"role": "user", "content": "Generate a long report"}],
    model="auto"
):
    print(token, end="", flush=True)  # Immediate feedback
```

---

### 4. Batch Similar Requests

```python
# Group similar prompts to benefit from caching
prompts = [
    "Summarize this article about AI",
    "Summarize this article about ML",
    "Summarize this article about DL"
]

for prompt in prompts:
    result = await service.generate(prompt)
    # Subsequent requests benefit from cache
```

---

### 5. Use Routing Info for Cost Preview

```python
# Preview cost before generation
info = service.get_routing_info("Explain quantum computing")

if info['estimated_cost_usd'] > 0.10:
    print(f"Warning: This request will cost ${info['estimated_cost_usd']:.4f}")
    user_confirm = input("Continue? (y/n): ")
    if user_confirm.lower() != 'y':
        return
```

---

### 6. Monitor Escalation Rates

```python
# High escalation rate = wrong tier selected
result = await service.generate_with_tier(
    prompt="Complex query",
    task_type="analysis"
)

if result['escalated']:
    # Log for analysis
    logger.warning(f"Request escalated: {result['request_id']}")

# Target: <10% escalation rate
# If higher, consider increasing min_tier in workspace preferences
```

---

## Troubleshooting

### Issue 1: "No LLM providers available"

**Symptom:** All generation calls fail with "No LLM providers available"

**Diagnosis:**
```python
# Check if providers are configured
service = LLMService()
print(f"Available: {service.is_available()}")

# Check handler clients
print(f"Clients: {list(service.handler.clients.keys())}")
```

**Solutions:**
1. Configure BYOK keys in settings or environment variables
2. Check API key validity
3. Verify network connectivity

---

### Issue 2: High costs despite tier routing

**Symptom:** Costs are higher than expected

**Diagnosis:**
```python
# Check which tier is being selected
result = await service.generate_with_tier(prompt="Test")
print(f"Tier: {result['tier']}")
print(f"Model: {result['model']}")
print(f"Cost: ${result['cost_cents']/100}")
```

**Solutions:**
1. Set `max_tier` in workspace preferences to limit maximum tier
2. Use `user_tier_override="standard"` for cost-sensitive workloads
3. Check if escalation is happening (`result['escalated']`)

---

### Issue 3: Structured output returns None

**Symptom:** `generate_structured` returns `None`

**Diagnosis:**
```python
# Check if instructor is available
try:
    import instructor
    print("Instructor available")
except ImportError:
    print("Install: pip install instructor")

# Check if clients are available
if not service.is_available():
    print("No LLM clients configured")
```

**Solutions:**
1. Install instructor: `pip install instructor`
2. Configure BYOK keys
3. Check Pydantic model is valid

---

### Issue 4: Slow streaming response

**Symptom:** Streaming has high latency

**Diagnosis:**
```python
import time
start = time.time()

async for token in service.stream_completion(messages=[{"role": "user", "content": "Test"}]):
    if token:
        print(f"First token latency: {time.time() - start:.2f}s")
        break
```

**Solutions:**
1. Check network latency to provider
2. Use geographically closer providers
3. Consider using faster models (e.g., gpt-4o-mini instead of claude-opus)

---

### Issue 5: Tier classification seems wrong

**Symptom:** Simple queries routed to expensive tiers

**Diagnosis:**
```python
# Check tier classification
tier = service.classify_tier("Hi there")
print(f"Classified tier: {tier.value}")

# Get tier description
desc = service.get_tier_description(tier)
print(f"Use cases: {desc['use_cases']}")
```

**Solutions:**
1. Provide `task_type` hint for better classification
2. Use `user_tier_override` to force specific tier
3. Set workspace preferences for consistent tier selection

---

## Appendix

### Type Hints

```python
from typing import Optional, Dict, Any, List, Union, Type, AsyncGenerator
from pydantic import BaseModel
from core.llm.cognitive_tier_system import CognitiveTier

class LLMService:
    async def generate(
        self,
        prompt: str,
        system_instruction: str = "You are a helpful assistant.",
        model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> str: ...

    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "auto",
        provider_id: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        agent_id: Optional[str] = None,
        db = None
    ) -> AsyncGenerator[str, None]: ...

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        system_instruction: str = "You are a helpful assistant.",
        temperature: float = 0.2,
        model: str = "auto",
        task_type: Optional[str] = None,
        agent_id: Optional[str] = None,
        image_payload: Optional[str] = None
    ) -> Optional[BaseModel]: ...

    async def generate_with_tier(
        self,
        prompt: str,
        system_instruction: str = "You are a helpful assistant.",
        task_type: Optional[str] = None,
        user_tier_override: Optional[str] = None,
        agent_id: Optional[str] = None,
        image_payload: Optional[str] = None
    ) -> Dict[str, Any]: ...
```

---

### Supported Providers

| Provider | Provider ID | Example Models |
|----------|-------------|----------------|
| OpenAI | `openai` | gpt-4o, gpt-4o-mini, gpt-4-turbo |
| Anthropic | `anthropic` | claude-3-5-sonnet, claude-3-opus, claude-3-haiku |
| DeepSeek | `deepseek` | deepseek-chat, deepseek-reasoner |
| Gemini | `gemini` | gemini-1.5-pro, gemini-1.5-flash |
| MiniMax | `minimax` | minimax-m2.5 |
| Groq | `groq` | llama-3.1-70b-versatile |
| Mistral | `mistral` | mistral-large, mistral-7b |
| Qwen | `qwen` | qwen-plus, qwen-max |
| Cohere | `cohere` | command-r-plus |

---

### Cognitive Tier Reference

| Tier | Cost Range | Use Cases | Example Models |
|------|------------|-----------|----------------|
| **MICRO** | <$0.01/M | Greetings, basic QA | gpt-4o-mini, claude-3-haiku |
| **STANDARD** | ~$0.50/M | General conversation | gpt-4o-mini, mini-m2.5 |
| **VERSATILE** | ~$2-5/M | Complex reasoning | gpt-4o, claude-3-5-sonnet |
| **HEAVY** | ~$10-20/M | Long documents | claude-3-5-sonnet, gpt-4-turbo |
| **COMPLEX** | ~$30+/M | Code generation, architecture | claude-3-opus, gpt-4 |

---

### References

- **LLMService Implementation**: `backend/core/llm_service.py`
- **BYOKHandler**: `backend/core/llm/byok_handler.py`
- **Cognitive Tier System**: `backend/docs/COGNITIVE_TIER_SYSTEM.md`
- **Tests**: `backend/tests/test_llm_service.py`

---

**Document Length:** 1100+ lines
**Last Updated:** March 22, 2026
**Maintained By:** Atom Platform Team
