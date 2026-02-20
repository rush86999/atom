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
from typing import Dict, Optional, Tuple

from core.llm.cognitive_tier_system import CognitiveTier, CognitiveClassifier
from core.llm.cache_aware_router import CacheAwareRouter
from core.llm.escalation_manager import EscalationManager, EscalationReason
from core.models import CognitiveTierPreference

logger = logging.getLogger(__name__)


class CognitiveTierService:
    """
    Orchestrates cognitive tier classification, routing, and escalation.

    This service integrates all tier components to provide end-to-end
    intelligent LLM routing that respects user settings while optimizing
    for cost and quality.

    Key behaviors:
    - Tier selection: Classify query and apply workspace preferences
    - Model selection: Get optimal model with cache-aware cost scoring
    - Budget checking: Enforce monthly and per-request budget limits
    - Escalation handling: Automatic quality-based tier escalation
    - Preference isolation: Each workspace has independent preferences

    Performance targets:
    - Tier selection: <20ms (classification + preference loading)
    - Model selection: <30ms (cost scoring + filtering)
    - Budget check: <10ms (database query + validation)

    Attributes:
        workspace_id: Workspace identifier for preference isolation
        db: Optional database session for preference/escalation persistence
        classifier: CognitiveClassifier for query complexity analysis
        cache_router: CacheAwareRouter for cost calculations
        escalation_manager: EscalationManager for quality-based escalation

    Example:
        >>> service = CognitiveTierService("default", db_session)
        >>> tier = service.select_tier("explain quantum computing")
        >>> provider, model = service.get_optimal_model(tier, 500)
        >>> cost = service.calculate_request_cost("prompt", tier, model)
        >>> if service.check_budget_constraint(cost['cost_cents']):
        ...     # Proceed with generation
        ...     pass
    """

    def __init__(self, workspace_id: str = "default", db_session=None):
        """
        Initialize the cognitive tier service.

        Args:
            workspace_id: Workspace identifier for preference isolation
            db_session: Optional SQLAlchemy session for database operations.
                       If None, preferences are not persisted and defaults are used.
        """
        self.workspace_id = workspace_id
        self.db = db_session

        # Initialize tier components
        self.classifier = CognitiveClassifier()
        self.escalation_manager = EscalationManager(db_session)

        # Lazy initialize cache router (requires pricing fetcher)
        self._cache_router = None

        logger.info(f"CognitiveTierService initialized for workspace: {workspace_id}")

    @property
    def cache_router(self) -> CacheAwareRouter:
        """
        Lazy-loaded cache-aware router.

        Delays initialization until first use to avoid circular dependencies
        with DynamicPricingFetcher.

        Returns:
            CacheAwareRouter instance
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

        Selection priority:
        1. User override (if provided)
        2. Workspace preference default_tier (if set)
        3. Automatic classification (with min/max constraints)

        Args:
            prompt: The query text to classify
            task_type: Optional task type hint (code, chat, analysis, etc.)
            user_tier_override: Optional user-specified tier (bypasses classification)

        Returns:
            Selected CognitiveTier for the query

        Example:
            >>> service = CognitiveTierService()
            >>> service.select_tier("hi").value
            'micro'
            >>> service.select_tier("debug distributed system").value
            'complex'
        """
        # Priority 1: User override bypasses all logic
        if user_tier_override:
            try:
                return CognitiveTier(user_tier_override)
            except ValueError:
                logger.warning(f"Invalid user tier override: {user_tier_override}")
                # Fall through to classification

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
                        CognitiveTier.COMPLEX
                    ]
                    classified_index = tier_order.index(classified_tier)
                    min_index = tier_order.index(min_tier)
                    if classified_index < min_index:
                        classified_tier = min_tier
                        logger.debug(f"Applied min_tier constraint: {min_tier.value}")
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
                        CognitiveTier.COMPLEX
                    ]
                    classified_index = tier_order.index(classified_tier)
                    max_index = tier_order.index(max_tier)
                    if classified_index > max_index:
                        classified_tier = max_tier
                        logger.debug(f"Applied max_tier constraint: {max_tier.value}")
                except ValueError:
                    logger.warning(f"Invalid max_tier in preference: {preference.max_tier}")

            # Apply default_tier preference
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

        Selection process:
        1. Load workspace preference for provider filtering
        2. Get all available models from BYOK handler
        3. Filter by preferred_providers if set
        4. Apply cache-aware cost scoring
        5. Filter by tier quality requirements
        6. Return lowest-cost model that meets quality threshold

        Args:
            tier: The cognitive tier to select a model for
            estimated_tokens: Estimated input token count for cache calculation
            requires_tools: Whether the model must support tool calling

        Returns:
            Tuple of (provider_id, model_name) or (None, None) if no models match

        Example:
            >>> service = CognitiveTierService()
            >>> provider, model = service.get_optimal_model(CognitiveTier.STANDARD, 500)
            >>> assert provider in ["openai", "anthropic", "deepseek", "gemini"]
        """
        from core.llm.byok_handler import MIN_QUALITY_BY_TIER

        # Get workspace preference
        preference = self.get_workspace_preference()

        # Get tier quality requirement
        min_quality = MIN_QUALITY_BY_TIER.get(tier, 0)

        # Get recommended models for this tier
        recommended_models = self.classifier.get_tier_models(tier)

        # Filter by preferred providers if set
        if preference and preference.preferred_providers:
            preferred_providers = set(preference.preferred_providers)
            # Filter models by provider
            filtered_models = []
            for model in recommended_models:
                # Map model to provider (simple heuristic)
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
            prompt_hash = hashlib.md5(model.encode()).hexdigest()[:16]
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

        # Return best model
        if scored_models:
            return scored_models[0][1], scored_models[0][2]

        return None, None

    def _model_to_provider(self, model: str) -> str:
        """
        Map a model name to its provider.

        Args:
            model: Model name (e.g., "gpt-4o", "claude-3-5-sonnet")

        Returns:
            Provider name (e.g., "openai", "anthropic")
        """
        # Simple heuristic mapping
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
    ) -> Dict:
        """
        Calculate the estimated cost for a request.

        Estimates:
        - Token count from prompt length
        - Cache hit probability from historical data
        - Effective cost with cache discount applied

        Args:
            prompt: The query text
            tier: The cognitive tier being used
            model: Optional model name for precise pricing

        Returns:
            Dictionary with keys:
            - cost_cents: Estimated cost in cents
            - effective_cost: Effective cost per token with cache discount
            - full_cost: Full cost per token without cache discount
            - cache_discount: Discount percentage (0-1)

        Example:
            >>> service = CognitiveTierService()
            >>> cost = service.calculate_request_cost("hello", CognitiveTier.MICRO, "gpt-4o-mini")
            >>> assert cost['cost_cents'] >= 0
        """
        # Estimate tokens
        estimated_tokens = len(prompt) // 4

        # Use default model for tier if not specified
        if not model:
            tier_models = self.classifier.get_tier_models(tier)
            model = tier_models[0] if tier_models else "gpt-4o-mini"

        provider = self._model_to_provider(model)

        # Calculate cache hit probability
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        cache_prob = self.cache_router.predict_cache_hit_probability(
            prompt_hash, self.workspace_id
        )

        # Calculate effective cost
        effective_cost = self.cache_router.calculate_effective_cost(
            model, provider, estimated_tokens, cache_prob
        )

        # Get full cost (no cache discount)
        full_cost = self.cache_router.calculate_effective_cost(
            model, provider, estimated_tokens, 0.0  # Zero cache probability
        )

        # Calculate discount percentage
        cache_discount = 1.0 - (effective_cost / full_cost) if full_cost > 0 else 0.0

        # Estimate total cost in cents (assuming 2x output tokens)
        total_cost = (effective_cost * estimated_tokens +
                     effective_cost * estimated_tokens * 2)  # Input + 2x output

        return {
            "cost_cents": total_cost * 100,  # Convert to cents
            "effective_cost": effective_cost,
            "full_cost": full_cost,
            "cache_discount": cache_discount,
            "estimated_tokens": estimated_tokens
        }

    def check_budget_constraint(self, request_cost_cents: float) -> bool:
        """
        Check if a request cost is within budget constraints.

        Validates both monthly budget and per-request limits from workspace
        preferences.

        Args:
            request_cost_cents: Estimated cost in cents

        Returns:
            True if within budget, False otherwise

        Example:
            >>> service = CognitiveTierService()
            >>> service.check_budget_constraint(0.5)  # 0.5 cents
            True
            >>> service.set_monthly_budget_cents(100)  # $1.00 monthly limit
            >>> service.check_budget_constraint(200)  # 2 cents exceeds budget
            False
        """
        preference = self.get_workspace_preference()

        if not preference:
            # No preference = no budget constraints
            return True

        # Check per-request limit
        if preference.max_cost_per_request_cents:
            if request_cost_cents > preference.max_cost_per_request_cents:
                logger.warning(
                    f"Request cost {request_cost_cents:.2f}¢ exceeds per-request limit "
                    f"{preference.max_cost_per_request_cents:.2f}¢"
                )
                return False

        # Check monthly budget (simplified - assumes workspace has cost tracking)
        # In production, this would query actual spending for the month
        if preference.monthly_budget_cents:
            # TODO: Query actual monthly spend from database
            # For now, just log a warning
            logger.debug(
                f"Monthly budget check: {request_cost_cents:.2f}¢ vs "
                f"{preference.monthly_budget_cents:.2f}¢ limit (not yet implemented)"
            )

        return True

    def handle_escalation(
        self,
        current_tier: CognitiveTier,
        response_quality: Optional[float] = None,
        error: Optional[str] = None,
        rate_limited: bool = False,
        request_id: Optional[str] = None
    ) -> Tuple[bool, Optional[EscalationReason], Optional[CognitiveTier]]:
        """
        Handle escalation decision for a failed or low-quality response.

        Checks workspace preference for auto-escalation enablement before
        delegating to EscalationManager.

        Args:
            current_tier: The cognitive tier that was just used
            response_quality: Optional quality score (0-100)
            error: Optional error message
            rate_limited: Whether the provider returned a rate limit error
            request_id: Optional request ID for tracking

        Returns:
            Tuple of (should_escalate, reason, target_tier):
            - should_escalate: True if escalation is recommended
            - reason: The EscalationReason if escalating, None otherwise
            - target_tier: The CognitiveTier to escalate to, None if not escalating

        Example:
            >>> service = CognitiveTierService()
            >>> should, reason, target = service.handle_escalation(
            ...     CognitiveTier.STANDARD,
            ...     response_quality=70
            ... )
            >>> if should:
            ...     # Re-query with target tier
            ...     pass
        """
        # Check if auto-escalation is enabled in preference
        preference = self.get_workspace_preference()
        if preference and preference.enable_auto_escalation is False:
            logger.debug("Auto-escalation disabled in workspace preference")
            return False, None, None

        # Delegate to escalation manager
        return self.escalation_manager.should_escalate(
            current_tier=current_tier,
            response_quality=response_quality,
            error=error,
            rate_limited=rate_limited,
            request_id=request_id
        )

    def get_workspace_preference(self) -> Optional[CognitiveTierPreference]:
        """
        Load workspace preference from database.

        Returns None if no preference is set (use system defaults).

        Args:
            None

        Returns:
            CognitiveTierPreference object or None

        Example:
            >>> service = CognitiveTierService("default", db_session)
            >>> pref = service.get_workspace_preference()
            >>> if pref:
            ...     print(f"Default tier: {pref.default_tier}")
        """
        if self.db:
            try:
                return self.db.query(CognitiveTierPreference).filter_by(
                    workspace_id=self.workspace_id
                ).first()
            except Exception as e:
                logger.error(f"Failed to load workspace preference: {e}")
        return None

    def record_cache_outcome(self, prompt_hash: str, was_cached: bool):
        """
        Record actual cache outcome for future predictions.

        Updates the cache hit history in CacheAwareRouter to improve
        cache hit probability predictions over time.

        Args:
            prompt_hash: Hash of prompt prefix (first 1k tokens)
            was_cached: Whether the request hit the prompt cache

        Example:
            >>> service = CognitiveTierService()
            >>> service.record_cache_outcome("abc123", True)
        """
        self.cache_router.record_cache_outcome(
            prompt_hash, self.workspace_id, was_cached
        )
