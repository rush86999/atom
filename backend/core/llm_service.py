"""
LLM Service module.

Provides a unified interface for LLM interactions across the platform,
wrapping the advanced BYOKHandler infrastructure.
"""

import json
import logging
import os
import asyncio
from typing import Optional, Dict, Any, List, Union, Type
from enum import Enum

from pydantic import BaseModel
from core.llm.byok_handler import BYOKHandler, QueryComplexity
from core.llm.cognitive_tier_system import CognitiveTier
from core.llm_usage_tracker import llm_usage_tracker

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    GROQ = "groq"
    MINIMAX = "minimax"
    MISTRAL = "mistral"
    QWEN = "qwen"
    COHERE = "cohere"


class LLMModel(str, Enum):
    """Common LLM models"""
    # OpenAI
    GPT4 = "gpt-4"
    GPT4_TURBO = "gpt-4-turbo"
    GPT35_TURBO = "gpt-3.5-turbo"
    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    GPT_5_3 = "gpt-5.3"

    # Anthropic
    CLAUDE_3_OPUS = "claude-3-opus-20240229"
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    CLAUDE_3_HAIKU = "claude-3-haiku-20240307"
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet"

    # DeepSeek
    DEEPSEEK_V3 = "deepseek-chat"
    DEEPSEEK_REASONER = "deepseek-reasoner"

    # Gemini
    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"

    # MiniMax
    MINIMAX_2_5 = "minimax-m2.5"


class LLMService:
    """
    LLM Service for managing LLM interactions across the platform.
    Provides unified interface for different LLM providers, wrapping BYOKHandler.
    """

    def __init__(self, workspace_id: str = "default", db=None):
        """
        Args:
            workspace_id: Workspace ID for BYOK resolution.
            db: Optional database session for BYOK/Usage tracking.
        """
        self.workspace_id = workspace_id
        self.handler = BYOKHandler(workspace_id=workspace_id, db_session=db)

    def get_provider(self, model: str) -> LLMProvider:
        """Get the provider for a given model."""
        model_l = model.lower()
        if "gpt" in model_l:
            return LLMProvider.OPENAI
        elif "claude" in model_l:
            return LLMProvider.ANTHROPIC
        elif "deepseek" in model_l:
            return LLMProvider.DEEPSEEK
        elif "gemini" in model_l:
            return LLMProvider.GEMINI
        elif "minimax" in model_l:
            return LLMProvider.MINIMAX
        elif "mistral" in model_l:
            return LLMProvider.MISTRAL
        elif "qwen" in model_l:
            return LLMProvider.QWEN
        elif "command" in model_l:
            return LLMProvider.COHERE
        else:
            return LLMProvider.OPENAI  # Default

    async def generate(
        self,
        prompt: str,
        system_instruction: str = "You are a helpful assistant.",
        model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """Simple text generation interface."""
        return await self.handler.generate_response(
            prompt=prompt,
            system_instruction=system_instruction,
            model_type=model,
            temperature=temperature,
            **kwargs
        )

    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate completion with OpenAI-style messages.
        Maps messages to prompt/system for BYOKHandler.
        """
        # Extract prompt and system from messages
        prompt = ""
        system_instruction = "You are a helpful assistant."
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            elif role == "user":
                prompt = content  # Use the last user message as prompt for now

        # Call underlying handler
        response_text = await self.handler.generate_response(
            prompt=prompt,
            system_instruction=system_instruction,
            model_type=model,
            temperature=temperature,
            **kwargs
        )

        # Approximate token usage (BYOKHandler tracks this internally in DB, 
        # but we return an estimation for immediate API consumers)
        input_tokens = self.estimate_tokens(prompt + system_instruction, model)
        output_tokens = self.estimate_tokens(response_text, model)

        return {
            "success": True,
            "content": response_text,
            "text": response_text, # Parity with some saas callers
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens
            },
            "model": model,
            "provider": self.get_provider(model).value
        }

    def estimate_tokens(self, text: str, model: str = "gpt-4o-mini") -> int:
        """Estimate token count for text."""
        try:
            import tiktoken
            try:
                # Try to get specific encoding or model match
                if "gpt-4" in model or "gpt-3.5" in model or "o1" in model or "o3" in model:
                    encoding = tiktoken.encoding_for_model("gpt-4o")
                else:
                    encoding = tiktoken.get_encoding("cl100k_base")
            except Exception:
                encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            # Fallback: ~4 chars per token
            return max(1, len(text) // 4)

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Estimate cost in USD."""
        # Use existing cost utilities if available
        try:
            from core.cost_config import get_llm_cost
            return get_llm_cost(model, input_tokens, output_tokens)
        except ImportError:
            # Fallback hardcoded pricing (approximate)
            if "gpt-4o-mini" in model: return (input_tokens * 0.15 + output_tokens * 0.6) / 1e6
            if "gpt-4o" in model: return (input_tokens * 5.0 + output_tokens * 15.0) / 1e6
            if "deepseek" in model: return (input_tokens * 0.14 + output_tokens * 0.28) / 1e6
            return (input_tokens * 1.0 + output_tokens * 2.0) / 1e6

    async def generate_with_tier(
        self,
        prompt: str,
        system_instruction: str = "You are a helpful assistant.",
        task_type: Optional[str] = None,
        user_tier_override: Optional[str] = None,
        agent_id: Optional[str] = None,
        image_payload: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate response using cognitive tier routing with intelligent 5-tier system.

        Phase 222-03: Exposes BYOKHandler's generate_with_cognitive_tier method for
        cost-optimized, quality-aware LLM routing with automatic escalation.

        Five Cognitive Tiers:
        - MICRO: Ultra-low cost (<$0.01/M tokens), simple tasks (greetings, basic QA)
        - STANDARD: Balanced cost/quality (~$0.50/M tokens), general tasks (chat, summarization)
        - VERSATILE: Advanced capabilities (~$2-5/M tokens), complex tasks (reasoning, analysis)
        - HEAVY: High-performance (~$10-20/M tokens), demanding tasks (code gen, research)
        - COMPLEX: Maximum quality (~$30+/M tokens), critical tasks (architecture, security)

        Pipeline:
        1. Classify prompt complexity (token count + semantic analysis + task type)
        2. Check budget constraints (monthly + per-request limits)
        3. Select optimal model (cache-aware cost scoring)
        4. Generate with automatic escalation on quality issues

        Args:
            prompt: The user query
            system_instruction: System prompt for the LLM
            task_type: Optional task type hint (code, chat, analysis, etc.)
            user_tier_override: Optional user-specified tier (bypasses classification)
                Valid values: "micro", "standard", "versatile", "heavy", "complex"
            agent_id: Optional agent ID for cost tracking and escalation history
            image_payload: Optional base64/URL image for multimodal input

        Returns:
            Dictionary with keys:
            - response: str - Generated text response
            - tier: str - Cognitive tier used (e.g., "standard", "versatile")
            - provider: str - Provider ID used (e.g., "openai", "anthropic")
            - model: str - Model name used (e.g., "gpt-4o-mini", "claude-3-5-sonnet")
            - cost_cents: float - Estimated cost in cents
            - escalated: bool - Whether escalation occurred (True if tier was upgraded)
            - request_id: str - Unique request ID for tracking
            - error: str - Error message if generation failed

        Example:
            >>> service = LLMService()
            >>> result = await service.generate_with_tier(
            ...     "Explain quantum computing in simple terms",
            ...     task_type="analysis"
            ... )
            >>> print(result["response"])
            >>> print(f"Tier: {result['tier']}, Model: {result['model']}, Cost: ${result['cost_cents']/100:.4f}")

            >>> # Force specific tier (bypass classification)
            >>> result = await service.generate_with_tier(
            ...     "Write a Python function",
            ...     user_tier_override="versatile"
            ... )
        """
        return await self.handler.generate_with_cognitive_tier(
            prompt=prompt,
            system_instruction=system_instruction,
            task_type=task_type,
            user_tier_override=user_tier_override,
            agent_id=agent_id,
            image_payload=image_payload
        )

    async def analyze_proposal(self, proposal: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Governance helper: Analyze an agent proposal for safety and alignment.
        """
        prompt = f"Analyze the following agent proposal for safety, alignment, and efficiency:\n\nPROPOSAL:\n{proposal}"
        if context:
            prompt += f"\n\nCONTEXT:\n{context}"

        system = "You are an Agent Governance Auditor. Evaluate the proposal and return a JSON-formatted analysis with 'safe' (bool), 'risk_level' (str), and 'recommendation' (str)."

        response = await self.generate(prompt, system_instruction=system, model="quality")

        try:
            # Try to extract JSON if the model wrapped it in markdown
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            else:
                json_str = response.strip()
            return json.loads(json_str)
        except Exception:
            return {
                "safe": "Unknown" in response or "safe" in response.lower(),
                "raw_response": response,
                "error": "Failed to parse structured audit"
            }

    def is_available(self) -> bool:
        """Check if LLM service is available by checking for any initialized clients."""
        return len(self.handler.clients) > 0

    def get_optimal_provider(
        self,
        complexity: str = "moderate",
        task_type: Optional[str] = None,
        prefer_cost: bool = True,
        tenant_plan: str = "free",
        is_managed_service: bool = True,
        requires_tools: bool = False,
        requires_structured: bool = False
    ) -> tuple[str, str]:
        """
        Get the optimal provider and model for a given complexity level.

        Uses the BPC (Benchmark-Price-Capability) algorithm to rank models
        based on quality benchmarks, pricing, and capabilities.

        Args:
            complexity: Query complexity level ("simple", "moderate", "complex", "advanced")
            task_type: Optional task type hint (e.g., "summarization", "code_generation")
            prefer_cost: Whether to prefer cost over quality
            tenant_plan: Tenant plan for model restrictions
            is_managed_service: Whether this is managed service or BYOK
            requires_tools: Whether model must support tool calling
            requires_structured: Whether model must support structured output

        Returns:
            Tuple of (provider_id, model_name)

        Example:
            >>> service = LLMService()
            >>> provider, model = service.get_optimal_provider(complexity="moderate")
            >>> print(f"Using {provider} with {model}")
        """
        # Map complexity string to QueryComplexity enum
        complexity_map = {
            "simple": QueryComplexity.SIMPLE,
            "moderate": QueryComplexity.MODERATE,
            "complex": QueryComplexity.COMPLEX,
            "advanced": QueryComplexity.ADVANCED
        }
        complexity_enum = complexity_map.get(complexity.lower(), QueryComplexity.MODERATE)

        return self.handler.get_optimal_provider(
            complexity=complexity_enum,
            task_type=task_type,
            prefer_cost=prefer_cost,
            tenant_plan=tenant_plan,
            is_managed_service=is_managed_service,
            requires_tools=requires_tools,
            requires_structured=requires_structured
        )

    def get_ranked_providers(
        self,
        complexity: str = "moderate",
        task_type: Optional[str] = None,
        prefer_cost: bool = True,
        tenant_plan: str = "free",
        is_managed_service: bool = True,
        requires_tools: bool = False,
        requires_structured: bool = False,
        estimated_tokens: int = 1000,
        cognitive_tier: Optional[str] = None
    ) -> List[tuple[str, str]]:
        """
        Get a ranked list of providers and models using the BPC algorithm.

        Cache-Aware Cost Optimization:
        When estimated_tokens is provided, uses cache-aware effective cost calculation
        to prioritize models with good prompt caching support (e.g., Anthropic).

        Cognitive Tier Filtering:
        When cognitive_tier is provided, uses 5-tier quality filtering instead of
        QueryComplexity for more granular control.

        Args:
            complexity: Query complexity level ("simple", "moderate", "complex", "advanced")
            task_type: Optional task type hint
            prefer_cost: Whether to prefer cost over quality
            tenant_plan: Tenant plan for model restrictions
            is_managed_service: Whether this is managed service or BYOK
            requires_tools: Whether model must support tool calling
            requires_structured: Whether model must support structured output
            estimated_tokens: Estimated input token count (for cache hit prediction)
            cognitive_tier: Optional cognitive tier ("micro", "standard", "versatile", "heavy", "complex")

        Returns:
            List of (provider_id, model_name) tuples ranked by value score

        Example:
            >>> service = LLMService()
            >>> providers = service.get_ranked_providers(
            ...     complexity="complex",
            ...     estimated_tokens=5000,
            ...     cognitive_tier="versatile"
            ... )
            >>> for provider, model in providers[:3]:
            ...     print(f"{provider}: {model}")
        """
        # Map complexity string to QueryComplexity enum
        complexity_map = {
            "simple": QueryComplexity.SIMPLE,
            "moderate": QueryComplexity.MODERATE,
            "complex": QueryComplexity.COMPLEX,
            "advanced": QueryComplexity.ADVANCED
        }
        complexity_enum = complexity_map.get(complexity.lower(), QueryComplexity.MODERATE)

        # Map cognitive_tier string to CognitiveTier enum if provided
        cognitive_tier_enum = None
        if cognitive_tier:
            tier_map = {
                "micro": CognitiveTier.MICRO,
                "standard": CognitiveTier.STANDARD,
                "versatile": CognitiveTier.VERSATILE,
                "heavy": CognitiveTier.HEAVY,
                "complex": CognitiveTier.COMPLEX
            }
            cognitive_tier_enum = tier_map.get(cognitive_tier.lower())

        return self.handler.get_ranked_providers(
            complexity=complexity_enum,
            task_type=task_type,
            prefer_cost=prefer_cost,
            tenant_plan=tenant_plan,
            is_managed_service=is_managed_service,
            requires_tools=requires_tools,
            requires_structured=requires_structured,
            estimated_tokens=estimated_tokens,
            workspace_id=self.workspace_id,
            cognitive_tier=cognitive_tier_enum
        )

    def get_routing_info(self, prompt: str, task_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get routing decision info without making an API call.

        Useful for UI preview features - shows users which model will be used
        and estimated cost before generation.

        Args:
            prompt: The user prompt to analyze
            task_type: Optional task type hint

        Returns:
            Dict with keys:
                - complexity: str (complexity level)
                - selected_provider: str (provider ID)
                - selected_model: str (model name)
                - available_providers: List[str] (list of providers)
                - cost_tier: str (budget/mid/premium)
                - estimated_cost_usd: Optional[float] (estimated cost)
                - error: Optional[str] (error message if no providers available)

        Example:
            >>> service = LLMService()
            >>> info = service.get_routing_info("Explain quantum computing")
            >>> print(f"Using {info['selected_model']} at {info['estimated_cost_usd']}")
        """
        return self.handler.get_routing_info(prompt=prompt, task_type=task_type)

    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "auto",
        provider_id: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        agent_id: Optional[str] = None,
        db = None
    ):
        """
        Stream LLM responses token-by-token with automatic provider fallback.

        Provides real-time streaming of LLM responses with governance tracking and
        automatic provider fallback on failure. This is the unified streaming interface
        for all LLM interactions in the platform.

        Args:
            messages: Chat messages in OpenAI format (role + content)
            model: Model name (default: "auto" for optimal model selection)
            provider_id: Provider identifier (default: "auto" for optimal provider)
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            agent_id: Optional agent ID for governance tracking
            db: Optional database session for governance tracking

        Yields:
            Individual tokens as they arrive from the LLM

        Example:
            ```python
            llm_service = LLMService()
            messages = [{"role": "user", "content": "Hello!"}]
            async for token in llm_service.stream_completion(messages):
                print(token, end="", flush=True)
            ```

        Note:
            - When provider_id="auto", analyzes query complexity to select optimal provider
            - Includes automatic provider fallback on failure
            - Integrates with governance tracking when agent_id and db are provided
        """
        # Analyze complexity for auto provider selection
        if provider_id == "auto":
            # Extract prompt from messages for complexity analysis
            prompt = ""
            for msg in messages:
                if msg.get("role") == "user":
                    prompt += msg.get("content", "") + "\n"

            # Get optimal provider based on complexity
            complexity = self.handler.analyze_query_complexity(prompt)
            optimal_provider, optimal_model = self.handler.get_optimal_provider(complexity)
            provider_id = optimal_provider  # Already a string, not an enum

            # Map model from "auto" to optimal model for complexity
            if model == "auto":
                model = optimal_model

        # Delegate to BYOKHandler's stream_completion
        async for token in self.handler.stream_completion(
            messages=messages,
            model=model,
            provider_id=provider_id,
            temperature=temperature,
            max_tokens=max_tokens,
            agent_id=agent_id,
            db=db
        ):
            yield token

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
    ) -> Optional[BaseModel]:
        """
        Generate structured output using Pydantic model validation.

        Provides tenant-aware routing between BYOK and Managed AI based on subscription,
        with support for vision inputs via image_payload.

        Args:
            prompt: The user prompt
            response_model: Pydantic model class for structured output validation
            system_instruction: System instruction for the LLM
            temperature: Sampling temperature (0.0-1.0)
            model: Model name (default: "auto" for optimal model selection)
            task_type: Optional task type hint (e.g., "summarization", "code_generation")
            agent_id: Optional agent ID for cost tracking
            image_payload: Optional Base64 image string or URL for vision support

        Returns:
            Instance of response_model with validated data, or None if generation fails

        Example:
            ```python
            from pydantic import BaseModel

            class SentimentAnalysis(BaseModel):
                sentiment: str  # "positive", "negative", "neutral"
                confidence: float
                key_points: List[str]

            llm_service = LLMService()
            result = await llm_service.generate_structured(
                prompt="Analyze the sentiment of this review...",
                response_model=SentimentAnalysis
            )
            if result:
                print(f"Sentiment: {result.sentiment}")
                print(f"Confidence: {result.confidence}")
            ```

        Note:
            - Tenant-aware routing: BYOK keys used if available, otherwise Managed AI
            - Vision support: Pass image_payload (Base64 or URL) for multimodal inputs
            - Graceful fallback: Returns None if instructor unavailable or generation fails
            - Auto model selection: When model="auto", selects optimal model for structured output
        """
        # Check if handler has clients available
        if not self.is_available():
            logger.warning("No LLM clients available for structured generation")
            return None

        # Delegate to BYOKHandler's generate_structured_response
        try:
            result = await self.handler.generate_structured_response(
                prompt=prompt,
                system_instruction=system_instruction,
                response_model=response_model,
                temperature=temperature,
                task_type=task_type,
                agent_id=agent_id,
                image_payload=image_payload
            )
            return result
        except Exception as e:
            logger.error(f"Structured generation failed: {e}")
            return None

    async def generate_embedding(
        self,
        text: str,
        model: str = "text-embedding-3-small"
    ) -> List[float]:
        """
        Generate embedding vector for a single text string.

        Phase 223-01: Embedding generation support for migration consistency.
        Provides unified interface for embedding generation using OpenAI's API.

        Args:
            text: The text string to generate embedding for
            model: Embedding model name (default: "text-embedding-3-small")
                - "text-embedding-3-small": 1536 dimensions, ~$0.00002/1K tokens
                - "text-embedding-3-large": 3072 dimensions, ~$0.00013/1K tokens

        Returns:
            List[float]: Embedding vector (1536 or 3072 dimensions depending on model)

        Raises:
            Exception: If OpenAI package not installed or API call fails

        Example:
            >>> service = LLMService()
            >>> embedding = await service.generate_embedding("Hello, world!")
            >>> print(len(embedding))  # 1536 for text-embedding-3-small
            >>> print(embedding[:3])   # First 3 dimensions

        Note:
            - Uses BYOKHandler for API key resolution (OpenAI BYOK key preferred)
            - Logs cost telemetry (model used, token count, estimated cost)
            - Lazy imports AsyncOpenAI to avoid import errors if openai not installed
        """
        try:
            # Lazy import to avoid errors if openai not installed
            from openai import AsyncOpenAI

            # Get API key from BYOKHandler or environment
            api_key = None
            if hasattr(self.handler, 'clients') and 'openai' in self.handler.clients:
                # Try to get API key from BYOK configuration
                openai_client = self.handler.clients.get('openai')
                if hasattr(openai_client, 'api_key'):
                    api_key = openai_client.api_key

            if not api_key:
                # Fallback to environment variable
                api_key = os.getenv("OPENAI_API_KEY")

            if not api_key:
                raise ValueError("OpenAI API key not found in BYOK configuration or OPENAI_API_KEY environment variable")

            # Create AsyncOpenAI client
            client = AsyncOpenAI(api_key=api_key)

            # Call embeddings API
            response = await client.embeddings.create(
                model=model,
                input=text
            )

            # Extract embedding vector
            embedding = response.data[0].embedding

            # Cost tracking telemetry
            token_count = response.usage.total_tokens if hasattr(response, 'usage') else len(text) // 4
            if model == "text-embedding-3-small":
                cost_per_1k = 0.00002
            elif model == "text-embedding-3-large":
                cost_per_1k = 0.00013
            else:
                cost_per_1k = 0.0001  # Fallback estimate

            estimated_cost = (token_count / 1000) * cost_per_1k

            logger.info(
                f"Embedding generated: model={model}, tokens={token_count}, "
                f"estimated_cost=${estimated_cost:.6f}"
            )

            # Track usage if llm_usage_tracker is available
            try:
                llm_usage_tracker.track_usage(
                    provider="openai",
                    model=model,
                    input_tokens=token_count,
                    output_tokens=0,
                    estimated_cost=estimated_cost
                )
            except Exception as tracking_error:
                logger.debug(f"Usage tracking failed (non-critical): {tracking_error}")

            return embedding

        except ImportError:
            raise Exception(
                "OpenAI package not installed. Run: pip install openai"
            )
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        model: str = "text-embedding-3-small"
    ) -> List[List[float]]:
        """
        Generate embedding vectors for multiple texts in a single batch operation.

        Phase 223-01: Batch embedding generation for efficiency and cost optimization.
        Processes multiple texts in batches of 2048 (OpenAI's limit) to minimize API calls.

        Args:
            texts: List of text strings to generate embeddings for
            model: Embedding model name (default: "text-embedding-3-small")
                - "text-embedding-3-small": 1536 dimensions, ~$0.00002/1K tokens
                - "text-embedding-3-large": 3072 dimensions, ~$0.00013/1K tokens

        Returns:
            List[List[float]]: List of embedding vectors (one per input text)
                - Each vector has 1536 or 3072 dimensions depending on model
                - Order matches input texts order

        Raises:
            Exception: If OpenAI package not installed or API call fails

        Example:
            >>> service = LLMService()
            >>> texts = ["Hello", "world", "batch"]
            >>> embeddings = await service.generate_embeddings_batch(texts)
            >>> print(len(embeddings))  # 3
            >>> print(len(embeddings[0]))  # 1536 for text-embedding-3-small

        Note:
            - Processes in batches of 2048 texts per API call (OpenAI limit)
            - Cost-effective: Single API call per batch instead of per text
            - Aggregates token counts across all batches for cost tracking
            - Logs batch size, total tokens, and estimated cost
        """
        try:
            # Lazy import to avoid errors if openai not installed
            from openai import AsyncOpenAI

            # Get API key from BYOKHandler or environment
            api_key = None
            if hasattr(self.handler, 'clients') and 'openai' in self.handler.clients:
                # Try to get API key from BYOK configuration
                openai_client = self.handler.clients.get('openai')
                if hasattr(openai_client, 'api_key'):
                    api_key = openai_client.api_key

            if not api_key:
                # Fallback to environment variable
                api_key = os.getenv("OPENAI_API_KEY")

            if not api_key:
                raise ValueError("OpenAI API key not found in BYOK configuration or OPENAI_API_KEY environment variable")

            # Create AsyncOpenAI client
            client = AsyncOpenAI(api_key=api_key)

            # Process in batches of 2048 (OpenAI limit)
            batch_size = 2048
            all_embeddings = []
            total_tokens = 0

            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_number = i // batch_size + 1
                total_batches = (len(texts) + batch_size - 1) // batch_size

                logger.debug(
                    f"Processing embedding batch {batch_number}/{total_batches} "
                    f"({len(batch)} texts)"
                )

                try:
                    # Call embeddings API for this batch
                    response = await client.embeddings.create(
                        model=model,
                        input=batch
                    )

                    # Extract embeddings from response
                    batch_embeddings = [item.embedding for item in response.data]
                    all_embeddings.extend(batch_embeddings)

                    # Track token count
                    if hasattr(response, 'usage'):
                        total_tokens += response.usage.total_tokens

                except Exception as batch_error:
                    logger.error(
                        f"Batch {batch_number} failed (texts {i}-{i+len(batch)}): {batch_error}"
                    )
                    raise Exception(
                        f"Embedding batch {batch_number} failed: {batch_error}. "
                        f"Batch index: {i}, Batch size: {len(batch)}"
                    ) from batch_error

            # Cost calculation
            if model == "text-embedding-3-small":
                cost_per_1k = 0.00002
            elif model == "text-embedding-3-large":
                cost_per_1k = 0.00013
            else:
                cost_per_1k = 0.0001  # Fallback estimate

            # Estimate tokens if not provided by API
            if total_tokens == 0:
                total_tokens = sum(len(text) // 4 for text in texts)

            estimated_cost = (total_tokens / 1000) * cost_per_1k

            logger.info(
                f"Batch embeddings generated: model={model}, texts={len(texts)}, "
                f"batches={total_batches}, total_tokens={total_tokens}, "
                f"estimated_cost=${estimated_cost:.6f}"
            )

            # Track usage if llm_usage_tracker is available
            try:
                llm_usage_tracker.track_usage(
                    provider="openai",
                    model=model,
                    input_tokens=total_tokens,
                    output_tokens=0,
                    estimated_cost=estimated_cost
                )
            except Exception as tracking_error:
                logger.debug(f"Usage tracking failed (non-critical): {tracking_error}")

            return all_embeddings

        except ImportError:
            raise Exception(
                "OpenAI package not installed. Run: pip install openai"
            )
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            raise

    def classify_tier(self, prompt: str, task_type: Optional[str] = None) -> CognitiveTier:
        """
        Classify a prompt into a cognitive tier.

        Phase 222-03: Helper method to understand tier decisions without making API calls.

        Uses the CognitiveClassifier to analyze prompt complexity based on:
        - Token count (shorter prompts -> lower tiers)
        - Semantic complexity (keywords, structure)
        - Task type hints (code, analysis, etc.)

        Args:
            prompt: The user prompt to classify
            task_type: Optional task type hint (code, chat, analysis, etc.)

        Returns:
            CognitiveTier enum value (MICRO, STANDARD, VERSATILE, HEAVY, or COMPLEX)

        Example:
            >>> service = LLMService()
            >>> tier = service.classify_tier("Hi there")
            >>> print(tier)  # CognitiveTier.MICRO

            >>> tier = service.classify_tier("Write a Python REST API with authentication", task_type="code")
            >>> print(tier)  # CognitiveTier.VERSATILE or HEAVY

        Note:
            This is a classification-only operation. It does not check budgets,
            select models, or make API calls. Use generate_with_tier() for full routing.
        """
        return self.handler.classify_cognitive_tier(prompt, task_type)

    def get_tier_description(self, tier: Union[str, CognitiveTier]) -> Dict[str, Any]:
        """
        Get human-readable description of a cognitive tier.

        Phase 222-03: Helper method to understand tier characteristics without making API calls.

        Provides detailed information about each cognitive tier including:
        - Cost range (per million tokens)
        - Quality level (benchmark scores)
        - Typical use cases
        - Example models

        Args:
            tier: Cognitive tier as string (e.g., "standard") or CognitiveTier enum

        Returns:
            Dictionary with keys:
                - name: str (tier name)
                - cost_range: str (cost per million tokens)
                - quality_level: str (quality description)
                - use_cases: List[str] (typical use cases)
                - example_models: List[str] (example models in this tier)

        Example:
            >>> service = LLMService()
            >>> desc = service.get_tier_description("versatile")
            >>> print(desc["cost_range"])  # "~$2-5/M tokens"
            >>> print(desc["use_cases"])   # ["Reasoning", "Analysis", "Code generation"]

            >>> # Can also use CognitiveTier enum
            >>> from core.llm.cognitive_tier_system import CognitiveTier
            >>> desc = service.get_tier_description(CognitiveTier.MICRO)
            >>> print(desc["cost_range"])  # "<$0.01/M tokens"

        Note:
            If tier string is invalid, returns description for STANDARD tier as fallback.
        """
        # Convert string to CognitiveTier enum if needed
        if isinstance(tier, str):
            tier_map = {
                "micro": CognitiveTier.MICRO,
                "standard": CognitiveTier.STANDARD,
                "versatile": CognitiveTier.VERSATILE,
                "heavy": CognitiveTier.HEAVY,
                "complex": CognitiveTier.COMPLEX
            }
            tier_enum = tier_map.get(tier.lower(), CognitiveTier.STANDARD)
        else:
            tier_enum = tier

        # Tier descriptions
        descriptions = {
            CognitiveTier.MICRO: {
                "name": "MICRO",
                "cost_range": "<$0.01/M tokens",
                "quality_level": "Basic quality for simple tasks",
                "use_cases": [
                    "Greetings and casual chat",
                    "Basic Q&A",
                    "Simple confirmations",
                    "Low-stakes recommendations"
                ],
                "example_models": [
                    "gpt-4o-mini",
                    "claude-3-haiku",
                    "gemini-1.5-flash"
                ]
            },
            CognitiveTier.STANDARD: {
                "name": "STANDARD",
                "cost_range": "~$0.50/M tokens",
                "quality_level": "Balanced cost/quality for general tasks",
                "use_cases": [
                    "General conversation",
                    "Text summarization",
                    "Basic explanations",
                    "Everyday tasks"
                ],
                "example_models": [
                    "gpt-4o-mini",
                    "claude-3-haiku",
                    "mini-m2.5"
                ]
            },
            CognitiveTier.VERSATILE: {
                "name": "VERSATILE",
                "cost_range": "~$2-5/M tokens",
                "quality_level": "Advanced capabilities for complex tasks",
                "use_cases": [
                    "Complex reasoning",
                    "Data analysis",
                    "Code generation",
                    "Multi-step problem solving"
                ],
                "example_models": [
                    "gpt-4o",
                    "claude-3-5-sonnet",
                    "gemini-1.5-pro"
                ]
            },
            CognitiveTier.HEAVY: {
                "name": "HEAVY",
                "cost_range": "~$10-20/M tokens",
                "quality_level": "High-performance for demanding tasks",
                "use_cases": [
                    "Advanced code generation",
                    "Research and analysis",
                    "Complex document processing",
                    "Architectural decisions"
                ],
                "example_models": [
                    "claude-3-opus",
                    "gpt-4-turbo",
                    "gemini-1.5-pro"
                ]
            },
            CognitiveTier.COMPLEX: {
                "name": "COMPLEX",
                "cost_range": "~$30+/M tokens",
                "quality_level": "Maximum quality for critical tasks",
                "use_cases": [
                    "Security analysis",
                    "System architecture",
                    "Critical business decisions",
                    "Complex multi-agent coordination"
                ],
                "example_models": [
                    "claude-3-opus",
                    "gpt-4",
                    "claude-3-5-sonnet"
                ]
            }
        }

        return descriptions.get(tier_enum, descriptions[CognitiveTier.STANDARD])

    def analyze_query_complexity(self, prompt: str, task_type: Optional[str] = None) -> QueryComplexity:
        """
        Analyze query complexity to determine optimal provider routing.

        Uses regex-based heuristic with expanded vocabulary for robust classification.

        Args:
            prompt: The user prompt to analyze
            task_type: Optional task type hint (code, chat, analysis, etc.)

        Returns:
            QueryComplexity enum value (SIMPLE, MODERATE, COMPLEX, or ADVANCED)

        Example:
            >>> service = LLMService()
            >>> complexity = service.analyze_query_complexity("Write a Python REST API")
            >>> print(complexity.value)  # 'complex' or 'advanced'
        """
        return self.handler.analyze_query_complexity(prompt, task_type)


def get_llm_service(workspace_id: str = "default", db=None) -> LLMService:
    """Factory function to get an LLMService instance."""
    return LLMService(workspace_id=workspace_id, db=db)
