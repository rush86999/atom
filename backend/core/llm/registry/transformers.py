"""Model Metadata Transformers for LLM Registry

This module provides transformer functions that convert raw API responses
from LiteLLM and OpenRouter into the standardized LLMModel schema.

Transformers handle:
- Provider name normalization
- Pricing extraction and conversion
- Capability inference from model names
- Context window extraction
- Metadata preservation
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Capability patterns for inference
VISION_CAPABILITIES = ['vision', 'multimodal', 'image']
TOOL_CAPABILITIES = ['tools', 'function_calling', 'functions']
AUDIO_CAPABILITIES = ['audio', 'speech', 'transcription']
JSON_CAPABILITIES = ['json_mode', 'json']

# Common capability patterns by provider
CAPABILITY_PATTERNS = {
    'vision': [
        'vision', 'gpt-4-v', 'gpt-4o', 'claude-3', 'gemini-',
        'multimodal', 'image', 'vl-'
    ],
    'tools': [
        'turbo', 'gpt-3.5', 'gpt-4', 'claude-3', 'gemini-',
        'function', 'tool'
    ],
    'audio': [
        'audio', 'speech', 'transcription', 'whisper'
    ],
    'json_mode': [
        'json', 'structured'
    ]
}


def normalize_provider(provider: str) -> str:
    """
    Normalize provider name to standard format.

    Maps variations like 'gpt', 'openai', 'claude', 'anthropic'
    to canonical provider names.

    Args:
        provider: Raw provider name from API

    Returns:
        Normalized lowercase provider name

    Examples:
        >>> normalize_provider('gpt')
        'openai'
        >>> normalize_provider('claude')
        'anthropic'
        >>> normalize_provider('openai')
        'openai'
    """
    if not provider:
        return 'unknown'

    provider_lower = provider.lower().strip()

    # OpenAI variations
    if any(p in provider_lower for p in ['openai', 'gpt', 'azure']):
        return 'openai'

    # Anthropic variations
    if any(p in provider_lower for p in ['anthropic', 'claude']):
        return 'anthropic'

    # Google variations
    if any(p in provider_lower for p in ['google', 'gemini', 'palm', 'vertex']):
        return 'google'

    # Meta variations
    if any(p in provider_lower for p in ['meta', 'llama', 'facebook']):
        return 'meta'

    # Mistral variations
    if any(p in provider_lower for p in ['mistral', 'mixtral']):
        return 'mistral'

    # Cohere variations
    if 'cohere' in provider_lower:
        return 'cohere'

    # Perplexity variations
    if 'perplexity' in provider_lower:
        return 'perplexity'

    # DeepSeek variations
    if 'deepseek' in provider_lower:
        return 'deepseek'

    # If no mapping found, return lowercase original
    return provider_lower


def infer_capabilities(model_name: str, description: str = '') -> List[str]:
    """
    Infer model capabilities from model name and description.

    Uses pattern matching to detect common capabilities like vision,
    tools, audio, and JSON mode.

    Args:
        model_name: Model identifier (e.g., 'gpt-4-vision-preview')
        description: Optional description from API

    Returns:
        List of inferred capabilities (e.g., ['vision', 'tools'])

    Examples:
        >>> infer_capabilities('gpt-4-vision-preview')
        ['vision', 'tools']
        >>> infer_capabilities('claude-3-opus')
        ['vision', 'tools']
        >>> infer_capabilities('whisper-1')
        ['audio']
    """
    if not model_name:
        return []

    capabilities = set()
    model_lower = model_name.lower()
    desc_lower = description.lower() if description else ''

    # Check each capability pattern
    for capability, patterns in CAPABILITY_PATTERNS.items():
        for pattern in patterns:
            if pattern in model_lower or pattern in desc_lower:
                capabilities.add(capability)
                break

    # Special case: if it's a GPT-4 or Claude model, it likely has tools
    if any(p in model_lower for p in ['gpt-4', 'gpt-3.5', 'claude-3']):
        capabilities.add('tools')

    # Special case: turbo models have tools
    if 'turbo' in model_lower:
        capabilities.add('tools')

    return sorted(list(capabilities))


def transform_litellm_model(data: Dict, model_name: str) -> Dict[str, Any]:
    """
    Transform LiteLLM model data to LLMModel schema.

    Extracts pricing, context window, and metadata from LiteLLM format.
    Infers capabilities from model name patterns.

    Args:
        data: Raw model data from LiteLLM API
        model_name: Model identifier (key from LiteLLM dict)

    Returns:
        Dictionary matching LLMModel columns

    Examples:
        >>> data = {
        ...     'max_tokens': 8192,
        ...     'input_cost_per_token': 0.00003,
        ...     'output_cost_per_token': 0.00006,
        ...     'litellm_provider': 'openai'
        ... }
        >>> result = transform_litellm_model(data, 'gpt-4')
        >>> result['provider']
        'openai'
        >>> result['context_window']
        8192
    """
    if not isinstance(data, dict):
        logger.warning(f"Invalid data type for model {model_name}: {type(data)}")
        return {}

    # Extract provider
    provider_raw = data.get('litellm_provider', '')
    provider = normalize_provider(provider_raw)

    # If provider unknown, try to infer from model_name
    if provider == 'unknown':
        provider = normalize_provider(model_name)

    # Extract context window (try multiple fields)
    context_window = (
        data.get('max_tokens') or
        data.get('max_input_tokens') or
        data.get('max_context_tokens') or
        None
    )

    # Extract pricing (convert to float if needed)
    input_price = data.get('input_cost_per_token')
    output_price = data.get('output_cost_per_token')

    if input_price is not None:
        try:
            input_price = float(input_price)
        except (ValueError, TypeError):
            input_price = None

    if output_price is not None:
        try:
            output_price = float(output_price)
        except (ValueError, TypeError):
            output_price = None

    # Infer capabilities
    capabilities = infer_capabilities(model_name)

    # Build metadata dict with original data
    metadata = {
        'litellm_provider': provider_raw,
        'mode': data.get('mode', 'chat'),
        'source': 'litellm',
        **{k: v for k, v in data.items() if k not in [
            'input_cost_per_token', 'output_cost_per_token',
            'max_tokens', 'max_input_tokens', 'max_context_tokens',
            'litellm_provider', 'mode'
        ]}
    }

    return {
        'provider': provider,
        'model_name': model_name,
        'context_window': context_window,
        'input_price_per_token': input_price,
        'output_price_per_token': output_price,
        'capabilities': capabilities,
        'provider_metadata': metadata
    }


def transform_openrouter_model(data: Dict) -> Dict[str, Any]:
    """
    Transform OpenRouter model data to LLMModel schema.

    Extracts pricing, context window, and metadata from OpenRouter format.
    Parses model_id to extract provider.

    Args:
        data: Raw model data from OpenRouter API

    Returns:
        Dictionary matching LLMModel columns

    Examples:
        >>> data = {
        ...     'id': 'openai/gpt-4',
        ...     'name': 'GPT-4',
        ...     'context_length': 8192,
        ...     'pricing': {'prompt': 0.00003, 'completion': 0.00006}
        ... }
        >>> result = transform_openrouter_model(data)
        >>> result['provider']
        'openai'
        >>> result['model_name']
        'openai/gpt-4'
    """
    if not isinstance(data, dict):
        logger.warning(f"Invalid data type: {type(data)}")
        return {}

    model_id = data.get('id', '')
    if not model_id:
        logger.warning("OpenRouter model missing 'id' field")
        return {}

    # Extract provider from model_id (format: "provider/model")
    parts = model_id.split('/', 1)
    provider_raw = parts[0] if len(parts) > 1 else ''
    provider = normalize_provider(provider_raw)

    # Extract context window
    context_window = (
        data.get('context_length') or
        data.get('context_window') or
        None
    )

    # Extract pricing
    pricing = data.get('pricing', {})
    if isinstance(pricing, dict):
        input_price = pricing.get('prompt')
        output_price = pricing.get('completion')

        # Convert to float if needed
        if input_price is not None:
            try:
                input_price = float(input_price)
            except (ValueError, TypeError):
                input_price = None

        if output_price is not None:
            try:
                output_price = float(output_price)
            except (ValueError, TypeError):
                output_price = None
    else:
        input_price = None
        output_price = None

    # Infer capabilities from name and description
    name = data.get('name', '')
    description = data.get('description', '')
    capabilities = infer_capabilities(model_id, f"{name} {description}")

    # Build metadata
    metadata = {
        'name': name,
        'description': description,
        'architecture': data.get('architecture'),
        'source': 'openrouter',
        **{k: v for k, v in data.items() if k not in [
            'id', 'name', 'description', 'context_length', 'context_window',
            'pricing', 'architecture'
        ]}
    }

    return {
        'provider': provider,
        'model_name': model_id,
        'context_window': context_window,
        'input_price_per_token': input_price,
        'output_price_per_token': output_price,
        'capabilities': capabilities,
        'provider_metadata': metadata
    }


def transform_batch(
    models: Dict[str, Dict],
    source: str,
    transformer_func: callable
) -> List[Dict[str, Any]]:
    """
    Transform a batch of models using the specified transformer.

    Args:
        models: Dictionary of models (model_id -> model_data)
        source: Source name ('litellm' or 'openrouter')
        transformer_func: Transform function to use

    Returns:
        List of transformed model dictionaries

    Examples:
        >>> litellm_models = {'gpt-4': {...}, 'claude-3': {...}}
        >>> transformed = transform_batch(
        ...     litellm_models,
        ...     'litellm',
        ...     transform_litellm_model
        ... )
        >>> len(transformed)
        2
    """
    transformed = []
    failed = 0

    for model_id, model_data in models.items():
        try:
            if source == 'litellm':
                result = transformer_func(model_data, model_id)
            elif source == 'openrouter':
                result = transformer_func(model_data)
            else:
                logger.warning(f"Unknown source: {source}")
                continue

            if result:
                transformed.append(result)
            else:
                failed += 1

        except Exception as e:
            logger.error(f"Error transforming model {model_id}: {e}")
            failed += 1

    if failed > 0:
        logger.warning(f"Failed to transform {failed} models from {source}")

    logger.info(f"Transformed {len(transformed)} models from {source}")
    return transformed


def merge_duplicate_models(
    models: List[Dict[str, Any]],
    priority_source: str = 'litellm'
) -> List[Dict[str, Any]]:
    """
    Merge duplicate models from different sources.

    When the same model appears from both LiteLLM and OpenRouter,
    prefer the priority_source data.

    Args:
        models: List of transformed model dictionaries
        priority_source: Which source to prefer ('litellm' or 'openrouter')

    Returns:
        List of models with duplicates merged
    """
    unique_models = {}
    duplicate_count = 0

    for model in models:
        key = (model['provider'], model['model_name'])

        if key not in unique_models:
            unique_models[key] = model
        else:
            # Duplicate found - check source priority
            existing_source = unique_models[key].get('provider_metadata', {}).get('source', '')
            new_source = model.get('provider_metadata', {}).get('source', '')

            if new_source == priority_source:
                unique_models[key] = model
                duplicate_count += 1
            elif existing_source != priority_source:
                # Keep existing, log the conflict
                duplicate_count += 1

    if duplicate_count > 0:
        logger.info(f"Merged {duplicate_count} duplicate models")

    return list(unique_models.values())
