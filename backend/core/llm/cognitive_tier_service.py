from __future__ import annotations
"""
Cognitive Tier Service - Orchestration Layer for Intelligent LLM Routing

This service orchestrates all components of the cognitive tier system:
- CognitiveClassifier: Query complexity classification
- CacheAwareRouter: Cost calculation with prompt caching
- EscalationManager: Automatic tier escalation on quality issues
- Workspace preferences: User overrides and budget constraints

Purpose: Provide unified service layer for cognitive tier management that
considers all factors (query complexity, caching, escalation, preferences).

Author: Atom AI Platform
Created: 2026-02-20
"""

import hashlib
import logging
from typing import Dict, Optional, Tuple, Any, List

from core.llm.cache_aware_router import CacheAwareRouter
from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier
from core.llm.escalation_manager import EscalationManager, EscalationReason
from core.models import CognitiveTierPreference
from core.llm.registry.models import LLMModel

logger = logging.getLogger(__name__)


class CognitiveTierService:
    """
    Orchestrates cognitive tier classification, routing, and escalation.

    This service integrates all tier components to provide end-to-end
    intelligent LLM routing that respects user settings while optimizing
    for cost and quality.
    """

    def __init__(
        self, workspace_id: str = "default", db_session=None, tenant_id: Optional[str] = None
    ):
        """
        Initialize the cognitive tier service.

        Args:
            workspace_id: Workspace identifier for preference isolation
            db_session: Optional SQLAlchemy session for database operations.
            tenant_id: Optional tenant identifier (SaaS-friendly logic)
        """
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        self.db = db_session

        # Initialize tier components
        self.classifier = CognitiveClassifier()
        self.escalation_manager = EscalationManager(
            db_session, workspace_id=workspace_id, tenant_id=tenant_id
        )

        # Lazy initialize cache router (requires pricing fetcher)
        self._cache_router = None

        logger.info(f"CognitiveTierService initialized for workspace: {workspace_id}")

    @property
    def cache_router(self) -> CacheAwareRouter:
        """
        Lazy-loaded cache-aware router.
        """
        if self._cache_router is None:
            from core.dynamic_pricing_fetcher import get_pricing_fetcher
            self._cache_router = CacheAwareRouter(get_pricing_fetcher())
        return self._cache_router

    def select_tier(
        self,
        prompt: str,
        task_type: Optional[str] = None,
        user_tier_override: Optional[str] = None
    ) -> CognitiveTier:
        """
        Select the appropriate cognitive tier for a query.
        """
        # Priority 1: User override
        if user_tier_override:
            try:
                return CognitiveTier(user_tier_override)
            except ValueError:
                logger.warning(f"Invalid user tier override: {user_tier_override}")

        # Priority 2: Load workspace preference
        preference = self.get_workspace_preference()

        # Classify the query
        classified_tier = self.classifier.classify(prompt, task_type)

        # Priority 3: Apply preference constraints
        if preference:
            # Apply min_tier constraint
            if preference.min_tier:
                try:
                    min_tier = CognitiveTier(preference.min_tier)
                    tier_order = [
                        CognitiveTier.MICRO,
                        CognitiveTier.STANDARD,
                        CognitiveTier.VERSATILE,
                        CognitiveTier.HEAVY,
                        CognitiveTier.COMPLEX,
                    ]
                    classified_index = tier_order.index(classified_tier)
                    min_index = tier_order.index(min_tier)
                    if classified_index < min_index:
                        classified_tier = min_tier
                except ValueError:
                    logger.warning(f"Invalid min_tier in preference: {preference.min_tier}")

            # Apply max_tier constraint
            if preference.max_tier:
                try:
                    max_tier = CognitiveTier(preference.max_tier)
                    tier_order = [
                        CognitiveTier.MICRO,
                        CognitiveTier.STANDARD,
                        CognitiveTier.VERSATILE,
                        CognitiveTier.HEAVY,
                        CognitiveTier.COMPLEX,
                    ]
                    classified_index = tier_order.index(classified_tier)
                    max_index = tier_order.index(max_tier)
                    if classified_index > max_index:
                        classified_tier = max_tier
                except ValueError:
                    logger.warning(f"Invalid max_tier in preference: {preference.max_tier}")

            # Apply default_tier override from preference
            if preference.default_tier:
                try:
                    return CognitiveTier(preference.default_tier)
                except ValueError:
                    logger.warning(f"Invalid default_tier in preference: {preference.default_tier}")

        return classified_tier

    def get_optimal_model(
        self,
        tier: CognitiveTier,
        estimated_tokens: int,
        requires_tools: bool = False
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Get the optimal provider and model for a cognitive tier.
        """
        # Get workspace preference
        preference = self.get_workspace_preference()

        # Get recommended models for this tier
        # Priority 1: Dynamic discovery from database registry
        recommended_models = self._get_dynamic_tier_models(tier)

        # Priority 2: Fallback to hardcoded recommendations if DB is empty
        if not recommended_models:
            recommended_models = self.classifier.get_tier_models(tier)

        # Filter by preferred providers if set
        if preference and preference.preferred_providers:
            preferred_providers = set(preference.preferred_providers)
            filtered_models = []
            for model in recommended_models:
                provider = self._model_to_provider(model)
                if provider in preferred_providers:
                    filtered_models.append(model)
            recommended_models = filtered_models

        if not recommended_models:
            logger.warning(f"No models found for tier: {tier.value}")
            return None, None

        # Score models by effective cost (cache-aware)
        scored_models = []
        for model in recommended_models:
            provider = self._model_to_provider(model)

            # Calculate cache hit probability
            prompt_hash = hashlib.sha256(f"{self.workspace_id}:{model}".encode()).hexdigest()[:16]
            cache_prob = self.cache_router.predict_cache_hit_probability(
                prompt_hash, self.workspace_id
            )

            # Calculate effective cost
            effective_cost = self.cache_router.calculate_effective_cost(
                model, provider, estimated_tokens, cache_prob
            )

            scored_models.append((effective_cost, provider, model))

        # Sort by cost (lowest first)
        scored_models.sort(key=lambda x: x[0])

        if scored_models:
            return scored_models[0][1], scored_models[0][2]

        return None, None

    def _get_dynamic_tier_models(self, tier: CognitiveTier) -> List[str]:
        """
        Query the LLMModel registry for models matching a cognitive tier's quality band.
        """
        if not self.db:
            return []

        # Define quality bands
        quality_map = {
            CognitiveTier.MICRO: (0, 40),
            CognitiveTier.STANDARD: (40, 65),
            CognitiveTier.VERSATILE: (65, 80),
            CognitiveTier.HEAVY: (80, 92),
            CognitiveTier.COMPLEX: (92, 101),
        }

        min_q, max_q = quality_map.get(tier, (0, 100))

        try:
            # Query active, non-deprecated models within quality band
            # Upstream might have tenant-isolated models or global ones
            query = self.db.query(LLMModel).filter(
                LLMModel.is_deprecated == False,
                LLMModel.quality_score >= min_q,
                LLMModel.quality_score < max_q,
            )
            
            # Restrict to tenant if provided
            if self.tenant_id:
                query = query.filter(LLMModel.tenant_id == self.tenant_id)
            
            # For MICRO, also include models with "mini" or "haiku" in name
            if tier == CognitiveTier.MICRO:
                micro_filter = LLMModel.model_name.ilike("%mini%") | LLMModel.model_name.ilike("%haiku%")
                query = query.filter((LLMModel.quality_score < 40) | micro_filter)

            models = query.order_by(LLMModel.quality_score.desc()).all()
            return [m.model_name for m in models]
        except Exception as e:
            logger.error(f"Failed to query dynamic models for tier {tier.value}: {e}")
            return []

    def _model_to_provider(self, model: str) -> str:
        """
        Heuristic mapping of model name to provider.
        """
        if model.startswith("gpt") or model.startswith("o3") or model.startswith("o4"):
            return "openai"
        elif model.startswith("claude"):
            return "anthropic"
        elif model.startswith("deepseek"):
            return "deepseek"
        elif model.startswith("gemini"):
            return "gemini"
        elif model.startswith("qwen"):
            return "moonshot"
        elif model.startswith("minimax"):
            return "minimax"
        else:
            return "unknown"

    def calculate_request_cost(
        self,
        prompt: str,
        tier: CognitiveTier,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate the estimated cost for a request.
        """
        estimated_tokens = len(prompt) // 4

        if not model:
            tier_models = self.classifier.get_tier_models(tier)
            model = tier_models[0] if tier_models else "gpt-4o-mini"

        provider = self._model_to_provider(model)

        # Calculate cache hit probability
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        cache_prob = self.cache_router.predict_cache_hit_probability(prompt_hash, self.workspace_id)

        # Calculate effective cost
        effective_cost = self.cache_router.calculate_effective_cost(
            model, provider, estimated_tokens, cache_prob
        )

        # Get full cost (no cache discount)
        full_cost = self.cache_router.calculate_effective_cost(
            model, provider, estimated_tokens, 0.0
        )

        cache_discount = 1.0 - (effective_cost / full_cost) if full_cost > 0 else 0.0

        # Estimate total cost in cents (Input + 2x output tokens)
        total_cost = (effective_cost * estimated_tokens * 3)

        return {
            "cost_cents": total_cost * 100,
            "effective_cost": effective_cost,
            "full_cost": full_cost,
            "cache_discount": cache_discount,
            "estimated_tokens": estimated_tokens,
        }

    def check_budget_constraint(self, request_cost_cents: float) -> bool:
        """
        Check if request cost is within budget.
        """
        preference = self.get_workspace_preference()
        if not preference:
            return True

        if preference.max_cost_per_request_cents:
            if request_cost_cents > preference.max_cost_per_request_cents:
                logger.warning(f"Request cost {request_cost_cents:.2f}c exceeds limit")
                return False

        return True

    def handle_escalation(
        self,
        current_tier: CognitiveTier,
        response_quality: Optional[float] = None,
        error: Optional[str] = None,
        rate_limited: bool = False,
        request_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[EscalationReason], Optional[CognitiveTier]]:
        """
        Handle escalation decision.
        """
        preference = self.get_workspace_preference()
        if preference and preference.enable_auto_escalation is False:
            return False, None, None

        return self.escalation_manager.should_escalate(
            current_tier=current_tier,
            response_quality=response_quality,
            error=error,
            rate_limited=rate_limited,
            request_id=request_id,
        )

    def get_workspace_preference(self) -> Optional[CognitiveTierPreference]:
        """
        Load preferences from database.
        """
        if self.db:
            try:
                query = self.db.query(CognitiveTierPreference).filter(
                    CognitiveTierPreference.workspace_id == self.workspace_id
                )
                if self.tenant_id:
                    query = query.filter(CognitiveTierPreference.tenant_id == self.tenant_id)
                return query.first()
            except Exception as e:
                logger.error(f"Failed to load preferences: {e}")
        return None

    def record_cache_outcome(self, prompt_hash: str, was_cached: bool):
        """
        Record actual cache outcome.
        """
        self.cache_router.record_cache_outcome(prompt_hash, self.workspace_id, was_cached)
