"""
Learning-Based LLM Routing Module

Phase 3 of ATOM_ENHANCEMENT_PLAN - Learning-Based LLM Routing.

Based on 2025-2026 research:
- "RouteLLM: Learning to Route" (arXiv:2406.18665)
- "State of AI 2025: 100T Token Study" (openrouter.ai)

Modules:
- preference_collector: User feedback and preference data collection
- routellm_trainer: Training pipeline for learning-based router
- cache_optimizer: Predictive cache warming and optimization
"""

from core.llm.routing.preference_collector import (
    PreferenceDataCollector,
    TrainingExample,
    RoutingDecision,
    RoutingFeedback,
    FeedbackConfig,
    FeedbackType,
    FeedbackSource,
    RoutingOutcome,
    get_preference_collector,
)

from core.llm.routing.routellm_trainer import (
    RouteLLMTrainer,
    RouterEvaluator,
    TrainingConfig,
    TrainingResult,
    ModelType,
    TrainingStatus,
    FeatureExtractor,
    get_router_trainer,
    get_router_evaluator,
)

from core.llm.routing.cache_optimizer import (
    CacheOptimizer,
    CacheWarmer,
    AccessPatternAnalyzer,
    CacheOptimizationConfig,
    CacheStrategy,
    AccessPattern,
    get_cache_optimizer,
    get_cache_warmer,
    get_pattern_analyzer,
)

__all__ = [
    # Preference collector
    "PreferenceDataCollector",
    "TrainingExample",
    "RoutingDecision",
    "RoutingFeedback",
    "FeedbackConfig",
    "FeedbackType",
    "FeedbackSource",
    "RoutingOutcome",
    "get_preference_collector",

    # RouteLLM trainer
    "RouteLLMTrainer",
    "RouterEvaluator",
    "TrainingConfig",
    "TrainingResult",
    "ModelType",
    "TrainingStatus",
    "FeatureExtractor",
    "get_router_trainer",
    "get_router_evaluator",

    # Cache optimizer
    "CacheOptimizer",
    "CacheWarmer",
    "AccessPatternAnalyzer",
    "CacheOptimizationConfig",
    "CacheStrategy",
    "AccessPattern",
    "get_cache_optimizer",
    "get_cache_warmer",
    "get_pattern_analyzer",
]
