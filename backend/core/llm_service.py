"""
LLM Service module.

Provides a unified interface for LLM interactions across the platform,
wrapping the advanced BYOKHandler infrastructure.
"""

import json
import logging
import os
import asyncio
from typing import Optional, Dict, Any, List, Union, Type, AsyncGenerator
from enum import Enum

from pydantic import BaseModel
from core.llm.byok_handler import BYOKHandler, QueryComplexity
from core.llm.cognitive_tier_system import CognitiveTier, CognitiveClassifier
from core.llm.context.token_counter import TokenCounter, ContextValidator
from core.llm_usage_tracker import llm_usage_tracker
from core.continuous_learning_service import ContinuousLearningService

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


class LLMSentiment(BaseModel):
    """Structured sentiment analysis output"""
    score: float  # -1.0 to 1.0
    label: str    # "positive", "neutral", "negative"
    confidence: float


class LLMTopics(BaseModel):
    """Structured topic extraction output"""
    topics: List[str]
    confidence: float


class LLMService:
    """
    LLM Service for managing LLM interactions across the platform.
    Provides unified interface for different LLM providers, wrapping BYOKHandler.
    
    Harmonized with SaaS version for feature parity.
    """

    def __init__(self, db=None, workspace_id: Optional[str] = None, tenant_id: Optional[str] = None):
        """
        Args:
            db: Optional SQLAlchemy session.
            workspace_id: Primary identifier for workspace-level grouping.
            tenant_id: Identifier for the tenant (SaaS convention).
        """
        self._db = db
        self._workspace_id = workspace_id or "default"
        self._tenant_id = tenant_id or "default"
        self._handler: Optional[BYOKHandler] = None
        
        # In single-tenant open source, we mostly care about workspace_id.
        # But we preserve tenant_id for compatibility.
        self._handler = BYOKHandler(workspace_id=self._workspace_id, tenant_id=self._tenant_id, db_session=db)
        self.continuous_learning = ContinuousLearningService(db) if db else None
        self._token_counter = TokenCounter()
        self._context_validator = ContextValidator()
        self._cognitive_classifier = CognitiveClassifier()

    @property
    def handler(self) -> BYOKHandler:
        """Alias for _handler (parity with some callers)."""
        return self._handler

    @property
    def workspace_id(self) -> str:
        """Return the workspace identifier."""
        return self._workspace_id

    @property
    def tenant_id(self) -> str:
        """Return the tenant identifier."""
        return self._tenant_id

    def _get_handler(self, workspace_id: Optional[str] = None, tenant_id: Optional[str] = None) -> BYOKHandler:
        """Helper to get or create a BYOKHandler for a specific workspace."""
        target_ws = workspace_id or tenant_id or self._workspace_id
        
        if self._handler and target_ws == self._workspace_id:
            return self._handler
            
        return BYOKHandler(workspace_id=target_ws, tenant_id=tenant_id or self._tenant_id, db_session=self._db)

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
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """Simple text generation interface."""
        # Personalization
        agent_id = kwargs.get("agent_id")
        user_id = kwargs.get("user_id")
        target_ws = workspace_id or tenant_id or self._workspace_id
        
        handler = self._get_handler(workspace_id=target_ws)
        
        if agent_id and self.continuous_learning:
            params = self.continuous_learning.get_personalized_parameters(
                tenant_id=target_ws,
                agent_id=agent_id,
                user_id=user_id
            )
            if "temperature" in params and "temperature" not in kwargs:
                temperature = params["temperature"]

        return await handler.generate_response(
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
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate completion with OpenAI-style messages.
        Maps messages to prompt/system for BYOKHandler.
        """
        handler = self._get_handler(workspace_id=workspace_id, tenant_id=tenant_id)
        
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
        response_text = await handler.generate_response(
            prompt=prompt,
            system_instruction=system_instruction,
            model_type=model,
            temperature=temperature,
            **kwargs
        )

        # Approximate token usage
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

    async def generate_structured_response(
        self,
        prompt: str,
        response_model: Any,
        system_instruction: str = "You are a helpful assistant.",
        model: str = "quality",
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Generate structured response using Pydantic model."""
        handler = self._get_handler(workspace_id=workspace_id, tenant_id=tenant_id)

        # Personalization
        agent_id = kwargs.get("agent_id")
        user_id = kwargs.get("user_id")
        if agent_id and self.continuous_learning:
            params = self.continuous_learning.get_personalized_parameters(
                tenant_id=workspace_id or tenant_id or self._workspace_id,
                agent_id=agent_id,
                user_id=user_id
            )
            if "temperature" in params and "temperature" not in kwargs:
                kwargs["temperature"] = params["temperature"]

        return await handler.generate_structured_response(
            prompt=prompt,
            system_instruction=system_instruction,
            response_model=response_model,
            task_type=model,
            **kwargs
        )

    async def stream_completion(
        self,
        messages: List[Dict],
        model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream LLM responses token-by-token."""
        handler = self._get_handler(workspace_id=workspace_id, tenant_id=tenant_id)
        
        # Resolve model if needed
        if model in ["auto", "fast", "quality", "balanced"]:
            last_user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            complexity = handler.analyze_query_complexity(last_user_msg)
            provider_id, resolved_model = handler.get_optimal_provider(complexity)
        else:
            resolved_model = model
            # In OS, we might need to infer provider_id or pass auto
            provider_id = "auto" 
            # Check if there's a better way to infer provider_id in OS BYOKHandler
            # OS BYOKHandler.stream_completion requires provider_id

        async for token in handler.stream_completion(
            messages=messages,
            model=resolved_model,
            provider_id=provider_id if provider_id != "auto" else "deepseek", # Default to deepseek if auto
            temperature=temperature,
            agent_id=agent_id,
            db=self._db,
            **kwargs
        ):
            yield token

    async def generate_embedding(
        self,
        text: str,
        model: str = "text-embedding-3-small",
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> List[float]:
        """Generate a single embedding via BYOKHandler."""
        handler = self._get_handler(workspace_id=workspace_id, tenant_id=tenant_id)
        
        # Use underlying handler's client
        provider_id = self.get_provider(model).value
        client = handler.async_clients.get(provider_id) or handler.clients.get(provider_id)
        
        if not client:
            raise ValueError(f"No client found for provider {provider_id}")

        # Note: In OS, BYOKHandler doesn't have a direct embed_text yet, 
        # so we use the client directly but through the handler's managed session.
        response = await client.embeddings.create(
            input=text,
            model=model,
            **kwargs
        )
        return response.data[0].embedding

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        model: str = "text-embedding-3-small",
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> List[List[float]]:
        """Generate batch embeddings via BYOKHandler."""
        handler = self._get_handler(workspace_id=workspace_id, tenant_id=tenant_id)
        provider_id = self.get_provider(model).value
        client = handler.async_clients.get(provider_id) or handler.clients.get(provider_id)

        if not client:
            raise ValueError(f"No client found for provider {provider_id}")

        response = await client.embeddings.create(
            input=texts,
            model=model,
            **kwargs
        )
        return [item.embedding for item in response.data]

    async def generate_speech(
        self,
        text: str,
        voice: str = "alloy",
        model: str = "tts-1",
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """Generate speech via BYOKHandler (OpenAI TTS)."""
        handler = self._get_handler(workspace_id=workspace_id, tenant_id=tenant_id)
        provider_id = self.get_provider(model).value
        client = handler.async_clients.get(provider_id) or handler.clients.get(provider_id)

        if not client:
            raise ValueError(f"No client found for provider {provider_id}")

        response = await client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            **kwargs
        )
        return response.read()

    async def transcribe_audio(
        self,
        file: Any,
        model: str = "whisper-1",
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Transcribe audio via BYOKHandler (OpenAI Whisper)."""
        handler = self._get_handler(workspace_id=workspace_id, tenant_id=tenant_id)
        provider_id = self.get_provider(model).value
        client = handler.async_clients.get(provider_id) or handler.clients.get(provider_id)

        if not client:
            raise ValueError(f"No client found for provider {provider_id}")

        response = await client.audio.transcriptions.create(
            model=model,
            file=file,
            **kwargs
        )
        return {"text": response.text}

    def estimate_tokens(self, text: Union[str, List[Dict[str, str]]], model: str = "gpt-4o-mini") -> int:
        """Estimate tokens for text or a list of chat messages."""
        if isinstance(text, str):
            return self._token_counter.count_tokens(text, model)
        elif isinstance(text, list):
            return self._context_validator.estimate_request_tokens(text, model)
        return 0

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Estimate cost in USD."""
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
        """Governance helper: Analyze an agent proposal for safety and alignment."""
        prompt = f"Analyze the following agent proposal for safety, alignment, and efficiency:\n\nPROPOSAL:\n{proposal}"
        if context:
            prompt += f"\n\nCONTEXT:\n{context}"

        system = "You are an Agent Governance Auditor. Evaluate the proposal and return a JSON-formatted analysis with 'safe' (bool), 'risk_level' (str), and 'recommendation' (str)."

        response = await self.generate(prompt, system_instruction=system, model="quality")

        try:
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
        """Check if LLM service is available."""
        return len(self.handler.clients) > 0 if hasattr(self, 'handler') and self.handler else False

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

    def get_available_providers(self) -> List[str]:
        """
        Get list of providers with valid API keys.

        Returns:
            List of provider IDs (e.g., ["openai", "anthropic", "deepseek"])

        Example:
            >>> service = LLMService()
            >>> providers = service.get_available_providers()
            >>> print(providers)  # ['openai', 'deepseek', ...]
        """
        return self.handler.get_available_providers()

    def get_context_window(self, model_name: str) -> int:
        """
        Get the context window size for a model from dynamic pricing data.
        Returns a safe default if not found.

        Args:
            model_name: Model identifier (e.g., "gpt-4o", "claude-3-5-sonnet")

        Returns:
            Context window size in tokens (e.g., 128000, 200000)

        Example:
            >>> service = LLMService()
            >>> context = service.get_context_window("gpt-4o")
            >>> print(context)  # 128000
        """
        return self.handler.get_context_window(model_name)

    def truncate_to_context(self, text: str, model_name: str, reserve_tokens: int = 1000) -> str:
        """
        Truncate text to fit within the model's context window.
        Reserves tokens for the response.

        Args:
            text: Input text to truncate
            model_name: Model identifier for context window lookup
            reserve_tokens: Tokens to reserve for response (default 1000)

        Returns:
            Truncated text that fits in context window, with truncation indicator

        Example:
            >>> service = LLMService()
            >>> short = service.truncate_to_context(long_text, "gpt-4o", reserve_tokens=2000)
        """
        return self.handler.truncate_to_context(text, model_name, reserve_tokens)

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
        model: str = "text-embedding-3-small",
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> List[float]:
        """
        Generate embedding vector for a single text string using unified BYOK resolution.
        Supports OpenAI and Cohere via BYOKHandler.
        """
        handler = self._get_handler(workspace_id=workspace_id, tenant_id=tenant_id)
        
        # Identify provider from model name
        provider = "openai"
        if "embed-english" in model.lower() or "embed-multilingual" in model.lower():
            provider = "cohere"

        try:
            embedding = await handler.generate_embedding(
                text=text,
                model=model,
                provider=provider
            )
            
            # Metadata for tracking
            token_count = len(text) // 4 # Basic estimate
            if provider == "openai":
                cost_per_1k = 0.00002 if model == "text-embedding-3-small" else 0.00013
                estimated_cost = (token_count / 1000) * cost_per_1k
            else:
                estimated_cost = (token_count / 1000) * 0.0001
            
            # Track usage
            try:
                llm_usage_tracker.track_usage(
                    provider=provider,
                    model=model,
                    input_tokens=token_count,
                    output_tokens=0,
                    estimated_cost=estimated_cost
                )
            except Exception as tracking_error:
                logger.debug(f"Usage tracking failed: {tracking_error}")

            return embedding

        except Exception as e:
            logger.error(f"Embedding generation failed for provider {provider}: {e}")
            raise

    async def transcribe_audio(
        self,
        file: Any,
        model: str = "whisper-1",
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        response_format: str = "json",
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio to text.
        
        Args:
            file: Audio file object (as required by OpenAI API)
            model: Transcription model (default: "whisper-1")
            language: Optional language of the audio
            prompt: Optional guiding prompt for transcription
            response_format: "json", "text", "srt", "verbose_json", "vtt"
            tenant_id: Optional tenant override
            
        Returns:
            Dict containing 'text' and metadata.
        """
        handler = self._get_handler(workspace_id=workspace_id, tenant_id=tenant_id)
        return await handler.generate_transcription(
            file=file,
            model=model,
            language=language,
            prompt=prompt,
            response_format=response_format
        )

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        model: str = "text-embedding-3-small",
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> List[List[float]]:
        """
        Generate embedding vectors for multiple texts in a single batch operation using unified BYOK.
        """
        handler = self._get_handler(workspace_id=workspace_id, tenant_id=tenant_id)
        
        provider = "openai"
        if "embed-english" in model.lower() or "embed-multilingual" in model.lower():
            provider = "cohere"

        try:
            all_embeddings = await handler.generate_embeddings_batch(
                texts=texts,
                model=model,
                provider=provider
            )
            
            # Metadata for tracking
            total_tokens = sum(len(t) // 4 for t in texts)
            if provider == "openai":
                cost_per_1k = 0.00002 if model == "text-embedding-3-small" else 0.00013
                estimated_cost = (total_tokens / 1000) * cost_per_1k
            else:
                estimated_cost = (total_tokens / 1000) * 0.0001

            # Track usage
            try:
                llm_usage_tracker.track_usage(
                    provider=provider,
                    model=model,
                    input_tokens=total_tokens,
                    output_tokens=0,
                    estimated_cost=estimated_cost
                )
            except Exception as tracking_error:
                logger.debug(f"Usage tracking failed: {tracking_error}")

            return all_embeddings

        except Exception as e:
            logger.error(f"Batch embedding generation failed for provider {provider}: {e}")
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


def get_llm_service(workspace_id: Optional[str] = None, db=None, tenant_id: Optional[str] = None) -> LLMService:
    """Factory function to get an LLMService instance."""
    return LLMService(workspace_id=workspace_id, tenant_id=tenant_id, db=db)
