import asyncio
from datetime import datetime
from enum import Enum
import hashlib
import json
import logging
import os
import re
import uuid
import threading
from typing import Any, AsyncGenerator, Dict, List, Optional

# Try imports for optional dependencies
try:
    from openai import AsyncOpenAI, OpenAI
except ImportError:
    OpenAI = None
    AsyncOpenAI = None

try:
    import instructor
    INSTRUCTOR_AVAILABLE = True
except ImportError:
    instructor = None
    INSTRUCTOR_AVAILABLE = False

# Core imports (moved from inline for better testability)
from core.benchmarks import get_quality_score, get_capability_score
from core.byok_endpoints import get_byok_manager
from core.cost_config import (
    BYOK_ENABLED_PLANS,
    MODEL_TIER_RESTRICTIONS,
    get_llm_cost)
from core.database import get_db_session
from core.dynamic_pricing_fetcher import (
    get_pricing_fetcher,
    get_pricing_fetcher_initialized,
    refresh_pricing_cache,
    DynamicPricingFetcher)
from core.llm.cache_aware_router import CacheAwareRouter
from core.llm.cognitive_tier_service import CognitiveTierService
from core.llm.cognitive_tier_system import CognitiveTier, CognitiveClassifier
from core.llm_usage_tracker import llm_usage_tracker
from core.lux_config import lux_config
from core.models import GovernanceDocument, AgentExecution, Tenant, Workspace, ModelCatalog
from core.llm_credential_service import LLMCredentialService

logger = logging.getLogger(__name__)


class QueryComplexity(Enum):
    """Query complexity levels for cost-based routing"""
    SIMPLE = "simple"       # Short, straightforward queries -> cheapest provider
    MODERATE = "moderate"   # Medium complexity -> balanced provider
    COMPLEX = "complex"     # Multi-step reasoning -> quality provider
    ADVANCED = "advanced"   # Code, math, analysis -> specialized provider


class NoProvidersConfiguredError(ValueError):
    """Raised when no LLM providers are configured.

    Subclasses ``ValueError`` so existing callers that catch ``ValueError``
    continue to work. Carries a recovery URL the UI can deep-link to so the
    new-user chat failure ("No LLM providers available") becomes an actionable
    "Configure now" CTA instead of an opaque 500.
    """

    def __init__(
        self,
        message: str = "No LLM providers configured.",
        recovery_url: str = "/settings/ai",
        error_code: str = "no_llm_provider",
    ):
        super().__init__(message)
        self.message = message
        self.recovery_url = recovery_url
        self.error_code = error_code

    def to_dict(self) -> Dict[str, str]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "recovery_url": self.recovery_url,
        }


# Provider tier mapping for cost optimization
PROVIDER_TIERS = {
    # Budget tier - cheapest, good for simple tasks
    "budget": ["deepseek", "moonshot", "glm", "ollama"],
    # Mid tier - balanced cost/quality
    "mid": ["anthropic", "gemini", "mistral"],
    # Premium tier - best quality, higher cost
    "premium": ["openai", "anthropic", "glm"],
    # Specialized - task-specific
    "code": ["deepseek", "openai"],
    "math": ["deepseek", "openai"],
    "creative": ["anthropic", "openai"],
}

# Model recommendations per provider (2026 Frontier Refresh)
COST_EFFICIENT_MODELS = {
    "openai": {
        QueryComplexity.SIMPLE: "o4-mini",
        QueryComplexity.MODERATE: "o4-mini",
        QueryComplexity.COMPLEX: "o3-mini",
        QueryComplexity.ADVANCED: "o3",
    },
    "anthropic": {
        QueryComplexity.SIMPLE: "claude-3-haiku-20240307",
        QueryComplexity.MODERATE: "claude-3-haiku-20240307",
        QueryComplexity.COMPLEX: "claude-3-5-sonnet",
        QueryComplexity.ADVANCED: "claude-4-opus",
    },
    "deepseek": {
        QueryComplexity.SIMPLE: "deepseek-chat",
        QueryComplexity.MODERATE: "deepseek-chat",
        QueryComplexity.COMPLEX: "deepseek-v3.2",
        QueryComplexity.ADVANCED: "deepseek-v3.2-speciale", # User Feedback: Lower cost, frontier reasoning
    },
    "gemini": {
        QueryComplexity.SIMPLE: "gemini-3.5-flash",
        QueryComplexity.MODERATE: "gemini-3.5-flash",
        QueryComplexity.COMPLEX: "gemini-3.5-flash",
        QueryComplexity.ADVANCED: "gemini-3-pro",
    },
    "moonshot": {
        QueryComplexity.SIMPLE: "qwen-3-7b",
        QueryComplexity.MODERATE: "qwen-3-7b",
        QueryComplexity.COMPLEX: "qwen-3-max",
        QueryComplexity.ADVANCED: "qwen-3-max",
    },
    "minimax": {
        QueryComplexity.SIMPLE: "MiniMax-M3-highspeed",
        QueryComplexity.MODERATE: "MiniMax-M3-highspeed",
        QueryComplexity.COMPLEX: "MiniMax-M3",
        QueryComplexity.ADVANCED: "MiniMax-M3",
    },
    "lux": {  # LUX Computer Use (Claude 3.5 Sonnet based)
        QueryComplexity.SIMPLE: "lux-1.0",
        QueryComplexity.MODERATE: "lux-1.0",
        QueryComplexity.COMPLEX: "lux-1.0",
        QueryComplexity.ADVANCED: "lux-1.0",
    },
    "qwen": {
        QueryComplexity.SIMPLE: "qwen-plus",
        QueryComplexity.MODERATE: "qwen-plus",
        QueryComplexity.COMPLEX: "qwen-plus",
        QueryComplexity.ADVANCED: "qwen-max",
    },
    "xiaomi": {
        QueryComplexity.SIMPLE: "xiaomi/mimo-v2.5-pro",
        QueryComplexity.MODERATE: "xiaomi/mimo-v2.5-pro",
        QueryComplexity.COMPLEX: "xiaomi/mimo-v2.5-pro",
        QueryComplexity.ADVANCED: "xiaomi/mimo-v2.5-pro",
    },
    "ollama": {
        QueryComplexity.SIMPLE: "llama3:8b",
        QueryComplexity.MODERATE: "llama3:8b",
        QueryComplexity.COMPLEX: "mistral:7b",
        QueryComplexity.ADVANCED: "mixtral:8x7b",
    },
    "glm": {  # Zhipu AI GLM family — OpenAI-compatible API
        QueryComplexity.SIMPLE: "glm-4.5",
        QueryComplexity.MODERATE: "glm-4.6",
        QueryComplexity.COMPLEX: "glm-5",
        QueryComplexity.ADVANCED: "glm-5.2",  # Latest flagship (June 2026) — 1M ctx, reasoning
    },
}


# Models that do not support tool calling or agentic runtimes (Phase 6.6)
# DEPRECATED: Use pricing_fetcher._model_supports_tools() instead
# This list is kept for reference/backwards compatibility only
# The pricing cache dynamically infers tool support from model metadata
MODELS_WITHOUT_TOOLS = {
    "deepseek-v3.2-speciale",
}

# Minimum quality scores by CognitiveTier for model filtering
MIN_QUALITY_BY_TIER = {
    CognitiveTier.MICRO: 0,
    CognitiveTier.STANDARD: 80,
    CognitiveTier.VERSATILE: 86,
    CognitiveTier.HEAVY: 90,
    CognitiveTier.COMPLEX: 94,
}

# Phase 14.5: Coordinated Multimodal Reasoning
# DEPRECATED: Use pricing_fetcher._model_supports_vision() instead
# This list is kept for reference/backwards compatibility only
# The pricing cache dynamically infers vision support from model metadata
REASONING_MODELS_WITHOUT_VISION = {
    "deepseek-v3.2",
    "deepseek-v3.2-speciale",
    "o3",
    "o3-mini",
    "deepseek-chat",
    "MiniMax-M3"
}

VISION_ONLY_MODELS = {
    "janus-pro-7b",
    "janus-pro-1.3b",
}


class BYOKHandler:
    """
    Handler for LLM interactions using BYOK system with intelligent cost optimization.
    Automatically routes queries to the most cost-effective provider based on complexity.

    Phase 68-04: MiniMax M3 Integration
    - Positioned in STANDARD tier with estimated $1/M pricing
    - API access may be closed - graceful fallback to next provider
    - Quality score 92 (latest flagship, 512K context, image input)
    - Native agent support, no prompt caching
    """
    def __init__(
        self,
        workspace_id: str = "default",
        tenant_id: str = "default",
        provider_id: str = "auto",
        cognitive_classifier: Optional[CognitiveClassifier] = None,
        cache_router: Optional[CacheAwareRouter] = None,
        db_session=None,
        tier_service: Optional[CognitiveTierService] = None,
        user_id: Optional[str] = None  # OAuth: User ID for credential resolution
    ):
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        self.user_id = user_id  # OAuth: Store user ID for credential service
        self.default_provider_id = provider_id if provider_id != "auto" else None
        self.clients: Dict[str, Any] = {}
        self.async_clients: Dict[str, Any] = {}
        self.byok_manager = get_byok_manager()

        # OAuth: Initialize credential service for unified credential resolution
        self.credential_service = LLMCredentialService(
            user_id=user_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id
        ) if user_id else None

        # Use injected dependencies or create defaults
        self.cognitive_classifier = cognitive_classifier or CognitiveClassifier()  # Phase 68: Cognitive tier system
        self._initialize_clients()

        # Initialize cache-aware router for cost optimization
        self.cache_router = cache_router or CacheAwareRouter(get_pricing_fetcher())

        # Initialize pricing fetcher for capability lookups (Phase 307-08)
        self.pricing_fetcher: DynamicPricingFetcher = get_pricing_fetcher()

        # Phase 68-06: Initialize Cognitive Tier Service for orchestration
        if db_session is not None:
            self.db_session = db_session
        else:
            try:
                self.db_session = get_db_session().__enter__()  # Get session for service
            except Exception as e:
                logger.warning(f"Could not create database session for tier service: {e}")
                self.db_session = None
        self.tier_service = tier_service or CognitiveTierService(workspace_id, self.db_session, tenant_id=tenant_id)

        # Phase 226.4-04: Initialize excluded models cache
        self.excluded_models = set()
        self._refresh_excluded_cache()

        # Phase 226.4-04: Initialize health monitor
        from core.provider_health_monitor import get_provider_health_monitor
        self.health_monitor = get_provider_health_monitor()
        self.async_clients = self.async_clients or {} # Ensure it exists if _initialize_clients failed

        # Thread safety for lazy embedding init
        self._embedding_initialized = False
        self._embedding_init_lock = threading.Lock()

    def _get_provider_fallback_order(self, primary_provider: str) -> List[str]:
        """
        Get provider fallback order for resilience.

        Provider priority based on reliability and cost:
        1. deepseek - Primary (most reliable, cost-effective)
        2. openai - Fallback (most reliable but expensive)
        3. moonshot - Fallback
        4. minimax - Fallback (Phase 68 integration)
        5. deepinfra - Last resort

        Args:
            primary_provider: The requested provider to try first

        Returns:
            List of provider IDs in fallback order
        """
        # All available providers that have clients initialized
        available_providers = list(self.async_clients.keys()) if self.async_clients else list(self.clients.keys())

        if not available_providers:
            return []

        # Fallback priority order (most reliable first)
        priority_order = ["deepseek", "openai", "moonshot", "minimax", "xiaomi", "deepinfra", "ollama"]

        # Build fallback list: primary first, then others in priority order
        fallback_order = []

        # Add primary provider first if it's available
        if primary_provider in available_providers:
            fallback_order.append(primary_provider)

        # Add remaining providers in priority order
        for provider in priority_order:
            if provider in available_providers and provider not in fallback_order:
                fallback_order.append(provider)

        # Add any remaining available providers not in priority list
        for provider in available_providers:
            if provider not in fallback_order:
                fallback_order.append(provider)

        return fallback_order

    def _refresh_excluded_cache(self):
        """Cache models with exclude_from_general_routing=True"""
        try:
            with get_db_session() as db:
                excluded = db.query(ModelCatalog.model_id).filter(
                    ModelCatalog.exclude_from_general_routing == True
                ).all()
                self.excluded_models = {m[0] for m in excluded}
                logger.debug(f"Refreshed excluded models cache: {len(self.excluded_models)} models excluded")
        except Exception as e:
            logger.warning(f"Failed to refresh excluded models cache: {e}")
            self.excluded_models = set()

    def _filter_by_capabilities(self, model_id: str, required_capability: Optional[str]) -> bool:
        """
        Check if model has the required capability.

        Args:
            model_id: Model identifier
            required_capability: Required capability (e.g., "computer_use", "vision", "tools")

        Returns:
            True if model has capability or no requirement, False otherwise
        """
        if not required_capability:
            return True  # No capability requirement

        try:
            with get_db_session() as db:
                model = db.query(ModelCatalog).filter_by(model_id=model_id).first()
                if not model:
                    return True  # Unknown models pass through
                capabilities = model.capabilities or ["chat"]
                return required_capability in capabilities
        except Exception as e:
            logger.warning(f"Failed to check capabilities for {model_id}: {e}")
            return True  # Pass through on error

    def _filter_by_health(self, provider_id: str) -> bool:
        """
        Check if provider is healthy enough for routing.

        Args:
            provider_id: Provider identifier

        Returns:
            True if provider is healthy (score >= 0.5) or unknown, False otherwise
        """
        if provider_id not in self.health_monitor.health_scores:
            return True  # Unknown providers pass through
        return self.health_monitor.get_health_score(provider_id) >= 0.5

    def _model_supports_tools(self, model_id: str) -> bool:
        """
        Check if model supports tool calling using pricing cache (not hardcoded lists).

        Replaces MODELS_WITHOUT_TOOLS pattern matching.

        Args:
            model_id: Model identifier

        Returns:
            True if model supports tools, False otherwise
        """
        capabilities = self.pricing_fetcher.get_model_capabilities(model_id)
        return capabilities.get("supports_tools", True)  # Default to True for unknown models

    def _model_supports_vision(self, model_id: str) -> bool:
        """
        Check if model supports vision using pricing cache (not hardcoded lists).

        Replaces hardcoded VISION_MODELS lists.

        Args:
            model_id: Model identifier

        Returns:
            True if model supports vision, False otherwise
        """
        capabilities = self.pricing_fetcher.get_model_capabilities(model_id)
        return capabilities.get("supports_vision", False)

    def _model_supports_reasoning(self, model_id: str) -> bool:
        """
        Check if model is a reasoning model using pricing cache (not hardcoded lists).

        Args:
            model_id: Model identifier

        Returns:
            True if model is a reasoning model, False otherwise
        """
        capabilities = self.pricing_fetcher.get_model_capabilities(model_id)
        return capabilities.get("supports_reasoning", False)

    def _initialize_clients(self) -> None:
        """Initialize clients for all available providers"""
        if not OpenAI:
            logger.warning("OpenAI package not installed. LLM features may be limited.")
            return

        # Initialize OpenAI-compatible clients for each provider
        providers_config = {
            "openai": {"base_url": None},
            "deepseek": {"base_url": "https://api.deepseek.com/v1"},
            "moonshot": {"base_url": "https://api.moonshot.cn/v1"},
            "deepinfra": {"base_url": "https://api.deepinfra.com/v1/openai"},
            "minimax": {"base_url": "https://api.minimax.io/v1"},  # MiniMax M3 (OpenAI-compatible)
            "lux": {"base_url": None},  # Phase 226.2-01: LUX Computer Use (uses Anthropic API)
            "qwen": {"base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"},
            "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/"},
            "xiaomi": {"base_url": "https://api.xiaomi.com/v1"},
            "ollama": {"base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")},
        }

        # Separate sync and async clients
        self.async_clients: Dict[str, Any] = {}

        # Phase 226.2-01: Special handling for LUX provider (uses Anthropic API key via lux_config)
        if "lux" in providers_config:
            # LUX uses Anthropic API key via lux_config or BYOK fallback
            api_key = lux_config.get_anthropic_key() or self.byok_manager.get_api_key("lux")
            if api_key:
                try:
                    self.clients["lux"] = OpenAI(api_key=api_key)
                    if AsyncOpenAI:
                        self.async_clients["lux"] = AsyncOpenAI(api_key=api_key)
                    logger.info("Initialized LUX provider with Anthropic client")
                except Exception as e:
                    logger.error(f"Failed to initialize LUX client: {e}")
            # Remove lux from providers_config so it doesn't get processed in the loop below
            del providers_config["lux"]

        # Ollama: Local LLM server (OpenAI-compatible). No API key required —
        # always initialize against the configured base_url (default localhost:11434).
        if "ollama" in providers_config:
            ollama_base_url = providers_config["ollama"]["base_url"]
            try:
                self.clients["ollama"] = OpenAI(
                    api_key="ollama",  # Dummy key — server ignores it
                    base_url=ollama_base_url,
                )
                if AsyncOpenAI:
                    self.async_clients["ollama"] = AsyncOpenAI(
                        api_key="ollama",
                        base_url=ollama_base_url,
                    )
                logger.info(f"Initialized Ollama (local) client at {ollama_base_url}")
            except Exception as e:
                logger.error(f"Failed to initialize Ollama client: {e}")
            # Remove so the API-key-based loop doesn't re-process it
            del providers_config["ollama"]

        for provider_id, config in providers_config.items():
            # OAuth + BYOK: Try credential service first (OAuth → BYOK → ENV)
            api_key = None
            credential_source = None

            if self.credential_service:
                try:
                    # Import asyncio for async call in sync context
                    import asyncio
                    # Try to get credential from service (OAuth priority)
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                    # Try to get credential with OAuth priority
                    credential_type, credential_value = loop.run_until_complete(
                        self.credential_service.get_credential(provider_id)
                    )
                    api_key = credential_value
                    credential_source = credential_type
                    logger.info(f"Using {credential_source.upper()} credential for {provider_id}")
                except Exception as e:
                    logger.debug(f"Credential service not available for {provider_id}: {e}")

            # Fallback to BYOK if credential service didn't provide one
            if not api_key and self.byok_manager.is_configured(self.workspace_id, provider_id):
                api_key = self.byok_manager.get_api_key(provider_id)
                credential_source = "byok"

            # Special case: Gemini BYOK fallback to Google / Google Flash / Gemini Flash variants
            if not api_key and provider_id == "gemini":
                for alt_provider in ["google", "google_flash", "google_flash_3_5", "gemini_flash", "gemini_flash_3_5"]:
                    if self.byok_manager.is_configured(self.workspace_id, alt_provider):
                        api_key = self.byok_manager.get_api_key(alt_provider)
                        credential_source = "byok"
                        break

            # Final fallback to environment variables
            if not api_key:
                env_key = f"{provider_id.upper()}_API_KEY"
                api_key = os.getenv(env_key)

                # Special case: Gemini can use GOOGLE_API_KEY
                if not api_key and provider_id == "gemini":
                    api_key = os.getenv("GOOGLE_API_KEY")

                if api_key:
                    credential_source = "env"

            # Initialize client if we have an API key
            if api_key:
                try:
                    self.clients[provider_id] = OpenAI(
                        api_key=api_key,
                        base_url=config["base_url"] # base_url can be None for OpenAI
                    )
                    if AsyncOpenAI:
                        self.async_clients[provider_id] = AsyncOpenAI(
                            api_key=api_key,
                            base_url=config["base_url"]
                        )
                    logger.info(f"Initialized {provider_id} client using {credential_source.upper()} credential")
                except Exception as e:
                    logger.error(f"Failed to initialize {provider_id} client: {e}")
            else:
                logger.debug(f"No credential available for {provider_id}, skipping initialization")

    def get_context_window(self, model_name: str) -> int:
        """
        Get the context window size for a model from dynamic pricing data.
        Returns a safe default if not found.
        """
        try:
            fetcher = get_pricing_fetcher()
            pricing = fetcher.get_model_price(model_name)
            if pricing:
                # Prefer max_input_tokens, fall back to max_tokens
                return pricing.get("max_input_tokens") or pricing.get("max_tokens") or 4096
        except Exception as e:
            logger.debug(f"Could not get context window for {model_name}: {e}")
        
        # Safe defaults by provider/model
        CONTEXT_DEFAULTS = {
            "gpt-4o": 128000,
            "gpt-4o-mini": 128000,
            "gpt-4": 8192,
            "claude-3": 200000,
            "deepseek-chat": 32768,
            "deepseek-reasoner": 32768,
            "gemini": 1000000,  # Gemini has huge context
        }
        for key, size in CONTEXT_DEFAULTS.items():
            if key in model_name.lower():
                return size
        return 4096  # Conservative default

    def truncate_to_context(self, text: str, model_name: str, reserve_tokens: int = 1000) -> str:
        """
        Truncate text to fit within the model's context window, preserving the
        HEAD (initial context, system setup, first request) and TAIL (most
        recent turns — the active task) verbatim. Only the stale MIDDLE is
        dropped.

        This is the boundary-protection principle from Hermes' 4-phase
        compressor, applied to a flat prompt string. We deliberately do NOT
        build an LLM-summarization phase here — Hermes' own summary compressor
        has 3 documented production bugs (JSON silent drop, tool-pair 400,
        anti-thrashing permanent lock). Provider compaction APIs are the
        correct place for lossy summarization; this method is the
        deterministic safety net beneath them.

        Tool-pair sanitization (keeping tool_call/tool_result pairs together)
        applies to message-ARRAY truncation, not flat-string; see
        sanitize_tool_pairs() for that path.
        """
        context_window = self.get_context_window(model_name)
        max_input_tokens = context_window - reserve_tokens

        # Approximate: 1 token ≈ 4 characters
        max_chars = max_input_tokens * 4

        if len(text) <= max_chars:
            return text

        # Boundary protection: preserve head + tail, drop the middle.
        # Tail gets a larger share (60%) — it contains the active task and
        # most recent observations, which matter most for the next step.
        marker = "\n\n[... %d chars of middle context elided (head + tail preserved) ...]\n\n"
        marker_overhead = len(marker % 0)
        budget = max_chars - marker_overhead - 100  # 100-char safety margin

        head_share = int(budget * 0.4)
        tail_share = budget - head_share

        head = text[:head_share]
        tail = text[-tail_share:]
        elided = len(text) - head_share - tail_share

        truncated = head + (marker % elided) + tail
        logger.warning(
            f"Truncated prompt from {len(text)} to {len(truncated)} chars for {model_name} "
            f"(head={head_share}, tail={tail_share}, elided={elided})"
        )
        return truncated

    @staticmethod
    def sanitize_tool_pairs(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ensure every ``tool`` role message is preceded by a matching
        ``assistant`` message carrying ``tool_calls``.

        OpenAI-compatible providers return HTTP 400 if a ``tool`` result
        appears without a preceding ``assistant.tool_calls`` — this happens
        when context-window truncation or compression cuts between a tool
        call and its result. This function:
          - injects a stub ``assistant`` message before any orphaned ``tool``
            result (Hermes' Phase-4 mitigation, minus the bug)
          - drops trailing ``assistant`` messages that have ``tool_calls``
            but whose ``tool`` results were truncated away

        This is the deterministic companion to ``truncate_to_context``'s
        boundary protection. Operates on message arrays only.
        """
        if not messages:
            return messages

        sanitized: List[Dict[str, Any]] = []
        for i, msg in enumerate(messages):
            role = msg.get("role")
            if role == "tool":
                # Check: is there a preceding assistant.tool_calls?
                prev = sanitized[-1] if sanitized else None
                prev_is_tool_call = (
                    prev
                    and prev.get("role") == "assistant"
                    and prev.get("tool_calls")
                )
                if not prev_is_tool_call:
                    # Inject a stub so the provider doesn't 400.
                    sanitized.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": msg.get("tool_call_id", "stub"),
                            "type": "function",
                            "function": {
                                "name": "_truncated_tool_call",
                                "arguments": "{}",
                            },
                        }],
                    })
                sanitized.append(msg)
            else:
                sanitized.append(msg)

        # Drop a trailing assistant.tool_calls whose tool result was truncated
        if (
            sanitized
            and sanitized[-1].get("role") == "assistant"
            and sanitized[-1].get("tool_calls")
            and not any(m.get("role") == "tool" for m in sanitized[-1:])
        ):
            # Actually: only drop if it's the very last AND has no content
            last = sanitized[-1]
            if last.get("tool_calls") and not last.get("content"):
                sanitized.pop()

        return sanitized

    def analyze_query_complexity(self, prompt: str, task_type: Optional[str] = None) -> QueryComplexity:
        """
        Analyze query complexity to determine optimal provider routing.
        Uses a robust regex-based heuristic with expanded vocabulary.
        """
        # 1. Length-based scoring (estimated tokens)
        estimated_tokens = len(prompt) / 4
        complexity_score = 0
        
        if estimated_tokens >= 2000:
            complexity_score += 3
        elif estimated_tokens >= 500:
            complexity_score += 2
        elif estimated_tokens >= 100:
            complexity_score += 1

        # 2. Regex-based vocabulary analysis
        # Using word boundaries \b to avoid matches inside other words
        patterns = {
            "simple": (r"\b(hello|hi|thanks|greetings|summarize|translate|list|what is|who is|define|how do i|simplify|brief|basic|short|quick|simple)\b", -2),
            "moderate": (r"\b(analyze|compare|evaluate|synthesize|explain|describe|detailed|background|concept|history|nuance|opinion|critique|pros and cons|advantages|disadvantages)\b", 1),
            "technical": (r"\b(calculate|equation|formula|solve|integral|derivative|calculus|geometry|algebra|math|maths|theorem|statistics|probability|regression|vector|matrix|tensor|log|exp|pow|sqrt|abs|sin|cos|tan|pi|infinity|prime|physics|chemistry|biology|science)\b", 3),
            "code": (r"\b(code|coding|function|class|method|script|scripting|debug|debugging|optimize|optimization|refactor|refactoring|snippet|implementation|interface|api|endpoint|webhook|database|sql|postgresql|mongodb|redis|schema|migration|json|xml|yaml|config|docker|kubernetes|aws|lambda|gcp|azure|def|var|let|const|import|return|print|async|await|try|except|catch|throw|public|private|static|final|struct|typedef|typedefs)\b", 3),
            "advanced": (r"\b(architecture|architecting|security audit|vulnerability|cryptography|encryption|decryption|authentication|authorization|auth|oauth|jwt|performance|bottleneck|concurrency|multithread|parallel|distributed|scale|scaling|load balance|cluster|proprietary|reverse engineer|obfuscate|obfuscation|enterprise|global|large-scale|purchase order|\bpo\b)\b", 5)
        }

        # Check for code blocks (significant weight)
        if "```" in prompt:
            complexity_score += 3

        for name, (pattern, weight) in patterns.items():
            if re.search(pattern, prompt, re.IGNORECASE):
                complexity_score += weight

        # 3. Task type override
        if task_type:
            if task_type in ["code", "analysis", "reasoning"]:
                complexity_score += 2
            elif task_type in ["chat", "general"]:
                complexity_score -= 1

        # 4. Map score to complexity level
        # Refined ranges: 2+ is COMPLEX, 5+ is ADVANCED
        if complexity_score <= 0:
            return QueryComplexity.SIMPLE
        elif complexity_score == 1:
            return QueryComplexity.MODERATE
        elif complexity_score <= 4:
            return QueryComplexity.COMPLEX
        else:
            return QueryComplexity.ADVANCED

    async def get_optimal_provider(
        self, 
        complexity: QueryComplexity, 
        task_type: Optional[str] = None, 
        prefer_cost: bool = True,
        tenant_plan: str = "free",
        is_managed_service: bool = True,
        requires_tools: bool = False, # Phase 6.6
        requires_structured: bool = False, # Phase 6.6
        turn_index: int = 0
    ) -> tuple[str, str]:
        """Get the single most optimal provider and model."""
        options = await self.get_ranked_providers(
            complexity, task_type, prefer_cost, tenant_plan, 
            is_managed_service, requires_tools, requires_structured,
            turn_index=turn_index
        )
        if options:
            return options[0]
        
        # Absolute fallback
        if self.clients:
            provider_id = list(self.clients.keys())[0]
            return provider_id, "gpt-4o-mini"

        raise NoProvidersConfiguredError(
            "You need an AI provider to do this. Add an API key or enable local Ollama to continue."
        )

    async def get_ranked_providers(
        self,
        complexity: QueryComplexity,
        task_type: Optional[str] = None,
        prefer_cost: bool = True,
        tenant_plan: str = "free",
        is_managed_service: bool = True,
        requires_tools: bool = False, # Phase 6.6
        requires_structured: bool = False, # Phase 6.6
        estimated_tokens: int = 1000, # Cache-aware routing
        workspace_id: str = "default", # Cache-aware routing
        cognitive_tier: Optional[CognitiveTier] = None,  # Phase 68: Cognitive tier system
        required_capability: Optional[str] = None,  # Phase 226.4-04: Capability-based routing
        turn_index: int = 0 # NEW: Deterministic BPC
    ) -> List[tuple[str, str]]:
        """
        Get a ranked list of providers and models using the BPC (Benchmark-Price-Capability) algorithm.
        This objectively ranks models based on their value proposition.

        Cache-Aware Extension (Deterministic):
        Uses turn_index (0 = first turn, 1+ = repeat turns) to determine whether
        to use full input price or cached input price.

        Phase 68 Extension:
        When cognitive_tier is provided, uses CognitiveTier-based quality filtering instead of
        QueryComplexity. This enables more granular 5-tier quality control.

        Phase 226.4-04 Extension:
        When required_capability is provided, filters models by capability (e.g., "computer_use", "vision", "tools")
        and uses capability-specific quality scores. Also filters out excluded models and unhealthy providers.

        Args:
            complexity: Query complexity level
            task_type: Optional task type hint
            prefer_cost: Whether to prefer cost over quality
            tenant_plan: Tenant plan for model restrictions
            cognitive_tier: Optional CognitiveTier for 5-tier quality filtering (Phase 68)
            is_managed_service: Whether this is managed service or BYOK
            requires_tools: Whether model must support tool calling
            requires_structured: Whether model must support structured output
            estimated_tokens: Estimated input token count (for cache hit prediction)
            workspace_id: Workspace ID for cache history lookup
            required_capability: Optional capability requirement (e.g., "computer_use", "vision", "tools")
            turn_index: Interaction turn (0 = creation, 1+ = reuse)

        Returns:
            List of (provider, model) tuples ranked by value score
        """
        ranked_options = []
        
        # 1. Dynamic BPC Selection (Data-Driven)
        try:
            # Lazy async initialization: auto-populate pricing cache on first use
            fetcher = await get_pricing_fetcher_initialized(auto_refresh=True)
            
            # Context window requirements
            MIN_CONTEXT_BY_COMPLEXITY = {
                QueryComplexity.SIMPLE: 4000,
                QueryComplexity.MODERATE: 8000,
                QueryComplexity.COMPLEX: 16000,
                QueryComplexity.ADVANCED: 32000
            }
            min_context = MIN_CONTEXT_BY_COMPLEXITY.get(complexity, 8000)

            # Filter criteria for benchmarks based on complexity
            # Phase 68: Use CognitiveTier thresholds if provided
            if cognitive_tier is not None:
                min_quality = MIN_QUALITY_BY_TIER.get(cognitive_tier, 0)
                logger.debug(f"Using CognitiveTier {cognitive_tier.value} quality threshold: {min_quality}")
            else:
                MIN_QUALITY_BY_COMPLEXITY = {
                    QueryComplexity.SIMPLE: 0,
                    QueryComplexity.MODERATE: 80,
                    QueryComplexity.COMPLEX: 88,
                    QueryComplexity.ADVANCED: 94
                }
                min_quality = MIN_QUALITY_BY_COMPLEXITY.get(complexity, 0)
            
            # Extraction tasks: cap max quality at 90. Pro/opus/frontier
            # models (91-100) are overkill for structured entity extraction.
            # IMPORTANT: For extraction, enforce the cap even if min_quality is higher.
            # COMPLEX tier (min_quality=94) with extraction cap should use max_quality=90,
            # and we adjust min down to avoid creating an impossible window.
            # Also exclude o-series models — they don't reliably return
            # message.content (reasoning goes to a separate field).
            if task_type == "extraction":
                max_quality = 90
                # Adjust min_quality down if it exceeds the cap
                min_quality = min(min_quality, 90)
                _excluded_models = {"o1", "o1-mini", "o1-pro", "o3", "o3-mini", "o4", "o4-mini"}
            else:
                max_quality = 100
                _excluded_models = set()
            
            available_providers = list(self.clients.keys())
            candidates = []
            
            # Use the entire pricing cache to discover models beyond hardcoded lists
            for model_id, pricing in fetcher.pricing_cache.items():
                litellm_provider = pricing.get("litellm_provider", "").lower()
                
                # Check if we have a client for this provider
                active_provider = next((p for p in available_providers if p in model_id.lower() or p == litellm_provider), None)
                if not active_provider:
                    continue
                
                # Check context window
                context_window = pricing.get("max_input_tokens") or pricing.get("max_tokens") or 0
                if context_window < min_context:
                    continue

                # Phase 226.4-04: Check capability filter
                if not self._filter_by_capabilities(model_id, required_capability):
                    continue

                # Phase 226.4-04: Check if model is excluded from general routing
                if not required_capability and model_id in self.excluded_models:
                    continue

                # Phase 226.4-04: Check provider health
                if not self._filter_by_health(active_provider):
                    continue

                # Check quality score (use capability-specific score if required)
                if required_capability:
                    quality_score = get_capability_score(model_id, required_capability)
                else:
                    quality_score = get_quality_score(model_id)

                if quality_score < min_quality or quality_score > max_quality:
                    continue

                # Exclude o-series from extraction tasks (no reliable content)
                if task_type == "extraction" and any(
                    m in model_id.lower() for m in _excluded_models
                ):
                    continue

                # Calculate BPC Value Score with Cache-Aware Cost
                # Value = (Quality^2) / Cost. We use 1e6 to make costs readable.

                # Calculate DETERMINISTIC cache-aware effective cost (Turn 0 vs Turn N)
                effective_cost = await self.cache_router.calculate_effective_cost(
                    model_id, active_provider, estimated_tokens, turn_index=turn_index
                )

                # Avoid division by zero and handle free models
                normalized_cost = max(effective_cost, 1e-9)

                # BPC Score: Higher is better value
                # Squaring quality penalizes low-end models regardless of price for complex tasks
                value_score = (quality_score ** 2) / (normalized_cost * 1e6)
                
                candidates.append({
                    "provider": active_provider,
                    "model": model_id,
                    "value_score": value_score,
                    "quality": quality_score,
                    "cost": effective_cost
                })
            
            # Sort by Value Score (Descending)
            candidates.sort(key=lambda x: x["value_score"], reverse=True)
            
            # Filter by plan restrictions
            allowed_models = MODEL_TIER_RESTRICTIONS.get(tenant_plan.lower(), MODEL_TIER_RESTRICTIONS["free"]) if is_managed_service else "*"
            
            def is_model_approved(model_id: str, allowed_list: any) -> bool:
                if allowed_list == "*" or "*" in allowed_list:
                    return True
                
                # Flexible matching: check if any allowed model name is part of the actual model_id
                model_id_lower = model_id.lower()
                
                # Check Tool/Structured constraints (Phase 6.6) - Use pricing cache lookup
                if (requires_tools or requires_structured) and not self._model_supports_tools(model_id):
                    return False

                return any(m.lower() in model_id_lower for m in allowed_list)

            for c in candidates:
                if is_model_approved(c["model"], allowed_models):
                    ranked_options.append((c["provider"], c["model"]))
            
            if ranked_options:
                logger.info(f"BPC Ranking Successful for {complexity.value}: Top model {ranked_options[0][1]} (Value: {candidates[0]['value_score']:.2f})")
                return ranked_options
                
        except Exception as e:
            logger.debug(f"BPC ranking failed, falling back to static mapping: {e}")
        
        # 2. Static Fallback (if BPC logic fails or cache empty)
        if complexity == QueryComplexity.SIMPLE:
            provider_priority = ["deepseek", "minimax", "qwen", "moonshot", "gemini", "openai", "anthropic"]
        elif complexity == QueryComplexity.MODERATE:
            provider_priority = ["deepseek", "minimax", "qwen", "gemini", "moonshot", "openai", "anthropic"]
        elif complexity == QueryComplexity.COMPLEX:
            provider_priority = ["gemini", "deepseek", "anthropic", "qwen", "minimax", "openai", "moonshot"]
        else: # ADVANCED
            provider_priority = ["openai", "deepseek", "anthropic", "qwen", "gemini", "moonshot", "minimax"]
        
        for provider_id in provider_priority:
            if provider_id in self.clients:
                models = COST_EFFICIENT_MODELS.get(provider_id, {})
                model = models.get(complexity, "gpt-4o-mini")
                
                if not is_managed_service:
                    # Filter for tool support even in BYOK (Phase 6.6) - Use pricing cache lookup
                    if (requires_tools or requires_structured) and not self._model_supports_tools(model):
                        # Fallback to r2 if speciale is disallowed
                        if provider_id == "deepseek" and model == "deepseek-v3.2-speciale":
                            model = "deepseek-r2"
                        else:
                            continue

                    ranked_options.append((provider_id, model))
                    continue

                allowed_models = MODEL_TIER_RESTRICTIONS.get(tenant_plan.lower(), MODEL_TIER_RESTRICTIONS["free"])
                
                # Check Tool/Structured Support (Phase 6.6)
                if (requires_tools or requires_structured) and model in MODELS_WITHOUT_TOOLS:
                    # Try to downgrade to a model that supports tools within the same provider
                    if provider_id == "deepseek" and model == "deepseek-v3.2-speciale":
                        model = "deepseek-r2" # r2 supports tools/structured
                    else:
                        continue # Skip this provider if no fallback found

                if "*" in allowed_models or model in allowed_models:
                    ranked_options.append((provider_id, model))
                    
        # Phase 68-Q: Boost Qwen to top if available and requested
        if "qwen" in self.clients:
            qwen_option = next(((p, m) for p, m in ranked_options if p == "qwen"), None)
            if qwen_option:
                ranked_options.remove(qwen_option)
                ranked_options.insert(0, qwen_option)

        return ranked_options

    async def generate_response(
        self, 
        prompt: str, 
        system_instruction: str = "You are a helpful assistant.",
        model_type: str = "auto",  # "auto", "fast", "quality", or specific model
        temperature: float = 0.7,
        task_type: Optional[str] = None,
        prefer_cost: bool = True,
        agent_id: Optional[str] = None, # Phase 65
        chain_id: Optional[str] = None, # NEW Phase 11
        image_payload: Optional[str] = None, # Phase 14: Base64 or URL
        turn_index: int = 0 # NEW: Deterministic BPC
    ) -> str:
        """
        Generate a response using cost-optimized provider routing.
        Supports multimodal inputs (text + image) via `image_payload`.
        """
        # Phase 72: Trial Restriction Check
        if self._is_trial_restricted():
            logger.warning(f"AI Blocked: Trial expired for workspace {self.workspace_id}")
            return "Trial Expired: Your free trial has ended. Please upgrade your plan in settings to continue using AI agents."
        if not self.clients:
            if task_type == "agentic":
                # FOR DEMO: Return a mock JSON that continues the agentic loop
                if "Check my inbox" in prompt or "analyze" in prompt.lower() or "market" in prompt.lower():
                    return json.dumps({
                        "thought": "The user wants a full end-to-end machinery quote and client analysis. I will start by performing the market analysis.",
                        "plan_update": ["Perform market analysis for brennan.ca", "Read inbound emails", "Calculate quote and save to Excel", "Update CRM", "Send final email with meeting invite"],
                        "action": "perform_market_analysis",
                        "action_input": {"client_url": "brennan.ca", "product_name": "5-Axis CNC Mill"},
                        "log": "> Starting Market Analysis for Brennan.ca...",
                        "deliverable": None
                    })
                return json.dumps({
                    "thought": "LLM not initialized, but running in agentic demo mode.",
                    "action": "DONE",
                    "log": "AI Employee Demo Mode active (No API Keys found)."
                })
            return "LLM Client not initialized (No API Keys configured)."
        
        # --- Budget Enforcement (Phase 56) ---
        if llm_usage_tracker.is_budget_exceeded(self.workspace_id):
            logger.warning(f"AI Generation Blocked: Budget exceeded for workspace {self.workspace_id}")
            return "🚨 BUDGET EXCEEDED: Your AI usage has reached 100% of your limit. Please increase your budget in Settings to continue."

        try:
            # --- Tier & Pricing Mode Enforcement (Phase 59 Refinement) ---
            
            with get_db_session() as db:
                try:
                    tenant_plan = "free"
                    is_managed = True

                    workspace = db.query(Workspace).filter(Workspace.id == self.workspace_id).first()
                    if workspace and workspace.tenant_id:
                        tenant = db.query(Tenant).filter(Tenant.id == (self.tenant_id if self.tenant_id != "default" else workspace.tenant_id)).first()
                        if tenant:
                            # 1. Determine Plan level
                            plan_type = tenant.plan_type
                            tenant_plan = plan_type.value if hasattr(plan_type, 'value') else str(plan_type).lower()

                            # 2. Determine if Managed or BYOK (Phase 50 Hybrid Logic)
                            complexity = self.analyze_query_complexity(prompt, task_type)

                            # Agents always require tools (Phase 6.6)
                            requires_tools = agent_id is not None or task_type == "agentic"

                            # Temporary provider check for key resolution
                            temp_provider_id, _ = await self.get_optimal_provider(
                                complexity, task_type, prefer_cost, tenant_plan,
                                is_managed_service=True, requires_tools=requires_tools,
                                turn_index=turn_index
                            )

                            tenant_key = self.byok_manager.get_tenant_api_key(self.tenant_id, temp_provider_id)
                            if tenant_key:
                                is_managed = False  # Custom Key = BYOK
                            elif tenant_plan.lower() in [p.lower() for p in BYOK_ENABLED_PLANS]:
                                is_managed = False  # Enterprise Plan = BYOK

                            # 3. Block Managed AI for Free Tier (Phase 59 User Req) - BYPASSED for AI Employee Demo
                            # We bypass this for 'agentic' task types to allow the demo to function
                            if is_managed and tenant_plan.lower() == "free" and task_type != "agentic":
                                # Check if we have ANY local api keys that can be used instead
                                if not self.clients:
                                    return "🚨 PLAN RESTRICTION: Managed AI is not available on the Free plan. Please add your own API key in Settings or upgrade to a Pro plan to continue."
                except Exception as e:
                    logger.warning(f"Failed to fetch tenant plan: {e}")

            # --- Phase 14-BYOK: Force BYOK behavior if local keys exist for agentic tasks ---
            if task_type == "agentic" and self.clients:
                is_managed = False
                tenant_plan = "enterprise" # Effectively unrestricted
                logger.info("Using local/BYOK mode for agentic task demo")

            # Analyze complexity
            complexity = self.analyze_query_complexity(prompt, task_type)
            
            # Identify tool/structured requirements (Phase 6.6)
            requires_tools = agent_id is not None or task_type == "agentic"
            
            # --- Phase 14: Vision Routing ---
            # If image payload exists, we MUST route to a model that supports vision (GPT-4o, Gemini 1.5 Pro)
            # We override the normal routing logic to prioritize Vision-Capable models
            requires_vision = image_payload is not None
            
            # Get ranked list of providers
            options = await self.get_ranked_providers(
                complexity, task_type, prefer_cost, tenant_plan, is_managed,
                requires_tools=requires_tools, requires_structured=False,
                turn_index=turn_index
            )

            # --- Learning-router re-ranking (flag-gated, phase 2 of rollout) ---
            # When enabled and a trained predictor exists for this tenant/task,
            # re-order BPC's already-filtered candidate list using the learned
            # satisfaction signal. Never adds/removes candidates — only re-orders
            # — so the live pricing-cache (not the router's stale registry)
            # remains the source of truth for which models are eligible. Cold
            # start (no predictor) leaves BPC order untouched. Best-effort: any
            # error falls back to BPC order so the hot path never breaks.
            options = await self._rerank_with_learning(options, prompt, task_type)

            # --- Phase 14.5: Coordinated Vision Logic ---
            if requires_vision:
                # Check if the primary ranked model supports vision natively
                primary_provider, primary_model = options[0] if options else (None, None)

                if primary_model and not self._model_supports_vision(primary_model):
                    logger.info(f"Coordinating vision for non-vision model: {primary_model}")
                    vision_desc = await self._get_coordinated_vision_description(
                        image_payload=image_payload,
                        tenant_plan=tenant_plan,
                        is_managed=is_managed
                    )
                    if vision_desc:
                        mapping_instr = (
                            "\n[COORDINATE MAPPING]:\n"
                            "The coordinates below are on a normalized 1000x1000 grid. "
                            "The browser viewport is 1280 pixels wide. "
                            "To click an element at [x, y], use browser_click_coords(x*1.28, y*H) where H is approximately 0.72*1.28.\n"
                        )
                        prompt = f"[VISUAL CONTEXT ANALYSIS]:\n{vision_desc}\n{mapping_instr}\n\n[USER REQUEST]:\n{prompt}"
                        # Disable image_payload for the reasoning call
                        image_payload = None 
                        requires_vision = False

            # Filter for Vision logic if needed
            if requires_vision:
                # 1. Specialized Task Preference (e.g., DeepSeek-OCR for PDF)
                if task_type == "pdf_ocr":
                    # Prefer DeepInfra DeepSeek-OCR or Direct DeepSeek
                    preferred_ocr = [(p, m) for p, m in options if "deepinfra" in p.lower() or "deepseek" in p.lower() or ("deepseek" in m.lower() and "ocr" in m.lower())]
                    if preferred_ocr:
                        options = preferred_ocr
                        logger.info(f"Prioritizing {preferred_ocr[0][0]} for PDF OCR task")

                # 2. Cache-based filter: Only keep models that support vision
                vision_options = []
                for prov, mod in options:
                    if self._model_supports_vision(mod):
                        vision_options.append((prov, mod))
                
                if vision_options:
                    options = vision_options
                elif not any("deepseek" in p.lower() for p, m in options):
                    # Fallback default if no ranked vision option matches
                    logger.warning("No standard vision models found in ranked options. Defaulting to GPT-4o.")
                    options = [("openai", "gpt-4o")] # Panic fallback
            
            if not options:
                return "No eligible LLM providers found for your current plan."

            last_error = None
            for provider_id, model in options:
                try:
                    import time
                    request_start = time.time()
                    client = self.clients[provider_id]
                    
                    # Construct Messages (Phase 14: Multimodal)
                    messages = []
                    messages.append({"role": "system", "content": system_instruction})
                    
                    if image_payload:
                        # OpenAI / Compatible Vision Format
                        user_content = [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_payload if image_payload.startswith("http") else f"data:image/jpeg;base64,{image_payload}"
                                }
                            }
                        ]
                        messages.append({"role": "user", "content": user_content})
                        logger.info(f"Adding visual payload to request for {model}")
                    else:
                        messages.append({"role": "user", "content": prompt})

                    # Make the request
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature
                    )
                    
                    result = response.choices[0].message.content
                    finish_reason = getattr(response.choices[0], "finish_reason", None)
                    observed_cost = None  # set below if usage attribution succeeds

                    # --- Dynamic Cost Attribution (Phase 47) ---
                    usage = getattr(response, 'usage', None)
                    if usage:
                        input_tokens = getattr(usage, 'prompt_tokens', 0)
                        output_tokens = getattr(usage, 'completion_tokens', 0)
                        
                        # Calculate real cost from dynamic pricing
                        try:
                            fetcher = get_pricing_fetcher()
                            cost = fetcher.estimate_cost(model, input_tokens, output_tokens)
                            
                            # Calculate Reference Cost (gpt-4o) for savings tracking (Phase 58)
                            reference_cost = fetcher.estimate_cost("gpt-4o", input_tokens, output_tokens)
                            savings_usd = max(0, reference_cost - cost) if reference_cost and cost is not None else 0.0
                            
                            # Fallback to static pricing if dynamic not available
                            if cost is None:
                                cost = get_llm_cost(model, input_tokens, output_tokens)
                                # Static reference cost fallback
                                ref_cost_static = get_llm_cost("gpt-4o", input_tokens, output_tokens)
                                savings_usd = max(0, ref_cost_static - cost)
                            
                            if cost and cost > 0:
                                # Record to LLM Usage Tracker
                                llm_usage_tracker.record(
                                    workspace_id=self.workspace_id,
                                    provider=provider_id,
                                    model=model,
                                    input_tokens=input_tokens,
                                    output_tokens=output_tokens,
                                    cost_usd=cost,
                                    savings_usd=savings_usd,
                                    agent_id=agent_id,
                                    chain_id=chain_id, # Phase 11
                                    complexity=complexity.value, # Phase 6.6
                                    is_managed_service=is_managed
                                )
                                logger.info(f"LLM Cost Attributed ({'Managed' if is_managed else 'BYOK'}): {model} - ${cost:.6f} (Saved: ${savings_usd:.6f})")
                            observed_cost = cost
                        except Exception as cost_err:
                            logger.warning(f"Could not attribute LLM cost: {cost_err}")

                        # --- Cache Outcome Recording (Phase 68) ---
                        # Record whether the request hit the prompt cache for future predictions
                        try:
                            prompt_hash = hashlib.sha256(f"{self.workspace_id}:{provider_id}:{model}".encode()).hexdigest()

                            # Check if response usage includes caching info
                            was_cached = False
                            if hasattr(usage, 'prompt_cache_hit_tokens'):
                                # Anthropic provides explicit cache hit token count
                                was_cached = getattr(usage, 'prompt_cache_hit_tokens', 0) > 0
                            elif hasattr(response, 'cache_controls'):
                                # OpenAI provides cache controls in response
                                was_cached = True  # If cache controls were present, it was cached

                            # Record outcome for future predictions
                            self.cache_router.record_cache_outcome(prompt_hash, self.workspace_id, was_cached)
                            logger.debug(f"Cache outcome recorded: {prompt_hash[:16]} -> {was_cached}")
                        except Exception as cache_err:
                            logger.debug(f"Could not record cache outcome: {cache_err}")

                    # Log for analytics
                    logger.info(f"BYOK Logic: complexity={complexity.value}, provider={provider_id}, model={model}")

                    # Phase 226.4-04: Record successful API call for health monitoring
                    latency_ms = (time.time() - request_start) * 1000
                    self.health_monitor.record_call(provider_id, success=True, latency_ms=latency_ms)

                    # Learning-router outcome observation (flag-gated, best-effort).
                    # Feeds real response quality (truncation, empty, etc.) into the
                    # per-model predictors so they learn from outcomes, not just
                    # "did the API return". No-op when ATOM_LEARNING_ROUTER is off.
                    await self._record_outcome_feedback(
                        model=model, provider_id=provider_id, task_type=task_type,
                        content=result, finish_reason=finish_reason,
                        success=True, cost=observed_cost, latency_ms=latency_ms,
                    )

                    return result

                except Exception as attempt_err:
                    logger.warning(f"Attempt failed for {provider_id}/{model}: {attempt_err}")
                    last_error = attempt_err

                    # Phase 226.4-04: Record failed API call for health monitoring
                    try:
                        latency_ms = (time.time() - request_start) * 1000
                        self.health_monitor.record_call(provider_id, success=False, latency_ms=latency_ms)
                    except:
                        pass  # Don't let health monitoring errors affect primary flow

                    # Learning-router outcome observation for failures.
                    await self._record_outcome_feedback(
                        model=model, provider_id=provider_id, task_type=task_type,
                        content=None, finish_reason=None,
                        success=False, cost=None, latency_ms=latency_ms,
                        exception=attempt_err,
                    )
                    continue # Try next provider
            
            return f"All providers failed. Last error: {str(last_error)}"

        except Exception as e:
            logger.error(f"LLM Generation failed: {e}")
            return f"Error generating response: {str(e)}"

    async def _record_outcome_feedback(
        self,
        model: str,
        provider_id: str,
        task_type: Optional[str],
        content: Optional[str],
        finish_reason: Optional[str],
        success: bool,
        cost: Optional[float],
        latency_ms: float,
        exception: Optional[Exception] = None,
        schema_error: bool = False,
    ) -> None:
        """Best-effort outcome observation for the learning router.

        Assess response quality from observable signals (finish_reason, content,
        exception, schema validation) and record it as feedback so per-model
        predictors learn from real outcomes. No-op when
        ``ATOM_LEARNING_ROUTER`` is off or when the router can't be
        instantiated. Never raises — failures are logged and swallowed so the
        hot generation path is unaffected.
        """
        if os.getenv("ATOM_LEARNING_ROUTER", "false").lower() != "true":
            return
        try:
            from core.llm.response_quality import assess_response_quality
            from core.learning_llm_router import LearningBasedRouter
            from core.llm.learning_router_registry import get_learning_router_instance
            import uuid

            learning_router = get_learning_router_instance()
            if learning_router is None:
                return

            quality = assess_response_quality(
                content=content,
                finish_reason=finish_reason,
                schema_error=schema_error,
                exception=exception,
            )
            fb = LearningBasedRouter.build_feedback(
                routing_result_id=str(uuid.uuid4()),
                tenant_id=self.tenant_id or "default",
                model_id=model,
                task_type=self._adapt_task_type(task_type),
                quality=quality,
                actual_cost=cost,
                actual_latency_ms=latency_ms,
            )
            await learning_router.record_feedback(fb)
        except Exception as e:
            logger.debug(f"Learning-router outcome observation skipped: {e}")

    @staticmethod
    def _adapt_task_type(task_type: Optional[str]) -> str:
        """Map the live path's ad-hoc task_type strings to the router vocabulary."""
        if not task_type:
            return "general"
        mapping = {
            "chat": "question_answering",
            "reasoning": "reasoning",
            "agentic": "tool_use",
            "extraction": "extraction",
            "pdf_ocr": "extraction",
            "code": "code_generation",
            "meta_orchestration": "tool_use",
        }
        return mapping.get(task_type.lower().strip(), "general")

    async def _rerank_with_learning(
        self,
        options: list,
        prompt: str,
        task_type: Optional[str],
    ) -> list:
        """Re-rank BPC's candidate list using the learned satisfaction signal.

        Only re-orders the existing list — never adds or removes candidates.
        Returns the original list unchanged when the learning router is off,
        when no predictor exists for this tenant/task (cold start), or on any
        error. ``options`` is a list of ``(provider_id, model)`` tuples from
        ``get_ranked_providers``.
        """
        if not options or len(options) <= 1:
            # Re-ranking needs at least 2 candidates to matter. Single-provider
            # setups yield 1 — log so operators can diagnose why learning had
            # no effect (it's expected, not a bug).
            if options and os.getenv("ATOM_LEARNING_ROUTER", "false").lower() == "true":
                logger.debug(
                    f"[LearningRouter] Only {len(options)} BPC candidate(s) — "
                    f"nothing to re-rank (configure multiple provider keys to "
                    f"give the learning router candidates to choose among)"
                )
            return options
        if os.getenv("ATOM_LEARNING_ROUTER", "false").lower() != "true":
            return options
        try:
            from core.llm.learning_router_registry import get_learning_router_instance
            learning_router = get_learning_router_instance()
            if learning_router is None:
                return options

            cache_key = f"{self.tenant_id or 'default'}:{self._adapt_task_type(task_type)}"
            per_model = learning_router._per_model_routers.get(cache_key)
            if per_model is None:
                return options  # cold start — no predictor for this tenant/task

            # Build the prompt features once (the 10-feature contract).
            estimated_tokens = max(1, len(prompt) // 4)
            features = learning_router._extract_request_features(
                type("RR", (), {
                    "task_type": self._adapt_task_type(task_type),
                    "estimated_tokens": estimated_tokens,
                    "requires_reasoning": False,
                })()
            )

            # Score each candidate by learned satisfaction, blended by confidence.
            # Candidates without a predictor keep their BPC-implied position
            # (score 0 so they sort below learned-favored models but above none).
            scored = []
            learned_any = False
            for idx, (provider_id, model) in enumerate(options):
                satisfaction = per_model.predict_satisfaction(model, features)
                if satisfaction is None:
                    # No predictor for this model — keep BPC order via a small
                    # negative score so it sorts after learned-positive models.
                    scored.append((-(idx * 0.001), provider_id, model))
                else:
                    blend = per_model.confidence(model)
                    score = blend * satisfaction
                    scored.append((score, provider_id, model))
                    if blend > 0:
                        learned_any = True

            if not learned_any:
                return options  # no predictor had enough data to influence

            # Stable sort by learned score descending (ties keep BPC order).
            scored.sort(key=lambda t: -t[0])
            reranked = [(pid, mdl) for _, pid, mdl in scored]
            logger.info(
                f"[LearningRouter] Re-ranked {len(reranked)} candidates for "
                f"{cache_key} (learned signal applied)"
            )
            return reranked
        except Exception as e:
            logger.debug(f"Learning-router re-rank skipped (non-fatal): {e}")
            return options

    async def generate_with_cognitive_tier(
        self,
        prompt: str,
        system_instruction: str = "You are a helpful assistant.",
        task_type: Optional[str] = None,
        user_tier_override: Optional[str] = None,
        agent_id: Optional[str] = None,
        image_payload: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate response using full cognitive tier pipeline.

        Phase 68-06: Integrates CognitiveTierService for end-to-end intelligent routing.

        Pipeline:
        1. Select cognitive tier (classification + workspace preferences)
        2. Check budget constraints (monthly + per-request)
        3. Get optimal model (cache-aware cost scoring)
        4. Generate with automatic escalation on quality issues

        Args:
            prompt: The user query
            system_instruction: System prompt for the LLM
            task_type: Optional task type hint (code, chat, analysis, etc.)
            user_tier_override: Optional user-specified tier (bypasses classification)
            agent_id: Optional agent ID for cost tracking
            image_payload: Optional base64/URL image for multimodal input

        Returns:
            Dictionary with keys:
            - response: Generated text response
            - tier: Cognitive tier used
            - provider: Provider ID used
            - model: Model name used
            - cost_cents: Estimated cost in cents
            - escalated: Whether escalation occurred

        Example:
            >>> handler = BYOKHandler()
            >>> result = await handler.generate_with_cognitive_tier(
            ...     "explain quantum computing",
            ...     task_type="analysis"
            ... )
            >>> print(result["response"])
            >>> print(f"Tier: {result['tier']}, Model: {result['model']}")
        """
        request_id = str(uuid.uuid4())

        # Phase 68-06: Step 1 - Select tier using CognitiveTierService
        tier = self.tier_service.select_tier(prompt, task_type, user_tier_override)

        # Phase 68-06: Step 2 - Check budget constraints
        estimated_cost = self.tier_service.calculate_request_cost(prompt, tier, None)
        if not self.tier_service.check_budget_constraint(estimated_cost.get('cost_cents', 0)):
            logger.warning(f"Budget exceeded for request {request_id}")
            return {
                "error": "Budget exceeded",
                "tier": tier.value,
                "estimated_cost_cents": estimated_cost.get('cost_cents', 0)
            }

        # Phase 68-06: Step 3 - Get optimal model (cache-aware)
        estimated_tokens = len(prompt) // 4
        requires_tools = agent_id is not None or task_type == "agentic"

        provider_id, model = self.tier_service.get_optimal_model(
            tier, estimated_tokens, requires_tools
        )

        if not provider_id or not model:
            logger.warning(f"No models available for tier: {tier.value}")
            return {
                "error": "No models available for this tier",
                "tier": tier.value
            }

        # Phase 68-06: Step 4 - Generate with escalation loop
        current_tier = tier
        max_escalations = 2
        escalated = False

        for attempt in range(max_escalations + 1):
            try:
                # Generate response
                response = await self.generate_response(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    model_type=model,  # Use specific model from tier service
                    task_type=task_type,
                    agent_id=agent_id,
                    image_payload=image_payload
                )

                # Phase 68-06: Step 5 - Check for escalation
                should_escalate, reason, target_tier = self.tier_service.handle_escalation(
                    current_tier, None, None, False, request_id
                )

                if not should_escalate:
                    # Success - return response with metadata
                    return {
                        "response": response,
                        "tier": current_tier.value,
                        "provider": provider_id,
                        "model": model,
                        "cost_cents": estimated_cost.get('cost_cents', 0),
                        "escalated": escalated,
                        "request_id": request_id
                    }

                # Escalate and retry
                logger.info(
                    f"Escalating request {request_id} from {current_tier.value} "
                    f"to {target_tier.value} (reason: {reason.value})"
                )
                current_tier = target_tier
                escalated = True

                # Get new model for escalated tier
                provider_id, model = self.tier_service.get_optimal_model(
                    current_tier, estimated_tokens, requires_tools
                )

                if not provider_id or not model:
                    logger.warning(f"No models available for escalated tier: {current_tier.value}")
                    # Return response from previous attempt
                    return {
                        "response": response,
                        "tier": tier.value,
                        "provider": provider_id,
                        "model": model,
                        "cost_cents": estimated_cost.get('cost_cents', 0),
                        "escalated": escalated,
                        "request_id": request_id
                    }

            except Exception as e:
                # Check for rate limit escalation
                is_rate_limited = "rate limit" in str(e).lower()

                should_escalate, reason, target_tier = self.tier_service.handle_escalation(
                    current_tier, None, str(e), is_rate_limited, request_id
                )

                if should_escalate and target_tier and attempt < max_escalations:
                    logger.warning(
                        f"Escalating request {request_id} due to error: {reason.value}"
                    )
                    current_tier = target_tier
                    escalated = True

                    # Get new model for escalated tier
                    provider_id, model = self.tier_service.get_optimal_model(
                        current_tier, estimated_tokens, requires_tools
                    )

                    if not provider_id or not model:
                        # No fallback available - return error
                        return {
                            "error": str(e),
                            "tier": current_tier.value,
                            "escalated": escalated
                        }

                    continue  # Retry with escalated tier

                # Max escalations reached or non-escalatable error
                logger.error(f"Generation failed after {attempt + 1} attempts: {e}")
                return {
                    "error": str(e),
                    "tier": current_tier.value,
                    "escalated": escalated
                }

        # Should not reach here, but return last response if loop completes
        return {
            "response": "Max escalation limit reached",
            "tier": current_tier.value,
            "escalated": escalated
        }

    async def generate_structured_response(
        self,
        prompt: str,
        system_instruction: str,
        response_model: Any,
        temperature: float = 0.2,
        task_type: Optional[str] = None,
        agent_id: Optional[str] = None,
        chain_id: Optional[str] = None, # NEW Phase 11
        image_payload: Optional[str] = None, # Phase 14: Vision Support
        cascade: bool = False,  # Phase 2 hallucination mitigation
    ) -> Any:
        """
        Generate a structured response using instructor with tenant-aware routing.
        Works with both BYOK and Managed AI.
        Supports multimodal inputs via `image_payload`.

        Phase 2 hallucination mitigation — ``cascade`` kwarg:

          When ``True`` AND the original call fails with a *schema-validation*
          error (pydantic ``ValidationError`` or ``json.JSONDecodeError``), the
          handler retries ONCE on the same-provider flagship model. The
          escalation target is resolved via
          ``hallucination_config.get_frontier_model_for_provider`` so the
          BYOK credential set, cost tracker, and rate limits stay constant
          (provider-family invariant is structural here). Transient failures
          (network, rate limit, auth) do NOT escalate — a bigger model won't
          fix them. Already-frontier models do NOT escalate (no double-spend).
          Default ``False`` = byte-identical to pre-Phase-2 behavior.

        Args:
            prompt: The user prompt
            system_instruction: System instruction for the LLM
            response_model: Pydantic model class for structured output
            temperature: Sampling temperature
            task_type: Optional task type hint
            agent_id: Optional agent ID for cost tracking
            image_payload: Optional Base64 image string or URL
            cascade: Opt in to single-retry frontier escalation on
                schema-validation failures (Phase 2 hallucination
                mitigation; default off).

        Returns:
            Instance of response_model or None if parsing fails
        """
        # Check trial/budget restrictions
        if self._is_trial_restricted():
            logger.warning(f"AI Blocked: Trial expired for workspace {self.workspace_id}")
            return None
            
        if not self.clients:
            logger.warning("No LLM clients available")
            return None
        
        try:
            # Check if instructor is available
            if not INSTRUCTOR_AVAILABLE:
                logger.warning("Instructor not available, falling back to raw response")
                return None
            
            # Get tenant plan and determine BYOK vs managed
            with get_db_session() as db:
                try:
                    tenant_plan = "free"
                    is_managed = True

                    workspace = db.query(Workspace).filter(Workspace.id == self.workspace_id).first()
                    if workspace and workspace.tenant_id:
                        tenant = db.query(Tenant).filter(Tenant.id == workspace.tenant_id).first()
                        if tenant:
                            plan_type = tenant.plan_type
                            tenant_plan = plan_type.value if hasattr(plan_type, 'value') else str(plan_type).lower()

                            # Check for custom BYOK keys
                            complexity = self.analyze_query_complexity(prompt, task_type)
                            temp_provider_id, _ = self.get_optimal_provider(complexity, task_type, True, tenant_plan, is_managed_service=True)

                            tenant_key = self.byok_manager.get_tenant_api_key(tenant.id, temp_provider_id)
                            if tenant_key:
                                is_managed = False
                            elif tenant_plan.lower() in [p.lower() for p in BYOK_ENABLED_PLANS]:
                                is_managed = False
                except Exception as e:
                    logger.warning(f"Failed to get tenant plan: {e}")
            
            # Block free tier managed AI
            if is_managed and tenant_plan.lower() == "free":
                logger.warning(f"Managed AI blocked for free tier workspace {self.workspace_id}")
                return None
            
            # Get optimal provider and model
            complexity = self.analyze_query_complexity(prompt, task_type)
            
            # Structured generation requires structured support (Phase 6.6)
            requires_tools = agent_id is not None or task_type == "agentic"
            
            # --- Phase 14: Vision Routing ---
            requires_vision = image_payload is not None
            # Get ranked options
            options = self.get_ranked_providers(
                complexity, task_type, True, tenant_plan, is_managed,
                requires_tools=True, requires_structured=True
            )

            # --- Phase 14.5: Coordinated Vision Logic ---
            if image_payload:
                primary_provider, primary_model = options[0] if options else (None, None)
                if primary_model and not self._model_supports_vision(primary_model):
                    logger.info(f"Coordinating vision (structured) for non-vision model: {primary_model}")
                    vision_desc = await self._get_coordinated_vision_description(
                        image_payload=image_payload,
                        tenant_plan=tenant_plan,
                        is_managed=is_managed
                    )
                    if vision_desc:
                        mapping_instr = (
                            "\n[COORDINATE MAPPING]:\n"
                            "The coordinates below are on a normalized 1000x1000 grid. "
                            "The browser viewport is 1280 pixels wide. "
                            "To click an element at [x, y], use browser_click_coords(x*1.28, y*H) where H is approximately 0.72*1.28.\n"
                        )
                        prompt = f"[VISUAL CONTEXT ANALYSIS]:\n{vision_desc}\n{mapping_instr}\n\n[USER REQUEST]:\n{prompt}"
                        image_payload = None 
            
            # Filter for Vision logic if needed - Use pricing cache lookup
            if requires_vision:
                vision_options = []
                for prov, mod in options:
                    if self._model_supports_vision(mod):
                        vision_options.append((prov, mod))
                
                if vision_options:
                    options = vision_options
                else:
                    logger.warning("No standard vision models found for structured output. Defaulting to GPT-4o.")
                    options = [("openai", "gpt-4o")] # Panic fallback

            if not options:
                return None

            # Phase 2 hallucination mitigation — cascade state.
            # Local only; never written to ``self`` (thread-safety).
            from core.hallucination_config import (
                get_frontier_model_for_provider,
                is_frontier_model,
            )

            try:
                from pydantic import ValidationError as _PydanticValidationError
            except ImportError:  # pragma: no cover - pydantic always present
                _PydanticValidationError = ()  # type: ignore[assignment]

            last_error = None
            last_was_schema_error = False
            cascade_attempted = False

            # Mutable list so we can insert the escalation target mid-loop
            # without re-iterating the original ranking.
            cascade_options: list = list(options)
            cascade_idx = 0

            while cascade_idx < len(cascade_options):
                provider_id, model = cascade_options[cascade_idx]
                cascade_idx += 1
                try:
                    # Get the client and wrap with instructor
                    client = self.clients[provider_id]
                    instructor_client = instructor.from_openai(client)
                    
                    # Truncate prompts to fit context window
                    context_window = self.get_context_window(model)
                    if len(prompt) > context_window * 3:  # ~3 chars per token estimate
                        # Pre-compress hook: drain durable facts before truncation
                        # drops them. Strictly additive (queue + worker), never
                        # blocks the user-visible response. Default ON.
                        try:
                            from core.turn_fact_queue import get_extraction_queue
                            get_extraction_queue().enqueue(
                                prompt=prompt,
                                workspace_id=self.workspace_id or "default",
                                model=model,
                            )
                            get_extraction_queue().ensure_worker()
                        except Exception as _qe:
                            logger.debug(f"turn_fact pre-compress enqueue skipped: {_qe}")

                        prompt = self.truncate_to_context(prompt, model, reserve_tokens=1500)
                        logger.info(f"Truncated prompt for model {model} (context: {context_window} tokens)")
                    
                    # Make the structured request
                    logger.info(f"Structured generation ({tenant_plan}, {'Managed' if is_managed else 'BYOK'}): {provider_id}/{model}")
                    
                    # Construct Messages (Phase 14: Multimodal)
                    messages = []
                    messages.append({"role": "system", "content": system_instruction})
                    
                    if image_payload:
                        # OpenAI / Compatible Vision Format
                        user_content = [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_payload if image_payload.startswith("http") else f"data:image/jpeg;base64,{image_payload}"
                                }
                            }
                        ]
                        messages.append({"role": "user", "content": user_content})
                        logger.info(f"Adding visual payload to STRUCTURED request for {model}")
                    else:
                        messages.append({"role": "user", "content": prompt})

                    result = instructor_client.chat.completions.create(
                        model=model,
                        response_model=response_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=1000
                    )
                    
                    # --- Record Usage (Phase 6.6) ---
                    try:
                        # Instructor attaches usage to the response object metadata
                        usage = getattr(result, "_raw_response", {}).usage if hasattr(result, "_raw_response") else None
                        if not usage and hasattr(result, "usage"):
                             usage = result.usage

                        if usage:
                            input_tokens = usage.prompt_tokens
                            output_tokens = usage.completion_tokens

                            fetcher = get_pricing_fetcher()
                            cost = fetcher.estimate_cost(model, input_tokens, output_tokens)

                            if cost and cost > 0:
                                llm_usage_tracker.record(
                                    workspace_id=self.workspace_id,
                                    provider=provider_id,
                                    model=model,
                                    input_tokens=input_tokens,
                                    output_tokens=output_tokens,
                                    cost_usd=cost,
                                    agent_id=agent_id,
                                    chain_id=chain_id, # Phase 11
                                    complexity=complexity.value,
                                    is_managed_service=is_managed
                                )
                    except Exception as cost_err:
                        logger.warning(f"Could not attribute structured LLM cost: {cost_err}")

                    # Learning-router outcome observation (structured success).
                    await self._record_outcome_feedback(
                        model=model, provider_id=provider_id, task_type=task_type,
                        content=str(result), finish_reason="stop",
                        success=True, cost=None, latency_ms=0.0,
                        schema_error=False,
                    )
                    return result
                except Exception as attempt_err:
                    logger.warning(f"Structured attempt failed for {provider_id}/{model}: {attempt_err}")
                    last_error = attempt_err
                    # Phase 2 cascade classification. Instructor wraps the
                    # underlying model output validation in pydantic; JSON
                    # decode failures come back as json.JSONDecodeError. Both
                    # are *schema* failures that a bigger model might fix.
                    # Everything else (network, rate limit, auth, context
                    # window) is transient and MUST NOT escalate.
                    is_schema_err = (
                        (
                            _PydanticValidationError
                            and isinstance(attempt_err, _PydanticValidationError)
                        )
                        or isinstance(attempt_err, json.JSONDecodeError)
                        or "validation" in str(attempt_err).lower()
                    )
                    last_was_schema_error = is_schema_err
                    # Learning-router outcome observation (structured failure).
                    # schema_error=True tells assess_response_quality this was a
                    # validation failure (not a transient provider error), so the
                    # predictor learns model X fails structured output for this task.
                    await self._record_outcome_feedback(
                        model=model, provider_id=provider_id, task_type=task_type,
                        content=None, finish_reason=None,
                        success=not is_schema_err, cost=None, latency_ms=0.0,
                        schema_error=is_schema_err,
                        exception=attempt_err if not is_schema_err else None,
                    )
                    # Fall through to the cascade check below (no continue).

                # ========================================================
                # Phase 2 hallucination mitigation: cascade escalation.
                # ========================================================
                # Fires only when:
                #   1. Caller opted in via ``cascade=True``.
                #   2. The just-failed attempt was a schema-validation
                #      error (transient errors don't benefit from a bigger
                #      model).
                #   3. We haven't already attempted an escalation (single
                #      retry per call).
                #   4. The just-failed model is not already frontier.
                #   5. The same provider has a known flagship to escalate
                #      to.
                #
                # ``insert`` at ``cascade_idx`` puts the frontier next in
                # the iteration order — it is tried BEFORE falling through
                # to other providers in the ranking. The provider-family
                # invariant is structural: the frontier is the flagship of
                # the CURRENT failing provider, so BYOK credentials, cost
                # tracking, and rate limits stay constant across the retry.
                if (
                    cascade
                    and last_was_schema_error
                    and not cascade_attempted
                    and not is_frontier_model(model)
                ):
                    frontier = get_frontier_model_for_provider(provider_id)
                    if frontier and frontier != model:
                        logger.info(
                            f"CASCADE ROUTING: escalating from {model} to {frontier} "
                            f"for provider {provider_id} workspace {self.workspace_id}"
                        )
                        cascade_attempted = True
                        cascade_options.insert(cascade_idx, (provider_id, frontier))

            logger.error(f"All structured providers failed. Last error: {last_error}")
            return None
            
        except Exception as e:
            logger.error(f"Structured generation failed: {e}")
            return None


    async def generate_transcription(
        self,
        file: Any,
        model: str = "whisper-1",
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        response_format: str = "json"
    ) -> Dict[str, Any]:
        """
        Transcribe audio to text using OpenAI Whisper.
        Uses BYOK keys for the 'openai' provider.
        """
        # Whisper is currently only supported via OpenAI provider in this architecture
        provider_id = "openai"
        client = self.async_clients.get(provider_id) or self.clients.get(provider_id)
        
        if not client:
            raise ValueError(f"OpenAI provider not configured for transcription. Please add an API key.")

        try:
            # Use the underlying openai client if it's patched by instructor
            # or use it directly if it's a standard client
            raw_client = getattr(client, "client", client)
            
            response = await raw_client.audio.transcriptions.create(
                model=model,
                file=file,
                language=language,
                prompt=prompt,
                response_format=response_format
            )
            
            # Format response (handle both standard and raw response types)
            text = response.text if hasattr(response, "text") else str(response)
            
            return {
                "text": text,
                "model": model,
                "provider": provider_id
            }
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            raise

    def get_available_providers(self) -> List[str]:

        """Get list of providers with valid API keys"""
        return list(self.clients.keys())

    def get_routing_info(self, prompt: str, task_type: Optional[str] = None) -> Dict[str, Any]:
        """Get routing decision info without making an API call (useful for UI)"""
        complexity = self.analyze_query_complexity(prompt, task_type)
        try:
            provider_id, model = self.get_optimal_provider(complexity, task_type)
            
            # Try to get dynamic pricing
            estimated_cost = None
            try:
                fetcher = get_pricing_fetcher()
                pricing = fetcher.get_model_price(model)
                if pricing:
                    # Estimate for ~500 token response
                    input_tokens = len(prompt) // 4
                    output_tokens = 500
                    estimated_cost = fetcher.estimate_cost(model, input_tokens, output_tokens)
            except Exception as e:
                logger.warning(f"Cost estimation failed for model {model}: {e}")
                estimated_cost = None
            
            return {
                "complexity": complexity.value,
                "selected_provider": provider_id,
                "selected_model": model,
                "available_providers": self.get_available_providers(),
                "cost_tier": "budget" if provider_id in PROVIDER_TIERS["budget"] else "mid" if provider_id in PROVIDER_TIERS["mid"] else "premium",
                "estimated_cost_usd": estimated_cost
            }
        except ValueError as e:
            return {
                "complexity": complexity.value,
                "error": str(e),
                "available_providers": []
            }

    async def refresh_pricing(self, force: bool = False) -> Dict[str, Any]:
        """Refresh dynamic pricing data from LiteLLM and OpenRouter"""
        try:
            pricing = await refresh_pricing_cache(force=force)
            return {"status": "success", "model_count": len(pricing)}
        except Exception as e:
            logger.error(f"Failed to refresh pricing: {e}")
            return {"status": "error", "message": str(e)}

    def get_provider_comparison(self) -> Dict[str, Any]:
        """Get cost comparison across all providers using dynamic pricing"""
        try:
            fetcher = get_pricing_fetcher()
            return fetcher.compare_providers()
        except Exception as e:
            logger.warning(f"Could not get provider comparison: {e}")
            # Return static fallback
            return {
                "openai": {"avg_cost_per_token": 0.00003, "tier": "premium"},
                "anthropic": {"avg_cost_per_token": 0.000025, "tier": "premium"},
                "deepseek": {"avg_cost_per_token": 0.000002, "tier": "budget"},
                "moonshot": {"avg_cost_per_token": 0.000003, "tier": "budget"},
            }

    def get_cheapest_models(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the cheapest models available"""
        try:
            fetcher = get_pricing_fetcher()
            return fetcher.get_cheapest_models(limit=limit)
        except Exception as e:
            logger.warning(f"Could not get cheapest models: {e}")
            return []
    async def _get_coordinated_vision_description(self, image_payload: str, tenant_plan: str, is_managed: bool) -> Optional[str]:
        """
        Calls a vision-only model to extract a semantic description of an image.
        This allows non-vision reasoning models to understand visual context.
        """
        # Pick a vision-only model (Janus)
        # For now, we'll try to use a specialized provider or default to a cheap vision model if Janus isn't configured
        # 1. Try Gemini Flash (Cheapest Vision)
        if "gemini" in self.clients:
            provider = "gemini"
            model = "gemini-2.0-flash-exp"  # Latest Gemini Flash model
        # 2. Try Deepseek / Janus
        elif "deepseek" in self.clients:
            provider = "deepseek"
            model = "janus-pro-7b"
        # 3. Last resort - GPT-4o-mini
        else:
            provider = "openai"
            model = "gpt-4o-mini"

        try:
            client = self.clients.get(provider)
            if not client: return None

            logger.info(f"Extracting visual description using {model}...")

            messages = [
                {
                    "role": "system",
                    "content": "You are a visual analysis specialist. Your goal is to describe a browser screenshot for an AI agent that cannot see it. "
                               "For every interactive element (buttons, links, inputs, icons, etc.), you MUST provide: "
                               "1. A name or label. "
                               "2. A brief description of its function. "
                               "3. Its precise coordinates as [x, y] center points on a normalized grid from 0 to 1000 "
                               "(where [0, 0] is top-left and [1000, 1000] is bottom-right). "
                               "Format elements as a clear list. Also describe the overall layout and active notifications."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this screenshot and provide a semantic list of interactive elements with [x, y] coordinates on a 1000x1000 grid."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_payload if image_payload.startswith("http") else f"data:image/jpeg;base64,{image_payload}"
                            }
                        }
                    ]
                }
            ]

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=500
            )

            desc = response.choices[0].message.content
            return desc
        except Exception as e:
            logger.error(f"Coordinated vision extraction failed: {e}")
            return None

    async def stream_completion(
        self,
        messages: List[Dict],
        model: str,
        provider_id: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        agent_id: Optional[str] = None,
        db = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream LLM responses token-by-token with optional governance tracking.

        Includes automatic provider fallback on failure for improved resilience.

        Args:
            messages: Chat messages in OpenAI format
            model: Model name
            provider_id: Provider identifier (e.g., "openai", "deepseek")
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            agent_id: Optional agent ID for governance tracking
            db: Optional database session for governance tracking

        Yields:
            Individual tokens as they arrive from the LLM
        """
        if not self.async_clients and not self.clients:
            raise ValueError("No clients initialized. Streaming unavailable.")

        # Get provider fallback order
        provider_order = self._get_provider_fallback_order(provider_id)

        if not provider_order:
            raise ValueError(f"No available providers for streaming. Requested: {provider_id}")

        # Governance tracking
        governance_enabled = os.getenv("STREAMING_GOVERNANCE_ENABLED", "true").lower() == "true"
        agent_execution = None

        last_error = None

        # Try each provider in fallback order
        for attempt_provider_id in provider_order:
            # Get client for this provider (prefer async, fallback to sync)
            client = self.async_clients.get(attempt_provider_id)
            if not client:
                client = self.clients.get(attempt_provider_id)

            if not client:
                logger.warning(f"No client available for provider: {attempt_provider_id}")
                continue

            logger.info(f"Attempting stream with provider: {attempt_provider_id} (requested: {provider_id})")

            try:
                import time
                request_start = time.time()
                # Create execution record if agent_id provided (only on first attempt)
                if agent_execution is None and agent_id and governance_enabled and db:
                    agent_execution = AgentExecution(
                        agent_id=agent_id,
                        workspace_id=self.workspace_id,
                        status="running",
                        input_summary=f"LLM stream: {model} ({attempt_provider_id})",
                        triggered_by="llm_stream"
                    )
                    db.add(agent_execution)
                    db.commit()
                    db.refresh(agent_execution)

                    logger.debug(f"Created agent execution {agent_execution.id} for LLM stream")

                # Use async streaming API
                stream = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True
                )

                token_count = 0
                async for chunk in stream:
                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, 'content') and delta.content:
                            token_count += 1
                            yield delta.content

                # Record successful completion
                if agent_execution and governance_enabled and db:
                    try:
                        agent_execution.status = "completed"
                        agent_execution.output_summary = f"Generated {token_count} tokens via {model} ({attempt_provider_id})"
                        agent_execution.completed_at = datetime.now()
                        db.commit()

                        # Record outcome for confidence scoring
                        from core.agent_governance_service import AgentGovernanceService
                        governance = AgentGovernanceService(db)
                        await governance.record_outcome(agent_id, success=True)

                        logger.info(f"Completed LLM stream execution {agent_execution.id} via {attempt_provider_id}")
                    except Exception as tracking_error:
                        logger.error(f"Failed to track LLM stream completion: {tracking_error}")

                # Phase 226.4-04: Record successful streaming API call for health monitoring
                latency_ms = (time.time() - request_start) * 1000
                self.health_monitor.record_call(attempt_provider_id, success=True, latency_ms=latency_ms)

                # Learning-router outcome observation (streaming success).
                await self._record_outcome_feedback(
                    model=model, provider_id=attempt_provider_id, task_type=None,
                    content="(streamed)", finish_reason="stop",
                    success=True, cost=None, latency_ms=latency_ms,
                )

                # Success! Return from the function
                return

            except Exception as e:
                last_error = e
                logger.warning(f"Streaming failed for {attempt_provider_id}/{model}: {e}")

                # Phase 226.4-04: Record failed streaming API call for health monitoring
                try:
                    latency_ms = (time.time() - request_start) * 1000
                    self.health_monitor.record_call(attempt_provider_id, success=False, latency_ms=latency_ms)
                except:
                    pass  # Don't let health monitoring errors affect primary flow

                # Learning-router outcome observation (streaming failure).
                await self._record_outcome_feedback(
                    model=model, provider_id=attempt_provider_id, task_type=None,
                    content=None, finish_reason=None,
                    success=False, cost=None, latency_ms=0.0,
                    exception=e,
                )

                # If this is not the last provider, try the next one
                if attempt_provider_id != provider_order[-1]:
                    logger.info(f"Falling back to next provider...")
                    continue

                # This was the last provider, fall through to error handling
                break

        # All providers failed - mark execution as failed and yield error
        logger.error(f"All {len(provider_order)} providers failed for {model}. Last error: {last_error}")

        if agent_execution and governance_enabled and db:
            try:
                agent_execution.status = "failed"
                agent_execution.error_message = f"All providers failed. Last: {str(last_error)}"
                agent_execution.completed_at = datetime.now()
                db.commit()

                # Record failure for confidence scoring
                from core.agent_governance_service import AgentGovernanceService
                governance = AgentGovernanceService(db)
                await governance.record_outcome(agent_id, success=False)

            except Exception as tracking_error:
                logger.error(f"Failed to track LLM stream failure: {tracking_error}")

        # Yield final error message
        yield f"\n\n[Error: All LLM providers failed. Last error: {str(last_error)}]"

    async def generate_embedding(
        self,
        text: str,
        model: str,
        provider: str = "openai"
    ) -> List[float]:
        """
        Generate embedding vector for a single text string using managed clients.
        
        Args:
            text: Text to embed
            model: Model identifier
            provider: Provider identifier ("openai" or "cohere")
            
        Returns:
            List of floats representing the embedding vector
        """
        client = self.async_clients.get(provider) or self.clients.get(provider)
        if not client:
            raise ValueError(f"No client available for provider: {provider}")

        logger.info(f"Attempting embedding with provider: {provider} (model: {model})")
        
        try:
            if provider == "openai":
                response = await client.embeddings.create(model=model, input=text)
                return response.data[0].embedding
            elif provider == "cohere":
                # Cohere async client uses .embed()
                response = await client.embed(texts=[text], model=model, input_type="search_document")
                return response.embeddings[0]
            else:
                raise ValueError(f"Provider {provider} does not support embeddings via BYOKHandler yet.")
        except Exception as e:
            logger.error(f"Embedding generation failed for {provider}: {e}")
            raise

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        model: str,
        provider: str = "openai"
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch using managed clients.
        """
        client = self.async_clients.get(provider) or self.clients.get(provider)
        if not client:
            raise ValueError(f"No client available for provider: {provider}")

        logger.info(f"Attempting batch embedding with provider: {provider} (model: {model}, count: {len(texts)})")
        
        try:
            if provider == "openai":
                response = await client.embeddings.create(model=model, input=texts)
                return [item.embedding for item in response.data]
            elif provider == "cohere":
                response = await client.embed(texts=texts, model=model, input_type="search_document")
                return [emb for emb in response.embeddings]
            else:
                raise ValueError(f"Provider {provider} does not support batch embeddings via BYOKHandler yet.")
        except Exception as e:
            logger.error(f"Batch embedding generation failed for {provider}: {e}")
            raise

    def classify_cognitive_tier(self, prompt: str, task_type: Optional[str] = None) -> CognitiveTier:
        """
        Classify a query into a cognitive tier using the 5-tier system.

        Phase 68: Wrapper method for CognitiveClassifier to enable easy cognitive
        tier classification from BYOKHandler instances.

        Args:
            prompt: The query text to classify
            task_type: Optional task type hint (code, chat, analysis, etc.)

        Returns:
            CognitiveTier classification for the query

        Example:
            >>> handler = BYOKHandler()
            >>> tier = handler.classify_cognitive_tier("explain quantum computing")
            >>> print(tier.value)  # 'standard' or 'versatile'
        """
        return self.cognitive_classifier.classify(prompt, task_type)

    def _is_trial_restricted(self) -> bool:
        """
        Check if the workspace has trial restrictions.
        Returns False for now (can be enhanced later).
        """
        try:
            with get_db_session() as db:
                workspace = db.query(Workspace).filter(Workspace.id == self.workspace_id).first()
                if workspace and hasattr(workspace, 'trial_ended') and workspace.trial_ended:
                    return True
                return False
        except Exception as e:
            logger.debug(f"Could not check trial restriction: {e}")
            return False
