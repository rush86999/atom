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

Ported from SaaS (atom-saas) with upstream compatibility:
- No UUID dependencies (uses String IDs)
- Compatible with upstream model structure
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional, List, Dict, Set, Tuple, Union
from collections import defaultdict

import numpy as np
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import Tenant, TenantSetting

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


class RoutingDecision(str, Enum):
    """Routing decision outcome"""

    ROUTE_SUCCESS = "route_success"  # Request routed successfully
    ROUTE_FAILURE = "route_failure"  # Routing failed, used fallback
    QUALITY_FAILURE = "quality_failure"  # Routed but quality insufficient
    COST_OVERAGE = "cost_overage"  # Routed but exceeded budget


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
        self._router_cache: Dict[str, Tuple[ModelSpec, float]] = {}
        self._training_samples: List[Dict[str, Any]] = []
        # SECURITY/STABILITY: caps to prevent unbounded memory growth
        # in long-running processes. Each cache evicts oldest entries
        # when the cap is exceeded.
        self._max_router_cache_size = 1000
        self._max_preference_data_per_key = 50
        self._max_training_samples = 5000

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
        """Filter models by latency requirements"""
        # Simplified: use speed_score as proxy for latency
        # speed_score 0.9 = ~50ms, 0.5 = ~500ms
        fast_models = []

        for model in candidates:
            # Convert speed_score to approximate latency
            if model.speed_score >= 0.7:
                fast_models.append(model)

        return fast_models

    def _score_candidates(
        self,
        candidates: List[ModelSpec],
        request: RoutingRequest,
    ) -> List[Tuple[ModelSpec, float]]:
        """Score candidates based on learned preferences and context"""
        scores = []

        # Get learned preference weights for this task type
        weights = self._get_learned_weights(request.task_type, request.tenant_id)

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

            scores.append((model, score))

        # Sort by score (descending)
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def _get_learned_weights(
        self, task_type: str, tenant_id: str
    ) -> Dict[str, float]:
        """Get learned preference weights for task type"""
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
        """Create routing result"""
        routing_time = datetime.now(timezone.utc)
        routing_time_ms = (routing_time.timestamp() * 1000) - start_ms

        # Estimate cost
        expected_cost = (model.cost_per_million * request.estimated_tokens) / 1_000_000

        return RoutingResult(
            selected_model=model,
            confidence=confidence,
            expected_cost=expected_cost,
            expected_quality=model.quality_score,
            reasoning=reasoning,
            alternatives=alternatives,
            routing_time_ms=routing_time_ms,
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

        This enables active learning by collecting preference data.
        """
        feedback_key = f"{feedback.tenant_id}:{feedback.task_type}"

        if feedback_key not in self._preference_data:
            self._preference_data[feedback_key] = []

        self._preference_data[feedback_key].append(feedback)

        # Cap per-key history to prevent unbounded growth in long-running
        # processes. Keep the most recent entries (highest signal value).
        if len(self._preference_data[feedback_key]) > self._max_preference_data_per_key:
            overflow = len(self._preference_data[feedback_key]) - self._max_preference_data_per_key
            del self._preference_data[feedback_key][:overflow]

        # Trigger retraining after accumulating enough feedback
        if len(self._preference_data[feedback_key]) >= 10:
            await self._retrain_router(feedback.tenant_id, feedback.task_type)

        logger.debug(
            f"Recorded routing feedback: tenant={feedback.tenant_id}, "
            f"model={feedback.model_id}, success={feedback.success}"
        )

    async def _retrain_router(self, tenant_id: str, task_type: str) -> None:
        """
        Retrain router with accumulated preference data.

        Implements active learning by updating routing weights.
        """
        feedback_list = self._preference_data.get(f"{tenant_id}:{task_type}", [])

        if not feedback_list:
            return

        # Simple weight adjustment based on success rates
        model_success = defaultdict(lambda: {"success": 0, "total": 0})

        for feedback in feedback_list:
            model_success[feedback.model_id]["total"] += 1
            if feedback.success and feedback.quality_satisfied:
                model_success[feedback.model_id]["success"] += 1

        # Update learned weights (simplified)
        # In production, this would use proper ML training
        cache_key = f"{tenant_id}:{task_type}"
        self._router_cache[cache_key] = (
            None,  # Placeholder for trained model
            0.0,  # Placeholder for accuracy
        )
        # Evict oldest entries if cache exceeds cap. Dicts preserve insertion
        # order in Python 3.7+ so the first key is the oldest.
        if len(self._router_cache) > self._max_router_cache_size:
            oldest = next(iter(self._router_cache))
            del self._router_cache[oldest]

        logger.info(
            f"Retrained router for tenant={tenant_id}, task={task_type} "
            f"with {len(feedback_list)} samples"
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


def get_learning_router(db: Session) -> LearningBasedRouter:
    """Factory function to get learning-based router"""
    return LearningBasedRouter(db)
