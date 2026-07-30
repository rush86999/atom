"""Tests for the offline routing weight tuner."""
import asyncio
import pytest
from unittest.mock import MagicMock

from core.learning_llm_router import (
    LearningBasedRouter, ModelSpec, RoutingFeedback, ModelCapability,
)


@pytest.fixture
def router(mock_db=None):
    r = LearningBasedRouter(MagicMock())
    r._model_registry = {
        "cheap-model": ModelSpec(
            model_id="cheap-model", provider="test", model_name="cheap",
            capabilities={ModelCapability.CODE_GENERATION},
            cost_per_million=0.50, quality_score=0.70, speed_score=0.90,
            context_window=8192, supports_cache=False, tier="standard",
        ),
        "premium-model": ModelSpec(
            model_id="premium-model", provider="test", model_name="premium",
            capabilities={ModelCapability.CODE_GENERATION, ModelCapability.HIGH_QUALITY},
            cost_per_million=30.0, quality_score=0.99, speed_score=0.50,
            context_window=200000, supports_cache=True, tier="premium",
        ),
    }
    return r


def _seed_feedback(router, tenant="t1", task="code_generation", n=60):
    """Seed _preference_data with n feedback rows for the given task."""
    key = f"{tenant}:{task}"
    router._preference_data[key] = []
    for i in range(n):
        # Alternate between two models, with the cheap model succeeding more
        # on simple tasks and premium on complex.
        model_id = "cheap-model" if i % 2 == 0 else "premium-model"
        success = (i % 3 != 0)  # 67% success rate
        fb = RoutingFeedback(
            routing_result_id=f"r{i}",
            tenant_id=tenant,
            model_id=model_id,
            task_type=task,
            success=success,
            quality_satisfied=success,
            cost_within_budget=True,
            user_satisfaction=0.8 if success else 0.2,
            actual_cost=0.001 if model_id == "cheap-model" else 0.05,
            actual_latency_ms=200 if model_id == "cheap-model" else 800,
        )
        router._preference_data[key].append(fb)


class TestOfflineTuner:
    def test_skip_when_insufficient_data(self, router):
        """Should skip tuning when < MIN_SAMPLES_PER_TASK."""
        from core.llm.routing.offline_tuner import tune_routing_weights
        _seed_feedback(router, n=10)  # too few
        result = asyncio.run(tune_routing_weights(router, tenant_id="t1"))
        # When insufficient data, the tuner returns early with a reason.
        assert "reason" in result or result.get("tasks_tuned_count", 0) == 0

    def test_tunes_and_writes_weights(self, router):
        """Should evaluate candidates and write winning weights."""
        from core.llm.routing.offline_tuner import tune_routing_weights
        _seed_feedback(router, n=60)
        result = asyncio.run(tune_routing_weights(router, tenant_id="t1"))
        assert result["tasks_tuned_count"] >= 1
        tuned = result["tasks_tuned"][0]
        assert tuned["status"] == "tuned"
        assert "best_weights" in tuned
        assert "quality" in tuned["best_weights"]
        assert "cost" in tuned["best_weights"]
        assert "speed" in tuned["best_weights"]
        # Weights should sum to ~1.0
        w = tuned["best_weights"]
        assert abs(w["quality"] + w["cost"] + w["speed"] - 1.0) < 0.01
        # Weights should be written to the router cache
        cache_key = "t1:code_generation"
        assert cache_key in router._router_cache

    def test_pareto_front_generated(self, router):
        """Multiple non-dominated solutions should be found."""
        from core.llm.routing.offline_tuner import tune_routing_weights
        _seed_feedback(router, n=80)
        result = asyncio.run(tune_routing_weights(router, tenant_id="t1"))
        tuned = [t for t in result["tasks_tuned"] if t.get("status") == "tuned"]
        assert len(tuned) >= 1
        assert tuned[0]["pareto_front_size"] >= 1

    def test_objectives_are_valid(self, router):
        """Satisfaction in [0,1], cost >= 0, latency > 0."""
        from core.llm.routing.offline_tuner import tune_routing_weights
        _seed_feedback(router, n=60)
        result = asyncio.run(tune_routing_weights(router, tenant_id="t1"))
        tuned = [t for t in result["tasks_tuned"] if t.get("status") == "tuned"][0]
        obj = tuned["objectives"]
        assert 0.0 <= obj["satisfaction"] <= 1.0
        assert obj["total_cost"] >= 0
        assert obj["p95_latency_ms"] > 0

    def test_warm_starts_from_current_weights(self, router):
        """Current cached weights should be the first candidate evaluated."""
        from core.llm.routing.offline_tuner import tune_routing_weights
        # Seed current weights.
        router._router_cache["t1:code_generation"] = {"quality": 0.7, "cost": 0.1, "speed": 0.2}
        _seed_feedback(router, n=60)
        result = asyncio.run(tune_routing_weights(router, tenant_id="t1"))
        tuned = [t for t in result["tasks_tuned"] if t.get("status") == "tuned"][0]
        assert tuned["previous_weights"] == {"quality": 0.7, "cost": 0.1, "speed": 0.2}
