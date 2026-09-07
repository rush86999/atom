import asyncio
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
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
from core.benchmarks import get_quality_score, get_capability_score, MODEL_QUALITY_SCORES
import core.byok_endpoints
def get_byok_manager(*args, **kwargs):
    return core.byok_endpoints.get_byok_manager(*args, **kwargs)

from core.cost_config import (
    BYOK_ENABLED_PLANS,
    MODEL_TIER_RESTRICTIONS,
    get_llm_cost)
from core.llm.provider_rate_limits import get_provider_rate_tracker
import core.database
def get_db_session(*args, **kwargs):
    return core.database.get_db_session(*args, **kwargs)
from core.dynamic_pricing_fetcher import (
    get_pricing_fetcher,
    get_pricing_fetcher_initialized,
    get_pricing_fetcher_initialized_sync,
    refresh_pricing_cache,
    DynamicPricingFetcher)
from core.llm_call_tracker import get_llm_call_tracker


# Dedicated daemon loop for __init__-time credential resolution. FastAPI async
# routes construct BYOKHandler synchronously while their thread's event loop is
# RUNNING — loop.run_until_complete() then raises "This event loop is already
# running" and ABANDONS the coroutine (RuntimeWarning: never awaited), so the
# credential service never resolved OAuth/subscription credentials on the
# gateway surface (only BYOK/env fallbacks ever fired).
_CREDENTIAL_LOOP: Optional["asyncio.AbstractEventLoop"] = None
_CREDENTIAL_LOOP_LOCK = threading.Lock()

# Reasoning models reject the ``logprobs`` kwarg outright ("logprobs are not
# supported with reasoning models"), so a soft-SC request to one ALWAYS fails
# and then pays the retry. Cache that verdict per provider/model after the
# first rejection so later calls skip the doomed attempt entirely — in a
# ranking cascade over several models this removes one failed network
# round-trip per structured call.
_LOGPROBS_UNSUPPORTED: set = set()


def _run_coroutine_sync(coro, timeout: float = 15.0):
    """Run ``coro`` synchronously from sync code — safe with or without a
    running event loop on the calling thread."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop on this thread: drive the coroutine on a fresh
        # loop — asyncio.get_event_loop() no longer creates one implicitly
        # on Python 3.14+, so that call raised RuntimeError here.
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    # A loop IS running here — schedule on the dedicated background loop.
    global _CREDENTIAL_LOOP
    with _CREDENTIAL_LOOP_LOCK:
        if _CREDENTIAL_LOOP is None:
            _CREDENTIAL_LOOP = asyncio.new_event_loop()
            _loop_thread = threading.Thread(
                target=_CREDENTIAL_LOOP.run_forever,
                daemon=True,
                name="byok-credential-loop",
            )
            _loop_thread.start()
    future = asyncio.run_coroutine_threadsafe(coro, _CREDENTIAL_LOOP)
    return future.result(timeout=timeout)


class AwaitableResult:
    """A wrapper that allows a synchronous result to be awaited, iterated, indexed, and sized.

    Enables dual-mode sync/async APIs.
    """
    def __init__(self, value):
        self.value = value

    def __await__(self):
        async def _async_val():
            return self.value
        return _async_val().__await__()

    def __iter__(self):
        return iter(self.value)

    def __len__(self):
        return len(self.value)

    def __getitem__(self, index):
        return self.value[index]

    def __eq__(self, other):
        val = other.value if isinstance(other, AwaitableResult) else other
        return self.value == val

    def __repr__(self):
        return repr(self.value)

    def __add__(self, other):
        val = other.value if isinstance(other, AwaitableResult) else other
        return self.value + val

    def __radd__(self, other):
        return other + self.value

    def __sub__(self, other):
        val = other.value if isinstance(other, AwaitableResult) else other
        return self.value - val

    def __rsub__(self, other):
        return other - self.value

    def __mul__(self, other):
        val = other.value if isinstance(other, AwaitableResult) else other
        return self.value * val

    def __rmul__(self, other):
        return other * self.value

    def __truediv__(self, other):
        val = other.value if isinstance(other, AwaitableResult) else other
        return self.value / val

    def __rtruediv__(self, other):
        return other / self.value

    def __lt__(self, other):
        val = other.value if isinstance(other, AwaitableResult) else other
        return self.value < val

    def __le__(self, other):
        val = other.value if isinstance(other, AwaitableResult) else other
        return self.value <= val

    def __gt__(self, other):
        val = other.value if isinstance(other, AwaitableResult) else other
        return self.value > val

    def __ge__(self, other):
        val = other.value if isinstance(other, AwaitableResult) else other
        return self.value >= val

    def __float__(self):
        return float(self.value)

    def __int__(self):
        return int(self.value)
from core.llm.cache_aware_router import CacheAwareRouter
from core.llm.cognitive_tier_service import CognitiveTierService
import core.llm.cognitive_tier_system
from core.llm.cognitive_tier_system import CognitiveTier
class CognitiveClassifier:
    def __new__(cls, *args, **kwargs):
        return core.llm.cognitive_tier_system.CognitiveClassifier(*args, **kwargs)
from core.llm_usage_tracker import llm_usage_tracker
from core.lux_config import lux_config
from core.models import GovernanceDocument, AgentExecution, Tenant, Workspace, ModelCatalog
from core.llm_credential_service import LLMCredentialService

logger = logging.getLogger(__name__)


def _stop_iteration_safe(fn, *args, **kwargs):
    """Worker-thread shim for _to_thread_safe — the StopIteration must be
    converted INSIDE the worker: once it lands on the executor's concurrent
    future, asyncio's chaining callback dies and the awaiter hangs (py<=3.12)."""
    try:
        return fn(*args, **kwargs)
    except StopIteration as e:
        raise RuntimeError(
            f"{getattr(fn, '__qualname__', fn)} raised StopIteration "
            f"(exhausted iterator?) — converted to keep the awaiting coroutine alive"
        ) from e


async def _to_thread_safe(fn, *args, **kwargs):
    """await fn(*args, **kwargs) in the default executor — asyncio.to_thread,
    but an escaped StopIteration becomes a normal RuntimeError.

    StopIteration set on the executor's concurrent future is fatal on Python
    <=3.12: asyncio's future-chaining callback calls
    set_exception(StopIteration), which is forbidden, so the callback dies and
    the awaiting coroutine NEVER resumes — the caller hangs forever
    (2026-09-05 CI: backend-tests timed out at 6h after a MagicMock
    side_effect list ran out inside the worker thread. A first fix converted
    around the await, which local Python 3.14 converts internally and so
    passed vacuously — CI's 3.11 hung and the new 300s seatbelt caught it)."""
    return await asyncio.to_thread(_stop_iteration_safe, fn, *args, **kwargs)

# --- P4 prompt-taint gate (shadow by default) -------------------------------
# The prompt IS the exfil payload on the LLM path: the full text leaves for a
# third-party processor. When the head of the outbound prompt classifies as
# restricted-sensitivity (PII/credential patterns), shadow mode logs a
# structured warning; ATOM_LLM_TAINT_ENFORCE additionally blocks the dispatch.
# Ordinary confidential business text is never flagged.
_LLM_TAINT_SHADOW = os.getenv("ATOM_LLM_TAINT_SHADOW", "true").lower() == "true"
_LLM_TAINT_ENFORCE = os.getenv("ATOM_LLM_TAINT_ENFORCE", "false").lower() == "true"

# Bounded per-request timeout for provider clients (seconds). The OpenAI SDK
# defaults to 600s; with multi-provider fallback + self-heal retries a wedged
# provider (dead key, hanging endpoint) could hold a request — and the
# threadpool/event loop — for many minutes (reproduced in E2E boot verify:
# POST /api/v1/ai/nlu froze the whole server). httpx applies this as a
# per-read timeout, so legitimately long streaming responses are unaffected.
LLM_REQUEST_TIMEOUT_DEFAULT_SECONDS = 120


def _last_user_text(messages: List[Dict]) -> str:
    """Extract the most recent user message's text for the taint gate."""
    for _m in reversed(messages or []):
        if isinstance(_m, dict) and _m.get("role") == "user":
            content = _m.get("content", "")
            if isinstance(content, list):
                # Multimodal form: keep only text parts.
                content = " ".join(
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                )
            return content if isinstance(content, str) else str(content)
    return ""


def _llm_request_timeout() -> float:
    """Resolve the provider request timeout from ``ATOM_LLM_REQUEST_TIMEOUT``."""
    raw = os.getenv("ATOM_LLM_REQUEST_TIMEOUT")
    if raw:
        try:
            return float(raw)
        except ValueError:
            logger.warning(
                "Invalid ATOM_LLM_REQUEST_TIMEOUT=%r, using default %s",
                raw,
                LLM_REQUEST_TIMEOUT_DEFAULT_SECONDS,
            )
    return LLM_REQUEST_TIMEOUT_DEFAULT_SECONDS


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


class GatewayBlockedError(Exception):
    """Raised by the LLM gateway when a request is blocked by a hard guard
    (trial expired or budget exceeded). Maps to an HTTP 429 on the gateway
    surface. The ``reason`` is exposed to clients (it is safe, non-sensitive);
    internal detail stays in logs.
    """

    def __init__(self, reason: str, message: str = "Request blocked"):
        super().__init__(message)
        self.reason = reason
        self.message = message


class AllProvidersFailedError(Exception):
    """Raised when every provider in the fallback chain failed for a
    non-streaming gateway completion. The message is logged server-side only
    and never leaked to the client (the gateway maps this to a generic 502)."""


class _EmptyCompletionError(RuntimeError):
    """A provider answered HTTP-200 with NO visible content.

    Reasoning models that exhaust their completion budget on hidden thinking
    return ``finish_reason='length'`` with ``content=None`` (observed live
    2026-09-01: a chat turn stalled ~2 minutes across retries and delivered
    an empty answer). Treated as a failed attempt so the next ranked
    provider serves the turn — never a silent None success."""


def _visible_content_missing(result: Any) -> bool:
    """True when a completion returned nothing the caller can use.

    ``None`` (reasoning consumed the whole budget before any answer) and
    whitespace-only strings are both dead payloads — every completion site
    in ``generate_response`` routes these into the failed-attempt path
    instead of recording a healthy success and handing None upward."""
    return result is None or (isinstance(result, str) and not result.strip())


# Completion cap for plain (non-streaming) completions — same rationale as
# the structured path's ATOM_STRUCTURED_MAX_TOKENS: reasoning models burn
# 750–3,155+ tokens thinking BEFORE the visible answer (measured on
# minimax-m3, 2026-08-31), and without an explicit cap the provider default
# starves the answer at finish_reason='length' with content=None. The cap is
# a ceiling, not a target — short answers are unaffected.
_DEFAULT_COMPLETION_MAX_TOKENS = int(os.getenv("ATOM_COMPLETION_MAX_TOKENS", "6000"))


# Provider tier mapping for cost optimization
PROVIDER_TIERS = {
    # Budget tier - cheapest, good for simple tasks
    "budget": ["deepseek", "moonshot", "glm", "ollama", "opencode-go"],
    # Mid tier - balanced cost/quality
    "mid": ["anthropic", "gemini", "mistral"],
    # Premium tier - best quality, higher cost
    "premium": ["openai", "anthropic", "glm"],
    # Specialized - task-specific
    "code": ["deepseek", "openai", "opencode-go"],
    "math": ["deepseek", "openai"],
    "creative": ["anthropic", "openai"],
}

# Model recommendations per provider (2026 Frontier Refresh)
COST_EFFICIENT_MODELS = {
    "openai": {
        QueryComplexity.SIMPLE: "o4-mini",
        QueryComplexity.MODERATE: "o4-mini",
        QueryComplexity.COMPLEX: "o3-mini",
        QueryComplexity.ADVANCED: "gpt-5.6-sol",
    },
    "anthropic": {
        QueryComplexity.SIMPLE: "claude-3-haiku-20240307",
        QueryComplexity.MODERATE: "claude-3-haiku-20240307",
        QueryComplexity.COMPLEX: "claude-3-5-sonnet",
        QueryComplexity.ADVANCED: "claude-mythos-5",
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
    "moonshot": {  # Moonshot AI (Kimi family)
        QueryComplexity.SIMPLE: "moonshot/kimi-k2-thinking",
        QueryComplexity.MODERATE: "moonshot/kimi-k2-thinking",
        QueryComplexity.COMPLEX: "kimi-k3",
        QueryComplexity.ADVANCED: "kimi-k3",
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
        # One local model, actually pulled (`ollama list` is the source of
        # truth — routing to catalog names that aren't pulled 404s every
        # request). llama3.1 (not llama3): the structured-generation path
        # uses tools, which plain llama3 does not support in Ollama.
        QueryComplexity.SIMPLE: "llama3.1:8b",
        QueryComplexity.MODERATE: "llama3.1:8b",
        QueryComplexity.COMPLEX: "llama3.1:8b",
        QueryComplexity.ADVANCED: "llama3.1:8b",
    },
    "glm": {  # Zhipu AI GLM family — OpenAI-compatible API
        QueryComplexity.SIMPLE: "glm-4.5",
        QueryComplexity.MODERATE: "glm-4.6",
        QueryComplexity.COMPLEX: "glm-5",
        QueryComplexity.ADVANCED: "glm-5.2",  # Latest flagship (June 2026) — 1M ctx, reasoning
    },
    "mistral": {
        QueryComplexity.SIMPLE: "mistral-small",
        QueryComplexity.MODERATE: "mistral-medium",
        QueryComplexity.COMPLEX: "mistral-large-latest",
        QueryComplexity.ADVANCED: "mistral-large-latest",
    },
    "groq": {  # Ultra-fast inference (Llama models)
        QueryComplexity.SIMPLE: "llama-3.1-8b-instant",
        QueryComplexity.MODERATE: "llama-3.1-8b-instant",
        QueryComplexity.COMPLEX: "llama-3.3-70b-versatile",
        QueryComplexity.ADVANCED: "llama-3.3-70b-versatile",
    },
    "openrouter": {  # OpenRouter — gateway to 300+ models via one key
        # Chinese models throughout (OpenRouter catalog, Aug 2026, all
        # tool-capable): minimax-m3 for routine turns ($0.30/$1.20 per M —
        # recall-capable and ~7x cheaper than claude-sonnet-5), DeepSeek V4
        # Pro for heavy turns ($0.51/$1.02 — Sonnet-5 class at 4-10x less).
        # BPC value ranking overrides this map per-call when the pricing
        # cache has openrouter entries; this is the fallback.
        QueryComplexity.SIMPLE: "minimax/minimax-m3",
        QueryComplexity.MODERATE: "minimax/minimax-m3",
        QueryComplexity.COMPLEX: "deepseek/deepseek-v4-pro",
        QueryComplexity.ADVANCED: "deepseek/deepseek-v4-pro",
    },
    "opencode-go": {  # OpenCode Go — low-cost subscription via OpenCode Zen gateway
        # https://opencode.ai/zen — tested+verified open coding models served
        # by the OpenCode team; one subscription key, no per-provider signups.
        QueryComplexity.SIMPLE: "deepseek-v4-flash",
        QueryComplexity.MODERATE: "deepseek-v4-flash",
        QueryComplexity.COMPLEX: "deepseek-v4-pro",
        QueryComplexity.ADVANCED: "kimi-k2.7-code",
    },
}


# Models that do not support tool calling or agentic runtimes (Phase 6.6)
# DEPRECATED: Use pricing_fetcher._model_supports_tools() instead
# This list is kept for reference/backwards compatibility only
# The pricing cache dynamically infers tool support from model metadata
MODELS_WITHOUT_TOOLS = {
    "deepseek-v3.2-speciale",
}

# OpenCode Go free-usage vs subscription-paid split.
# Per the official Zen docs (opencode.ai/docs/zen): free models carry a
# "-free" suffix in their gateway ID (deepseek-v4-flash-free, mimo-v2.5-free,
# laguna-s-2.1-free, ling-3.0-tiny-free, longcat-2.0-free, north-mini-code-free,
# nemotron-3-ultra-free, big-pickle) and are "available for a limited time".
# Their free allowance can be exhausted — the gateway then returns
# CreditsError / "Insufficient balance" even with an ACTIVE subscription,
# while the paid models would complete fine. When a free-usage attempt fails
# with an insufficient-balance error, the same request is retried on a paid
# model before falling back to other providers. Override via env:
#   OPENCODE_FREE_PAID_FALLBACK='{"deepseek-v4-flash-free": "deepseek-v4-flash"}'
OPCODE_FREE_MODEL_SUFFIX = "-free"

# Documented paid-sibling fallbacks (model ID as listed on opencode.ai/zen).
# Any free model WITHOUT an explicit entry falls back to the cheapest PAID
# model (deepseek-v4-flash, $0.14/$0.28 per 1M tokens).
OPCODE_FREE_MODEL_PAID_FALLBACK_DEFAULTS = {
    "deepseek-v4-flash-free": "deepseek-v4-flash",
    "mimo-v2.5-free": "minimax-m2.7",
}


def _is_opencode_free_model(model: str) -> bool:
    """True for OpenCode Zen free-usage models (documented "-free" suffix)."""
    return model.endswith(OPCODE_FREE_MODEL_SUFFIX)


def _opencode_free_paid_fallback() -> dict:
    raw = os.getenv("OPENCODE_FREE_PAID_FALLBACK", "").strip()
    if raw:
        try:
            overrides = json.loads(raw)
            if isinstance(overrides, dict):
                return {k: v for k, v in overrides.items() if isinstance(v, str)}
            logger.warning("OPENCODE_FREE_PAID_FALLBACK must be a JSON object — ignoring")
        except (ValueError, TypeError):
            logger.warning("OPENCODE_FREE_PAID_FALLBACK is not valid JSON — ignoring")
    return dict(OPCODE_FREE_MODEL_PAID_FALLBACK_DEFAULTS)


def _opencode_paid_fallback_model(model: str) -> Optional[str]:
    """Map a free-usage model to the subscription-paid model to retry with."""
    if not _is_opencode_free_model(model):
        return None
    fallbacks = _opencode_free_paid_fallback()
    paid = fallbacks.get(model)
    if paid:
        return paid
    return "deepseek-v4-flash"  # cheapest paid model


# Free-usage models to retry with when the PAID tier is out of credits.
# The subscription balance can be exhausted (CreditsError on every paid
# model) while the "-free" allowance still works — verified live against
# the Zen gateway: nemotron-3.5-lightning-free, laguna-s-2.1-free and
# nemotron-3-ultra-free all complete with a zero-balance workspace.
# Override via env: OPENCODE_FREE_TIER_MODELS='["model-a-free", ...]'
OPCODE_FREE_TIER_FALLBACK_DEFAULTS = [
    "nemotron-3.5-lightning-free",
    "laguna-s-2.1-free",
    "nemotron-3-ultra-free",
]


def _opencode_free_tier_fallbacks(model: str) -> list:
    """Ordered fallback chain for an opencode model that hit a budget error.

    Free model → its paid sibling first, then the verified free tier.
    Paid model → straight to the free tier (the paid balance is gone).
    """
    raw = os.getenv("OPENCODE_FREE_TIER_MODELS", "").strip()
    chain: list = []
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                chain = [m for m in parsed if isinstance(m, str)]
            else:
                logger.warning("OPENCODE_FREE_TIER_MODELS must be a JSON list — ignoring")
        except (ValueError, TypeError):
            logger.warning("OPENCODE_FREE_TIER_MODELS is not valid JSON — ignoring")
    if not chain:
        chain = list(OPCODE_FREE_TIER_FALLBACK_DEFAULTS)
    chain = [m for m in chain if m != model]
    if _is_opencode_free_model(model):
        paid = _opencode_paid_fallback_model(model)
        if paid and paid != model:
            chain.insert(0, paid)
    return chain


# --- OpenRouter: budget-exhausted → free-model fallback (round 80w2) ---
# OpenRouter serves many models with a ":free" variant that has no per-token
# cost but lower rate limits. When the user's credits are exhausted on a
# paid model, retry on the :free sibling before skipping the provider.
OPENROUTER_PAID_FREE_FALLBACK_DEFAULTS = {
    "openai/gpt-4o-mini": "google/gemma-2-9b-it:free",
    "anthropic/claude-3.5-sonnet": "meta-llama/llama-3.1-8b-instruct:free",
    "anthropic/claude-3-sonnet": "meta-llama/llama-3.1-8b-instruct:free",
    "openai/gpt-4o": "google/gemma-2-9b-it:free",
    "google/gemini-flash-1.5": "google/gemma-2-9b-it:free",
}

_openrouter_free_fallback_cache: dict | None = None


def _openrouter_free_fallback() -> dict:
    """Read OPENROUTER_FREE_FALLBACK env override or return defaults."""
    global _openrouter_free_fallback_cache
    if _openrouter_free_fallback_cache is not None:
        return _openrouter_free_fallback_cache
    raw = os.getenv("OPENROUTER_FREE_FALLBACK", "").strip()
    if raw:
        try:
            overrides = json.loads(raw)
            if isinstance(overrides, dict):
                result = {k: v for k, v in overrides.items() if isinstance(v, str)}
                _openrouter_free_fallback_cache = result
                return result
            logger.warning("OPENROUTER_FREE_FALLBACK must be a JSON object — ignoring")
        except (ValueError, TypeError):
            logger.warning("OPENROUTER_FREE_FALLBACK is not valid JSON — ignoring")
    _openrouter_free_fallback_cache = dict(OPENROUTER_PAID_FREE_FALLBACK_DEFAULTS)
    return _openrouter_free_fallback_cache


def _openrouter_free_fallback_model(model: str) -> Optional[str]:
    """Map an OpenRouter paid model to its :free fallback variant.

    Returns None if the model already ends with ":free" (nothing to fall
    back to) or no mapping exists and no default free model is available.
    """
    if model.endswith(":free"):
        return None
    fallbacks = _openrouter_free_fallback()
    free = fallbacks.get(model)
    if free:
        return free
    # Default: use a known-good free model
    return "google/gemma-2-9b-it:free"


def _is_insufficient_balance_error(err: Exception) -> bool:
    """True when an LLM error means the gateway's free/credit allowance is gone.

    Matches the OpenCode Go gateway CreditsError body:
    ``{'type': 'CreditsError', 'message': 'Insufficient balance. ...'}`` — but
    stays loose so any provider reporting credit exhaustion triggers the paid
    retry path.
    """
    text = str(err).lower()
    return (
        "insufficient balance" in text
        or "creditserror" in text
        or "credit limit" in text
        or "insufficient credit" in text
        or "payment required" in text
        or ("billing" in text and "401" in text)
    )


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


def _get_drift_detector():
    """R82 module hook: lazy drift-detector accessor (monkeypatchable in tests)."""
    from core.llm.model_provenance import get_drift_detector

    return get_drift_detector()


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

        # OpenCode Go / gateway rate-awareness: custom per-provider RPM/TPM/
        # context limits feeding routing decisions (headroom penalty + clamp).
        self.rate_tracker = get_provider_rate_tracker()

        # Last concrete (model, provider) selected by BPC and actually called.
        # generate_response returns only the text, so callers (LLMService.
        # generate_completion) read these to surface the real model in the
        # response and key feedback correctly (instead of the "auto" input).
        self._last_used_model: Optional[str] = None
        self._last_used_provider: Optional[str] = None
        # Chain-of-thought from the last completed call (delta.reasoning /
        # reasoning_content / thinking fields, provider-dependent). Like the
        # model/provider stash above: generate_response returns only text, so
        # callers read this to persist + display WHAT the model was thinking
        # (reasoning drawers, feedback training). Cleared per call.
        self._last_reasoning: Optional[str] = None
        # routing_result_id stashed by _rerank_with_learning when it computed
        # per-decision prompt features, so the outcome hook can recover them
        # (train/serve consistency). None when re-ranking didn't fire.
        self._pending_routing_result_id: Optional[str] = None

        # Thread safety for lazy embedding init
        self._embedding_initialized = False
        self._embedding_init_lock = threading.Lock()

    def _provider_serves_model(self, provider_id: str, model: str) -> bool:
        """Heuristic: does this provider's client serve this model?

        Cross-provider streaming fallback previously reused the same model name
        on every provider (e.g. asking Anthropic to serve 'gpt-4o'), which 404s
        on most fallbacks (Bug 14). We can't know the provider's full catalog
        without an API call, so use the model-name prefix as the signal — the
        same heuristic BPC uses (provider id appears in the model id). Local
        providers (ollama/vllm/lmstudio) serve arbitrary model names, so they
        always match.
        """
        if not model:
            return True
        model_l = model.lower()
        # Local/open providers serve whatever model name is configured.
        if provider_id in {"ollama", "vllm", "lmstudio", "local"} or provider_id.startswith("local_"):
            return True
        # Gateways (opencode-go/zen, openrouter) serve model families from
        # many vendors under bare gateway IDs (e.g. 'deepseek-v4-flash'),
        # so family-prefix matching can't apply — the gateway client is
        # authoritative for any model routed to it.
        if provider_id in {"opencode-go", "opencode", "zen", "openrouter"}:
            return True
        # Provider id is a substring of the model id (e.g. 'openai' in
        # 'gpt-4o'? no — but 'deepseek' in 'deepseek-chat', 'gemini' in
        # 'gemini-2.5-flash', 'qwen' in 'qwen-plus'). Also handle the common
        # family prefixes.
        family_for_provider = {
            "openai": ("gpt", "o1", "o3", "o4", "chatgpt"),
            "anthropic": ("claude",),
            "deepseek": ("deepseek",),
            "gemini": ("gemini",),
            "qwen": ("qwen",),
            "moonshot": ("kimi", "moonshot"),
            "minimax": ("minimax",),
            "glm": ("glm", "chatglm"),
        }
        prefixes = family_for_provider.get(provider_id)
        if prefixes:
            return any(model_l.startswith(p) for p in prefixes)
        return provider_id in model_l

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
        available_providers = list(self.clients.keys())

        # Same availability rule as ranking: a local runtime that isn't
        # answering stays out of the fallback chain — mid-request fallback
        # to a dead ollama just adds its connection timeout to the failure.
        if "ollama" in available_providers and self._ollama_runtime_state()[0] != "up":
            available_providers = [p for p in available_providers if p != "ollama"]

        if not available_providers:
            return []

        # Fallback priority order (most reliable first)
        priority_order = ["deepseek", "openai", "opencode-go", "moonshot", "minimax", "xiaomi", "deepinfra", "ollama"]

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

    def _load_capability_index(self) -> Optional[Dict[str, list]]:
        """Bulk-load {model_id -> capabilities} from ModelCatalog in ONE query.

        The BPC ranking loop iterates the full pricing cache (hundreds of
        models) and previously called _filter_by_capabilities per model, each
        opening its own DB session — hundreds of round-trips per request plus
        connection-pool pressure whenever a capability filter was active. This
        fetches them all at once; returns None on failure (callers fall back to
        the per-model path, which still passes unknown/error models through).
        """
        try:
            with get_db_session() as db:
                rows = db.query(ModelCatalog).all()
            return {row.model_id: (row.capabilities or ["chat"]) for row in rows}
        except Exception as e:
            logger.warning(f"Could not bulk-load capability index: {e}")
            return None

    def _filter_by_capabilities(
        self,
        model_id: str,
        required_capability: Optional[str],
        capability_index: Optional[Dict[str, list]] = None,
    ) -> bool:
        """
        Check if model has the required capability.

        Args:
            model_id: Model identifier
            required_capability: Required capability (e.g., "computer_use", "vision", "tools")
            capability_index: optional pre-built {model_id -> capabilities} map
                from _load_capability_index(). When provided, avoids a per-model
                DB query inside the hot BPC loop.

        Returns:
            True if model has capability or no requirement, False otherwise.
            Unknown models and DB errors pass through (conservative: don't drop
            a candidate we can't verify — the caller's quality/health filters
            still apply).
        """
        if not required_capability:
            return True  # No capability requirement

        # BYOK composite ids ("openrouter/openai/gpt-4o") — the catalog may
        # key the base name; try progressively stripped variants so a
        # vision/tools model behind a router prefix isn't misclassified.
        def _name_variants(mid: str):
            yield mid
            base = mid
            while "/" in base:
                base = base.split("/", 1)[1]
                yield base

        # Fast path: use the pre-built index (no DB round-trip).
        if capability_index is not None:
            capabilities = capability_index.get(model_id)
            if capabilities is None:
                for variant in _name_variants(model_id):
                    if variant in capability_index:
                        return required_capability in capability_index[variant]
                return True  # Unknown model — pass through
            return required_capability in capabilities

        try:
            with get_db_session() as db:
                model = None
                for variant in _name_variants(model_id):
                    model = db.query(ModelCatalog).filter_by(model_id=variant).first()
                    if model:
                        break
                if not model:
                    return True  # Unknown models pass through
                capabilities = model.capabilities or ["chat"]
                return required_capability in capabilities
        except Exception as e:
            logger.warning(f"Failed to check capabilities for {model_id}: {e}")
            return True  # Pass through on error

    # Providers below this score are hard-excluded from BPC candidacy. Kept
    # low (0.2) on purpose: a higher threshold (the old 0.5) hard-excluded
    # borderline-healthy providers entirely rather than down-ranking them,
    # creating a recovery deadlock — an excluded provider can't get the
    # successful calls needed to push its score back up. Only genuinely-dead
    # providers (score < 0.2, i.e. ~30% success at zero latency) are dropped;
    # borderline ones remain candidates and self-correct via the sliding window.
    _HEALTH_EXCLUDE_THRESHOLD = 0.2

    def _filter_by_health(self, provider_id: str) -> bool:
        """
        Check if provider is healthy enough to remain a candidate.

        Only critically-unhealthy providers (score < _HEALTH_EXCLUDE_THRESHOLD)
        are excluded. Borderline providers are kept (they're effectively
        down-ranked by the broader cost/quality scoring and self-heal via the
        sliding window as successes accumulate).

        Args:
            provider_id: Provider identifier

        Returns:
            True if provider is healthy enough or unknown, False if dead.
        """
        if provider_id not in self.health_monitor.health_scores:
            return True  # Unknown providers pass through (optimistic)
        # Circuit breaker: a provider with recent consecutive connection
        # failures is benched entirely for a short cooldown, regardless of
        # EMA score — connection-dead gateways used to keep ranking on value
        # alone and every call stage re-paid the connect-timeout cascade
        # (observed 2026-08-31: minutes-long chat turns, client-visible
        # timeouts) before the sliding window could react. Strict `is True`
        # so stubbed monitors (tests) keep the legacy behavior.
        try:
            if self.health_monitor.is_breaker_open(provider_id) is True:
                return False
        except Exception:
            pass
        return self.health_monitor.get_health_score(provider_id) >= self._HEALTH_EXCLUDE_THRESHOLD

    @staticmethod
    def _stamp_sample_logprob(result: Any) -> None:
        """R83 #6: attach the sample's mean token log-probability.

        Reads ``choices[0].logprobs.content`` from instructor's
        ``_raw_response`` (present when the request asked for logprobs) and
        stamps ``_atom_mean_logprob`` on the parsed model. Best-effort:
        no logprobs / no raw response / non-writable model ⇒ no stamp, and
        the voter weighs that sample 1.0 (hard-vote semantics).
        """
        raw = getattr(result, "_raw_response", None)
        choices = getattr(raw, "choices", None) if raw is not None else None
        logprobs = getattr(choices, "__getitem__", lambda i: None)(0) if choices else None
        content = getattr(getattr(logprobs, "logprobs", None), "content", None)
        if not content:
            return
        try:
            mean_lp = sum(float(getattr(c, "logprob", 0.0)) for c in content) / len(content)
            setattr(result, "_atom_mean_logprob", mean_lp)
        except (TypeError, ZeroDivisionError, AttributeError):
            return

    @staticmethod
    def _capture_echoed_model(response: Any) -> None:
        """R82: record the provider-echoed (resolved) model ID for this call.

        Reads the ``model`` field off the raw provider response (same
        ``_raw_response`` pattern used for logprobs/usage) into a contextvar.
        This is the POST-flight identity — diverges from the requested model
        exactly on silent checkpoint bumps, which ModelDriftDetector then
        flags in _record_outcome_feedback. Best-effort: never raises.
        """
        try:
            from core.llm.model_provenance import set_resolved_model

            if response is None:
                return
            raw = getattr(response, "_raw_response", None) or response
            set_resolved_model(getattr(raw, "model", None))
        except Exception:
            pass

    @staticmethod
    def _reasoning_from_message(message: Any) -> str:
        """Extract chain-of-thought from a completion message across the
        provider-specific field names: DeepSeek ``reasoning_content``,
        OpenRouter ``reasoning``, vLLM/SGLang ``reasoning_content``, some
        clients ``thinking`` — with extras nested in ``model_extra`` when the
        SDK version predates the field. Returns '' when absent.
        """
        if message is None:
            return ""
        for attr in ("reasoning_content", "reasoning", "thinking_content", "thinking"):
            val = getattr(message, attr, None)
            if isinstance(val, str) and val.strip():
                return val.strip()
        extra = getattr(message, "model_extra", None)
        if isinstance(extra, dict):
            for key in ("reasoning_content", "reasoning", "thinking_content", "thinking"):
                val = extra.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
        return ""

    def _stash_last_reasoning(self, response: Any) -> None:
        """Stash the chain-of-thought of the last non-streaming completion
        onto ``self._last_reasoning`` (same stash pattern as
        _last_used_model). Best-effort: never raises."""
        try:
            msg = response.choices[0].message
            self._last_reasoning = self._reasoning_from_message(msg) or None
        except Exception:
            self._last_reasoning = None

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
        # NOTE: models with an EXPLICIT supports_tools=False in the cache are
        # hard-excluded (data-backed). Models ABSENT from the cache default to
        # tool-capable (availability-first — see dynamic_pricing_fetcher.
        # get_model_capabilities: the old conservative-False default barred
        # every model that postdated the cache snapshot from agentic routing,
        # producing a total agent outage on a stale cache).
        return bool(capabilities.get("supports_tools", False))

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
        if capabilities.get("supports_vision", False):
            return True
        # BYOK composite ids ("openrouter/openai/gpt-4o"): the pricing cache
        # may key the base name — retry stripped variants before concluding
        # a model is text-only (a false negative demotes perfectly good
        # BYOK vision models during vision routing).
        base = model_id or ""
        while "/" in base:
            base = base.split("/", 1)[1]
            if self.pricing_fetcher.get_model_capabilities(base).get(
                "supports_vision", False
            ):
                return True
        return False

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

    # Availability probe caching. A DOWN runtime must neither stall routing
    # (probes are cached, and localhost connection-refused is instant anyway)
    # nor gate-keep recovery — the down state is re-checked every minute, so
    # a restarted Ollama rejoins the pool without a restart of the backend.
    _OLLAMA_PROBE_TTL_UP = 300
    _OLLAMA_PROBE_TTL_DOWN = 60

    def _ollama_runtime_state(self):
        """("up", pulled_model_names) when the local Ollama runtime answers
        /api/tags, else ("down", None). Cached per state so routing never
        probes per call. Base names are included alongside tagged ones, so a
        catalog 'llama3.1' matches a pulled 'llama3.1:8b'."""
        cache = getattr(self, "_ollama_probe_cache", None)
        now = time.time()
        if cache:
            checked_at, state, pulled = cache
            ttl = (
                self._OLLAMA_PROBE_TTL_UP
                if state == "up"
                else self._OLLAMA_PROBE_TTL_DOWN
            )
            if now - checked_at < ttl:
                return state, pulled
        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1").rstrip("/")
        if base.endswith("/v1"):
            base = base[: -len("/v1")]
        try:
            import httpx

            resp = httpx.get(f"{base}/api/tags", timeout=(1.0, 2.0))
            resp.raise_for_status()
            names = {
                m.get("name")
                for m in resp.json().get("models", [])
                if m.get("name")
            }
        except Exception:
            self._ollama_probe_cache = (now, "down", None)
            return "down", None
        expanded = set(names)
        for n in names:
            expanded.add(n.split(":", 1)[0])
        self._ollama_probe_cache = (now, "up", expanded)
        return "up", expanded

    def _initialize_clients(self) -> None:
        """Initialize clients for all available providers"""
        import sys
        if not OpenAI:
            logger.warning("OpenAI package not installed. LLM features may be limited.")
            return

        # Initialize OpenAI-compatible clients for each provider
        providers_config = {
            "openai": {"base_url": None},
            "anthropic": {"base_url": "https://api.anthropic.com/v1"},
            "deepseek": {"base_url": "https://api.deepseek.com/v1"},
            "moonshot": {"base_url": "https://api.moonshot.cn/v1"},
            "deepinfra": {"base_url": "https://api.deepinfra.com/v1/openai"},
            "minimax": {"base_url": "https://api.minimax.io/v1"},  # MiniMax M3 (OpenAI-compatible)
            "lux": {"base_url": None},  # Phase 226.2-01: LUX Computer Use (uses Anthropic API)
            "qwen": {"base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"},
            "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/"},
            "xiaomi": {"base_url": "https://api.xiaomi.com/v1"},
            "ollama": {"base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")},
            # OpenRouter — unified gateway to 300+ models (OpenAI, Anthropic,
            # Google, Meta, …). OpenAI-compatible; one key → all models.
            "openrouter": {"base_url": "https://openrouter.ai/api/v1"},
            # Zhipu AI GLM family — OpenAI-compatible API
            "glm": {"base_url": "https://open.bigmodel.cn/api/paas/v4"},
            # Mistral — OpenAI-compatible API
            "mistral": {"base_url": "https://api.mistral.ai/v1"},
            # Groq — ultra-fast inference, OpenAI-compatible
            "groq": {"base_url": "https://api.groq.com/openai/v1"},
            # Phase C: six OpenAI-compatible providers (all expose /v1)
            "xai": {"base_url": "https://api.x.ai/v1"},          # Grok
            "cerebras": {"base_url": "https://api.cerebras.ai/v1"},
            "fireworks": {"base_url": "https://api.fireworks.ai/inference/v1"},
            "huggingface": {"base_url": "https://router.huggingface.co/v1"},
            "nvidia_nim": {"base_url": "https://integrate.api.nvidia.com/v1"},
            "zai": {"base_url": "https://api.z.ai/api/paas/v4"},
            # OpenCode Go — low-cost subscription gateway (OpenCode Zen).
            # OpenAI-compatible /chat/completions; one key serves the whole
            # tested model catalog. Custom rates/limits (RPM/TPM/context) are
            # enforced at routing time via core.llm.provider_rate_limits.
            "opencode-go": {"base_url": os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/v1")},
            # "opencode" is a first-class catalog id now (API Keys page) —
            # same gateway, so it needs the same base_url or a UI-stored key
            # under that id would build a client pointed at the OpenAI
            # default and every call would 404/401 there.
            "opencode": {"base_url": os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/v1")},
        }

        # Separate sync and async clients
        self.async_clients: Dict[str, Any] = {}

        # Providers whose client was built from a process-environment API key
        # (as opposed to a DB-stored BYOK/OAuth credential). In the AGPL
        # self-hosted edition an env key IS the user's own key, so these
        # providers must be treated as BYOK by the plan-gating logic below —
        # free-tier model allow-lists only apply to managed (platform) keys.
        self.env_key_providers: set = set()

        # Phase 226.2-01: Special handling for LUX provider (uses Anthropic API key via lux_config)
        if "lux" in providers_config:
            if "pytest" not in sys.modules:
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

        if "ollama" in providers_config:
            if "pytest" not in sys.modules:
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
            del providers_config["ollama"]

        for provider_id, config in providers_config.items():
            # OAuth + BYOK: Try credential service first (OAuth → BYOK → ENV)
            api_key = None
            credential_source = None

            if self.credential_service:
                try:
                    # Try to get credential with OAuth priority. The previous
                    # run_until_complete abandoned the coroutine whenever a
                    # loop was already running (FastAPI async routes), so
                    # OAuth/subscription credentials never resolved there.
                    credential_type, credential_value = _run_coroutine_sync(
                        self.credential_service.get_credential(provider_id)
                    )
                    if isinstance(credential_value, str) and credential_value:
                        api_key = credential_value
                        credential_source = credential_type
                    logger.info(f"Using {credential_source.upper()} credential for {provider_id}")
                except Exception as e:
                    logger.debug(f"Credential service not available for {provider_id}: {e}")

            # Fallback to BYOK if credential service didn't provide one.
            # Guard with isinstance: a non-string value (corrupted store
            # entry, or a test double returning Mock objects) must NOT count
            # as "found" — otherwise the env fallback below is skipped and
            # the provider silently loses its client entirely.
            if not api_key and self.byok_manager.is_configured(self.workspace_id, provider_id):
                candidate = self.byok_manager.get_api_key(provider_id)
                if isinstance(candidate, str) and candidate:
                    api_key = candidate
                    credential_source = "byok"

            # Special case: Gemini BYOK fallback to Google / Google Flash / Gemini Flash variants
            if not api_key and provider_id == "gemini":
                for alt_provider in ["google", "google_flash", "google_flash_3_5", "gemini_flash", "gemini_flash_3_5"]:
                    if self.byok_manager.is_configured(self.workspace_id, alt_provider):
                        candidate = self.byok_manager.get_api_key(alt_provider)
                        if isinstance(candidate, str) and candidate:
                            api_key = candidate
                            credential_source = "byok"
                            break

            # Final fallback to environment variables
            if not api_key:
                env_key = f"{provider_id.upper()}_API_KEY"

                # Special case: providers whose IDs can't be upper-cased into
                # a valid env name (hyphen breaks the convention).
                # opencode-go → OPENCODE_API_KEY.
                if provider_id == "opencode-go":
                    env_key = "OPENCODE_API_KEY"

                api_key = os.getenv(env_key)

                # Special case: Gemini can use GOOGLE_API_KEY
                if not api_key and provider_id == "gemini":
                    api_key = os.getenv("GOOGLE_API_KEY")

                if api_key:
                    credential_source = "env"
                    self.env_key_providers.add(provider_id)

            # BYOK file-store credential (data/byok_keys.json): same ownership
            # as an env key — the operator's own credential, not a
            # platform-billed managed key. Plan allowlists exist to gate
            # PLATFORM billing, so locally-stored keys must be exempt from
            # plan gating (single-tenant: every key is the operator's own).
            if api_key and credential_source == "byok":
                self.env_key_providers.add(provider_id)

            # Filter out known dummy/invalid placeholder keys
            if api_key and (api_key.startswith("60a9596d") or api_key.startswith("dummy") or len(api_key) < 12):
                logger.debug(f"Ignoring placeholder/invalid API key for {provider_id}")
                api_key = None

            # Initialize client if we have an API key
            if api_key:
                try:
                    # OpenRouter recommends HTTP-Referer + X-Title headers for
                    # better rate-limit treatment. Other providers ignore them.
                    client_kwargs = {
                        "api_key": api_key,
                        "base_url": config["base_url"],  # can be None for OpenAI
                        "timeout": _llm_request_timeout(),
                    }
                    if provider_id == "openrouter":
                        client_kwargs["default_headers"] = {
                            "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "https://atom.ai"),
                            "X-Title": "Atom",
                        }
                    self.clients[provider_id] = OpenAI(**client_kwargs)
                    if AsyncOpenAI:
                        self.async_clients[provider_id] = AsyncOpenAI(**client_kwargs)
                    logger.info(f"Initialized {provider_id} client using {credential_source.upper()} credential")
                except Exception as e:
                    logger.error(f"Failed to initialize {provider_id} client: {e}")
            else:
                logger.debug(f"No credential available for {provider_id}, skipping initialization")

        # Load user-registered local model providers (Ollama, LM Studio, vLLM,
        # etc.) from the DB and create OpenAI-compatible clients for each.
        # Their models become eligible for BPC ranking alongside cloud models.
        self._load_local_providers()

    def _load_local_providers(self) -> None:
        """Load registered local model providers from the DB into self.clients.

        Each provider gets a client keyed by ``local_{id}``. Their models are
        injected into the pricing cache so BPC ranking and capability detection
        work without special-casing. Best-effort: a DB failure or no providers
        registered is a clean no-op.
        """
        try:
            from core.database import get_db_session
            from core.models import LocalModelProvider, LocalModelCapabilities

            with get_db_session() as db:
                ws_id = self.workspace_id or "default"
                providers = db.query(LocalModelProvider).filter(
                    LocalModelProvider.workspace_id == ws_id,
                    LocalModelProvider.is_active == True,  # noqa: E712
                ).all()

                if not providers:
                    return

                fetcher = get_pricing_fetcher()

                for provider in providers:
                    provider_key = f"local_{provider.id[:8]}"
                    api_key = provider.api_key or "local"
                    base_url = provider.base_url.rstrip("/")

                    try:
                        self.clients[provider_key] = OpenAI(api_key=api_key, base_url=base_url)
                        self.async_clients[provider_key] = AsyncOpenAI(api_key=api_key, base_url=base_url)
                        logger.info(f"Loaded local provider '{provider.name}' ({provider.provider_type}) at {base_url}")
                    except Exception as e:
                        logger.warning(f"Could not create client for local provider '{provider.name}': {e}")
                        continue

                    # Inject the provider's models into the pricing cache.
                    caps = db.query(LocalModelCapabilities).filter(
                        LocalModelCapabilities.provider_id == provider.id
                    ).all()

                    if caps:
                        for cap in caps:
                            fetcher.pricing_cache[cap.model_id] = {
                                "model_id": cap.model_id,
                                "litellm_provider": provider.provider_type,
                                "input_cost": 0.0,
                                "output_cost": 0.0,
                                "max_input_tokens": cap.context_window or 8192,
                                "supports_tools": cap.supports_tools,
                                "supports_vision": cap.supports_vision,
                                "supports_reasoning": cap.supports_reasoning,
                                "quality_score": cap.quality_score,
                            }
                    else:
                        # No capabilities configured — register a generic entry
                        # so the model at least appears in BPC with defaults.
                        fetcher.pricing_cache[f"{provider.provider_type}_default"] = {
                            "model_id": f"{provider.provider_type}_default",
                            "litellm_provider": provider.provider_type,
                            "input_cost": 0.0,
                            "output_cost": 0.0,
                            "max_input_tokens": 8192,
                            "supports_tools": True,
                            "supports_vision": False,
                            "supports_reasoning": False,
                            "quality_score": 0.5,
                        }
        except Exception as e:
            logger.debug(f"Could not load local providers (non-fatal): {e}")

    def _track_rate_usage(self, provider_id: str, input_tokens: int = 0,
                          output_tokens: int = 0, model_id: Optional[str] = None) -> None:
        """Feed token usage into the custom rate tracker (best-effort, no-op).

        Only providers with custom RPM/TPM limits registered in
        ``core.llm.provider_rate_limits`` (e.g. opencode-go) are tracked; the
        tracker is otherwise a clean no-op so routing behavior is unchanged.

        ``model_id`` enables per-model accounting: weighted provider-level
        TPM consumption + independent per-model RPM/TPM limits + persisted
        monthly usage for subscription-quota routing.
        """
        try:
            self.rate_tracker.record_usage(provider_id, input_tokens, output_tokens,
                                           model_id=model_id)
        except Exception:
            logger.debug("Rate usage tracking failed (non-fatal)", exc_info=True)

    def _track_llm_call(self, provider: str, model: str, success: bool,
                        latency_ms: float = 0.0, input_tokens: int = 0,
                        output_tokens: int = 0, fallback: bool = False,
                        fallback_provider: Optional[str] = None,
                        error: Optional[str] = None) -> None:
        """Record a per-call LLM provider usage entry (best-effort, no-op).

        Feeds ``core.llm_call_tracker``: one record per provider attempt
        (success or failure) with timestamp/provider/model/latency/tokens/
        fallback/error, plus Prometheus counters/histograms. Covers every
        provider (opencode-go, openai, anthropic, deepseek, gemini, ollama,
        ...) across all dispatch paths. Never raises — tracking failures are
        logged and swallowed so the hot generation path is unaffected.
        """
        try:
            get_llm_call_tracker().record(
                provider=provider, model=model, success=success,
                latency_ms=latency_ms, input_tokens=input_tokens,
                output_tokens=output_tokens, fallback=fallback,
                fallback_provider=fallback_provider, error=error,
            )
        except Exception:
            logger.debug("LLM call tracking failed (non-fatal)", exc_info=True)

    def _monthly_tpm_limit(self) -> Optional[int]:
        """Opt-in monthly subscription allowance (``OPENCODE_MONTHLY_TPM``).

        When set, the BPC ranker hard-skips providers whose persisted usage
        for the current calendar month meets/exceeds the allowance — the
        in-window RPM/TPM guards burst rates, this guards the flat-rate
        subscription's monthly budget.
        """
        try:
            raw = os.getenv("OPENCODE_MONTHLY_TPM", "").strip()
            if not raw:
                return None
            limit = int(raw)
            return limit if limit > 0 else None
        except (TypeError, ValueError):
            logger.warning("OPENCODE_MONTHLY_TPM is not a valid integer — ignoring")
            return None

    def _monthly_budget_exhausted(self, provider_id: str, monthly_tpm_limit: int) -> bool:
        """True when a provider's monthly quota (weighted) is exhausted.

        Uses the persisted monthly totals from the rate tracker (best-effort);
        providers without a persistence layer never report exhausted, so
        routing keeps working if the DB is unavailable (fail-open, matches the
        rest of rate tracking).
        """
        try:
            monthly = self.rate_tracker.get_monthly_usage(provider_id)
            if not monthly:
                return False
            total = int(monthly.get("total_tokens") or 0)
            return total >= monthly_tpm_limit
        except Exception:
            logger.debug("Monthly quota check failed (non-fatal)", exc_info=True)
            return False

    def _pinned_model_fits(self, model: str, needed_tokens: int) -> bool:
        """Whether a pinned (provider_model) call may keep its pin given the
        request's estimated size (input + completion headroom).

        The pin exists for latency/quality on a known-reachable model, but it
        silently bypassed every context-window check — a learning-heavy
        prompt would overflow the pinned model and fail where the ranker
        would have chosen a bigger window. Unpin (caller re-ranks) ONLY when
        the pricing cache KNOWS the model and its window cannot hold the
        request: unknown models pass, because the conservative 4096 default
        would otherwise unpin every uncatalogued pin for no reason.
        """
        try:
            pricing = get_pricing_fetcher().get_model_price(model)
            if not pricing:
                return True
            window = pricing.get("max_input_tokens") or pricing.get("max_tokens") or 0
            if not window:
                return True
            return window >= needed_tokens
        except Exception:
            return True

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
            "deepseek-v4": 200000,  # OpenCode Zen models
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
        marker = "\n\n[... Content truncated: %d chars of middle context elided (head + tail preserved) ...]\n\n"
        marker_overhead = len(marker % 0)
        budget = max(100, max_chars - marker_overhead - 100)  # 100-char safety margin

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
        # Code vocabulary: words that double as everyday English ("try",
        # "return", "import", "class", "print", "final"…) were removed after
        # "try again" scored +3 and routed a trivial chat turn to the premium
        # tier. What remains is unambiguous in business chat; the leftover
        # weight still requires corroboration (code fence or a 2nd match).
        patterns = {
            "simple": (r"\b(hello|hi|thanks|greetings|summarize|translate|list|what is|who is|define|how do i|simplify|brief|basic|short|quick|simple)\b", -2),
            "moderate": (r"\b(analyze|compare|evaluate|synthesize|explain|describe|detailed|background|concept|history|nuance|opinion|critique|pros and cons|advantages|disadvantages)\b", 1),
            "technical": (r"\b(calculate|equation|formula|solve|integral|derivative|calculus|geometry|algebra|math|maths|theorem|statistics|probability|regression|vector|matrix|tensor|log|exp|pow|sqrt|abs|sin|cos|tan|pi|infinity|prime|physics|chemistry|biology|science)\b", 3),
            "code": (r"\b(code|coding|debug|debugging|optimize|optimization|refactor|refactoring|snippet|api|endpoint|webhook|sql|postgresql|mongodb|redis|json|xml|yaml|docker|kubernetes|aws|lambda|gcp|azure|async|await|typedef)\b", 3),
            "advanced": (r"\b(architecture|architecting|security audit|vulnerability|cryptography|encryption|decryption|authentication|authorization|auth|oauth|jwt|performance|bottleneck|concurrency|multithread|parallel|distributed|scale|scaling|load balance|cluster|proprietary|reverse engineer|obfuscate|obfuscation|enterprise|global|large-scale|purchase order|purchase orders)\b", 5)
        }

        # Check for code blocks (significant weight)
        has_code_fence = "```" in prompt
        if has_code_fence:
            complexity_score += 3

        code_vocab_matches = len(re.findall(patterns["code"][0], prompt, re.IGNORECASE))
        for name, (pattern, weight) in patterns.items():
            if not re.search(pattern, prompt, re.IGNORECASE):
                continue
            if name == "code" and not has_code_fence and code_vocab_matches < 2:
                # A lone technical word ("send the api docs") must not flip the
                # tier on its own — require a code fence or a second match.
                continue
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

    def get_optimal_provider(
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
        options = self.get_ranked_providers(
            complexity, task_type, prefer_cost, tenant_plan, 
            is_managed_service, requires_tools, requires_structured,
            turn_index=turn_index
        )
        if options:
            return AwaitableResult(options[0])
        
        # Absolute fallback
        if self.clients:
            provider_id = list(self.clients.keys())[0]
            return AwaitableResult((provider_id, "gpt-4o-mini"))

        raise NoProvidersConfiguredError(
            "No LLM providers available. You need an AI provider to do this. Add an API key or enable local Ollama to continue."
        )

    def get_ranked_providers(
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
        max_quality: Optional[int] = None,  # Stage-router "fast" steering: upper quality bound
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
            fetcher = get_pricing_fetcher_initialized_sync(auto_refresh=True)
            
            # Context window requirements
            MIN_CONTEXT_BY_COMPLEXITY = {
                QueryComplexity.SIMPLE: 4000,
                QueryComplexity.MODERATE: 8000,
                QueryComplexity.COMPLEX: 16000,
                QueryComplexity.ADVANCED: 32000
            }
            min_context = MIN_CONTEXT_BY_COMPLEXITY.get(complexity, 8000)
            # Learning-heavy prompts (canvas co-editor recall, transcripts)
            # dwarf the complexity floor — the request's OWN estimated size
            # sets the real window requirement, plus completion headroom
            # (reasoning models burn output budget thinking before they
            # answer). Callers passing estimated_tokens explicitly get a
            # window-aware candidate filter; the 1000 default (unset) keeps
            # the complexity floor only.
            if estimated_tokens and estimated_tokens > 1000:
                min_context = max(
                    min_context,
                    estimated_tokens + _DEFAULT_COMPLETION_MAX_TOKENS,
                )

            # Filter criteria for benchmarks based on complexity
            # Phase 68: Use CognitiveTier thresholds if provided
            if cognitive_tier is not None:
                min_quality = MIN_QUALITY_BY_TIER.get(cognitive_tier, 0)
                logger.debug(f"Using CognitiveTier {cognitive_tier.value} quality threshold: {min_quality}")
            else:
                MIN_QUALITY_BY_COMPLEXITY = {
                    # SIMPLE floor is 85, not 0: "simple" query != "any model".
                    # Short conversational follow-ups ("who was that lead
                    # again?") classify SIMPLE yet need transcript recall —
                    # measured on Aug 30, sub-85 models (qwen3.7-flash,
                    # deepseek-v4-flash) ignored their own prior answers and
                    # claimed no access. Every chat turn gets a model that
                    # passes recall; cost efficiency picks WITHIN the capable
                    # pool (minimax-m3 at $0.30/$1.20 is still ~7x cheaper
                    # than claude-sonnet-5).
                    QueryComplexity.SIMPLE: 85,
                    QueryComplexity.MODERATE: 80,
                    QueryComplexity.COMPLEX: 88,
                    # ADVANCED was 94 (frontier-only): the only vetted models
                    # clearing it were qwen3-max ($2.34/M blended) and
                    # deepseek-v4-pro — so every "advanced"-classified request
                    # paid flagship prices. Recalibrated to 90 (Sept 6): the
                    # 2026 flash tier now benchmarks at last-gen-flagship
                    # level (gemini-3-flash beats o3/GPT-5 on a medical
                    # accuracy battery, PMC12894337; gpt-5-mini = 99.3% of
                    # gpt-5 quality at 4.2x lower cost, Wolfia), and BOTH
                    # passed the same Aug-30 transcript-recall probe that set
                    # the SIMPLE floor (scripts/bpc_recall_probe_sept2026.py;
                    # glm-5.3-flash / qwen3.8-flash / v4-flash-0731 failed it
                    # and stay below 85). 90 keeps the line at "frontier-class
                    # or measured-equivalent" — minimax-m3 (89, no external
                    # frontier-class evidence) still tops out at COMPLEX.
                    # Result: advanced -> gpt-5-mini ($1.13/M blended,
                    # recall ✓) instead of qwen3-max ($2.34/M); deepseek BYOK
                    # advanced -> deepseek-reasoner (91, $0.35/M, recall ✓
                    # probed Sept 6) instead of deepseek-v4-pro ($2.64/M).
                    QueryComplexity.ADVANCED: 90
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
                max_quality = min(90, max_quality) if max_quality is not None else 90
                # Adjust min_quality down if it exceeds the cap
                min_quality = min(min_quality, 90)
                _excluded_models = {"o1", "o1-mini", "o1-pro", "o3", "o3-mini", "o4", "o4-mini"}
            else:
                max_quality = min(100, max_quality) if max_quality is not None else 100
                _excluded_models = set()

            # A caller-supplied cap ("fast" steering) can sit below a raised
            # min floor (e.g. ADVANCED=94 vs cap 89) — clamp so the window
            # stays non-empty instead of filtering every candidate out.
            if max_quality is not None:
                min_quality = min(min_quality, max_quality)
            
            available_providers = list(self.clients.keys())
            candidates = []

            # When a capability filter is active, bulk-load the capability index
            # ONCE instead of querying the DB per model inside the loop below
            # (hundreds of round-trips + connection-pool pressure). None when no
            # filter is needed (the per-model call is then a no-op anyway).
            capability_index = (
                self._load_capability_index() if required_capability else None
            )

            # Use the entire pricing cache to discover models beyond hardcoded lists
            # Phase 5': kick off (never block on) measured endpoint telemetry for
            # openrouter-hosted models so subsequent calls have fresh health data.
            _or_telemetry_ids: List[str] = []
            if "openrouter" in self.clients:
                try:
                    from core.llm.openrouter_endpoints import (
                        get_endpoint_monitor as _get_endpoint_monitor,
                        telemetry_enabled as _or_telemetry_enabled,
                    )
                    if _or_telemetry_enabled():
                        _or_telemetry_ids = [
                            mid for mid, p in fetcher.pricing_cache.items()
                            if (p.get("litellm_provider") or "").lower() == "openrouter"
                        ][:50]
                        if _or_telemetry_ids:
                            _get_endpoint_monitor().ensure_refresh_started(_or_telemetry_ids)
                except Exception as e:  # noqa: BLE001 — telemetry must never break routing
                    logger.debug(f"Endpoint telemetry kickoff skipped: {e}")

            for model_id, pricing in fetcher.pricing_cache.items():
                litellm_provider = pricing.get("litellm_provider", "").lower()

                # Check if we have a client for this provider. Exact catalog
                # match wins: OpenRouter-hosted IDs often CONTAIN another
                # client's name ("deepseek/deepseek-v4-flash-0731" contains
                # "deepseek"), and the old substring-first match handed those
                # to the wrong client — api.deepseek.com 400s prefixed IDs
                # ("supported names are deepseek-v4-pro, deepseek-v4-flash,
                # …", verified Sept 6), so every such request paid a failed
                # call before escalating. Substring stays as the fallback for
                # models the catalog can't attribute (local providers).
                active_provider = next(
                    (p for p in available_providers if p == litellm_provider), None
                )
                if not active_provider:
                    active_provider = next(
                        (p for p in available_providers if p in model_id.lower()), None
                    )
                if not active_provider:
                    continue

                # Ollama routes ONLY when the local runtime is available —
                # free local models rank well on value, so an unreachable
                # runtime sitting in the pool made every request pay its
                # connection-failure tax before failing over. Availability
                # is probed (cached) and even when up, only models ACTUALLY
                # pulled can serve: catalog names that aren't pulled 404.
                if active_provider == "ollama":
                    ollama_state, pulled = self._ollama_runtime_state()
                    if ollama_state != "up":
                        continue
                    if model_id.split("/", 1)[-1] not in pulled:
                        continue

                if active_provider == "openrouter":
                    # OpenRouter hosts 480+ models; only a vetted allowlist
                    # (exact entries in MODEL_QUALITY_SCORES) may rank. The
                    # partial-match quality scorer crosses model families on
                    # openrouter IDs (a roleplay finetune outscored deepseek
                    # flagship 92-to-42), so unvetted candidates would win on
                    # garbage scores. ":batch"/":floor" suffixes are offline
                    # gateway variants, never interactive chat. Within the
                    # vetted pool the value score (quality²/cost) then always
                    # picks the CHEAPEST model above the tier's quality floor,
                    # adapting automatically as prices change.
                    if ":" in model_id or model_id not in MODEL_QUALITY_SCORES:
                        continue
                
                # Check context window (clamped by the provider's custom
                # max_context limit, if configured — e.g. opencode-go caps the
                # context the gateway will serve regardless of the model's own
                # advertised window)
                context_window = pricing.get("max_input_tokens") or pricing.get("max_tokens") or 0
                provider_max_context = self.rate_tracker.get_max_context(active_provider)
                if provider_max_context is not None:
                    context_window = min(context_window, provider_max_context)
                if context_window < min_context:
                    continue

                # Phase M (measurement only): count candidates whose OpenRouter
                # payload marks them expired. expiration_date means "may be
                # removed", so routing is deliberately unchanged — this feeds
                # the staleness stats that decide plan-v2 Phases 1–3.
                _exp = pricing.get("expiration_date")
                if _exp:
                    try:
                        from core.dynamic_pricing_fetcher import is_expiration_past
                        if is_expiration_past(_exp):
                            fetcher.record_stale_consideration(model_id)
                    except Exception:  # noqa: BLE001 — measurement must never break routing
                        pass

                # Phase 226.4-04: Check capability filter
                if not self._filter_by_capabilities(model_id, required_capability, capability_index):
                    continue

                # Phase 226.4-04: Check if model is excluded from general routing
                if not required_capability and model_id in self.excluded_models:
                    continue

                # Phase 226.4-04: Check provider health
                if not self._filter_by_health(active_provider):
                    continue

                # Phase 5': measured endpoint health for openrouter-hosted
                # models. Unknown/no-data ⇒ untouched (fail-open). Measured
                # uptime below floor ⇒ skip; p50 latency above cap ⇒ soft
                # value-score penalty applied at scoring time.
                endpoint_penalty = 1.0
                if active_provider == "openrouter" and _or_telemetry_ids:
                    try:
                        from core.llm.openrouter_endpoints import (
                            endpoint_health_gate,
                        )
                        gate = endpoint_health_gate(model_id)
                    except Exception:  # noqa: BLE001
                        gate = 1.0
                    if gate is None:
                        continue
                    endpoint_penalty = gate

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

                # Calculate DETERMINISTIC cache-aware effective cost (Turn 0 vs Turn N)
                effective_cost = self.cache_router.calculate_effective_cost(
                    model_id, active_provider, estimated_tokens, turn_index=turn_index
                )

                # NOTE: value_score is computed in a second pass below, after we
                # know the pool's cost scale, so free/local models (cost == 0.0)
                # can be floored RELATIVE to paid models rather than with an
                # absolute floor that either let them dominate unconditionally
                # (old 1e-9 → ~1000x advantage) or over-penalized them.
                candidates.append({
                    "provider": active_provider,
                    "model": model_id,
                    "quality": quality_score,
                    "cost": effective_cost,
                    "endpoint_penalty": endpoint_penalty,
                })

            # Second pass: compute value_score with a pool-relative cost floor.
            # Free models are floored at ~half the median PAID cost in this
            # candidate pool, so they remain cheap-but-finite: a free model
            # still beats an equal-quality paid model, but a substantially-
            # higher-quality paid model can win (Bug 8). The factor (0.5) is
            # chosen so that quality gaps (squared in the numerator) overcome
            # the price advantage: quality 0.95 paid beats quality 0.5 free,
            # while quality-0.9 free still beats quality-0.9 paid.
            paid_costs = sorted(c["cost"] for c in candidates if c["cost"] > 0)
            if paid_costs:
                median_paid = paid_costs[len(paid_costs) // 2]
                relative_floor = max(median_paid * 0.5, 1e-9)
            else:
                relative_floor = 1e-9  # all-free pool — original behavior

            # Rate-aware pass: providers with custom RPM/TPM limits (e.g.
            # opencode-go) are penalized by their remaining headroom, and
            # hard-skipped once their budget is exhausted this window. Without
            # limits configured headroom is always 1.0 (no behavior change).
            #
            # Per-model extension (OpenCode Go quota accounting): each model
            # also carries a quota weight + optional per-model RPM/TPM limits.
            # A model with its own limits is hard-skipped INDEPENDENTLY (one
            # quota-hungry model can't take the whole provider down), and the
            # model's quota weight penalizes its value score so cheap models
            # win when quality parity holds.
            _rate_headroom_cache: Dict[str, float] = {}
            _monthly_exhausted: Dict[str, bool] = {}
            monthly_tpm_limit = self._monthly_tpm_limit()
            for c in candidates:
                provider_id = c["provider"]
                model_id = c["model"]

                # Monthly subscription allowance hard-skip (opt-in via
                # OPENCODE_MONTHLY_TPM). Weighted against each model's quota
                # weight, so heavy models drain the allowance faster.
                if monthly_tpm_limit:
                    if provider_id not in _monthly_exhausted:
                        _monthly_exhausted[provider_id] = self._monthly_budget_exhausted(
                            provider_id, monthly_tpm_limit
                        )
                    if _monthly_exhausted[provider_id]:
                        logger.info(
                            f"BPC skipped {provider_id} — monthly subscription "
                            f"quota exhausted (limit={monthly_tpm_limit})"
                        )
                        continue

                # Per-model headroom when the model has its own limits; falls
                # back to the provider headroom otherwise.
                model_headroom = self.rate_tracker.get_model_headroom(provider_id, model_id)
                if model_headroom <= 0.0:
                    logger.info(
                        f"BPC skipped {provider_id}/{model_id} — per-model rate "
                        f"budget exhausted (headroom={model_headroom:.2f})"
                    )
                    continue

                if provider_id not in _rate_headroom_cache:
                    _rate_headroom_cache[provider_id] = self.rate_tracker.get_headroom(provider_id)
                headroom = _rate_headroom_cache[provider_id]
                if headroom <= 0.0:
                    logger.info(
                        f"BPC skipped {provider_id} — custom rate budget exhausted "
                        f"(headroom={headroom:.2f})"
                    )
                    continue
                c["headroom"] = headroom
                c["model_headroom"] = model_headroom
                c["quota_weight"] = self.rate_tracker.get_model_weight(provider_id, model_id)

            # Drop exhausted providers entirely so they can't leak into the
            # ranked output or break the value-score sort below.
            candidates = [c for c in candidates if "headroom" in c]

            for c in candidates:
                normalized_cost = max(c["cost"], relative_floor)
                # BPC Score: Higher is better value.
                # Squaring quality penalizes low-end models for complex tasks.
                # The headroom factor (0.25–1.0) deprioritizes providers that
                # are approaching their custom rate ceiling without an abrupt
                # cliff — the router still prefers them at 95% quality parity
                # but a healthy provider wins as limits tighten.
                # The quota factor (0.25–1.0) penalizes quota-hungry OpenCode Go
                # models: weight 1.0 (flash-equivalent) scores 1.0, a ~12x
                # heavier model ~0.61, a ~43x heavier model ~0.47 — a mild
                # routing preference that only matters at quality parity (the
                # model's per-token price is already in ``cost``, so this only
                # nudges, never overrides, quality).
                quota_factor = 1.0
                weight = c.get("quota_weight") or 1.0
                if weight > 1.0:
                    quota_factor = max(0.25, min(1.0, (1.0 / weight) ** 0.2))
                c["value_score"] = (
                    ((c["quality"] ** 2) / (normalized_cost * 1e6))
                    * max(0.25, c["headroom"])
                    * quota_factor
                    * c.get("endpoint_penalty", 1.0)
                )

            
            # Sort by Value Score (Descending)
            candidates.sort(key=lambda x: x["value_score"], reverse=True)
            
            # Filter by plan restrictions. Plan gating is for MANAGED
            # (platform-billed) keys only: an env-provided key IS the
            # operator's own credential (see env_key_providers note in
            # __init__), so plan allowlists must not zero out its candidates.
            def _plan_applies(provider_id: str) -> bool:
                own_keys = getattr(self, "env_key_providers", set())
                return is_managed_service and provider_id not in own_keys

            def is_model_approved(model_id: str, allowed_list: any) -> bool:
                # The local runtime is the authority for its own models: the
                # remote catalog carries no capability data for pulled names,
                # and its conservative default hid working local models
                # (llama3.1:8b serves tools even though the cache is silent).
                # Availability + pulled-model gating happens at candidate
                # time; a local model that genuinely lacks tools surfaces a
                # normal call error like any other provider mismatch.
                is_local = model_id.lower().startswith("ollama/")
                if (
                    (requires_tools or requires_structured)
                    and not is_local
                    and not self._model_supports_tools(model_id)
                ):
                    return False

                if allowed_list == "*" or "*" in allowed_list:
                    return True
                
                # Flexible matching: check if any allowed model name is part of the actual model_id
                model_id_lower = model_id.lower()

                return any(m.lower() in model_id_lower for m in allowed_list)

            for c in candidates:
                allowed_models = (
                    MODEL_TIER_RESTRICTIONS.get((tenant_plan or "free").lower(), MODEL_TIER_RESTRICTIONS["free"])
                    if _plan_applies(c["provider"]) else "*"
                )
                if is_model_approved(c["model"], allowed_models):
                    ranked_options.append((c["provider"], c["model"]))

            # Availability-first fail-open: the pricing cache's capability
            # inference can mark genuinely tool-capable models False (and a
            # failed cache refresh leaves it empty), so the filter can
            # eliminate EVERY candidate — observed live as a total agent
            # outage on a structured ReAct request. Structured-only requests
            # degrade gracefully (instructor falls back to prompt-based
            # extraction), so the capability filter fails open with a warning
            # rather than zeroing out the fleet. requires_tools stays HARD —
            # an agentic loop without tool-calling is broken no matter what.
            # Plan/allowlist filtering also stays hard (that's entitlement).
            if not ranked_options and candidates and not requires_tools:
                logger.warning(
                    "BPC capability filter eliminated all %d candidates "
                    "(tools/structured metadata missing or conservative) — "
                    "failing open so routing continues",
                    len(candidates),
                )
                ranked_options = [(c["provider"], c["model"]) for c in candidates]

            if ranked_options:
                logger.info(f"BPC Ranking Successful for {getattr(complexity, 'value', complexity)}: Top model {ranked_options[0][1]} (Value: {candidates[0]['value_score']:.2f})")
                return AwaitableResult(ranked_options)
                
        except Exception as e:
            logger.debug(f"BPC ranking failed, falling back to static mapping: {e}")
        
        # 2. Static Fallback (if BPC logic fails or cache empty)
        if complexity == QueryComplexity.SIMPLE:
            provider_priority = ["deepseek", "minimax", "qwen", "moonshot", "gemini", "opencode-go", "openai", "anthropic", "openrouter"]
        elif complexity == QueryComplexity.MODERATE:
            provider_priority = ["deepseek", "minimax", "qwen", "gemini", "moonshot", "opencode-go", "openai", "anthropic", "openrouter"]
        elif complexity == QueryComplexity.COMPLEX:
            provider_priority = ["gemini", "deepseek", "anthropic", "qwen", "minimax", "opencode-go", "openai", "moonshot", "openrouter"]
        else: # ADVANCED
            provider_priority = ["openai", "deepseek", "opencode-go", "anthropic", "qwen", "gemini", "moonshot", "minimax", "openrouter"]
        
        capability_blocked_options: List[tuple] = []

        # Hard-gate parity with the dynamic ranker above. The static fallback
        # exists to recover from pricing-cache misses/exceptions — NOT to
        # override the rate/monthly/context hard-skips: whenever those gates
        # empty the dynamic pool (e.g. the SIMPLE quality floor leaves only
        # one candidate), falling through here re-added the exact exhausted
        # provider the gates had just excluded, routing into guaranteed 429s.
        FALLBACK_MIN_CONTEXT = {
            QueryComplexity.SIMPLE: 4000,
            QueryComplexity.MODERATE: 8000,
            QueryComplexity.COMPLEX: 16000,
            QueryComplexity.ADVANCED: 32000,
        }
        fallback_min_context = FALLBACK_MIN_CONTEXT.get(complexity, 8000)
        fallback_monthly_tpm_limit = self._monthly_tpm_limit()

        for provider_id in provider_priority:
            if provider_id in self.clients:
                models = COST_EFFICIENT_MODELS.get(provider_id, {})
                model = models.get(complexity, "gpt-4o-mini")

                # Same hard gates as the dynamic ranker's rate-aware pass:
                # provider/per-model headroom, monthly subscription quota,
                # and the provider-level context clamp.
                if self.rate_tracker.get_headroom(provider_id) <= 0.0:
                    continue
                if self.rate_tracker.get_model_headroom(provider_id, model) <= 0.0:
                    continue
                if fallback_monthly_tpm_limit and self._monthly_budget_exhausted(
                    provider_id, fallback_monthly_tpm_limit
                ):
                    continue
                provider_max_context = self.rate_tracker.get_max_context(provider_id)
                if (
                    provider_max_context is not None
                    and provider_max_context < fallback_min_context
                ):
                    continue

                # Check Tool/Structured Support (Phase 6.6 / BUG-113): the
                # dynamic pricing cache is authoritative for capabilities.
                # requires_tools is a HARD requirement (an agentic loop
                # without tool-calling is broken no matter what), while
                # structured-only blocks are soft — instructor degrades to
                # prompt-based extraction, so they may fail open below when
                # the filter would otherwise zero out the whole ranking.
                try:
                    capability_blocked = (
                        (requires_tools or requires_structured)
                        and not self._model_supports_tools(model)
                    )
                except Exception:
                    capability_blocked = False  # cache unavailable — best-effort
                if capability_blocked and provider_id == "deepseek" and model == "deepseek-v3.2-speciale":
                    # The r2 downgrade resolves the block outright (r2 is the
                    # known tool-capable variant).
                    model = "deepseek-r2"
                    capability_blocked = False
                if capability_blocked and requires_tools:
                    continue

                if not is_managed_service:
                    ranked_options.append((provider_id, model))
                    continue

                # Plan gating applies to managed keys only (env keys are the
                # operator's own — see _plan_applies in the BPC path).
                allowed_models = (
                    MODEL_TIER_RESTRICTIONS.get((tenant_plan or "free").lower(), MODEL_TIER_RESTRICTIONS["free"])
                    if (is_managed_service and provider_id not in getattr(self, "env_key_providers", set())) else "*"
                )

                # Substring approval, mirroring is_model_approved() in the BPC
                # path: the tier allowlists carry short names ("claude-3-haiku")
                # while COST_EFFICIENT_MODELS carries dated variants
                # ("claude-3-haiku-20240307"). Exact membership matched nothing,
                # so a free-plan tenant got zero ranked models whenever BPC was
                # unavailable (pricing cache down / cache-router failure).
                if "*" in allowed_models or any(
                    m.lower() in model.lower() for m in allowed_models
                ):
                    ranked_options.append((provider_id, model))
                elif capability_blocked:
                    # Blocked by capability AND outside the plan allowlist —
                    # a fail-open candidate (plan check stays the hard
                    # entitlement; see the fail-open below).
                    capability_blocked_options.append((provider_id, model))

        # Availability-first fail-open (mirrors the BPC path): structured-only
        # requests degrade gracefully, so the capability filter fails open
        # with a warning rather than returning zero options. requires_tools
        # stays hard — a non-tool model is useless to an agentic loop.
        if not ranked_options and capability_blocked_options and not requires_tools:
            logger.warning(
                "Static fallback capability filter eliminated all %d options "
                "(tools/structured metadata missing or conservative) — failing "
                "open so routing continues",
                len(capability_blocked_options),
            )
            ranked_options = capability_blocked_options

        # Phase 68-Q: Boost Qwen to top if available and requested
        if "qwen" in self.clients:
            qwen_option = next(((p, m) for p, m in ranked_options if p == "qwen"), None)
            if qwen_option:
                ranked_options.remove(qwen_option)
                ranked_options.insert(0, qwen_option)

        return AwaitableResult(ranked_options)

    def _llm_taint_check(self, text: str, provider_id: str, model: str) -> Optional[str]:
        """P4 prompt-taint gate. Returns a block reason under enforce mode,
        None when the call may proceed. Shadow mode logs only. Never raises."""
        if not (_LLM_TAINT_SHADOW or _LLM_TAINT_ENFORCE):
            return None
        try:
            from core.data_taint_tracker import assess_prompt_outbound

            decision = assess_prompt_outbound(text or "", provider_id, model)
        except Exception:
            return None
        if decision is None:
            return None
        if _LLM_TAINT_SHADOW:
            logger.warning(
                "llm_taint.shadow provider=%s model=%s max_observed=%s — %s "
                "(set ATOM_LLM_TAINT_ENFORCE=true to block)",
                provider_id, model, decision.get("max_observed"),
                decision.get("reason"),
            )
        if _LLM_TAINT_ENFORCE:
            return (
                "[LLM CALL BLOCKED] Prompt classified restricted-sensitivity "
                f"(potential PII/secrets); dispatch to {provider_id}/{model} "
                "denied by taint policy (ATOM_LLM_TAINT_ENFORCE)."
            )
        return None

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
        turn_index: int = 0, # NEW: Deterministic BPC
        cognitive_tier: Optional[str] = None,  # x-atom-tier override
        intent_override: Optional[str] = None,  # x-atom-intent override
        sticky_hint: Optional[tuple] = None,  # LKGP (provider, model) hint
        messages: Optional[List[Dict[str, Any]]] = None,  # Full conversation (chat path)
    ) -> str:
        """
        Generate a response using cost-optimized provider routing.
        Supports multimodal inputs (text + image) via `image_payload`.
        """
        # Stage router: clear any stale decision carrier from a previous
        # structured call in this task — plain/fallback generations must not
        # write outcomes onto a prior turn's audit row. (The structured path
        # records its own attempts and re-sets the carrier per call.)
        try:
            from core.llm.stage_router import set_stage_decision_carrier

            set_stage_decision_carrier(None)
        except Exception:
            pass

        # R82: clear any stale resolved-model echo from a previous call in
        # this task so outcome feedback never attributes an old provider echo
        # to a new request.
        try:
            from core.llm.model_provenance import clear_resolved_model

            clear_resolved_model()
        except Exception:
            pass

        # Same staleness rule for the chain-of-thought stash: a call that
        # produces no reasoning must not inherit the previous call's.
        self._last_reasoning = None

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
                            elif self.env_key_providers:
                                # AGPL self-hosted edition: an env-configured key is
                                # the user's own key — BYOK, never plan-restricted.
                                # (temp_provider_id may itself be skewed by the
                                # free-tier allow-list, so match on any env key.)
                                is_managed = False
                            elif tenant_plan.lower() in [p.lower() for p in BYOK_ENABLED_PLANS]:
                                is_managed = False  # Enterprise Plan = BYOK

                            # 3. Block Managed AI for Free Tier (Phase 59 User Req) - BYPASSED for AI Employee Demo
                            # We bypass this for 'agentic' task types to allow the demo to function.
                            # NOTE: the no-local-keys case is already handled by the `if not self.clients`
                            # gate above (LLM Client not initialized), so a separate restriction return
                            # here would be unreachable dead code.
                except Exception as e:
                    logger.warning(f"Failed to fetch tenant plan: {e}")

            # --- Phase 14-BYOK: Force BYOK behavior if local keys exist for agentic tasks ---
            if task_type == "agentic" and self.clients:
                is_managed = False
                tenant_plan = "enterprise" # Effectively unrestricted
                logger.info("Using local/BYOK mode for agentic task demo")

            # Analyze complexity (skipped when x-atom-tier override forces a tier)
            forced_tier_enum: Optional[CognitiveTier] = None
            if cognitive_tier:
                try:
                    forced_tier_enum = CognitiveTier(cognitive_tier.lower())
                    # Keep the real QueryComplexity enum — a plain string here
                    # crashes later at ``complexity.value`` (the success path
                    # logs it), turning EVERY forced-tier request into a fake
                    # "provider failure" after the model already answered.
                    complexity = QueryComplexity.COMPLEX
                except ValueError:
                    logger.warning(f"Invalid cognitive_tier override: {cognitive_tier}")
                    complexity = self.analyze_query_complexity(prompt, task_type)
            else:
                complexity = self.analyze_query_complexity(prompt, task_type)

            # --- Stage-router / caller model-type steering ---
            # Documented vocabulary: "auto", "fast", "quality", or a concrete
            # model name (stage_router.map_decision_to_model_type emits the
            # first three; the tier-escalation loop passes concrete models).
            # Previously this parameter was accepted and DROPPED, so an
            # enforced stage-router decision changed audit rows but never the
            # actual model selection. An explicit x-atom-tier override
            # (cognitive_tier) always wins over the soft steering.
            max_quality_override: Optional[int] = None
            pinned_model: Optional[str] = None
            if cognitive_tier is None and model_type and model_type != "auto":
                if model_type == "quality":
                    forced_tier_enum = CognitiveTier.HEAVY
                elif model_type == "fast":
                    max_quality_override = 89
                else:
                    pinned_model = model_type

            # Identify tool/structured requirements (Phase 6.6)
            requires_tools = agent_id is not None or task_type == "agentic"

            # --- Phase 14: Vision Routing ---
            # If image payload exists, we MUST route to a model that supports vision (GPT-4o, Gemini 1.5 Pro)
            # We override the normal routing logic to prioritize Vision-Capable models
            requires_vision = image_payload is not None

            # Get ranked list of providers (forced_tier_enum drives min-quality
            # selection when an x-atom-tier override is present) — window-aware:
            # the conversation transcript plus prompt set the candidate
            # context floor.
            _est_input_chars = len(prompt or "") + sum(
                len(str(m.get("content") or ""))
                for m in (messages or []) if isinstance(m, dict)
            )
            # BYOK images count toward context: a typical image costs
            # ~85-1105 tokens depending on detail (OpenAI accounting) —
            # reserve the high case so window checks don't under-count.
            _image_tokens = 1106 if requires_vision else 0
            options = await self.get_ranked_providers(
                complexity, task_type, prefer_cost, tenant_plan, is_managed,
                requires_tools=requires_tools, requires_structured=False,
                turn_index=turn_index,
                cognitive_tier=forced_tier_enum,
                max_quality=max_quality_override,
                estimated_tokens=max(1000, _est_input_chars // 4) + _image_tokens,
                # Vision turns rank ONLY vision-capable candidates up front —
                # the old flow ranked vision-blind and either fell back to a
                # lossy image-description pass or hard-pinned GPT-4o, which a
                # BYOK user without an OpenAI key cannot call.
                required_capability=("vision" if requires_vision else None),
            )

            # --- LKGP (Last-Known-Good-Path) sticky boost ---
            # If the session has a last-known-good (provider, model) from a
            # prior successful turn AND that pair is in the candidate list,
            # boost it to position 0 for multi-turn consistency. Evidence:
            # vLLM #1439, Vercel, LLM Gateway — all recommend session
            # stickiness. Falls through silently if the sticky pair is absent
            # or unhealthy.
            if sticky_hint and len(sticky_hint) == 2:
                _sp, _sm = sticky_hint
                sticky_pair = (_sp, _sm)
                if sticky_pair in options:
                    options.remove(sticky_pair)
                    options.insert(0, sticky_pair)
                    logger.debug(f"[LKGP] boosted {_sp}/{_sm} to position 0")

            # --- Intent detection (domain classifier) ---
            # Detects the routing-relevant domain (coding, reasoning, etc.) and
            # feeds it to the learning router so per-model predictors learn
            # intent-specific preferences. Best-effort: any error leaves intent
            # as None and routing behaves as before. An explicit override (from
            # the x-atom-intent header path) skips detection.
            detected_intent = intent_override
            if detected_intent is None:
                try:
                    from core.llm.intent_detector import get_intent_detector
                    _ir = get_intent_detector().detect(prompt)
                    if _ir.category is not None and _ir.confidence >= 0.5:
                        detected_intent = _ir.category
                except Exception:
                    logger.debug("Intent detection failed; continuing without", exc_info=True)

            # --- Learning-router re-ranking (flag-gated, phase 2 of rollout) ---
            # When enabled and a trained predictor exists for this tenant/task,
            # re-order BPC's already-filtered candidate list using the learned
            # satisfaction signal. Never adds/removes candidates — only re-orders
            # — so the live pricing-cache (not the router's stale registry)
            # remains the source of truth for which models are eligible. Cold
            # start (no predictor) leaves BPC order untouched. Best-effort: any
            # error falls back to BPC order so the hot path never breaks.
            options = await self._rerank_with_learning(options, prompt, task_type, intent=detected_intent)

            # --- Concrete-model pinning (model_type = specific model) ---
            # Hoist every candidate serving the requested concrete model to the
            # front (provider order preserved) so the tier-escalation loop's
            # explicit choice is attempted first; the remaining ranked
            # candidates stay available as fallback.
            if pinned_model:
                pinned_opts = [(p, m) for p, m in options if m == pinned_model]
                if pinned_opts:
                    rest_opts = [(p, m) for p, m in options if m != pinned_model]
                    options = pinned_opts + rest_opts
                    logger.debug(f"[model-type] pinned '{pinned_model}' candidates to front")

            # Capture the decision id minted by _rerank_with_learning (if any) in
            # a local so EVERY provider attempt in the fallback loop below can
            # correlate its feedback back to the same prompt features. Previously
            # the id was consumed on the FIRST attempt (success OR failure): if
            # the top-ranked model failed and the loop fell through to a second
            # provider, that fallback's feedback got a random id and lost feature
            # correlation — exactly when the predictor most needs to learn
            # "model X fails". The features are request-level (not per-model), so
            # one id correctly serves the whole ranked list.
            decision_id_for_feedback = self._pending_routing_result_id
            self._pending_routing_result_id = None

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

            # P4 prompt-taint gate (single check — the prompt text is
            # identical for every candidate provider).
            _taint_block = self._llm_taint_check(
                prompt,
                options[0][0] if options else "",
                options[0][1] if options else "",
            )
            if _taint_block:
                return _taint_block

            last_error = None
            primary_provider = options[0][0] if options else None
            failed_providers = set()
            for provider_id, model in options:
                if provider_id in failed_providers:
                    continue
                # Per-provider flag: each provider gets at most one self-heal retry.
                heal_attempted_for_current = False
                try:
                    import time
                    request_start = time.time()
                    client = self.clients.get(provider_id)
                    if not client:
                        failed_providers.add(provider_id)
                        continue
                    
                    # Construct Messages (Phase 14: Multimodal).
                    # Callers that built a real conversation (system blocks +
                    # transcript + current message — the chat path) pass it
                    # via `messages`; flattening that to prompt+system threw
                    # the transcript away, so follow-up questions referencing
                    # earlier turns were answered blind.
                    if messages:
                        messages = [dict(m) for m in messages]
                    else:
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
                        # RTK compression: compress terminal/tool output in the
                        # prompt before sending to the LLM. Only touches free-
                        # form log/terminal text — structured data (JSON/SQL/API
                        # responses) is detected and skipped entirely. Default
                        # ON (ATOM_COMPRESSION_ENABLED + COMPRESS_RTK_ENABLED).
                        try:
                            from core.llm.compression import get_compression_pipeline
                            _compressed_prompt, _rtk_metrics = (
                                get_compression_pipeline().compress_tool_output(prompt)
                            )
                            if _rtk_metrics.savings_tokens > 0:
                                prompt = _compressed_prompt
                        except Exception:
                            pass  # compression must never break the hot path
                        messages.append({"role": "user", "content": prompt})

                    # Make the request.
                    # asyncio.to_thread: `client` is the SYNC OpenAI SDK, so a
                    # bare call here blocked the event loop for the whole LLM
                    # round trip — one in-flight extraction/chat turn stalled
                    # EVERY concurrent request (observed: ingestion-status
                    # hung 60s while GraphRAG extraction awaited openrouter).
                    response = await _to_thread_safe(
                        client.chat.completions.create,
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=_DEFAULT_COMPLETION_MAX_TOKENS,
                    )
                    self._capture_echoed_model(response)
                    self._stash_last_reasoning(response)

                    result = response.choices[0].message.content
                    finish_reason = getattr(response.choices[0], "finish_reason", None)
                    if _visible_content_missing(result):
                        # An empty visible payload is a FAILED attempt, not a
                        # success: recording it as healthy and returning None
                        # left the chat path with nothing and the provider
                        # ranked ever higher (observed live 2026-09-01).
                        # Raise into the attempt handler so the next ranked
                        # provider takes the turn.
                        try:
                            self.health_monitor.record_call(
                                provider_id, success=False,
                                latency_ms=(time.time() - request_start) * 1000,
                            )
                        except Exception:
                            pass
                        raise _EmptyCompletionError(
                            f"{provider_id}/{model} returned no visible content "
                            f"(finish_reason={finish_reason})"
                        )
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

                            # Fallback to static pricing if dynamic not available
                            if cost is None:
                                cost = get_llm_cost(model, input_tokens, output_tokens)
                                reference_cost = get_llm_cost("gpt-4o", input_tokens, output_tokens)

                            savings_usd = max(0, reference_cost - cost) if (reference_cost is not None and cost is not None) else 0.0

                            # Record even when the cost resolves to 0/None
                            # (unpriced model) — the budget guard enforces from
                            # recorded usage, so skipping would be
                            # unattributed spend.
                            llm_usage_tracker.record(
                                workspace_id=self.workspace_id,
                                provider=provider_id,
                                model=model,
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                                cost_usd=cost or 0.0,
                                savings_usd=savings_usd,
                                agent_id=agent_id,
                                chain_id=chain_id, # Phase 11
                                complexity=complexity.value, # Phase 6.6
                                is_managed_service=is_managed
                            )
                            if cost:
                                logger.info(f"LLM Cost Attributed ({'Managed' if is_managed else 'BYOK'}): {model} - ${cost:.6f} (Saved: ${savings_usd:.6f})")
                            observed_cost = cost
                        except Exception as cost_err:
                            logger.warning(f"Could not attribute LLM cost: {cost_err}")

                        # --- Cache Outcome Recording (Phase 68) ---
                        # Record whether the request hit the prompt cache for future predictions
                        try:
                            # Hash the actual prompt PREFIX (first 1k chars), not just
                            # workspace/provider/model. The old key collapsed every request
                            # for the same (ws, provider, model) onto one history bucket
                            # regardless of prompt, so the cache-hit prediction was global
                            # noise (a cacheable prompt inflated the predicted hit rate for
                            # unrelated prompts). The prefix matches the cache providers'
                            # own prefix-matching behavior and bounds the hash input size.
                            _prompt_prefix = (prompt or "")[:1000]
                            prompt_hash = hashlib.sha256(
                                f"{self.workspace_id}:{provider_id}:{model}:{_prompt_prefix}".encode()
                            ).hexdigest()

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
                    self._track_rate_usage(
                        provider_id,
                        input_tokens=getattr(usage, 'prompt_tokens', 0) if usage else 0,
                        output_tokens=getattr(usage, 'completion_tokens', 0) if usage else 0,
                        model_id=model,
                    )
                    self._track_llm_call(
                        provider=provider_id, model=model, success=True,
                        latency_ms=latency_ms,
                        input_tokens=getattr(usage, 'prompt_tokens', 0) if usage else 0,
                        output_tokens=getattr(usage, 'completion_tokens', 0) if usage else 0,
                        fallback=provider_id != primary_provider,
                        fallback_provider=primary_provider if provider_id != primary_provider else None,
                    )

                    # Learning-router outcome observation (flag-gated, best-effort).
                    # Feeds real response quality (truncation, empty, etc.) into the
                    # per-model predictors so they learn from outcomes, not just
                    # "did the API return". No-op when ATOM_LEARNING_ROUTER is off.
                    await self._record_outcome_feedback(
                        model=model, provider_id=provider_id, task_type=task_type,
                        content=result, finish_reason=finish_reason,
                        success=True, cost=observed_cost, latency_ms=latency_ms,
                        routing_result_id=decision_id_for_feedback,
                    )

                    # Stash the concrete model/provider so generate_completion
                    # can surface the real model (not the "auto" input) in its
                    # return dict — for the model badge and correct feedback keying.
                    self._last_used_model = model
                    self._last_used_provider = provider_id

                    return result

                except Exception as attempt_err:
                    logger.warning(f"Attempt failed for {provider_id}/{model}: {attempt_err}")
                    last_error = attempt_err

                    err_str = str(attempt_err)

                    # Round 80w2: insufficient-balance → model fallback before
                    # skipping the provider. OpenCode Go: free → paid sibling,
                    # then the verified free tier when the paid balance is
                    # exhausted too. OpenRouter: paid → :free variant. Both
                    # gateways serve the same model families from one key; a
                    # budget error on one tier shouldn't kill the request when
                    # another tier works.
                    if provider_id in {"opencode-go", "opencode", "zen", "openrouter"} and _is_insufficient_balance_error(attempt_err):
                        if provider_id in {"opencode-go", "opencode", "zen"}:
                            fallback_chain = _opencode_free_tier_fallbacks(model)
                        else:
                            _orf = _openrouter_free_fallback_model(model)
                            fallback_chain = [_orf] if _orf and _orf != model else []
                        for fallback_model in fallback_chain:
                            if fallback_model == model:
                                continue
                            logger.info(
                                f"Budget exhausted on {provider_id}/{model} — "
                                f"retrying with {fallback_model}"
                            )
                            try:
                                response = await _to_thread_safe(
                                    client.chat.completions.create,
                                    model=fallback_model,
                                    messages=messages,
                                    temperature=temperature,
                                    max_tokens=_DEFAULT_COMPLETION_MAX_TOKENS,
                                )
                                self._capture_echoed_model(response)
                                self._stash_last_reasoning(response)
                                result = response.choices[0].message.content
                                if _visible_content_missing(result):
                                    raise _EmptyCompletionError(
                                        f"fallback {fallback_model} returned no visible content"
                                    )
                                self._last_used_model = fallback_model
                                self._last_used_provider = provider_id
                                logger.info(
                                    f"Fallback succeeded: {provider_id}/{fallback_model}"
                                )
                                return result
                            except Exception as fb_err:
                                logger.warning(
                                    f"Fallback {fallback_model} also failed: {fb_err}"
                                )
                        # All tiers exhausted — skip this provider

                    # Phase 226.4-04: Record failed API call for health monitoring.
                    # Recorded BEFORE the connection-error skip below: connect-level
                    # failures are the strongest dead-provider signal, and this
                    # branch used to `continue` first — the health score stayed
                    # optimistic, the dead provider kept ranking, and every call
                    # re-paid the connect-timeout cascade before failing over.
                    try:
                        latency_ms = (time.time() - request_start) * 1000
                        self.health_monitor.record_call(
                            provider_id, success=False, latency_ms=latency_ms,
                            connection_failure=(
                                "connection error" in err_str.lower()
                                or "refused" in err_str.lower()
                                or "unreachable" in err_str.lower()
                            ),
                        )
                        self._track_llm_call(
                            provider=provider_id, model=model, success=False,
                            latency_ms=latency_ms,
                            fallback=provider_id != primary_provider,
                            fallback_provider=primary_provider if provider_id != primary_provider else None,
                            error=str(attempt_err)[:500],
                        )
                    except Exception:
                        pass  # Don't let health monitoring errors affect primary flow

                    if "401" in err_str or "auth" in err_str.lower() or "invalid" in err_str.lower() or "connection error" in err_str.lower() or "refused" in err_str.lower() or "1000" in err_str:
                        failed_providers.add(provider_id)
                        continue

                    # --- Self-healing autofix (rule-based, single attempt) ---
                    # If this was a repairable 4xx (param rename, unsupported
                    # param, context overflow, etc.), try patching the request
                    # body and retrying ONCE before falling back to the next
                    # provider. Mirrors the structured-response cascade pattern.
                    # ``heal_attempted`` is per-provider so each provider gets
                    # one heal shot.
                    if not heal_attempted_for_current:
                        heal_attempted_for_current = True
                        try:
                            from core.llm.routing.request_healer import get_request_healer
                            healer = get_request_healer()
                            heal_kwargs = {
                                "model": model,
                                "messages": messages,
                                "temperature": temperature,
                                "max_tokens": _DEFAULT_COMPLETION_MAX_TOKENS,
                            }
                            if image_payload and isinstance(messages[-1].get("content"), list):
                                heal_kwargs["messages"] = messages  # multimodal
                            heal_result = healer.heal(attempt_err, heal_kwargs, provider_id, model)
                            if heal_result.patched_kwargs is not None:
                                logger.info(
                                    f"[SelfHeal] retrying {provider_id}/{model} with "
                                    f"patch={heal_result.rule} keys={heal_result.patched_keys}"
                                )
                                try:
                                    response = await _to_thread_safe(
                                        client.chat.completions.create,
                                        **heal_result.patched_kwargs
                                    )
                                    self._capture_echoed_model(response)
                                    self._stash_last_reasoning(response)
                                    result = response.choices[0].message.content
                                    if _visible_content_missing(result):
                                        raise _EmptyCompletionError(
                                            f"healed retry on {model} returned no visible content"
                                        )
                                    finish_reason = getattr(response.choices[0], "finish_reason", None)
                                    logger.info(
                                        f"[SelfHeal] retry SUCCEEDED for {provider_id}/{model} "
                                        f"(rule={heal_result.rule})"
                                    )
                                    # Record success + that a heal was involved.
                                    latency_ms = (time.time() - request_start) * 1000
                                    try:
                                        self.health_monitor.record_call(provider_id, success=True, latency_ms=latency_ms)
                                    except Exception:
                                        pass
                                    self._track_rate_usage(provider_id, model_id=model)
                                    self._track_llm_call(
                                        provider=provider_id, model=model, success=True,
                                        latency_ms=latency_ms,
                                        fallback=provider_id != primary_provider,
                                        fallback_provider=primary_provider if provider_id != primary_provider else None,
                                    )
                                    await self._record_outcome_feedback(
                                        model=model, provider_id=provider_id, task_type=task_type,
                                        content=result, finish_reason=finish_reason,
                                        success=True, cost=None, latency_ms=latency_ms,
                                        routing_result_id=decision_id_for_feedback,
                                    )
                                    self._last_used_model = model
                                    self._last_used_provider = provider_id
                                    return result
                                except Exception as retry_err:
                                    logger.warning(
                                        f"[SelfHeal] retry FAILED for {provider_id}/{model}: "
                                        f"{retry_err} (rule={heal_result.rule})"
                                    )
                                    last_error = retry_err
                        except Exception:
                            logger.debug("[SelfHeal] healer raised; skipping", exc_info=True)

                    # --- OpenCode Go free-usage → paid retry ---
                    # A free-usage model (gateway ID ends in "-free") draws
                    # from the account's FREE allowance, which can be
                    # exhausted even with an active subscription — the gateway
                    # then answers CreditsError / "Insufficient balance" while
                    # paid models would complete fine. Re-issue the SAME
                    # request on the subscription-paid fallback model before
                    # falling back to the next provider.
                    if (
                        provider_id == "opencode-go"
                        and _is_opencode_free_model(model)
                        and _is_insufficient_balance_error(attempt_err)
                    ):
                        paid_model = _opencode_paid_fallback_model(model)
                        if paid_model and paid_model != model:
                            try:
                                response = await _to_thread_safe(
                                    client.chat.completions.create,
                                    model=paid_model,
                                    messages=messages,
                                    temperature=temperature,
                                    max_tokens=_DEFAULT_COMPLETION_MAX_TOKENS,
                                )
                                self._capture_echoed_model(response)
                                self._stash_last_reasoning(response)
                                result = response.choices[0].message.content
                                if _visible_content_missing(result):
                                    raise _EmptyCompletionError(
                                        f"paid retry {paid_model} returned no visible content"
                                    )
                                finish_reason = getattr(response.choices[0], "finish_reason", None)
                                logger.info(
                                    f"OpenCode Go free-model retry SUCCEEDED on paid model "
                                    f"{paid_model} (free {model} hit credit limit)"
                                )
                                latency_ms = (time.time() - request_start) * 1000
                                try:
                                    self.health_monitor.record_call(provider_id, success=True, latency_ms=latency_ms)
                                except Exception:
                                    pass
                                self._track_rate_usage(provider_id, model_id=paid_model)
                                self._track_llm_call(
                                    provider=provider_id, model=paid_model, success=True,
                                    latency_ms=latency_ms,
                                    fallback=provider_id != primary_provider,
                                    fallback_provider=primary_provider if provider_id != primary_provider else None,
                                )
                                await self._record_outcome_feedback(
                                    model=paid_model, provider_id=provider_id, task_type=task_type,
                                    content=result, finish_reason=finish_reason,
                                    success=True, cost=None, latency_ms=latency_ms,
                                    routing_result_id=decision_id_for_feedback,
                                )
                                self._last_used_model = paid_model
                                self._last_used_provider = provider_id
                                return result
                            except Exception as paid_err:
                                logger.warning(
                                    f"OpenCode Go paid retry FAILED for {paid_model}: {paid_err}"
                                )
                                last_error = paid_err

                    # Learning-router outcome observation for failures.
                    await self._record_outcome_feedback(
                        model=model, provider_id=provider_id, task_type=task_type,
                        content=None, finish_reason=None,
                        success=False, cost=None, latency_ms=latency_ms,
                        exception=attempt_err,
                        routing_result_id=decision_id_for_feedback,
                    )
                    continue # Try next provider
            
            logger.error(f"All providers failed. Last error: {last_error}")
            return "I'm sorry, I couldn't generate a response. Please check your API key configuration in Settings or try again."

        except Exception as e:
            logger.error(f"LLM Generation failed: {e}")
            logger.error(f"LLM Generation failed: {e}", exc_info=True)
            return "I'm sorry, an error occurred while generating a response. Please try again."

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
        routing_result_id: Optional[str] = None,
        resolved_model: Optional[str] = None,
    ) -> None:
        """Best-effort outcome observation for the learning router.

        Assess response quality from observable signals (finish_reason, content,
        exception, schema validation) and record it as feedback so per-model
        predictors learn from real outcomes. No-op when
        ``ATOM_LEARNING_ROUTER`` is off or when the router can't be
        instantiated. Never raises — failures are logged and swallowed so the
        hot generation path is unaffected.

        ``routing_result_id``: when provided (stashed by _rerank_with_learning),
        the feedback carries the id so record_feedback recovers the real
        per-decision prompt features — eliminating train/serve skew. When None,
        a random id is used (feedback falls back to task-level feature defaults).

        ``resolved_model``: R82 provider-echoed model ID. When omitted, falls
        back to the per-call contextvar set by ``_capture_echoed_model``.
        Either way, ``(provider_id, model, resolved)`` is fed to the silent-
        bump drift detector — independent of the learning-router flag.
        """
        # R82: silent-bump drift observation (independent of ATOM_LEARNING_ROUTER).
        try:
            from core.llm.model_provenance import (
                get_resolved_model as _cv_resolved,
            )

            effective_resolved = resolved_model or _cv_resolved()
            _get_drift_detector().observe(provider_id, model, effective_resolved or None)
        except Exception:
            pass  # drift detection is best-effort; never blocks generation

        # Stage router outcome join (independent of the learning router flag):
        # when a stage decision is active for this request, write the attempt's
        # outcome back onto the audit row so the calibration script gets
        # cost/quality/latency per decision. Never raises.
        try:
            from core.llm.stage_router import get_stage_decision_carrier, record_stage_outcome

            stage_decision_id = get_stage_decision_carrier()
            if stage_decision_id:
                record_stage_outcome(
                    decision_id=stage_decision_id,
                    success=success,
                    schema_error=schema_error,
                    exception=exception,
                    content=content,
                    finish_reason=finish_reason,
                    actual_cost=cost,
                    actual_latency_ms=latency_ms,
                    actual_model=model,
                    actual_provider=provider_id,
                )
        except Exception:
            pass  # stage outcome is best-effort; never blocks generation

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
            # Use the stashed decision id when available so feedback recovers
            # the real prompt features (train/serve consistency). Fall back to
            # a random id (task-level feature defaults) when re-ranking didn't fire.
            decision_id = routing_result_id or str(uuid.uuid4())
            fb = LearningBasedRouter.build_feedback(
                routing_result_id=decision_id,
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
        intent: Optional[str] = None,
    ) -> list:
        """Re-rank BPC's candidate list using the learned satisfaction signal.

        Only re-orders the existing list — never adds or removes candidates.
        Returns the original list unchanged when the learning router is off,
        when no learned signal exists (no predictor AND no EMA history), or on
        any error. ``options`` is a list of ``(provider_id, model)`` tuples from
        ``get_ranked_providers``.

        ``intent`` is NOT part of the predictor cache key: training
        (record_feedback) carries no intent dimension, so an intent-scoped key
        would never hit a trained predictor (the live path was dead whenever
        ATOM_LEARNING_ROUTER=true). Predictors are tenant/task-scoped, matching
        the route() path. Intent still enters the *feature vector* (one-hot
        ``intent_*`` features) so per-model predictors learn intent-specific
        satisfaction within the tenant/task bucket — train/serve consistent
        because the same features are stashed with the decision and recovered
        at feedback time.
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

            # NOTE: the predictor cache key MUST match the training side
            # (record_feedback -> _retrain_router -> _get_per_model_router),
            # which keys per-model predictors under "{tenant}:{task}" — the
            # feedback pipeline has no intent dimension (RoutingFeedback /
            # llm_routing_feedback carry no intent column). An earlier revision
            # appended ":{intent or '_'}" here as a third dimension, but
            # training never wrote that key, so the live path always missed
            # ("cold start") and ATOM_LEARNING_ROUTER=true never re-ranked —
            # the feature was inert in the production path. The 2-part key
            # keeps predictors tenant/task-scoped, consistent with route().
            # Intent still steers routing as one-hot FEATURES (below), which
            # the feedback pipeline DOES carry (stashed prompt_features).
            cache_key = f"{self.tenant_id or 'default'}:{self._adapt_task_type(task_type)}"
            per_model = learning_router._per_model_routers.get(cache_key)

            # EMA can steer even when NO predictor bucket exists yet (full cold
            # start): the EMA term is evaluated per-candidate below, and the
            # learned_any check decides whether any signal exists at all. This
            # used to early-return here, which made the documented cold-start
            # handoff (EMA carries while predictors are cold) dead on the live
            # path. Only skip when neither predictors nor EMA could contribute.
            from core.llm.learning_router_registry import ema_router_enabled

            use_ema = ema_router_enabled()
            if per_model is None and not use_ema:
                return options  # nothing learned available for this tenant/task

            # Build the prompt features once (the 16-feature contract: 10
            # baseline + 6 intent one-hots). The synthetic request object
            # mirrors RoutingRequest without conversation_context — the
            # extractor reads both defensively (getattr), so this can't throw.
            estimated_tokens = max(1, len(prompt) // 4)
            features = learning_router._extract_request_features(
                type("RR", (), {
                    "task_type": self._adapt_task_type(task_type),
                    "estimated_tokens": estimated_tokens,
                    "requires_reasoning": False,
                    "intent": intent,
                })()
            )

            # Score each candidate by the SAME blend the route() path uses:
            # a learned per-model satisfaction term (confidence-weighted) PLUS,
            # when ATOM_EMA_ROUTER_ENABLED, an EMA/online-telemetry term weighted
            # by (1 - confidence). Previously this live path only ever consulted
            # the predictor and ignored EMA entirely, so the EMA flag had zero
            # effect on production routing. Now EMA drives re-ranking during
            # cold-start (no/weak predictor) and hands off as predictors mature.
            tenant = self.tenant_id or "default"
            task = self._adapt_task_type(task_type)
            ema_weight = getattr(learning_router, "_EMA_SCORE_WEIGHT", 0.3)

            scored = []
            learned_any = False
            for idx, (provider_id, model) in enumerate(options):
                if per_model is None:
                    confidence = 0.0
                    pred_term = 0.0
                else:
                    satisfaction = per_model.predict_satisfaction(model, features)
                    if satisfaction is None:
                        # No predictor for this model.
                        confidence = 0.0
                        pred_term = 0.0
                    else:
                        confidence = per_model.confidence(model)
                        pred_term = confidence * satisfaction
                        if confidence > 0:
                            learned_any = True

                # EMA / online term. Even when the predictor is cold
                # (confidence≈0), observed telemetry can still steer ranking.
                ema_term = 0.0
                if use_ema:
                    ema_key = f"{tenant}:{task}:{model}"
                    ema_data = learning_router._ema_scores.get(ema_key, {})
                    # success is the EMA of (success AND quality_satisfied), in
                    # [0,1]. Missing history -> no EMA contribution for this model.
                    if "success" in ema_data:
                        ema_term = (1.0 - confidence) * ema_weight * ema_data["success"]
                        if ema_data.get("success", 0.0) > 0:
                            learned_any = True

                score = pred_term + ema_term
                if score == 0.0:
                    # No learned signal at all (predictor cold AND no EMA): keep
                    # BPC order via a small negative score so this model sorts
                    # after any learned-favored model but above none.
                    score = -(idx * 0.001)
                scored.append((score, provider_id, model))

            if not learned_any:
                return options  # no predictor had enough data to influence

            # Stable sort by learned score descending (ties keep BPC order).
            scored.sort(key=lambda t: -t[0])
            reranked = [(pid, mdl) for _, pid, mdl in scored]

            # Mint a routing_result_id and stash the prompt features under it
            # so the outcome-observation hook can recover the REAL features
            # (not task-level defaults) when feedback arrives. This closes the
            # train/serve-skew gap: predictors train on the same features used
            # to make the decision. Stash via the router's thread-safe helper —
            # concurrent handlers on the shared singleton otherwise race on the
            # dict (lost updates / iteration crashes during eviction).
            decision_id = learning_router.stash_decision(features)
            self._pending_routing_result_id = decision_id

            logger.info(
                f"[LearningRouter] Re-ranked {len(reranked)} candidates for "
                f"{cache_key} (learned signal applied, decision_id={decision_id[:8]})"
            )
            return reranked
        except Exception as e:
            logger.debug(f"Learning-router re-rank skipped (non-fatal): {e}")
            return options

    def _stash_decision_features(
        self, prompt: str, task_type: Optional[str], intent: Optional[str] = None
    ) -> Optional[str]:
        """Stash this request's prompt features and return a decision id.

        Paths that DON'T re-rank (structured output, streaming) previously
        recorded outcome feedback with a random id, so record_feedback could
        never recover the real prompt features — predictors for those paths
        trained on constant task-level defaults (Bug 2). This mints a
        routing_result_id and stashes the same feature vector the predictor
        contract expects, so feedback from these paths also trains on real
        features. No-op (returns None) when the learning router is off or on
        any error — callers pass the id through and feedback degrades to the
        random-id path unchanged.

        ``intent`` (when given) is encoded as one-hot intent_* features in the
        stashed vector so these paths' predictors learn intent-specific
        satisfaction too. When None, best-effort intent detection runs on the
        prompt (mirrors generate_response) — any failure leaves intent unset
        (all-zero intent features).
        """
        if os.getenv("ATOM_LEARNING_ROUTER", "false").lower() != "true":
            return None
        try:
            if intent is None:
                try:
                    from core.llm.intent_detector import get_intent_detector

                    _ir = get_intent_detector().detect(prompt)
                    if _ir.category is not None and _ir.confidence >= 0.5:
                        intent = _ir.category
                except Exception:
                    logger.debug(
                        "Intent detection failed; continuing without", exc_info=True
                    )
            from core.llm.learning_router_registry import get_learning_router_instance

            learning_router = get_learning_router_instance()
            if learning_router is None:
                return None
            estimated_tokens = max(1, len(prompt) // 4)
            features = learning_router._extract_request_features(
                type("RR", (), {
                    "task_type": self._adapt_task_type(task_type),
                    "estimated_tokens": estimated_tokens,
                    "requires_reasoning": False,
                    "intent": intent,
                })()
            )
            # Stash via the router's thread-safe helper (concurrent handlers on
            # the shared singleton otherwise race on _routing_decisions).
            return learning_router.stash_decision(features)
        except Exception as e:
            logger.debug(f"Stash-decision-features skipped (non-fatal): {e}")
            return None

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

        # R82: reset stale resolved-model echo (same rationale as
        # generate_response's stage-carrier reset).
        try:
            from core.llm.model_provenance import clear_resolved_model

            clear_resolved_model()
        except Exception:
            pass

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

                # generate_response signals failure by returning an apology
                # string rather than raising (its internal fallback). Detect
                # those so escalation can fire on generation failures, not just
                # exceptions (Bug 2): the except block below was unreachable for
                # generation errors because they never raised.
                _GEN_FAILURE_MARKERS = (
                    "i'm sorry, i couldn't generate",
                    "i'm sorry, but an error occurred",
                )
                gen_failed = isinstance(response, str) and any(
                    m in response.lower() for m in _GEN_FAILURE_MARKERS
                )

                if gen_failed:
                    # Treat as an error and let escalation decide (rate-limit /
                    # error branches in should_escalate).
                    should_escalate, reason, target_tier = self.tier_service.handle_escalation(
                        current_tier, None, "generation_failed", False, request_id
                    )
                else:
                    # Phase 68-06: Step 5 - Assess quality and check for
                    # escalation. Previously this passed response_quality=None,
                    # so the QUALITY_THRESHOLD branch never fired and a
                    # truncated/low-quality response was returned as success
                    # every time (Bug 1). Assess the real quality (0-100) and
                    # pass it so quality breaches escalate to a stronger tier.
                    try:
                        from core.llm.response_quality import assess_response_quality
                        rq = assess_response_quality(
                            content=response, finish_reason="stop"
                        )
                        quality_0_100 = (rq.quality_score or 0.0) * 100.0
                    except Exception:
                        quality_0_100 = None
                    should_escalate, reason, target_tier = self.tier_service.handle_escalation(
                        current_tier, quality_0_100, None, False, request_id
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
        provider_model: Optional[tuple] = None,  # R72 F: pin a single (provider, model)
        allow_moa: bool = True,                  # R72 F: opt out of MoA dispatch
        disable_reasoning: bool = False,         # tiny planning calls: skip hidden thinking
        max_tokens: Optional[int] = None,        # explicit structured cap (SC voter passes this)
        stage_decision_id: Optional[str] = None,  # Stage router: audit-row join
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

        R72 Workstream F — Mixture-of-Agents (``allow_moa`` / ``provider_model``):

          When ``allow_moa=True`` (default) AND the global
          ``ATOM_MOA_ENABLED`` flag is on AND this is a genuinely
          hard/irreversible task (COMPLEX/ADVANCED complexity or a
          code/analysis/reasoning task type) with >= 2 candidate providers,
          the handler draws ``ATOM_MOA_SAMPLES`` independent structured
          samples (one per top-ranked provider) then ONE aggregator call to
          synthesize the final answer. MoA replaces the outer cascade loop
          when it fires; each sample still runs with ``cascade`` applied.

          ``provider_model=(provider, model)`` pins the option list to that
          single tuple (used by MoA samples + the aggregator) and disables
          MoA dispatch to prevent recursion. ``allow_moa=False`` opts out of
          MoA entirely (used by the self-consistency voter's own samples).
          Defaults are chosen so an unmodified call is byte-identical to
          pre-R72 behavior (MoA only fires for hard tasks when enabled).

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
            provider_model: Optional ``(provider, model)`` tuple to pin the
                option list to a single provider/model (R72 F).
            allow_moa: Whether Mixture-of-Agents may fire (R72 F; default
                True). Set False to force the single-attempt path.

        Returns:
            Instance of response_model or None if parsing fails
        """
        # Stage router outcome join: stash the decision id on the per-request
        # carrier so _record_outcome_feedback writes the attempt's outcome
        # back onto the audit row (calibration data). Best-effort, never
        # blocks generation.
        try:
            from core.llm.stage_router import set_stage_decision_carrier

            set_stage_decision_carrier(stage_decision_id)
        except Exception:
            pass

        # Check trial/budget restrictions
        if self._is_trial_restricted():
            logger.warning(f"AI Blocked: Trial expired for workspace {self.workspace_id}")
            return None

        # R82: reset stale resolved-model echo before structured attempts.
        try:
            from core.llm.model_provenance import clear_resolved_model

            clear_resolved_model()
        except Exception:
            pass

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
                            temp_provider_id, _ = await self.get_optimal_provider(complexity, task_type, True, tenant_plan, is_managed_service=True)

                            tenant_key = self.byok_manager.get_tenant_api_key(tenant.id, temp_provider_id)
                            if tenant_key:
                                is_managed = False
                            elif self.env_key_providers:
                                # AGPL self-hosted edition: env key = user's own key = BYOK
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
            # Get ranked options — window-aware: the request's own size
            # (learning sections + transcripts can be large) sets the
            # candidate context floor, not just the complexity class.
            estimated_input_tokens = max(
                1000, (len(prompt) + len(system_instruction or "")) // 4
            )
            options = await self.get_ranked_providers(
                complexity, task_type, True, tenant_plan, is_managed,
                requires_tools=True, requires_structured=True,
                estimated_tokens=estimated_input_tokens,
            )

            # R72 Workstream F — MoA recursion guard: when a (provider, model)
            # is pinned, reduce the option list to that single tuple so sample
            # and aggregator calls never re-rank providers. The pin is kept
            # ONLY if the pinned model's window can hold the request: the pin
            # used to bypass every context check, and a learning-heavy prompt
            # overflowed it where the ranker would have chosen a bigger model.
            if provider_model is not None:
                if not self._pinned_model_fits(
                    provider_model[1],
                    estimated_input_tokens + _DEFAULT_COMPLETION_MAX_TOKENS,
                ):
                    logger.warning(
                        f"Unpinning {provider_model[1]} — context window cannot "
                        f"hold ~{estimated_input_tokens} input tokens + completion; "
                        f"re-ranking across all capable providers"
                    )
                    provider_model = None
                else:
                    options = [provider_model]

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

            # --- R72 Workstream F: Mixture-of-Agents dispatch ---
            # MoA replaces the outer cascade loop when it fires. Only for
            # genuinely hard tasks (COMPLEX/ADVANCED or code/analysis/
            # reasoning) with >= 2 candidate providers. Vision and pinned
            # provider_model calls never use MoA (both would distort the
            # sample set / re-trigger recursion).
            from core.hallucination_config import (
                get_moa_samples,
                is_moa_enabled,
            )
            if (
                allow_moa
                and is_moa_enabled()
                and provider_model is None
                and image_payload is None
                and len(options) >= 2
                and self._moa_eligible(complexity, task_type)
            ):
                return await self.generate_structured_moa(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    response_model=response_model,
                    temperature=temperature,
                    task_type=task_type,
                    agent_id=agent_id,
                    chain_id=chain_id,
                    options=options,
                    tenant_plan=tenant_plan,
                    is_managed=is_managed,
                    complexity=complexity,
                    cascade=cascade,
                )

            # Stash prompt features for this decision so the structured-output
            # outcome hook can recover REAL features (not task defaults) when
            # recording feedback. The structured path doesn't re-rank, so without
            # this its feedback trained predictors on constant features (Bug 2).
            structured_decision_id = self._stash_decision_features(prompt, task_type)

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
            primary_provider = cascade_options[0][0] if cascade_options else None
            failed_providers = set()

            while cascade_idx < len(cascade_options):
                provider_id, model = cascade_options[cascade_idx]
                cascade_idx += 1
                if provider_id in failed_providers:
                    continue
                try:
                    # Get the client and wrap with instructor
                    client = self.clients.get(provider_id)
                    if not client:
                        failed_providers.add(provider_id)
                        continue
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

                    _structured_start = time.time()
                    # R83 #6: soft self-consistency — request logprobs and
                    # stamp the parsed model with its mean token logprob so
                    # the voter can weight samples by probability. Default ON
                    # (shadow-only — the vote outcome never changes); strictly
                    # off = byte-identical request and response handling.
                    # A gateway that rejects the ``logprobs`` kwarg gets ONE
                    # retry without it, so soft-SC can never fail a
                    # structured call that would otherwise succeed.
                    _soft_sc_on = False
                    try:
                        from core.hallucination_config import is_sc_soft_enabled
                        _soft_sc_on = is_sc_soft_enabled()
                    except Exception:
                        pass
                    # Completion cap for structured calls. 1000 starved
                    # reasoning models (minimax-m3 burns 750–3,155 tokens
                    # thinking BEFORE the answer): the plan died at
                    # finish_reason='length' with content=None and the whole
                    # structured stage reported "all providers failed"
                    # (observed live on the canvas editor, 2026-08-31). The
                    # cap is a ceiling, not a target — short answers are
                    # unaffected — so default generously and allow override.
                    # An explicit per-call cap (e.g. the SC voter's 500-token
                    # judge samples) wins over the env default.
                    _structured_max_tokens = int(
                        max_tokens) if max_tokens else int(
                        os.getenv("ATOM_STRUCTURED_MAX_TOKENS", "6000")
                    )
                    _create_kwargs = dict(
                        model=model,
                        response_model=response_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=_structured_max_tokens,
                    )
                    if disable_reasoning:
                        # OpenRouter unified reasoning switch: a reasoning
                        # model burns 1,200–2,000 hidden tokens (30–60s)
                        # BEFORE a 60-line planning answer — measured on
                        # minimax-m3 for the canvas editor + tool planner
                        # (2026-09-01). Planning prompts need no thinking;
                        # this turns minute-long stages into seconds.
                        # extra_body, because the typed SDK create() rejects
                        # provider-extension kwargs directly.
                        _create_kwargs["extra_body"] = {
                            "reasoning": {"enabled": False, "exclude": True},
                        }
                    _logprobs_key = f"{provider_id}/{model}"
                    if _soft_sc_on and _logprobs_key not in _LOGPROBS_UNSUPPORTED:
                        _create_kwargs["logprobs"] = True
                    try:
                        # to_thread: instructor here wraps the SYNC client — a
                        # bare call blocked the loop for the whole structured
                        # round trip (same starvation as generate_response).
                        result = await _to_thread_safe(
                            instructor_client.chat.completions.create, **_create_kwargs
                        )
                    except Exception as _reasoning_reject:
                        # Some endpoints run reasoning-mandatory models and
                        # reject the disable switch with a 400 ("Reasoning is
                        # mandatory for this endpoint"). Retry once WITHOUT
                        # the extra_body rather than failing the stage.
                        if "reasoning" in str(_reasoning_reject).lower() and _create_kwargs.get("extra_body"):
                            _create_kwargs.pop("extra_body", None)
                            result = await _to_thread_safe(
                                instructor_client.chat.completions.create, **_create_kwargs
                            )
                        else:
                            raise
                    except Exception as _soft_exc:
                        if not _soft_sc_on or "logprobs" not in _create_kwargs:
                            raise
                        _create_kwargs.pop("logprobs", None)
                        if "logprobs are not supported" in str(_soft_exc).lower():
                            _LOGPROBS_UNSUPPORTED.add(_logprobs_key)
                        logger.warning(
                            f"soft-SC logprobs request failed for {provider_id}/{model} "
                            f"({_soft_exc}); retrying once without logprobs"
                        )
                        result = await _to_thread_safe(
                            instructor_client.chat.completions.create, **_create_kwargs
                        )
                    self._capture_echoed_model(result)  # reads _raw_response.model
                    _structured_latency_ms = (time.time() - _structured_start) * 1000.0
                    if _soft_sc_on:
                        # Best-effort — no stamp ⇒ voter weight 1.0.
                        try:
                            self._stamp_sample_logprob(result)
                        except Exception:
                            pass
                    # Instructor wraps the underlying response; finish_reason
                    # may be on the raw response. Default to "stop" only when
                    # unavailable (the API succeeded structurally).
                    _structured_finish = "stop"
                    try:
                        _raw = getattr(result, "_raw_response", None)
                        if _raw is not None:
                            _fr = getattr(_raw, "finish_reason", None) or getattr(
                                getattr(_raw, "choices", [{}])[0] if getattr(_raw, "choices", None) else {},
                                "finish_reason", None,
                            )
                            if _fr:
                                _structured_finish = _fr
                    except Exception:
                        pass

                    # --- Record Usage (Phase 6.6) ---
                    _structured_cost = None  # surfaced to the feedback call below
                    try:
                        # Instructor attaches usage to the response object metadata.
                        # Never index into raw_response when it lacks `.usage`
                        # (providers/mocks may omit it) — an AttributeError here
                        # used to leave `usage` unbound and kill the whole
                        # structured attempt with a confusing NameError.
                        raw_response = getattr(result, "_raw_response", None)
                        usage = getattr(raw_response, "usage", None) if raw_response is not None else None
                        if not usage and hasattr(result, "usage"):
                             usage = result.usage

                        if usage:
                            input_tokens = usage.prompt_tokens
                            output_tokens = usage.completion_tokens
                            self._track_rate_usage(provider_id, input_tokens, output_tokens,
                                                   model_id=model)

                            fetcher = get_pricing_fetcher()
                            cost = fetcher.estimate_cost(model, input_tokens, output_tokens)
                            if cost is None:
                                cost = get_llm_cost(model, input_tokens, output_tokens)
                            _structured_cost = cost

                            # Record even when the cost resolves to 0/None
                            # (unpriced model) — the budget guard enforces
                            # from recorded usage, so skipping would be
                            # unattributed spend.
                            llm_usage_tracker.record(
                                workspace_id=self.workspace_id,
                                provider=provider_id,
                                model=model,
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                                cost_usd=cost or 0.0,
                                agent_id=agent_id,
                                chain_id=chain_id, # Phase 11
                                complexity=complexity.value,
                                is_managed_service=is_managed
                            )
                    except Exception as cost_err:
                        logger.warning(f"Could not attribute structured LLM cost: {cost_err}")

                    # Per-call provider usage tracking (always recorded on
                    # structured success, even when usage is unavailable).
                    self._track_llm_call(
                        provider=provider_id, model=model, success=True,
                        latency_ms=_structured_latency_ms,
                        input_tokens=getattr(usage, 'prompt_tokens', 0) if usage else 0,
                        output_tokens=getattr(usage, 'completion_tokens', 0) if usage else 0,
                        fallback=provider_id != primary_provider,
                        fallback_provider=primary_provider if provider_id != primary_provider else None,
                    )

                    # Learning-router outcome observation (structured success).
                    # Pass the REAL finish_reason/latency/cost so predictors can
                    # learn "model X truncates structured output" / "model Y is
                    # slow" — previously these were hardcoded (stop/0.0/None),
                    # making structured-output feedback useless for learning.
                    await self._record_outcome_feedback(
                        model=model, provider_id=provider_id, task_type=task_type,
                        content=str(result), finish_reason=_structured_finish,
                        success=True, cost=_structured_cost, latency_ms=_structured_latency_ms,
                        schema_error=False,
                        routing_result_id=structured_decision_id,
                    )
                    return result
                except Exception as attempt_err:
                    logger.warning(f"Structured attempt failed for {provider_id}/{model}: {attempt_err}")
                    last_error = attempt_err

                    err_str = str(attempt_err)
                    # Record failed structured call for health monitoring.
                    # The structured cascade never fed the health monitor, so
                    # connection-dead providers stayed optimistically healthy,
                    # kept ranking, and re-paid the connect-timeout cascade on
                    # every call (observed 2026-08-31 on chat turns).
                    _is_conn_fail = (
                        "connection error" in err_str.lower()
                        or "refused" in err_str.lower()
                        or "unreachable" in err_str.lower()
                    )
                    try:
                        self.health_monitor.record_call(
                            provider_id, success=False, latency_ms=0.0,
                            connection_failure=_is_conn_fail,
                        )
                    except Exception:
                        pass  # Don't let health monitoring errors affect primary flow
                    if "401" in err_str or "auth" in err_str.lower() or "invalid" in err_str.lower() or "connection error" in err_str.lower() or "refused" in err_str.lower() or "1000" in err_str:
                        failed_providers.add(provider_id)
                        continue
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
                    # Per-call provider usage tracking (structured failure).
                    # Schema failures count as failed calls (matching the
                    # learning-router convention); everything else is a
                    # provider failure with the error surfaced.
                    self._track_llm_call(
                        provider=provider_id, model=model, success=not is_schema_err,
                        latency_ms=0.0,
                        fallback=provider_id != primary_provider,
                        fallback_provider=primary_provider if provider_id != primary_provider else None,
                        error=str(attempt_err)[:500],
                    )
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
                        routing_result_id=structured_decision_id,
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


    def _moa_eligible(self, complexity: QueryComplexity, task_type: Optional[str]) -> bool:
        """MoA is worth its N-1 extra LLM calls only on genuinely hard tasks."""
        if complexity in (QueryComplexity.COMPLEX, QueryComplexity.ADVANCED):
            return True
        if task_type and task_type.lower() in {"code", "analysis", "reasoning"}:
            return True
        return False

    @staticmethod
    def _render_sample(sample: Any) -> str:
        """Serialize a structured sample for the aggregator prompt."""
        try:
            if hasattr(sample, "model_dump"):
                return json.dumps(sample.model_dump(), default=str)
            if hasattr(sample, "dict"):
                return json.dumps(sample.dict(), default=str)
        except Exception:
            pass
        return str(sample)

    @staticmethod
    def _build_moa_aggregator_prompt(
        prompt: str, samples: List[Any], agreement: Optional[float] = None
    ) -> str:
        """Concatenate the original request + N candidate answers so the
        aggregator can reconcile them into a single best structured answer.

        ``agreement`` (P4a confidence-modulated update): the consensus ratio
        across the sample pool modulates the aggregation instruction — high
        agreement → harmonize without inventing; low agreement → resolve the
        contradictions explicitly. None (or default) → legacy instruction.
        """
        parts = [
            "[MIXTURE-OF-AGENTS]: synthesize the single best final answer from "
            "the candidate answers below. Produce exactly one answer of the "
            "requested form.\n\n[USER REQUEST]:\n" + prompt,
        ]
        if agreement is not None:
            if agreement >= 0.75:
                parts.insert(
                    1,
                    "[CONSENSUS]: the candidates agree strongly ("
                    f"{agreement:.0%}). Harmonize them into one coherent "
                    "answer WITHOUT introducing new claims or details.",
                )
            elif agreement < 0.5:
                parts.insert(
                    1,
                    "[CONSENSUS]: the candidates disagree substantially ("
                    f"{agreement:.0%}). Identify and resolve the contradictions "
                    "explicitly; say which evidence you weighted and why.",
                )
            else:
                parts.insert(
                    1,
                    f"[CONSENSUS]: candidates partially agree ({agreement:.0%}). "
                    "Reconcile differences; prefer the majority view where "
                    "evidence is ambiguous.",
                )
        for i, sample in enumerate(samples, start=1):
            parts.append(f"\n[CANDIDATE ANSWER {i}]:\n{BYOKHandler._render_sample(sample)}")
        return "\n".join(parts)

    async def generate_structured_moa(
        self,
        prompt: str,
        system_instruction: str,
        response_model: Any,
        temperature: float,
        task_type: Optional[str],
        agent_id: Optional[str],
        chain_id: Optional[str],
        options: List[tuple],
        tenant_plan: str,
        is_managed: bool,
        complexity: QueryComplexity,
        cascade: bool,
    ) -> Any:
        """Mixture-of-Agents for hard structured tasks (R72 Workstream F).

        Draws ``min(ATOM_MOA_SAMPLES, len(options))`` independent samples,
        one per top-ranked ``(provider, model)`` pair, then ONE aggregator
        call on the best-ranked provider to synthesize the final answer.

        Each sample runs the FULL normal path (cascade, cost tracking, outcome
        feedback) via ``generate_structured_response`` with a pinned
        ``provider_model`` and ``allow_moa=False`` (no recursion). The
        aggregator is a final pinned call that sees all candidate answers.
        Aggregator failure degrades to the best-ranked valid sample.

        Returns ``None`` only when every sample AND the aggregator failed.
        """
        from core.hallucination_config import get_moa_samples, is_moa_diversity_enabled
        from core.llm.self_consistency_voter import SelfConsistencyVoter

        n = min(get_moa_samples(), len(options))
        sample_specs = options[:n]  # best-ranked first

        # P4a (W3): diversity-aware init — per-sample perspective overlays
        # (arXiv 2601.19921), disabled by default (kill-switch parity).
        overlays = SelfConsistencyVoter.diversity_overlays(
            n, enabled=is_moa_diversity_enabled()
        )

        async def _sample(pair, idx: int) -> Any:
            provider_id, model = pair
            overlay = overlays[idx] if idx < len(overlays) else ""
            sample_sys = f"{system_instruction}\n\n{overlay}" if overlay else system_instruction
            try:
                return await self.generate_structured_response(
                    prompt=prompt,
                    system_instruction=sample_sys,
                    response_model=response_model,
                    temperature=temperature,
                    task_type=task_type,
                    agent_id=agent_id,
                    chain_id=chain_id,
                    image_payload=None,
                    cascade=cascade,
                    provider_model=pair,
                    allow_moa=False,
                )
            except Exception as e:
                logger.warning(f"MoA sample failed for {provider_id}/{model}: {e}")
                return None

        samples = await asyncio.gather(*[_sample(p, i) for i, p in enumerate(sample_specs)])
        valid = [s for s in samples if s is not None]
        if not valid:
            return None
        if len(valid) == 1:
            return valid[0]

        # P4a (W3): confidence-modulated update — the consensus ratio across
        # the sample pool modulates the aggregation instruction (high
        # agreement → harmonize, low → resolve contradictions explicitly).
        agreement: Optional[float] = None
        try:
            hashes = [SelfConsistencyVoter._hash_sample(s) for s in valid]
            agreement = max(hashes.count(h) for h in hashes) / len(valid)
            logger.info(
                f"MoA sample consensus: agreement={agreement:.2f} "
                f"({len(valid)} valid samples)"
            )
        except Exception as e:
            logger.debug(f"MoA agreement computation skipped: {e}")

        # Post-hoc irreversibility audit: if the consensus looks destructive,
        # surface it for observability. Callers already gate irreversible
        # actions via self-consistency; MoA only records the evidence.
        try:
            if SelfConsistencyVoter.is_irreversible(valid[0]):
                logger.info(
                    f"MoA consensus for workspace {self.workspace_id} looks "
                    f"irreversible (audit only)"
                )
        except Exception:
            pass

        # Aggregator: reconcile candidate answers on the best-ranked provider.
        aggregated_prompt = self._build_moa_aggregator_prompt(prompt, valid, agreement=agreement)
        aggregator_result = await self.generate_structured_response(
            prompt=aggregated_prompt,
            system_instruction=system_instruction,
            response_model=response_model,
            temperature=temperature,
            task_type=task_type,
            agent_id=agent_id,
            chain_id=chain_id,
            image_payload=None,
            cascade=cascade,
            provider_model=sample_specs[0],
            allow_moa=False,
        )
        if aggregator_result is not None:
            return aggregator_result
        # Graceful degradation: best-ranked valid sample wins.
        return valid[0]

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
            comparison = fetcher.compare_providers()
            if comparison:
                return comparison
            # An EMPTY result is as unusable as a failed fetch (e.g. the price
            # cache holds only zero-cost entries) — fall through to the static
            # table so the pricing surface never renders an empty comparison.
            logger.warning("No dynamic provider comparison data; using static fallback")
        except Exception as e:
            logger.warning(f"Could not get provider comparison: {e}")
        # Static fallback
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

            response = await _to_thread_safe(
                client.chat.completions.create,
                model=model,
                messages=messages,
                max_tokens=500
            )
            self._capture_echoed_model(response)

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
        db = None,
        task_type: Optional[str] = "chat",
        extra_kwargs: Optional[Dict[str, Any]] = None,
        reasoning_sink: Optional[Dict[str, Any]] = None,
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
            extra_kwargs: Extra kwargs forwarded to the provider stream call
                (e.g. ``stop``/``top_p`` — previously silently dropped, so the
                gateway's streaming requests could not honor stop sequences).
            reasoning_sink: Optional dict. When provided, chain-of-thought
                deltas (``delta.reasoning`` / ``reasoning_content`` /
                ``thinking`` — provider-dependent) are APPENDED to
                ``reasoning_sink["deltas"]`` instead of being dropped. Existing
                callers that don't pass it are unaffected: the yield contract
                (visible content tokens only) is unchanged.

        Yields:
            Individual tokens as they arrive from the LLM
        """
        if not self.async_clients and not self.clients:
            raise ValueError("No available providers. No clients initialized. Streaming unavailable.")

        # Get provider fallback order
        provider_order = self._get_provider_fallback_order(provider_id)

        if not provider_order:
            raise ValueError(f"No available providers for streaming. Requested: {provider_id}")

        primary_provider = provider_order[0] if provider_order else None

        # Stash prompt features for this decision so the streaming outcome hook
        # can recover REAL features (not task defaults) when recording feedback.
        # The streaming path doesn't re-rank, so without this its feedback
        # trained predictors on constant features (Bug 2). Derive a prompt
        # string from the last user message for feature extraction.
        stream_prompt = ""
        for _m in reversed(messages):
            if isinstance(_m, dict) and _m.get("role") == "user":
                stream_prompt = str(_m.get("content", ""))
                break
        stream_decision_id = self._stash_decision_features(stream_prompt, task_type)

        # P4 prompt-taint gate (shadow by default; blocks under enforce).
        _taint_block = self._llm_taint_check(
            stream_prompt, primary_provider or "", model
        )
        if _taint_block:
            yield f"Error: {_taint_block}"
            return

        # Governance tracking
        governance_enabled = os.getenv("STREAMING_GOVERNANCE_ENABLED", "true").lower() == "true"
        agent_execution = None

        last_error = None

        # Try each provider in fallback order
        for attempt_provider_id in provider_order:
            # Per-provider flag: at most one self-heal stream retry.
            heal_attempted_stream = False
            # Get client for this provider (prefer async, fallback to sync)
            client = self.async_clients.get(attempt_provider_id)
            if not client:
                client = self.clients.get(attempt_provider_id)

            if not client:
                logger.warning(f"No client available for provider: {attempt_provider_id}")
                continue

            # Skip fallback providers that don't serve this model — cross-
            # provider streaming fallback previously retried the SAME model
            # name on incompatible providers (e.g. 'gpt-4o' on Anthropic),
            # which 404s and wastes the attempt (Bug 14). The requested
            # primary provider is always tried regardless (the caller asked
            # for it explicitly and may know something the heuristic doesn't).
            if attempt_provider_id != provider_id and not self._provider_serves_model(
                attempt_provider_id, model
            ):
                logger.debug(
                    f"Skipping stream fallback to {attempt_provider_id}: does not serve model '{model}'"
                )
                continue

            logger.info(f"Attempting stream with provider: {attempt_provider_id} (requested: {provider_id})")

            try:
                import time
                request_start = time.time()
                # True once any token has been yielded — a mid-stream failure
                # must NOT re-issue the request (would duplicate content).
                _tokens_yielded = False
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
                create_kwargs: Dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                }
                if extra_kwargs:
                    create_kwargs.update(
                        {k: v for k, v in extra_kwargs.items() if v is not None}
                    )
                stream = await client.chat.completions.create(**create_kwargs)

                token_count = 0
                # Accumulate streamed content (capped) so the outcome hook can
                # assess real quality (truncation/refusal/empty) instead of the
                # literal placeholder "(streamed)", which always scored 0.7 and
                # masked truncation. Cap keeps memory bounded for long streams.
                _stream_content_parts = []
                _stream_content_chars = 0
                _STREAM_CONTENT_CAP = 4000
                _stream_finish_reason = None
                async for chunk in stream:
                    if chunk.choices:
                        choice = chunk.choices[0]
                        delta = choice.delta
                        # Chain-of-thought deltas ride a separate field
                        # (provider-dependent name) and were previously
                        # dropped on the floor. Capture into the caller's
                        # sink when one is provided; the visible-content
                        # yield contract is untouched.
                        if reasoning_sink is not None:
                            _rdelta = self._reasoning_from_message(delta)
                            if _rdelta:
                                reasoning_sink.setdefault("deltas", []).append(_rdelta)
                        if hasattr(delta, 'content') and delta.content:
                            token_count += 1
                            if _stream_content_chars < _STREAM_CONTENT_CAP:
                                _stream_content_parts.append(delta.content)
                                _stream_content_chars += len(delta.content)
                            _tokens_yielded = True
                            yield delta.content
                        # Capture the real finish_reason from the final chunk
                        # (OpenAI/compatible APIs populate it on the last choice).
                        fr = getattr(choice, "finish_reason", None)
                        if fr:
                            _stream_finish_reason = fr

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
                self._track_rate_usage(attempt_provider_id, output_tokens=token_count,
                                       model_id=model)
                self._track_llm_call(
                    provider=attempt_provider_id, model=model, success=True,
                    latency_ms=latency_ms, output_tokens=token_count,
                    fallback=attempt_provider_id != primary_provider,
                    fallback_provider=primary_provider if attempt_provider_id != primary_provider else None,
                )

                # Learning-router outcome observation (streaming success).
                # Pass the accumulated content + real finish_reason so quality
                # assessment can detect truncation/refusal/empty on streams
                # (previously hardcoded "(streamed)"/"stop" masked all of these).
                await self._record_outcome_feedback(
                    model=model, provider_id=attempt_provider_id, task_type=task_type,
                    content="".join(_stream_content_parts),
                    finish_reason=_stream_finish_reason or "stop",
                    success=True, cost=None, latency_ms=latency_ms,
                    routing_result_id=stream_decision_id,
                )

                # Success! Return from the function
                return

            except Exception as e:
                last_error = e
                logger.warning(f"Streaming failed for {attempt_provider_id}/{model}: {e}")

                # Phase 226.4-04: Record failed streaming API call for health monitoring
                try:
                    latency_ms = (time.time() - request_start) * 1000
                    self.health_monitor.record_call(attempt_provider_id, success=False, latency_ms=latency_ms,
                                                    connection_failure=(
                                                        "connection error" in str(e).lower()
                                                        or "refused" in str(e).lower()
                                                        or "unreachable" in str(e).lower()
                                                    ))
                    self._track_llm_call(
                        provider=attempt_provider_id, model=model, success=False,
                        latency_ms=latency_ms,
                        fallback=attempt_provider_id != primary_provider,
                        fallback_provider=primary_provider if attempt_provider_id != primary_provider else None,
                        error=str(e)[:500],
                    )
                except Exception:                     pass  # Don't let health monitoring errors affect primary flow

                # --- Self-healing autofix (rule-based, single attempt) ---
                # For repairable 4xx errors only. Retries the stream creation
                # with a patched body once before falling back to the next
                # provider. Heal is only attempted on the initial stream
                # creation failure (before any tokens were yielded), never
                # mid-stream.
                if not heal_attempted_stream:
                    heal_attempted_stream = True
                    try:
                        from core.llm.routing.request_healer import get_request_healer
                        healer = get_request_healer()
                        heal_kwargs = {
                            "model": model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                            "stream": True,
                        }
                        heal_result = healer.heal(e, heal_kwargs, attempt_provider_id, model)
                        if heal_result.patched_kwargs is not None:
                            logger.info(
                                f"[SelfHeal-stream] retrying {attempt_provider_id}/{model} "
                                f"with patch={heal_result.rule} keys={heal_result.patched_keys}"
                            )
                            try:
                                stream = await client.chat.completions.create(
                                    **heal_result.patched_kwargs
                                )
                                logger.info(
                                    f"[SelfHeal-stream] retry SUCCEEDED for "
                                    f"{attempt_provider_id}/{model} (rule={heal_result.rule})"
                                )
                                # The patched stream succeeded — fall through to
                                # the normal streaming loop below by re-running
                                # the token iteration. We can't easily re-enter
                                # the try block, so yield from the patched stream
                                # inline and return on success.
                                token_count = 0
                                _stream_content_parts = []
                                _stream_content_chars = 0
                                _STREAM_CONTENT_CAP = 4000
                                _stream_finish_reason = None
                                async for chunk in stream:
                                    if chunk.choices:
                                        choice = chunk.choices[0]
                                        delta = choice.delta
                                        if hasattr(delta, 'content') and delta.content:
                                            token_count += 1
                                            if _stream_content_chars < _STREAM_CONTENT_CAP:
                                                _stream_content_parts.append(delta.content)
                                                _stream_content_chars += len(delta.content)
                                            _tokens_yielded = True
                                            yield delta.content
                                        if getattr(choice, 'finish_reason', None):
                                            _stream_finish_reason = choice.finish_reason
                                latency_ms = (time.time() - request_start) * 1000
                                try:
                                    self.health_monitor.record_call(attempt_provider_id, success=True, latency_ms=latency_ms)
                                except Exception:
                                    pass
                                self._track_rate_usage(attempt_provider_id, output_tokens=token_count,
                                                       model_id=model)
                                self._track_llm_call(
                                    provider=attempt_provider_id, model=model, success=True,
                                    latency_ms=latency_ms, output_tokens=token_count,
                                    fallback=attempt_provider_id != primary_provider,
                                    fallback_provider=primary_provider if attempt_provider_id != primary_provider else None,
                                )
                                await self._record_outcome_feedback(
                                    model=model, provider_id=attempt_provider_id, task_type=task_type,
                                    content="".join(_stream_content_parts),
                                    finish_reason=_stream_finish_reason or "stop",
                                    success=True, cost=None, latency_ms=latency_ms,
                                    routing_result_id=stream_decision_id,
                                )
                                return
                            except Exception as retry_err:
                                logger.warning(
                                    f"[SelfHeal-stream] retry FAILED for "
                                    f"{attempt_provider_id}/{model}: {retry_err} "
                                    f"(rule={heal_result.rule})"
                                )
                                last_error = retry_err
                    except Exception:
                        logger.debug("[SelfHeal-stream] healer raised; skipping", exc_info=True)

                # --- OpenCode Go free-usage → paid retry (streaming) ---
                # Mirrors the non-streaming retry: a free-usage model
                # (gateway ID ends in "-free") draws from the account's FREE
                # allowance, which can be exhausted even with an ACTIVE
                # subscription — the gateway then answers CreditsError /
                # "Insufficient balance" while paid models would complete
                # fine. Re-issue the SAME streaming request on the paid
                # fallback model before falling back to the next provider.
                # Only when the failure happened BEFORE any token was
                # yielded — a mid-stream error must not duplicate content.
                if (
                    not _tokens_yielded
                    and attempt_provider_id == "opencode-go"
                    and _is_opencode_free_model(model)
                    and _is_insufficient_balance_error(e)
                ):
                    paid_model = _opencode_paid_fallback_model(model)
                    if paid_model and paid_model != model:
                        try:
                            retry_kwargs: Dict[str, Any] = {
                                "model": paid_model,
                                "messages": messages,
                                "temperature": temperature,
                                "max_tokens": max_tokens,
                                "stream": True,
                            }
                            if extra_kwargs:
                                retry_kwargs.update(
                                    {k: v for k, v in extra_kwargs.items() if v is not None}
                                )
                            stream = await client.chat.completions.create(**retry_kwargs)
                            logger.info(
                                f"OpenCode Go free-model stream retry started on paid model "
                                f"{paid_model} (free {model} hit credit limit)"
                            )
                            token_count = 0
                            _stream_content_parts = []
                            _stream_content_chars = 0
                            _STREAM_CONTENT_CAP = 4000
                            _stream_finish_reason = None
                            async for chunk in stream:
                                if chunk.choices:
                                    choice = chunk.choices[0]
                                    delta = choice.delta
                                    if hasattr(delta, 'content') and delta.content:
                                        token_count += 1
                                        if _stream_content_chars < _STREAM_CONTENT_CAP:
                                            _stream_content_parts.append(delta.content)
                                            _stream_content_chars += len(delta.content)
                                        yield delta.content
                                    if getattr(choice, 'finish_reason', None):
                                        _stream_finish_reason = choice.finish_reason
                            latency_ms = (time.time() - request_start) * 1000
                            try:
                                self.health_monitor.record_call(attempt_provider_id, success=True, latency_ms=latency_ms)
                            except Exception:
                                pass
                            self._track_rate_usage(attempt_provider_id, output_tokens=token_count,
                                                   model_id=paid_model)
                            self._track_llm_call(
                                provider=attempt_provider_id, model=paid_model, success=True,
                                latency_ms=latency_ms, output_tokens=token_count,
                                fallback=attempt_provider_id != primary_provider,
                                fallback_provider=primary_provider if attempt_provider_id != primary_provider else None,
                            )
                            await self._record_outcome_feedback(
                                model=paid_model, provider_id=attempt_provider_id, task_type=task_type,
                                content="".join(_stream_content_parts),
                                finish_reason=_stream_finish_reason or "stop",
                                success=True, cost=None, latency_ms=latency_ms,
                                routing_result_id=stream_decision_id,
                            )
                            return
                        except Exception as retry_err:
                            logger.warning(
                                f"OpenCode Go free-model stream retry FAILED on paid model "
                                f"{paid_model}: {retry_err}"
                            )
                            last_error = retry_err

                # Learning-router outcome observation (streaming failure).
                await self._record_outcome_feedback(
                    model=model, provider_id=attempt_provider_id, task_type=task_type,
                    content=None, finish_reason=None,
                    success=False, cost=None, latency_ms=0.0,
                    exception=e,
                    routing_result_id=stream_decision_id,
                )

                # If this is not the last provider, try the next one
                if attempt_provider_id != provider_order[-1]:
                    logger.info(f"Falling back to next provider...")
                    continue

                # This was the last provider, fall through to error handling
                break

        # All providers failed — mark execution as failed and yield error.
        # #4 fix: wrap post-loop error path so CancelledError (client
        # disconnect, a BaseException) still cleans up the execution record.
        try:
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
            yield "\n\n[Error: All LLM providers failed. Please check your API key configuration and try again.]"
        except BaseException:
            # Client disconnect / CancelledError: mark execution as failed.
            if agent_execution is not None and getattr(agent_execution, 'status', None) == "running":
                try:
                    agent_execution.status = "failed"
                    agent_execution.error_message = "Stream interrupted"
                    agent_execution.completed_at = datetime.now(timezone.utc)
                    db.commit()
                except Exception:
                    pass
            raise

    async def chat_completion(
        self,
        messages: List[Dict],
        model: str,
        provider_id: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        task_type: Optional[str] = "chat",
        agent_id: Optional[str] = None,
        extra_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Non-streaming chat completion with fallback + self-heal (gateway).

        Mirrors ``stream_completion``'s fallback/heal shape but returns a full
        OpenAI-compatible completion dict instead of yielding tokens. The full
        message history is passed through untouched (no flattening) so
        multi-turn gateway callers (Claude Code, Hermes, OpenAI-SDK apps) get
        correct context.

        Args:
            messages: Chat messages in OpenAI format (full history).
            model: Model name.
            provider_id: Primary provider identifier.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            task_type: Task type hint (for routing/feedback).
            agent_id: Optional agent ID for cost tracking.
            extra_kwargs: Extra kwargs forwarded to the provider (e.g. ``stop``).

        Returns:
            OpenAI-shaped completion dict with ``choices`` and ``usage``.

        Raises:
            GatewayBlockedError: Trial expired or budget exceeded.
            ValueError: No clients / no providers configured.
            AllProvidersFailedError: Every provider in the fallback chain failed.
        """
        if not self.async_clients and not self.clients:
            raise ValueError("No available providers. No clients initialized. Completion unavailable.")

        # Hard guards (mapped to 429 by the gateway).
        # FAIL CLOSED: if the budget/trial tracker is unavailable (DB error,
        # import failure, etc.) we cannot confirm the workspace is within
        # budget — block the request rather than silently allowing unbounded
        # spend. Previously this swallowed the tracker exception via
        # ``except Exception: pass``, disabling the only spend guard on the
        # gateway path.
        try:
            if llm_usage_tracker.is_budget_exceeded(self.workspace_id):
                raise GatewayBlockedError("budget_exceeded", "Budget exceeded")
        except GatewayBlockedError:
            raise
        except Exception as tracker_err:
            logger.error(
                f"Budget tracker unavailable for workspace {self.workspace_id}; "
                f"blocking request (fail-closed): {tracker_err}"
            )
            raise GatewayBlockedError(
                "budget_check_failed",
                "Unable to verify budget status. Please try again.",
            )
        trial_check = getattr(llm_usage_tracker, "is_trial_expired", None)
        if callable(trial_check):
            try:
                if trial_check(self.workspace_id):
                    raise GatewayBlockedError("trial_expired", "Trial expired")
            except GatewayBlockedError:
                raise
            except Exception as trial_err:
                logger.warning(
                    f"Trial check failed for workspace {self.workspace_id} "
                    f"(allowing — trial gate is advisory): {trial_err}"
                )

        provider_order = self._get_provider_fallback_order(provider_id)
        if not provider_order:
            raise ValueError(f"No available providers for completion. Requested: {provider_id}")

        last_error: Optional[Exception] = None
        prompt_str = ""
        for _m in reversed(messages):
            if isinstance(_m, dict) and _m.get("role") == "user":
                content = _m.get("content", "")
                prompt_str = content if isinstance(content, str) else str(content)
                break
        decision_id = self._stash_decision_features(prompt_str, task_type)

        # P4 prompt-taint gate (shadow by default; GatewayBlockedError maps to
        # a 4xx by the gateway's error mapping).
        _taint_block = self._llm_taint_check(
            prompt_str, provider_id, model
        )
        if _taint_block:
            raise GatewayBlockedError("taint_blocked", _taint_block)

        base_kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if extra_kwargs:
            base_kwargs.update({k: v for k, v in extra_kwargs.items() if v is not None})

        primary_provider = provider_order[0] if provider_order else None
        for attempt_provider_id in provider_order:
            heal_attempted = False
            client = self.async_clients.get(attempt_provider_id)
            if not client:
                client = self.clients.get(attempt_provider_id)
            if not client:
                logger.warning(f"No client available for provider: {attempt_provider_id}")
                continue

            # Skip fallback providers that don't serve this model (same
            # heuristic as stream_completion). The requested primary is always
            # tried regardless.
            if attempt_provider_id != provider_id and not self._provider_serves_model(
                attempt_provider_id, model
            ):
                logger.debug(
                    f"Skipping fallback to {attempt_provider_id}: does not serve model '{model}'"
                )
                continue

            logger.info(f"Attempting completion with provider: {attempt_provider_id} (requested: {provider_id})")
            try:
                request_start = datetime.now()
                response = await client.chat.completions.create(**base_kwargs)
                self._capture_echoed_model(response)
                latency_ms = (datetime.now() - request_start).total_seconds() * 1000.0

                choice = response.choices[0] if getattr(response, "choices", None) else None
                content = ""
                if choice is not None:
                    content = getattr(choice.message, "content", "") or ""
                finish_reason = getattr(choice, "finish_reason", None) or "stop"

                usage = getattr(response, "usage", None)
                prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
                completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
                total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)

                cost: Optional[float] = None
                try:
                    fetcher = get_pricing_fetcher()
                    cost = fetcher.estimate_cost(model, prompt_tokens or 0, completion_tokens or 0)
                    if cost is None:
                        cost = get_llm_cost(model, prompt_tokens or 0, completion_tokens or 0)
                except Exception as cost_err:
                    logger.warning(f"Could not attribute LLM cost: {cost_err}")
                else:
                    # Record even when the cost resolves to 0/None (unpriced
                    # model) — the budget guard enforces from recorded usage,
                    # so skipping would be unattributed spend. Only a FAILED
                    # resolution skips recording.
                    try:
                        llm_usage_tracker.record(
                            workspace_id=self.workspace_id,
                            provider=attempt_provider_id,
                            model=model,
                            input_tokens=prompt_tokens or 0,
                            output_tokens=completion_tokens or 0,
                            cost_usd=cost or 0.0,
                            savings_usd=0.0,
                            agent_id=agent_id,
                            complexity=str(getattr(self.analyze_query_complexity(prompt_str, task_type), "value", "moderate")),
                        )
                    except Exception as cost_err:
                        logger.warning(f"Could not record LLM usage: {cost_err}")

                self.health_monitor.record_call(attempt_provider_id, success=True, latency_ms=latency_ms)
                self._track_rate_usage(
                    attempt_provider_id,
                    input_tokens=prompt_tokens or 0,
                    output_tokens=completion_tokens or 0,
                    model_id=model,
                )
                self._track_llm_call(
                    provider=attempt_provider_id, model=model, success=True,
                    latency_ms=latency_ms,
                    input_tokens=prompt_tokens or 0,
                    output_tokens=completion_tokens or 0,
                    fallback=attempt_provider_id != primary_provider,
                    fallback_provider=primary_provider if attempt_provider_id != primary_provider else None,
                )
                await self._record_outcome_feedback(
                    model=model, provider_id=attempt_provider_id, task_type=task_type,
                    content=content, finish_reason=finish_reason,
                    success=True, cost=cost, latency_ms=latency_ms,
                    routing_result_id=decision_id,
                )
                self._last_used_model = model
                self._last_used_provider = attempt_provider_id

                return {
                    "id": f"chatcmpl_atom_{uuid.uuid4().hex}",
                    "object": "chat.completion",
                    "created": int(datetime.now().timestamp()),
                    "model": model,
                    "provider": attempt_provider_id,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": content},
                            "finish_reason": finish_reason,
                            "logprobs": None,
                        }
                    ],
                    "usage": {
                        "prompt_tokens": prompt_tokens or 0,
                        "completion_tokens": completion_tokens or 0,
                        "total_tokens": total_tokens,
                    },
                }

            except Exception as e:
                last_error = e
                logger.warning(f"Completion failed for {attempt_provider_id}/{model}: {e}")
                try:
                    latency_ms = (datetime.now() - request_start).total_seconds() * 1000.0
                    self.health_monitor.record_call(attempt_provider_id, success=False, latency_ms=latency_ms,
                                                    connection_failure=(
                                                        "connection error" in str(e).lower()
                                                        or "refused" in str(e).lower()
                                                        or "unreachable" in str(e).lower()
                                                    ))
                    self._track_llm_call(
                        provider=attempt_provider_id, model=model, success=False,
                        latency_ms=latency_ms,
                        fallback=attempt_provider_id != primary_provider,
                        fallback_provider=primary_provider if attempt_provider_id != primary_provider else None,
                        error=str(e)[:500],
                    )
                except Exception:
                    pass

                # --- Self-healing autofix (rule-based, single attempt) ---
                if not heal_attempted:
                    heal_attempted = True
                    try:
                        from core.llm.routing.request_healer import get_request_healer
                        healer = get_request_healer()
                        heal_result = healer.heal(e, dict(base_kwargs), attempt_provider_id, model)
                        if heal_result.patched_kwargs is not None:
                            logger.info(
                                f"[SelfHeal] retrying {attempt_provider_id}/{model} "
                                f"with patch={heal_result.rule} keys={heal_result.patched_keys}"
                            )
                            try:
                                healed_response = await client.chat.completions.create(**heal_result.patched_kwargs)
                                self._capture_echoed_model(healed_response)
                                healed_choice = healed_response.choices[0] if getattr(healed_response, "choices", None) else None
                                healed_content = ""
                                if healed_choice is not None:
                                    healed_content = getattr(healed_choice.message, "content", "") or ""
                                healed_finish = getattr(healed_choice, "finish_reason", None) or "stop"
                                healed_usage = getattr(healed_response, "usage", None)
                                hp = getattr(healed_usage, "prompt_tokens", 0) if healed_usage else 0
                                hc = getattr(healed_usage, "completion_tokens", 0) if healed_usage else 0
                                try:
                                    heal_cost = get_pricing_fetcher().estimate_cost(model, hp, hc)
                                except Exception:
                                    heal_cost = None
                                self.health_monitor.record_call(attempt_provider_id, success=True, latency_ms=0.0)
                                self._track_rate_usage(attempt_provider_id, input_tokens=hp, output_tokens=hc,
                                                       model_id=model)
                                self._track_llm_call(
                                    provider=attempt_provider_id, model=model, success=True,
                                    latency_ms=(datetime.now() - request_start).total_seconds() * 1000.0,
                                    input_tokens=hp, output_tokens=hc,
                                    fallback=attempt_provider_id != primary_provider,
                                    fallback_provider=primary_provider if attempt_provider_id != primary_provider else None,
                                )
                                await self._record_outcome_feedback(
                                    model=model, provider_id=attempt_provider_id, task_type=task_type,
                                    content=healed_content, finish_reason=healed_finish,
                                    success=True, cost=heal_cost, latency_ms=0.0,
                                    routing_result_id=decision_id,
                                )
                                self._last_used_model = model
                                self._last_used_provider = attempt_provider_id
                                return {
                                    "id": f"chatcmpl_atom_{uuid.uuid4().hex}",
                                    "object": "chat.completion",
                                    "created": int(datetime.now().timestamp()),
                                    "model": model,
                                    "provider": attempt_provider_id,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "message": {"role": "assistant", "content": healed_content},
                                            "finish_reason": healed_finish,
                                            "logprobs": None,
                                        }
                                    ],
                                    "usage": {
                                        "prompt_tokens": hp,
                                        "completion_tokens": hc,
                                        "total_tokens": hp + hc,
                                    },
                                }
                            except Exception as retry_err:
                                logger.warning(
                                    f"[SelfHeal] retry FAILED for {attempt_provider_id}/{model}: {retry_err} "
                                    f"(rule={heal_result.rule})"
                                )
                                last_error = retry_err
                    except Exception:
                        logger.debug("[SelfHeal] healer raised; skipping", exc_info=True)

                # --- OpenCode Go free-usage → paid retry ---
                # Mirrors generate_response/stream_completion: a free-usage
                # model (gateway ID ends in "-free") draws from the account's
                # FREE allowance, which can be exhausted even with an ACTIVE
                # subscription — the gateway then answers CreditsError /
                # "Insufficient balance" while paid models would complete
                # fine. Re-issue the SAME request on the subscription-paid
                # fallback model before falling back to the next provider.
                # The gateway path (chat_completion backs the inbound LLM
                # Gateway and workflow engine) previously lacked this retry
                # entirely, so free-tier exhaustion surfaced as hard failures.
                if (
                    attempt_provider_id == "opencode-go"
                    and _is_opencode_free_model(model)
                    and _is_insufficient_balance_error(e)
                ):
                    paid_model = _opencode_paid_fallback_model(model)
                    if paid_model and paid_model != model:
                        try:
                            retry_kwargs: Dict[str, Any] = {
                                k: v for k, v in base_kwargs.items() if k != "model"
                            }
                            retry_kwargs["model"] = paid_model
                            paid_response = await client.chat.completions.create(**retry_kwargs)
                            self._capture_echoed_model(paid_response)
                            p_choice = (
                                paid_response.choices[0]
                                if getattr(paid_response, "choices", None)
                                else None
                            )
                            p_content = ""
                            if p_choice is not None:
                                p_content = getattr(p_choice.message, "content", "") or ""
                            p_finish = getattr(p_choice, "finish_reason", None) or "stop"
                            p_usage = getattr(paid_response, "usage", None)
                            pp = getattr(p_usage, "prompt_tokens", 0) if p_usage else 0
                            pc = getattr(p_usage, "completion_tokens", 0) if p_usage else 0
                            latency_ms = (datetime.now() - request_start).total_seconds() * 1000.0
                            self.health_monitor.record_call(attempt_provider_id, success=True, latency_ms=latency_ms)
                            self._track_rate_usage(
                                attempt_provider_id,
                                input_tokens=pp,
                                output_tokens=pc,
                                model_id=paid_model,
                            )
                            self._track_llm_call(
                                provider=attempt_provider_id, model=paid_model, success=True,
                                latency_ms=latency_ms, input_tokens=pp, output_tokens=pc,
                                fallback=attempt_provider_id != primary_provider,
                                fallback_provider=primary_provider if attempt_provider_id != primary_provider else None,
                            )
                            # Usage attribution: the gateway enforces budgets
                            # from recorded usage — an unattributed retry would
                            # be unbounded spend on this path. Record even when
                            # the cost resolves to 0/None (unpriced model);
                            # only a FAILED resolution skips recording.
                            paid_cost: Optional[float] = None
                            try:
                                fetcher = get_pricing_fetcher()
                                paid_cost = fetcher.estimate_cost(paid_model, pp or 0, pc or 0)
                                if paid_cost is None:
                                    paid_cost = get_llm_cost(paid_model, pp or 0, pc or 0)
                            except Exception as cost_err:
                                logger.warning(f"Could not attribute LLM cost: {cost_err}")
                            else:
                                try:
                                    llm_usage_tracker.record(
                                        workspace_id=self.workspace_id,
                                        provider=attempt_provider_id,
                                        model=paid_model,
                                        input_tokens=pp or 0,
                                        output_tokens=pc or 0,
                                        cost_usd=paid_cost or 0.0,
                                        savings_usd=0.0,
                                        agent_id=agent_id,
                                        complexity=str(getattr(self.analyze_query_complexity(prompt_str, task_type), "value", "moderate")),
                                    )
                                except Exception as cost_err:
                                    logger.warning(f"Could not record LLM usage: {cost_err}")
                            await self._record_outcome_feedback(
                                model=paid_model, provider_id=attempt_provider_id, task_type=task_type,
                                content=p_content, finish_reason=p_finish,
                                success=True, cost=paid_cost, latency_ms=latency_ms,
                                routing_result_id=decision_id,
                            )
                            self._last_used_model = paid_model
                            self._last_used_provider = attempt_provider_id
                            logger.info(
                                f"OpenCode Go free-model retry SUCCEEDED on paid model "
                                f"{paid_model} (free {model} hit credit limit)"
                            )
                            return {
                                "id": f"chatcmpl_atom_{uuid.uuid4().hex}",
                                "object": "chat.completion",
                                "created": int(datetime.now().timestamp()),
                                "model": paid_model,
                                "provider": attempt_provider_id,
                                "choices": [
                                    {
                                        "index": 0,
                                        "message": {"role": "assistant", "content": p_content},
                                        "finish_reason": p_finish,
                                        "logprobs": None,
                                    }
                                ],
                                "usage": {
                                    "prompt_tokens": pp or 0,
                                    "completion_tokens": pc or 0,
                                    "total_tokens": (pp or 0) + (pc or 0),
                                },
                            }
                        except Exception as paid_err:
                            logger.warning(
                                f"OpenCode Go paid retry FAILED for {paid_model}: {paid_err}"
                            )
                            last_error = paid_err

                await self._record_outcome_feedback(
                    model=model, provider_id=attempt_provider_id, task_type=task_type,
                    content=None, finish_reason=None,
                    success=False, cost=None, latency_ms=0.0,
                    exception=e, routing_result_id=decision_id,
                )

        raise AllProvidersFailedError(
            f"All {len(provider_order)} providers failed for {model}. Last error: {last_error}"
        )

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
