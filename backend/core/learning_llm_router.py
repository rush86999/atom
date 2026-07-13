"""
Learning-Based LLM Router

Based on 2025-2026 research:
- RouteLLM Research (arXiv 2406.18665)
- BYOK Survey (ACL 2025.l2m2-1.12)
- OpenRouter AI State of AI
- 100T Token Study insights

This service implements:
1. Custom RouteLLM-style model routing
2. Preference data collection from routing decisions
3. Active learning for router improvement
4. Cost-aware model selection with quality prediction

Success Criteria:
- 90% routing accuracy
- 15% additional cost reduction vs rule-based
- <50ms routing decision latency
"""
from __future__ import annotations
import uuid
import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional, List, Dict, Set, Tuple, Union
from uuid import UUID
from collections import defaultdict

from sqlalchemy.orm import Session

from core.database import get_db_session
from core.models import LLMRoutingFeedback
from core.llm.response_quality import ResponseQuality
from core.llm.routing import (
    TrainingConfig,
    TrainingExample,
    TrainingStatus,
    PerModelRouter,
)

logger = logging.getLogger(__name__)


class ModelCapability(str, Enum):
    """Model capability classification"""

    CODE_GENERATION = "code_generation"
    REASONING = "reasoning"
    TOOL_USE = "tool_use"
    VISION = "vision"
    LONG_CONTEXT = "long_context"
    FAST_RESPONSE = "fast_response"
    CHEAP = "cheap"
    HIGH_QUALITY = "high_quality"


@dataclass
class ModelSpec:
    """Model specification for routing"""

    model_id: str  # Internal model identifier
    provider: str  # Provider name
    model_name: str  # External model name (e.g., "gpt-4o")
    capabilities: Set[ModelCapability]
    cost_per_million: float  # Cost per 1M tokens (average of input/output)
    quality_score: float  # 0.0-1.0, based on benchmarks
    speed_score: float  # 0.0-1.0, tokens/sec
    context_window: int  # Maximum context length
    supports_cache: bool
    tier: str  # Pricing tier: standard, plus, premium
    api_region: str = "default"  # API region: default, us, eu, sg, cn, international


@dataclass
class RoutingRequest:
    """Request context for routing decision"""

    tenant_id: str
    task_type: str  # e.g., "code_generation", "question_answering"
    estimated_tokens: int
    requires_quality: bool = True  # Whether high quality is needed
    requires_reasoning: bool = False
    requires_vision: bool = False
    max_latency_ms: Optional[int] = None
    budget_limit: Optional[float] = None
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    conversation_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingResult:
    """Result of routing decision"""

    selected_model: ModelSpec
    confidence: float  # Router confidence in this choice (0-1)
    expected_cost: float  # Expected cost for this request
    expected_quality: float  # Expected quality score
    reasoning: str  # Human-readable explanation
    alternatives: List[ModelSpec]  # Alternative models considered
    routing_time_ms: float
    # Correlates this decision to later RoutingFeedback. Callers should pass
    # this id back when recording feedback so the router can recover the
    # original prompt features for training. Empty when not generated.
    routing_result_id: str = ""
    # The prompt features used at route time. Echoed back for observability and
    # so callers can attach them to feedback without re-deriving them.
    prompt_features: Dict[str, float] = field(default_factory=dict)


@dataclass
class RoutingFeedback:
    """Feedback on routing decision"""

    routing_result_id: str
    tenant_id: str
    model_id: str
    task_type: str
    success: bool  # Whether routing succeeded
    quality_satisfied: bool  # Whether quality met expectations
    cost_within_budget: bool  # Whether cost was acceptable
    user_satisfaction: Optional[float] = None  # 0-1 if available
    actual_cost: Optional[float] = None
    actual_latency_ms: Optional[float] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _check_cost_within_budget(tenant_id: str, actual_cost: Optional[float]) -> bool:
    """Whether an observed cost is within the tenant's budget.

    Defaults to True (within budget) when no cost was observed or when budget
    enforcement can't be reached — a missing signal should not mark a response
    as over-budget. When the cost IS known and the tenant has exceeded their
    budget (per the existing ``llm_usage_tracker``), this returns False so the
    predictor can learn that expensive models hurt budget adherence.
    """
    if actual_cost is None:
        return True
    try:
        from core.llm_usage_tracker import llm_usage_tracker
        return not llm_usage_tracker.is_budget_exceeded(tenant_id)
    except Exception:
        # Budget tracker unavailable — don't penalize.
        return True


class LearningBasedRouter:
    """
    Learning-Based LLM Router

    Implements RouteLLM-style routing with:
    - Preference data collection from actual usage
    - Active learning for continuous improvement
    - Pareto-optimal routing (quality vs cost)
    - Tier-aware routing strategies
    """

    def __init__(self, db: Session):
        self.db = db
        self._model_registry: Dict[str, ModelSpec] = {}
        self._preference_data: Dict[str, List[RoutingFeedback]] = {}
        # Learned per-task weights derived from feedback, keyed "{tenant}:{task}".
        self._router_cache: Dict[str, Dict[str, float]] = {}

        # Bounded-memory caps (R17-2): unbounded caches grew without limit.
        self._max_router_cache_size = 1000
        self._max_preference_data_per_key = 5000

        # Minimum samples to train a single per-model predictor.
        self._min_samples_per_model = 20

        # Per-model satisfaction predictors, keyed "{tenant}:{task}". Each holds
        # one sklearn estimator per model id that served that task. This is the
        # structure that makes routing decisions actually change with feedback.
        self._per_model_routers: Dict[str, PerModelRouter] = {}
        self._max_per_model_routers = 1000  # Bounded (R17-2 pattern)
        # Pending routing decisions awaiting feedback, keyed by routing_result_id.
        # Stores the prompt features computed at route time so that, when feedback
        # arrives, the per-model predictors can be trained on the REAL features
        # that were used to make the decision — eliminating train/serve skew and
        # letting predictors discriminate within a task (short vs long, etc.).
        self._routing_decisions: Dict[str, Dict[str, float]] = {}
        self._max_routing_decisions = 10000  # bounded (R17-2 pattern)

        # Initialize model registry
        self._initialize_model_registry()

    def _initialize_model_registry(self):
        """Initialize available models with their capabilities"""
        # OpenAI models
        self._model_registry.update({
            "gpt-4o": ModelSpec(
                model_id="gpt-4o",
                provider="openai",
                model_name="gpt-4o",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.TOOL_USE,
                    ModelCapability.VISION,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.HIGH_QUALITY,
                },
                cost_per_million=2.50,
                quality_score=0.92,
                speed_score=0.70,
                context_window=128000,
                supports_cache=True,
                tier="premium",
            ),
            "gpt-4o-mini": ModelSpec(
                model_id="gpt-4o-mini",
                provider="openai",
                model_name="gpt-4o-mini",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.TOOL_USE,
                    ModelCapability.FAST_RESPONSE,
                    ModelCapability.CHEAP,
                },
                cost_per_million=0.15,
                quality_score=0.82,
                speed_score=0.85,
                context_window=128000,
                supports_cache=True,
                tier="standard",
            ),
            "o1-preview": ModelSpec(
                model_id="o1-preview",
                provider="openai",
                model_name="o1-preview",
                capabilities={
                    ModelCapability.REASONING,
                    ModelCapability.HIGH_QUALITY,
                },
                cost_per_million=15.00,
                quality_score=0.96,
                speed_score=0.30,
                context_window=200000,
                supports_cache=False,
                tier="premium",
            ),
        })

        # Anthropic models
        self._model_registry.update({
            "claude-3-5-sonnet": ModelSpec(
                model_id="claude-3-5-sonnet",
                provider="anthropic",
                model_name="claude-3-5-sonnet-20241022",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.TOOL_USE,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.HIGH_QUALITY,
                },
                cost_per_million=3.00,
                quality_score=0.94,
                speed_score=0.75,
                context_window=200000,
                supports_cache=True,
                tier="premium",
            ),
            "claude-3-5-haiku": ModelSpec(
                model_id="claude-3-5-haiku",
                provider="anthropic",
                model_name="claude-3-5-haiku-20241022",
                capabilities={
                    ModelCapability.FAST_RESPONSE,
                    ModelCapability.CHEAP,
                },
                cost_per_million=0.25,
                quality_score=0.80,
                speed_score=0.90,
                context_window=200000,
                supports_cache=False,
                tier="standard",
            ),
        })

        # DeepSeek (cost-effective alternative, uses international API)
        self._model_registry.update({
            "deepseek-chat": ModelSpec(
                model_id="deepseek-chat",
                provider="deepseek",
                model_name="deepseek-chat",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.CHEAP,
                },
                cost_per_million=0.14,
                quality_score=0.78,
                speed_score=0.65,
                context_window=128000,
                supports_cache=False,
                tier="standard",
                api_region="international",  # Use international API endpoint
            ),
        })

        # Gemini models
        self._model_registry.update({
            "gemini-2.5-flash": ModelSpec(
                model_id="gemini-2.5-flash",
                provider="google",
                model_name="gemini-2.5-flash",
                capabilities={
                    ModelCapability.FAST_RESPONSE,
                    ModelCapability.CHEAP,
                },
                cost_per_million=0.08,
                quality_score=0.75,
                speed_score=0.95,
                context_window=1000000,
                supports_cache=True,
                tier="standard",
            ),
            # Gemini 3.5 Flash (Google, 2026) - 1M context, thinking mode
            "gemini-3.5-flash": ModelSpec(
                model_id="gemini-3.5-flash",
                provider="google",
                model_name="gemini-3.5-flash",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.VISION,
                    ModelCapability.FAST_RESPONSE,
                    ModelCapability.LONG_CONTEXT,
                },
                cost_per_million=5.25,  # Average of $1.50 input, $9.00 output
                quality_score=0.90,
                speed_score=0.85,
                context_window=1000000,
                supports_cache=True,
                tier="premium",
            ),
            # Gemini 3.1 Pro (Google, 2026) - 2M context, frontier reasoning
            "gemini-3.1-pro": ModelSpec(
                model_id="gemini-3.1-pro",
                provider="google",
                model_name="gemini-3.1-pro",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.VISION,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.HIGH_QUALITY,
                },
                cost_per_million=7.00,  # Average of $2 input, $12 output
                quality_score=0.93,
                speed_score=0.72,
                context_window=2000000,  # 2M context
                supports_cache=True,
                tier="premium",
            ),
        })

        # GPT-5.5 (OpenAI, 2026)
        self._model_registry.update({
            "gpt-5.5": ModelSpec(
                model_id="gpt-5.5",
                provider="openai",
                model_name="gpt-5.5",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.TOOL_USE,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.HIGH_QUALITY,
                },
                cost_per_million=5.00,
                quality_score=0.98,
                speed_score=0.72,
                context_window=1050000,
                supports_cache=True,
                tier="premium",
            ),
        })

        # Claude Opus 4.6 (Anthropic, 2026)
        self._model_registry.update({
            "claude-opus-4.6": ModelSpec(
                model_id="claude-opus-4.6",
                provider="anthropic",
                model_name="claude-opus-4.6",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.TOOL_USE,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.HIGH_QUALITY,
                },
                cost_per_million=15.00,
                quality_score=0.99,
                speed_score=0.65,
                context_window=1000000,
                supports_cache=True,
                tier="premium",
            ),
        })

        # DeepSeek V4 Flash (2026, uses international API) - 284B MoE, 13B active
        self._model_registry.update({
            "deepseek-v4-flash": ModelSpec(
                model_id="deepseek-v4-flash",
                provider="deepseek",
                model_name="deepseek-v4-flash",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.TOOL_USE,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.FAST_RESPONSE,
                    ModelCapability.CHEAP,
                },
                cost_per_million=0.28,
                quality_score=0.88,
                speed_score=0.92,
                context_window=1000000,
                supports_cache=True,
                tier="standard",
                api_region="international",  # Use international API endpoint
            ),
        })

        # DeepSeek V4 Pro (2026, uses international API)
        self._model_registry.update({
            "deepseek-v4-pro": ModelSpec(
                model_id="deepseek-v4-pro",
                provider="deepseek",
                model_name="deepseek-v4-pro",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.TOOL_USE,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.HIGH_QUALITY,
                },
                cost_per_million=0.50,
                quality_score=0.95,
                speed_score=0.70,
                context_window=1000000,
                supports_cache=True,
                tier="premium",
                api_region="international",  # Use international API endpoint
            ),
        })

        # GLM-5 (Zhipu AI, 2026, uses Singapore API)
        self._model_registry.update({
            "glm-5": ModelSpec(
                model_id="glm-5",
                provider="zhipu",
                model_name="glm-5",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.HIGH_QUALITY,
                },
                cost_per_million=1.20,
                quality_score=0.96,
                speed_score=0.68,
                context_window=200000,
                supports_cache=True,
                tier="premium",
                api_region="sg",  # Use Singapore API endpoint
            ),
            # GLM-5.2 (Zhipu AI, 2026) - Long-horizon flagship
            "glm-5.2": ModelSpec(
                model_id="glm-5.2",
                provider="zhipu",
                model_name="glm-5.2",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.HIGH_QUALITY,
                },
                cost_per_million=1.50,
                quality_score=0.97,
                speed_score=0.70,
                context_window=1000000,
                supports_cache=True,
                tier="premium",
                api_region="sg",  # Use Singapore API endpoint
            ),
        })

        # Kimi K2.6 (Moonshot AI, 2026, uses international API)
        self._model_registry.update({
            "kimi-k2.6": ModelSpec(
                model_id="kimi-k2.6",
                provider="moonshot",
                model_name="kimi-k2.6",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.VISION,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.HIGH_QUALITY,
                },
                cost_per_million=0.80,
                quality_score=0.93,
                speed_score=0.75,
                context_window=256000,
                supports_cache=True,
                tier="premium",
                api_region="international",  # Use international API endpoint
            ),
        })

        # Qwen 2.5 Max (Alibaba, 2026, uses international API)
        self._model_registry.update({
            "qwen-2.5-max": ModelSpec(
                model_id="qwen-2.5-max",
                provider="alibaba",
                model_name="qwen-2.5-max",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.HIGH_QUALITY,
                },
                cost_per_million=0.60,
                quality_score=0.94,
                speed_score=0.72,
                context_window=128000,
                supports_cache=True,
                tier="premium",
                api_region="international",  # Use international API endpoint
            ),
        })

        # Cohere Command R+ (2026)
        self._model_registry.update({
            "command-r-plus": ModelSpec(
                model_id="command-r-plus",
                provider="cohere",
                model_name="command-r-plus",
                capabilities={
                    ModelCapability.REASONING,
                    ModelCapability.TOOL_USE,
                    ModelCapability.CODE_GENERATION,
                },
                cost_per_million=1.56,
                quality_score=0.88,
                speed_score=0.78,
                context_window=128000,
                supports_cache=True,
                tier="plus",
            ),
        })

        # Mistral Large 3 (Mistral AI, 2026)
        self._model_registry.update({
            "mistral-large-3": ModelSpec(
                model_id="mistral-large-3",
                provider="mistral",
                model_name="mistral-large-3",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.VISION,
                    ModelCapability.HIGH_QUALITY,
                },
                cost_per_million=0.80,
                quality_score=0.91,
                speed_score=0.74,
                context_window=128000,
                supports_cache=True,
                tier="premium",
            ),
        })

        # Fable 5 (Anthropic Mythos-class, 2026)
        self._model_registry.update({
            "fable-5": ModelSpec(
                model_id="fable-5",
                provider="anthropic",
                model_name="claude-fable-5",
                capabilities={
                    ModelCapability.VISION,
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.HIGH_QUALITY,
                },
                cost_per_million=30.00,
                quality_score=0.99,
                speed_score=0.60,
                context_window=1000000,
                supports_cache=True,
                tier="premium",
            ),
        })

        # Claude Opus 4.8 (Anthropic, 2026)
        self._model_registry.update({
            "claude-opus-4.8": ModelSpec(
                model_id="claude-opus-4.8",
                provider="anthropic",
                model_name="claude-opus-4.8",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.TOOL_USE,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.HIGH_QUALITY,
                },
                cost_per_million=20.00,
                quality_score=0.995,
                speed_score=0.67,
                context_window=1000000,
                supports_cache=True,
                tier="premium",
            ),
        })

        # MiniMax-Text-01 (MiniMax, 2026) - 4M context, largest of any model
        self._model_registry.update({
            "minimax-text-01": ModelSpec(
                model_id="minimax-text-01",
                provider="minimax",
                model_name="minimax-text-01",
                capabilities={
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.REASONING,
                    ModelCapability.HIGH_QUALITY,
                },
                cost_per_million=0.40,
                quality_score=0.92,
                speed_score=0.55,
                context_window=4000000,
                supports_cache=True,
                tier="premium",
                api_region="sg",  # Use Singapore API endpoint
            ),
            # MiniMax M3 (MiniMax, 2026) - 428B params, SOTA coding capability
            "minimax-m3": ModelSpec(
                model_id="minimax-m3",
                provider="minimax",
                model_name="minimax-m3",
                capabilities={
                    ModelCapability.CODE_GENERATION,
                    ModelCapability.REASONING,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.HIGH_QUALITY,
                },
                cost_per_million=0.60,
                quality_score=0.96,
                speed_score=0.72,
                context_window=2000000,
                supports_cache=True,
                tier="premium",
                api_region="sg",  # Use Singapore API endpoint
            ),
        })

        logger.info(f"Initialized router with {len(self._model_registry)} models")

    async def route(
        self, request: RoutingRequest
    ) -> RoutingResult:
        """
        Route request to optimal model based on context and learning.

        Args:
            request: RoutingRequest with context

        Returns:
            RoutingResult with selected model and metadata
        """
        start_time = datetime.now(timezone.utc)
        start_ms = start_time.timestamp() * 1000

        # Step 1: Filter models by capability requirements
        candidates = self._filter_by_capabilities(request)

        if not candidates:
            # Fallback to cheapest model if no candidates match
            fallback = self._get_cheapest_model()
            return self._create_routing_result(
                fallback,
                request,
                0.3,  # Low confidence
                "No models matched requirements, using fallback",
                [],
                start_ms,
            )

        # Step 2: Apply cost constraints
        if request.budget_limit:
            candidates = self._filter_by_cost(
                candidates, request.budget_limit, request.estimated_tokens
            )

        # Step 3: Apply latency constraints
        if request.max_latency_ms:
            candidates = self._filter_by_latency(candidates, request.max_latency_ms)

        if not candidates:
            fallback = self._get_cheapest_model()
            return self._create_routing_result(
                fallback,
                request,
                0.4,
                "No models matched constraints, using fallback",
                [],
                start_ms,
            )

        # Step 4: Score candidates based on learned preferences
        scored_candidates = self._score_candidates(
            candidates, request
        )

        # Step 5: Select best model
        selected, score = scored_candidates[0]

        # Get alternatives (top 3)
        alternatives = [m for m, s in scored_candidates[1:4]]

        routing_time = datetime.now(timezone.utc)
        elapsed_ms = (routing_time - start_time).total_seconds() * 1000
        routing_time_ms = elapsed_ms

        result = self._create_routing_result(
            selected,
            request,
            score,
            self._generate_reasoning(selected, request, score),
            alternatives,
            routing_time_ms,
        )

        logger.info(
            f"Routed {request.task_type} to {selected.model_name} "
            f"(confidence={score:.2f}, cost=${result.expected_cost:.4f})"
        )

        return result

    def _filter_by_capabilities(
        self, request: RoutingRequest
    ) -> List[ModelSpec]:
        """Filter models by required capabilities"""
        candidates = []

        required_capabilities = set()
        if request.requires_quality:
            required_capabilities.add(ModelCapability.HIGH_QUALITY)
        if request.requires_reasoning:
            required_capabilities.add(ModelCapability.REASONING)
        if request.requires_vision:
            required_capabilities.add(ModelCapability.VISION)
        if request.max_latency_ms and request.max_latency_ms < 1000:
            required_capabilities.add(ModelCapability.FAST_RESPONSE)

        for model in self._model_registry.values():
            # Check if model has all required capabilities
            if required_capabilities.issubset(model.capabilities):
                candidates.append(model)

        return candidates

    def _filter_by_cost(
        self,
        candidates: List[ModelSpec],
        budget_limit: float,
        estimated_tokens: int,
    ) -> List[ModelSpec]:
        """Filter models by cost budget"""
        affordable = []

        for model in candidates:
            # Estimate cost
            estimated_cost = (model.cost_per_million * estimated_tokens) / 1_000_000
            if estimated_cost <= budget_limit:
                affordable.append(model)

        return affordable

    def _filter_by_latency(
        self,
        candidates: List[ModelSpec],
        max_latency_ms: int,
    ) -> List[ModelSpec]:
        """Filter models by latency requirements.

        Uses speed_score as a proxy for latency: a model with speed_score ``s``
        is estimated at roughly ``100 / s`` ms (so 1.0 ≈ 100ms, 0.5 ≈ 200ms).
        Models whose estimated latency is within ``max_latency_ms`` are kept.
        """
        fast_models = []
        for model in candidates:
            if model.speed_score <= 0:
                continue
            estimated_latency_ms = 100.0 / model.speed_score
            if estimated_latency_ms <= max_latency_ms:
                fast_models.append(model)
        return fast_models

    def _score_candidates(
        self,
        candidates: List[ModelSpec],
        request: RoutingRequest,
    ) -> List[Tuple[ModelSpec, float]]:
        """Score candidates based on learned preferences and context.

        Combines the rule-based quality/cost/speed score with a learned
        per-model satisfaction signal. When a model has a trained predictor
        for this tenant/task, its predicted satisfaction probability boosts
        (or penalizes) the score — this is what makes routing decisions
        change as feedback accumulates. Cold start (no predictor) leaves the
        rule-based score untouched.
        """
        scores = []

        # Get learned preference weights for this task type
        weights = self._get_learned_weights(request.task_type, request.tenant_id)

        # Look up the per-model predictors for this tenant/task (may be absent).
        cache_key = f"{request.tenant_id}:{request.task_type}"
        per_model = self._per_model_routers.get(cache_key)
        # Pre-compute the request's prompt features once for all predictors.
        request_features = self._extract_request_features(request) if per_model else None

        for model in candidates:
            score = 0.0

            # Quality component
            quality_weight = weights.get("quality", 0.4)
            if request.requires_quality:
                quality_weight *= 1.2  # Boost quality importance
            score += model.quality_score * quality_weight

            # Cost component (inverse - cheaper is better)
            cost_weight = weights.get("cost", 0.3)
            if request.budget_limit:
                cost_weight *= 1.5  # Boost cost importance with budget
            # Normalize cost (lower is better)
            max_cost = max(m.cost_per_million for m in candidates)
            cost_score = 1.0 - (model.cost_per_million / max_cost)
            score += cost_score * cost_weight

            # Speed component
            speed_weight = weights.get("speed", 0.2)
            if request.max_latency_ms:
                speed_weight *= 1.5
            score += model.speed_score * speed_weight

            # Capability matching bonus
            if ModelCapability.LONG_CONTEXT in model.capabilities:
                # Bonus for tasks that might need long context
                if request.estimated_tokens > 50000:
                    score += 0.1

            # Tenant preference override
            tenant_pref = request.user_preferences.get("preferred_model")
            if tenant_pref and tenant_pref in model.model_name.lower():
                score += 0.15

            # Learned per-model satisfaction signal. The blend weight scales
            # with how much data backs this predictor (see PerModelRouter.confidence),
            # so cold-start models get zero learned influence and the rule-based
            # score above dominates — no regression for new tenants.
            if per_model is not None and request_features is not None:
                satisfaction = per_model.predict_satisfaction(
                    model.model_id, request_features
                )
                if satisfaction is not None:
                    blend = per_model.confidence(model.model_id)
                    score += blend * satisfaction

            scores.append((model, score))

        # Sort by score (descending)
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def _get_learned_weights(
        self, task_type: str, tenant_id: str
    ) -> Dict[str, float]:
        """Get learned preference weights for task type.

        When a tenant/task pair has accumulated enough feedback to retrain,
        ``_retrain_router`` derives real ``{quality, cost, speed}`` weights from
        observed per-model success rates and stores them in ``_router_cache``.
        Otherwise we fall back to sensible per-task-type defaults.
        """
        # Check for tenant-specific learning data
        cache_key = f"{tenant_id}:{task_type}"

        if cache_key in self._router_cache:
            return self._router_cache[cache_key]

        # Default weights based on task type
        default_weights = {
            "code_generation": {"quality": 0.5, "cost": 0.2, "speed": 0.3},
            "question_answering": {"quality": 0.4, "cost": 0.3, "speed": 0.3},
            "reasoning": {"quality": 0.6, "cost": 0.1, "speed": 0.3},
            "tool_use": {"quality": 0.3, "cost": 0.3, "speed": 0.4},
            "vision": {"quality": 0.5, "cost": 0.2, "speed": 0.3},
            "extraction": {"quality": 0.3, "cost": 0.4, "speed": 0.3},
        }

        return default_weights.get(task_type, {
            "quality": 0.4, "cost": 0.3, "speed": 0.3
        })

    def _get_cheapest_model(self) -> ModelSpec:
        """Get cheapest available model as fallback"""
        cheapest = None
        min_cost = float("inf")

        for model in self._model_registry.values():
            if model.cost_per_million < min_cost:
                min_cost = model.cost_per_million
                cheapest = model

        return cheapest or list(self._model_registry.values())[0]

    def _create_routing_result(
        self,
        model: ModelSpec,
        request: RoutingRequest,
        confidence: float,
        reasoning: str,
        alternatives: List[ModelSpec],
        start_ms: float,
    ) -> RoutingResult:
        """Create routing result.

        Generates a routing_result_id and stashes the prompt features used at
        decision time into ``self._routing_decisions`` so that later feedback
        (carrying the same id) can train predictors on the real features.
        """
        routing_time = datetime.now(timezone.utc)
        routing_time_ms = (routing_time.timestamp() * 1000) - start_ms

        # Estimate cost
        expected_cost = (model.cost_per_million * request.estimated_tokens) / 1_000_000

        routing_result_id = str(uuid.uuid4())
        prompt_features = self._extract_request_features(request)

        # Stash the decision so feedback can recover the prompt features. Bound
        # the store (R17-2 pattern): evict the oldest entries when over the cap.
        self._routing_decisions[routing_result_id] = prompt_features
        if len(self._routing_decisions) > self._max_routing_decisions:
            overflow = len(self._routing_decisions) - self._max_routing_decisions
            for stale_id in list(self._routing_decisions.keys())[:overflow]:
                del self._routing_decisions[stale_id]

        return RoutingResult(
            selected_model=model,
            confidence=confidence,
            expected_cost=expected_cost,
            expected_quality=model.quality_score,
            reasoning=reasoning,
            alternatives=alternatives,
            routing_time_ms=routing_time_ms,
            routing_result_id=routing_result_id,
            prompt_features=prompt_features,
        )

    def _generate_reasoning(
        self, model: ModelSpec, request: RoutingRequest, score: float
    ) -> str:
        """Generate human-readable reasoning for routing choice"""
        reasons = []

        if ModelCapability.HIGH_QUALITY in model.capabilities and request.requires_quality:
            reasons.append("high quality requirements")

        if request.budget_limit:
            cost_estimate = (model.cost_per_million * request.estimated_tokens) / 1_000_000
            if cost_estimate <= request.budget_limit:
                reasons.append(f"within budget (${cost_estimate:.4f} <= ${request.budget_limit:.4f})")

        if request.max_latency_ms and model.speed_score >= 0.7:
            reasons.append("meets latency requirements")

        if score > 0.7:
            reasons.append("strong learned preference match")

        return "Selected " + model.model_name + " because " + ", ".join(reasons)

    async def record_feedback(self, feedback: RoutingFeedback) -> None:
        """
        Record routing feedback for learning.

        This enables active learning by collecting preference data. If the
        feedback carries a ``routing_result_id`` that matches a pending
        decision, the prompt features captured at route time are attached to
        the feedback so per-model predictors train on real (not constant)
        features.
        """
        # Recover the prompt features from the decision store so training uses
        # the same features that were used to make the decision (no train/serve
        # skew). Falls back to None -> _feedback_to_training_example derives
        # task-level defaults (graceful degradation for evicted/restarted ids).
        recovered = self._routing_decisions.get(feedback.routing_result_id)
        if recovered is not None:
            feedback._prompt_features = recovered  # type: ignore[attr-defined]
        elif feedback.routing_result_id:
            logger.debug(
                f"routing_result_id not found in decision store (evicted or "
                f"pre-restart); training will use task-level feature defaults"
            )

        feedback_key = f"{feedback.tenant_id}:{feedback.task_type}"

        if feedback_key not in self._preference_data:
            self._preference_data[feedback_key] = []

        self._preference_data[feedback_key].append(feedback)

        # Bound memory: keep only the most recent feedback per key (R17-2).
        if len(self._preference_data[feedback_key]) > self._max_preference_data_per_key:
            # Drop the oldest entries to stay within the cap.
            del self._preference_data[feedback_key][
                : len(self._preference_data[feedback_key]) - self._max_preference_data_per_key
            ]

        # Write through to DB so learned data survives restarts. Best-effort:
        # a DB failure must not break the hot routing path (in-memory state
        # remains authoritative for reads).
        recovered_features = getattr(feedback, "_prompt_features", None)
        self._persist_feedback(feedback, recovered_features)

        # Trigger retraining once there's enough feedback for a per-model
        # predictor (the lowest learning threshold). _retrain_router internally
        # decides what to train based on available data.
        if len(self._preference_data[feedback_key]) >= self._min_samples_per_model:
            await self._retrain_router(feedback.tenant_id, feedback.task_type)

        logger.debug(
            f"Recorded routing feedback: tenant={feedback.tenant_id}, "
            f"model={feedback.model_id}, success={feedback.success}"
        )

    async def _retrain_router(self, tenant_id: str, task_type: str) -> None:
        """
        Retrain router with accumulated preference data.

        Trains one per-model satisfaction predictor per model that has enough
        feedback, and derives ``{quality, cost, speed}`` routing weights from
        observed per-model success rates (used as the cold-start baseline).
        """
        feedback_list = self._preference_data.get(f"{tenant_id}:{task_type}", [])

        if not feedback_list:
            return

        # ---- Per-model empirical success rates (used to derive weights) ----
        model_success = defaultdict(lambda: {"success": 0, "total": 0})

        for feedback in feedback_list:
            model_success[feedback.model_id]["total"] += 1
            if feedback.success and feedback.quality_satisfied:
                model_success[feedback.model_id]["success"] += 1

        cache_key = f"{tenant_id}:{task_type}"

        # ---- Train per-model satisfaction predictors ----
        # Partition feedback by model and train one tiny predictor per model
        # that has enough samples. These predictors are what _score_candidates
        # consults to make routing decisions change with feedback.
        per_model = self._get_per_model_router(cache_key)
        by_model: Dict[str, List[RoutingFeedback]] = defaultdict(list)
        for feedback in feedback_list:
            by_model[feedback.model_id].append(feedback)

        trained_predictors: List[str] = []
        for model_id, model_feedback in by_model.items():
            if len(model_feedback) < self._min_samples_per_model:
                continue
            examples = [
                self._feedback_to_training_example(fb, task_type)
                for fb in model_feedback
            ]
            try:
                result = per_model.train(model_id, examples)
                if result.status == TrainingStatus.COMPLETED:
                    trained_predictors.append(
                        f"{model_id}({result.accuracy:.2f})"
                    )
            except Exception as e:
                logger.warning(
                    f"Per-model training failed for {model_id} "
                    f"(tenant={tenant_id}, task={task_type}): {e}"
                )

        # ---- Derive {quality, cost, speed} weights from success rates ----
        # Kept as the cold-start baseline; per-model predictors layer on top
        # of this in _score_candidates.
        weights = self._derive_weights_from_success(model_success, task_type)
        self._set_cached_weights(cache_key, weights, tenant_id)

        logger.info(
            f"Updated router for tenant={tenant_id}, task={task_type} "
            f"with {len(feedback_list)} samples; "
            f"predictors=[{', '.join(trained_predictors)}]"
        )

    def _persist_feedback(
        self, feedback: RoutingFeedback, prompt_features: Optional[Dict[str, float]]
    ) -> None:
        """Best-effort write-through of one feedback row to the DB.

        Uses a short-lived session (not the long-lived ``self.db``) per the
        codebase session-management guidance. Failures are logged and swallowed
        so a DB issue never breaks the hot routing path.
        """
        try:
            with get_db_session() as db:
                row = LLMRoutingFeedback(
                    routing_result_id=feedback.routing_result_id,
                    tenant_id=feedback.tenant_id,
                    task_type=feedback.task_type,
                    model_id=feedback.model_id,
                    success=feedback.success,
                    quality_satisfied=feedback.quality_satisfied,
                    cost_within_budget=feedback.cost_within_budget,
                    user_satisfaction=feedback.user_satisfaction,
                    actual_cost=feedback.actual_cost,
                    actual_latency_ms=feedback.actual_latency_ms,
                    prompt_features=prompt_features,
                )
                db.add(row)
        except Exception as e:
            logger.warning(
                f"Could not persist routing feedback to DB (non-fatal, "
                f"in-memory state remains): {e}"
            )

    @staticmethod
    def build_feedback(
        routing_result_id: str,
        tenant_id: str,
        model_id: str,
        task_type: str,
        quality: "ResponseQuality",
        actual_cost: Optional[float] = None,
        actual_latency_ms: Optional[float] = None,
    ) -> RoutingFeedback:
        """Build a RoutingFeedback from a ResponseQuality assessment.

        Centralizes the mapping from a quality assessment to the feedback
        dataclass so every observation point (chat endpoint, BYOK outcome
        hook, explicit user feedback) uses identical semantics. ``user_satisfaction``
        is populated from the quality score so the per-model predictors get a
        graded signal.
        """
        return RoutingFeedback(
            routing_result_id=routing_result_id,
            tenant_id=tenant_id,
            model_id=model_id,
            task_type=task_type,
            success=quality.success,
            quality_satisfied=quality.quality_satisfied,
            cost_within_budget=_check_cost_within_budget(tenant_id, actual_cost),
            user_satisfaction=quality.quality_score,
            actual_cost=actual_cost,
            actual_latency_ms=actual_latency_ms,
        )

    def load_feedback_from_db(self, tenant_id: Optional[str] = None) -> int:
        """Hydrate ``_preference_data`` from the DB so learned data survives restarts.

        Call on startup (or lazily). Reads are capped per key by
        ``_max_preference_data_per_key`` (R17-2). Returns the number of rows
        loaded. Safe to call when the table is empty (clean cold start).
        """
        loaded = 0
        try:
            with get_db_session() as db:
                query = db.query(LLMRoutingFeedback)
                if tenant_id is not None:
                    query = query.filter(
                        LLMRoutingFeedback.tenant_id == tenant_id
                    )
                query = query.order_by(LLMRoutingFeedback.created_at.desc())
                rows = query.all()

            # Group rows by "{tenant}:{task}" and hydrate in-memory state,
            # most-recent-first, capped per key.
            by_key: Dict[str, List[RoutingFeedback]] = defaultdict(list)
            for row in rows:
                fb = RoutingFeedback(
                    routing_result_id=row.routing_result_id,
                    tenant_id=row.tenant_id,
                    model_id=row.model_id,
                    task_type=row.task_type,
                    success=row.success,
                    quality_satisfied=row.quality_satisfied,
                    cost_within_budget=row.cost_within_budget,
                    user_satisfaction=row.user_satisfaction,
                    actual_cost=row.actual_cost,
                    actual_latency_ms=row.actual_latency_ms,
                    timestamp=row.created_at,
                )
                # Stash the persisted prompt features so subsequent retraining
                # trains on real features (not task defaults).
                if row.prompt_features:
                    fb._prompt_features = row.prompt_features  # type: ignore[attr-defined]
                key = f"{row.tenant_id}:{row.task_type}"
                by_key[key].append(fb)
                loaded += 1

            for key, fbs in by_key.items():
                # rows are most-recent-first; keep the most recent within cap.
                self._preference_data[key] = fbs[: self._max_preference_data_per_key]
        except Exception as e:
            logger.warning(
                f"Could not load routing feedback from DB (non-fatal, "
                f"starting with empty state): {e}"
            )
            return 0

        if loaded:
            logger.info(f"Loaded {loaded} routing feedback rows from DB")
        return loaded

    def _get_per_model_router(self, cache_key: str) -> PerModelRouter:
        """Get (or lazily create) the per-model predictor set for a tenant/task.

        On first creation for any key, restore persisted predictors from disk
        (``load_all``) so learned models survive restarts. The shared model
        directory means all PerModelRouter instances see the same restored set.
        """
        pmr = self._per_model_routers.get(cache_key)
        if pmr is None:
            pmr = PerModelRouter()
            try:
                pmr.load_all()
            except Exception as e:
                logger.debug(f"Could not load persisted predictors: {e}")
            self._per_model_routers[cache_key] = pmr
            # Bound growth: evict oldest entries when over the cap.
            if len(self._per_model_routers) > self._max_per_model_routers:
                _overflow = len(self._per_model_routers) - self._max_per_model_routers
                for _stale_key in list(self._per_model_routers.keys())[:_overflow]:
                    del self._per_model_routers[_stale_key]
        return pmr

    def _extract_request_features(self, request: RoutingRequest) -> Dict[str, float]:
        """Extract the trainer's 10 prompt features from a RoutingRequest.

        This mirrors the feature contract in FeatureExtractor.feature_names so
        that per-model predictors (trained on the same feature space) are
        queried consistently at route time. It is the single point to enrich
        if feedback later captures richer prompt characteristics.

        Content signals (has_code, has_numbers, avg_word_length) are derived
        from the task type by default, but if the caller supplies a prompt text
        or pre-computed signals in ``request.conversation_context`` (keys:
        ``"prompt_text"``, ``"has_code"``, ``"has_numbers"``,
        ``"avg_word_length"``), those are used instead — enabling genuine
        within-task discrimination.
        """
        import math

        task = request.task_type
        tokens = max(1, request.estimated_tokens)
        ctx = request.conversation_context or {}

        # Content signals: prefer caller-supplied values, then prompt-text
        # inspection, then task-type defaults.
        prompt_text = ctx.get("prompt_text") or ""
        has_code = (
            ctx.get("has_code")
            if "has_code" in ctx
            else (1.0 if "```" in prompt_text else (1.0 if task == "code_generation" else 0.0))
        )
        has_numbers = (
            ctx.get("has_numbers")
            if "has_numbers" in ctx
            else (1.0 if any(ch.isdigit() for ch in prompt_text) else (1.0 if request.requires_reasoning else 0.0))
        )
        avg_word_length = ctx.get("avg_word_length")
        if avg_word_length is None:
            if prompt_text:
                words = prompt_text.split()
                avg_word_length = len(prompt_text) / max(len(words), 1) if words else 5.0
            else:
                avg_word_length = 5.0

        return {
            "log_tokens": math.log2(tokens + 1),
            "token_bucket": self._token_bucket(tokens),
            "task_code": 1.0 if task == "code_generation" else 0.0,
            "task_analysis": 1.0 if task == "extraction" else 0.0,
            "task_reasoning": 1.0 if task == "reasoning" else 0.0,
            "task_chat": 1.0 if task == "question_answering" else 0.0,
            "task_general": 1.0 if task not in {
                "code_generation", "extraction", "reasoning", "question_answering"
            } else 0.0,
            "has_code": float(has_code),
            "has_numbers": float(has_numbers),
            "avg_word_length": float(avg_word_length),
        }

    @staticmethod
    def _token_bucket(tokens: int) -> float:
        if tokens < 100:
            return 0.0
        if tokens < 500:
            return 1.0
        if tokens < 2000:
            return 2.0
        if tokens < 5000:
            return 3.0
        return 4.0

    @staticmethod
    def _task_default_features(task_type: str) -> Dict[str, float]:
        """Task-level prompt-feature defaults used when no decision features are
        available (cold/evicted/un-correlated feedback). These match the
        feature contract of FeatureExtractor.feature_names.
        """
        return {
            "log_tokens": 0.0,
            "token_bucket": 1.0,  # mid-size bucket
            "task_code": 1.0 if task_type == "code_generation" else 0.0,
            "task_analysis": 1.0 if task_type == "extraction" else 0.0,
            "task_reasoning": 1.0 if task_type == "reasoning" else 0.0,
            "task_chat": 1.0 if task_type == "question_answering" else 0.0,
            "task_general": 1.0 if task_type not in {
                "code_generation", "extraction", "reasoning", "question_answering"
            } else 0.0,
            "has_code": 1.0 if task_type == "code_generation" else 0.0,
            "has_numbers": 0.0,
            "avg_word_length": 5.0,
        }

    def _feedback_to_training_example(
        self, feedback: RoutingFeedback, task_type: str
    ) -> TrainingExample:
        """Convert a RoutingFeedback into a trainer TrainingExample.

        Prefers the prompt features recovered from the original routing
        decision (stashed on ``feedback._prompt_features`` by
        ``record_feedback``) so the predictor trains on the same features used
        at route time — eliminating train/serve skew and enabling within-task
        discrimination. Falls back to task-level defaults when no decision
        features are available (evicted id, pre-restart, or un-correlated).
        """
        prompt_features = getattr(feedback, "_prompt_features", None)
        if not prompt_features:
            prompt_features = self._task_default_features(task_type)

        if feedback.user_satisfaction is not None:
            satisfaction = float(feedback.user_satisfaction)
        else:
            satisfaction = 1.0 if (feedback.success and feedback.quality_satisfied) else 0.0

        # Recover an approximate token count from the captured features so the
        # TrainingExample carries something other than a placeholder 0.
        estimated_tokens = 0
        log_tokens = prompt_features.get("log_tokens", 0.0)
        if log_tokens > 0:
            import math
            estimated_tokens = int(math.pow(2, log_tokens) - 1)

        return TrainingExample(
            estimated_tokens=estimated_tokens,
            task_type=task_type,
            prompt_features=prompt_features,
            chosen_model=feedback.model_id,
            user_satisfaction=satisfaction,
            was_successful=feedback.success,
            quality_score=satisfaction,
        )

    @staticmethod
    def _derive_weights_from_success(
        model_success: Dict[str, Dict[str, int]], task_type: str
    ) -> Dict[str, float]:
        """Translate per-model success rates into {quality, cost, speed} weights.

        Higher observed success → weight quality more heavily (the models that
        deliver quality are the ones worth prioritizing). Cost/speed are scaled
        down in proportion so the weights stay normalized. Falls back to the
        per-task defaults when no usable samples exist.
        """
        defaults = {
            "code_generation": {"quality": 0.5, "cost": 0.2, "speed": 0.3},
            "question_answering": {"quality": 0.4, "cost": 0.3, "speed": 0.3},
            "reasoning": {"quality": 0.6, "cost": 0.1, "speed": 0.3},
            "tool_use": {"quality": 0.3, "cost": 0.3, "speed": 0.4},
            "vision": {"quality": 0.5, "cost": 0.2, "speed": 0.3},
            "extraction": {"quality": 0.3, "cost": 0.4, "speed": 0.3},
        }

        total_samples = sum(s["total"] for s in model_success.values())
        if total_samples == 0:
            return defaults.get(task_type, {"quality": 0.4, "cost": 0.3, "speed": 0.3})

        overall_success = sum(s["success"] for s in model_success.values()) / total_samples
        base = defaults.get(task_type, {"quality": 0.4, "cost": 0.3, "speed": 0.3})

        # Scale quality by how well models are doing overall relative to a
        # neutral 0.5 baseline: strong outcomes → favor quality; poor outcomes
        # → favor cost/speed (i.e. be more conservative).
        quality_factor = 0.5 + overall_success  # range ~0.5..1.5
        quality = min(0.8, base["quality"] * quality_factor)

        # Redistribute the remainder between cost and speed, preserving their
        # original ratio.
        remainder = 1.0 - quality
        cost_speed_sum = base["cost"] + base["speed"] or 1.0
        cost = remainder * (base["cost"] / cost_speed_sum)
        speed = remainder * (base["speed"] / cost_speed_sum)

        return {"quality": quality, "cost": cost, "speed": speed}

    def _set_cached_weights(
        self,
        cache_key: str,
        weights: Dict[str, float],
        tenant_id: str,
    ) -> None:
        """Store learned weights, evicting oldest entries when over the cap (R17-2)."""
        self._router_cache[cache_key] = weights
        if len(self._router_cache) > self._max_router_cache_size:
            # Evict oldest tenant entries first (deterministic by insertion key).
            # Keys are "{tenant}:{task}"; drop until back under the cap.
            overflow = len(self._router_cache) - self._max_router_cache_size
            for key in list(self._router_cache.keys())[:overflow]:
                del self._router_cache[key]
            logger.debug(
                f"Evicted {overflow} router cache entries (cap="
                f"{self._max_router_cache_size}) for tenant={tenant_id}"
            )

    async def get_routing_statistics(
        self, tenant_id: str
    ) -> Dict[str, Any]:
        """Get routing statistics for a tenant"""
        stats = {
            "tenant_id": tenant_id,
            "total_models": len(self._model_registry),
            "feedback_samples": sum(
                len(v) for v in self._preference_data.values()
                if v and v[0].tenant_id == tenant_id
            ),
            "cached_weights": len(self._router_cache),
        }

        # Calculate success rate by model
        model_stats = defaultdict(lambda: {"success": 0, "total": 0})
        for feedback_list in self._preference_data.values():
            for feedback in feedback_list:
                if feedback.tenant_id == tenant_id:
                    model_stats[feedback.model_id]["total"] += 1
                    if feedback.success:
                        model_stats[feedback.model_id]["success"] += 1

        stats["model_success_rates"] = {}
        for model_id, counts in model_stats.items():
            if counts["total"] > 0:
                stats["model_success_rates"][model_id] = (
                    counts["success"] / counts["total"]
                )

        return stats

    def get_available_models(
        self,
        capabilities: Optional[List[ModelCapability]] = None,
        tier: Optional[str] = None,
        max_cost: Optional[float] = None,
    ) -> List[ModelSpec]:
        """Get available models with optional filtering"""
        models = list(self._model_registry.values())

        if capabilities:
            required = set(capabilities)
            models = [m for m in models if required.issubset(m.capabilities)]

        if tier:
            models = [m for m in models if m.tier == tier]

        if max_cost:
            models = [m for m in models if m.cost_per_million <= max_cost]

        return models

    def update_model_registry(self, models: List[Dict[str, Any]]) -> int:
        """
        Update model registry with new model definitions.

        Useful for dynamic model discovery.
        """
        added = 0
        for model_def in models:
            model_id = model_def.get("model_id")
            if not model_id:
                continue

            # Parse capabilities
            caps_str = model_def.get("capabilities", [])
            capabilities = {
                ModelCapability(c) for c in caps_str
                if c in ModelCapability.__members__
            }

            spec = ModelSpec(
                model_id=model_id,
                provider=model_def.get("provider", "unknown"),
                model_name=model_def.get("model_name", model_id),
                capabilities=capabilities,
                cost_per_million=model_def.get("cost_per_million", 0.0),
                quality_score=model_def.get("quality_score", 0.5),
                speed_score=model_def.get("speed_score", 0.5),
                context_window=model_def.get("context_window", 4096),
                supports_cache=model_def.get("supports_cache", False),
                tier=model_def.get("tier", "standard"),
            )

            if model_id not in self._model_registry:
                self._model_registry[model_id] = spec
                added += 1
            else:
                # Update existing
                self._model_registry[model_id] = spec

        logger.info(f"Updated model registry: added {added} models")
        return added

    def load_local_models_into_registry(self, workspace_id: str = "default") -> int:
        """Load user-registered local models into the learning router's registry.

        Reads LocalModelProvider + LocalModelCapabilities from the DB and calls
        update_model_registry with each as a ModelSpec (cost=0). This makes
        local models eligible for per-model predictor training and re-ranking —
        a local model that serves good responses will accumulate positive
        feedback and the re-ranker will start preferring it, at zero cost.

        Returns the number of models added/updated.
        """
        try:
            from core.database import get_db_session
            from core.models import LocalModelProvider, LocalModelCapabilities

            model_defs = []
            with get_db_session() as db:
                providers = db.query(LocalModelProvider).filter(
                    LocalModelProvider.workspace_id == workspace_id,
                    LocalModelProvider.is_active == True,  # noqa: E712
                ).all()

                for provider in providers:
                    caps = db.query(LocalModelCapabilities).filter(
                        LocalModelCapabilities.provider_id == provider.id
                    ).all()

                    if caps:
                        for cap in caps:
                            cap_list = []
                            if cap.supports_tools:
                                cap_list.append("tool_use")
                            if cap.supports_vision:
                                cap_list.append("vision")
                            if cap.supports_reasoning:
                                cap_list.append("reasoning")
                            model_defs.append({
                                "model_id": cap.model_id,
                                "provider": provider.provider_type,
                                "model_name": cap.model_id,
                                "capabilities": cap_list,
                                "cost_per_million": 0.0,
                                "quality_score": cap.quality_score or 0.5,
                                "speed_score": cap.speed_score or 0.5,
                                "context_window": cap.context_window or 8192,
                                "tier": "budget",
                            })
                    else:
                        # Provider has no configured capabilities — register
                        # with defaults so it at least appears in the registry.
                        model_defs.append({
                            "model_id": f"{provider.provider_type}_default",
                            "provider": provider.provider_type,
                            "model_name": f"{provider.name} (default)",
                            "capabilities": [],
                            "cost_per_million": 0.0,
                            "quality_score": 0.5,
                            "speed_score": 0.5,
                            "context_window": 8192,
                            "tier": "budget",
                        })

            if model_defs:
                return self.update_model_registry(model_defs)
            return 0
        except Exception as e:
            logger.debug(f"Could not load local models into registry (non-fatal): {e}")
            return 0

    async def export_routing_data(
        self, tenant_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """
        Export routing data for analysis or external training.

        Useful for:
        - Analyzing routing patterns
        - Training custom RouteLLM models
        - Cost optimization analysis
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Collect feedback data
        export_data = {
            "tenant_id": tenant_id,
            "export_date": datetime.now(timezone.utc).isoformat(),
            "data_days": days,
            "routing_feedback": [],
            "model_performance": {},
            "task_type_stats": {},
        }

        for feedback_list in self._preference_data.values():
            for feedback in feedback_list:
                if feedback.tenant_id != tenant_id:
                    continue

                if feedback.timestamp >= cutoff_date:
                    export_data["routing_feedback"].append({
                        "model_id": feedback.model_id,
                        "task_type": feedback.task_type,
                        "success": feedback.success,
                        "quality_satisfied": feedback.quality_satisfied,
                        "cost_within_budget": feedback.cost_within_budget,
                        "user_satisfaction": feedback.user_satisfaction,
                        "actual_cost": feedback.actual_cost,
                        "actual_latency_ms": feedback.actual_latency_ms,
                        "timestamp": feedback.timestamp.isoformat(),
                    })

        logger.info(
            f"Exported {len(export_data['routing_feedback'])} routing records "
            f"for tenant {tenant_id}"
        )

        return export_data

    def clear_learning_cache(self, tenant_id: Optional[str] = None):
        """Clear learned weights (useful for testing or reset)"""
        if tenant_id:
            # Clear only tenant-specific cache
            keys_to_delete = [
                k for k in self._router_cache
                if k.startswith(f"{tenant_id}:")
            ]
            for key in keys_to_delete:
                del self._router_cache[key]
        else:
            # Clear all cache
            self._router_cache.clear()

        logger.info(f"Cleared learning cache for tenant={tenant_id or 'all'}")

    # ========================================================================
    # HYPOTHESIS TREE REFINEMENT INTEGRATION (Phase 2026-06-19)
    # ========================================================================

    async def optimize_routing_configuration(
        self,
        tenant_id: str,
        task_type: str,
        requirements: Dict[str, Any],
        tier: str = "solo",
        optimization_goals: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Optimize multi-agent routing configuration using HTR.

        Explores different routing strategies (model sequences, caching,
        fallback patterns) to find optimal cost/quality tradeoffs.

        Args:
            tenant_id: Tenant ID for multi-tenancy
            task_type: Task type to optimize routing for
            requirements: Task requirements (latency, quality, cost targets)
            tier: Pricing tier for budget limits
            optimization_goals: Specific goals (cost, quality, latency)

        Returns:
            Optimization result with best routing configuration
        """
        from core.hypothesis_tree import HypothesisTree

        optimization_goals = optimization_goals or ["cost", "quality"]

        # Build an in-memory hypothesis tree to structure the exploration.
        # (HypothesisTree is a plain dataclass, not an ORM model — this method
        # computes and returns a recommendation; it does not persist a row.)
        tree_id = str(uuid.uuid4())
        tree = HypothesisTree(
            id=tree_id,
            task_id=task_type,
            task_description=f"Routing optimization for {task_type}",
            complexity_level="standard",
            tier=tier,
        )

        # Generate routing hypotheses
        hypotheses = await self._generate_routing_hypotheses(
            task_type,
            requirements,
            optimization_goals,
        )

        # Validate each hypothesis
        best_config = None
        best_score = -1.0
        nodes_created = 0
        pruning_events = []

        for hypothesis in hypotheses:
            if nodes_created >= self._get_tier_limit(tier):
                break

            # Validate routing hypothesis
            validation = await self._validate_routing_hypothesis(
                hypothesis,
                requirements,
            )

            if validation["passed"]:
                score = validation["score"]
                if score > best_score:
                    best_score = score
                    best_config = validation["config"]
            else:
                pruning_events.append({
                    "hypothesis": hypothesis.description,
                    "reason": validation.get("reason", "unknown"),
                    "details": validation.get("details", ""),
                })

            nodes_created += 1

        # Update tree with results
        tree.completed_at = datetime.now(timezone.utc)
        tree.total_nodes_expanded = nodes_created
        tree.total_tokens_used = 0  # Routing uses minimal tokens
        tree.winning_path = []

        logger.info(
            f"[RoutingOptimizer] Optimized {task_type} routing: "
            f"explored {nodes_created} hypotheses, best_score={best_score:.2f}"
        )

        return {
            "tenant_id": tenant_id,
            "task_type": task_type,
            "optimized_config": best_config,
            "tree_id": tree_id,
            "nodes_explored": nodes_created,
            "pruning_events": pruning_events,
            "optimization_score": best_score,
        }

    async def _generate_routing_hypotheses(
        self,
        task_type: str,
        requirements: Dict[str, Any],
        goals: List[str],
    ) -> List[Dict[str, Any]]:
        """Generate routing optimization hypotheses."""
        hypotheses = []

        # Get candidate models
        all_models = list(self._model_registry.values())

        # Hypothesis 1: Single best model
        best_model = max(all_models, key=lambda m: m.quality_score)
        hypotheses.append({
            "description": f"Single premium model: {best_model.model_name}",
            "config": {
                "strategy": "single_model",
                "primary_model": best_model.model_id,
                "fallback_enabled": False,
                "caching_enabled": True,
            },
            "estimated_cost": best_model.cost_per_million / 1000,
            "estimated_quality": best_model.quality_score,
            "estimated_latency": 1000 / best_model.speed_score,
        })

        # Hypothesis 2: Model cascade (premium → standard → cheap)
        premium = [m for m in all_models if m.tier == "premium"]
        standard = [m for m in all_models if m.tier in ("plus", "standard")]
        cheap = [m for m in all_models if m.tier == "standard" and "cheap" in m.model_name.lower()]

        if premium and standard:
            hypotheses.append({
                "description": "Cascade strategy: premium → standard",
                "config": {
                    "strategy": "cascade",
                    "models": [m.model_id for m in premium[:2]],
                    "fallback": standard[0].model_id if standard else None,
                    "caching_enabled": True,
                },
                "estimated_cost": (premium[0].cost_per_million + standard[0].cost_per_million) / 2000,
                "estimated_quality": premium[0].quality_score,
                "estimated_latency": 1200,
            })

        # Hypothesis 3: Caching-heavy strategy
        if "cost" in goals:
            cacheable_models = [m for m in all_models if m.supports_cache]
            if cacheable_models:
                hypotheses.append({
                    "description": "Aggressive caching with fastest model",
                    "config": {
                        "strategy": "cached",
                        "primary_model": cacheable_models[0].model_id,
                        "cache_ttl": 3600,
                        "cache_warmup": True,
                    },
                    "estimated_cost": cacheable_models[0].cost_per_million / 2000,
                    "estimated_quality": cacheable_models[0].quality_score * 0.95,
                    "estimated_latency": 200,
                })

        # Hypothesis 4: Quality-first strategy
        if "quality" in goals:
            high_quality = [m for m in all_models if m.quality_score > 0.95]
            if high_quality:
                hypotheses.append({
                    "description": "Quality-first with best models",
                    "config": {
                        "strategy": "quality_first",
                        "primary_model": high_quality[0].model_id,
                        "fallback": high_quality[1].model_id if len(high_quality) > 1 else None,
                        "caching_enabled": False,
                    },
                    "estimated_cost": high_quality[0].cost_per_million / 1000,
                    "estimated_quality": high_quality[0].quality_score,
                    "estimated_latency": 1500,
                })

        return hypotheses

    async def _validate_routing_hypothesis(
        self,
        hypothesis: Dict[str, Any],
        requirements: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate a routing hypothesis against requirements."""
        passed = True
        reason = None
        details = ""
        score = 0.0

        # Check cost requirements
        max_cost = requirements.get("max_cost_per_1k", 0.10)
        if hypothesis["estimated_cost"] > max_cost:
            passed = False
            reason = "cost_exceeded"
            details = f"Cost ${hypothesis['estimated_cost']:.4f} exceeds ${max_cost:.4f}"

        # Check latency requirements
        max_latency = requirements.get("max_latency_ms", 5000)
        if hypothesis["estimated_latency"] > max_latency:
            passed = False
            reason = "latency_exceeded"
            details = f"Latency {hypothesis['estimated_latency']:.0f}ms exceeds {max_latency}ms"

        # Check quality requirements
        min_quality = requirements.get("min_quality", 0.8)
        if hypothesis["estimated_quality"] < min_quality:
            passed = False
            reason = "quality_insufficient"
            details = f"Quality {hypothesis['estimated_quality']:.2f} below {min_quality:.2f}"

        if passed:
            # Calculate score based on requirements
            score = (
                (hypothesis["estimated_quality"] * 0.4) +
                (1.0 - min(1.0, hypothesis["estimated_cost"] / max_cost)) * 0.3 +
                (1.0 - min(1.0, hypothesis["estimated_latency"] / max_latency)) * 0.3
            )

        return {
            "passed": passed,
            "reason": reason,
            "details": details,
            "score": score,
            "config": hypothesis["config"],
        }

    def _get_tier_limit(self, tier: str) -> int:
        """Get max nodes for pricing tier."""
        return {"free": 3, "solo": 8, "enterprise": 20}.get(tier, 8)


def get_learning_router(db: Session) -> LearningBasedRouter:
    """Factory function to get learning-based router"""
    return LearningBasedRouter(db)
