"""Round 80 — Offline routing weight tuner coverage (multi-objective Pareto
search over observed feedback, replayed counterfactually).

Covers: candidate evaluation, Pareto dominance, weight normalization,
task-gating (MIN_SAMPLES_PER_TASK), warm-start with current weights,
best-from-frontier selection, and writing winners back via
``_set_cached_weights``.
"""
from __future__ import annotations

import asyncio
import random
from types import SimpleNamespace

import pytest

from core.llm.routing import offline_tuner as ot
from core.llm.routing.offline_tuner import (
    DEFAULT_FALLBACK,
    DEFAULT_TASK_WEIGHTS,
    MIN_SAMPLES_PER_TASK,
    N_CANDIDATES,
    _evaluate_candidate,
    _is_dominated,
    _normalize_weights,
    tune_routing_weights,
)


class _Spec:
    def __init__(self, quality=0.5, cost=1.0, speed=0.5):
        self.quality_score = quality
        self.cost_per_million = cost
        self.speed_score = speed


class _FB:
    def __init__(self, model_id, success=True, quality_satisfied=True,
                 cost=None, latency=None):
        self.model_id = model_id
        self.success = success
        self.quality_satisfied = quality_satisfied
        self.actual_cost = cost
        self.actual_latency_ms = latency


def _router(preference_data=None, registry=None, cache=None):
    router = SimpleNamespace(
        _preference_data=preference_data or {},
        _model_registry=registry or {},
        _router_cache=cache or {},
        _set_cached_weights_calls=[],
    )
    router._set_cached_weights = lambda key, weights, tenant: router._set_cached_weights_calls.append(
        (key, weights, tenant)
    )
    return router


def _rows(model_ids, n, success_rate=1.0, cost=0.01, latency=800):
    rows = []
    rng = random.Random(42)
    for i in range(n):
        mid = model_ids[i % len(model_ids)]
        rows.append(
            _FB(mid, success=success_rate >= 1.0 or rng.random() < success_rate,
                quality_satisfied=True, cost=cost, latency=latency + i)
        )
    return rows


class TestNormalizeWeights:
    def test_sums_to_one(self):
        w = _normalize_weights(1, 1, 1)
        assert w["quality"] == pytest.approx(1 / 3)
        assert w["cost"] == pytest.approx(1 / 3)
        assert w["speed"] == pytest.approx(1 / 3)

    def test_zero_total_falls_back(self):
        assert _normalize_weights(0, 0, 0) == DEFAULT_FALLBACK

    def test_negative_totals_fall_back(self):
        assert _normalize_weights(-1, -1, 0) == DEFAULT_FALLBACK


class TestIsDominated:
    def test_dominated_when_all_axes_are_better_or_equal(self):
        # Objectives: higher sat is better; lower cost/latency is better.
        assert _is_dominated((0.5, 10.0, 500), (1.0, 5.0, 100)) is True
        assert _is_dominated((0.5, 10.0, 500), (0.5, 10.0, 500)) is True  # equal → dominated
        assert _is_dominated((0.5, 10.0, 500), (0.4, 20.0, 600)) is False
        assert _is_dominated((0.9, 10.0, 500), (0.9, 20.0, 100)) is False
        assert _is_dominated((0.5, 10.0, 500), (0.6, 10.0, 600)) is False  # better sat, worse lat


class TestEvaluateCandidate:
    def _specs(self):
        return {
            "quality-leader": _Spec(quality=0.95, cost=50.0, speed=0.4),
            "cheap-leader": _Spec(quality=0.3, cost=1.0, speed=0.95),
            "balanced": _Spec(quality=0.6, cost=10.0, speed=0.7),
        }

    def test_picks_quality_leader_under_quality_weights(self):
        specs = self._specs()
        rows = [{
            "models": {mid: {
                "quality_score": s.quality_score,
                "cost_per_million": s.cost_per_million,
                "speed_score": s.speed_score,
                "success": 1.0, "actual_cost": 0.05, "actual_latency_ms": 400,
            } for mid, s in specs.items()},
        }]
        sat, cost, _ = _evaluate_candidate({"quality": 1.0, "cost": 0.0, "speed": 0.0}, rows, specs)
        assert sat == 1.0  # winner (quality-leader) succeeded
        assert cost == pytest.approx(0.05)

    def test_picks_cheap_leader_under_cost_weights(self):
        specs = self._specs()
        # quality-leader FAILED this row; cheap leader succeeded.
        rows = [{
            "models": {
                "quality-leader": {"quality_score": 0.95, "cost_per_million": 50.0, "speed_score": 0.4,
                                   "success": 0.0, "actual_cost": 0.5, "actual_latency_ms": 300},
                "cheap-leader": {"quality_score": 0.3, "cost_per_million": 1.0, "speed_score": 0.95,
                                 "success": 1.0, "actual_cost": 0.01, "actual_latency_ms": 500},
            },
        }]
        sat, cost, _ = _evaluate_candidate({"quality": 0.0, "cost": 1.0, "speed": 0.0}, rows, specs)
        assert sat == 1.0  # cheap leader won and succeeded
        assert cost == pytest.approx(0.01)

    def test_p95_latency(self):
        rows = [{
            "models": {"m": {"quality_score": 0.5, "cost_per_million": 1.0, "speed_score": 0.5,
                             "success": 1.0, "actual_cost": 0.01, "actual_latency_ms": lat}},
        } for lat in range(100, 200)]
        _, _, p95 = _evaluate_candidate({"quality": 0.4, "cost": 0.3, "speed": 0.3}, rows, {"m": _Spec()})
        # sorted latencies 100..199 → p95 index = int(100*0.95) = 95 → 195
        assert p95 == 195

    def test_no_matching_rows_returns_empty_signal(self):
        sat, cost, lat = _evaluate_candidate(DEFAULT_FALLBACK, [{"models": {}}], {})
        assert sat == 0.0
        assert cost == 0.0
        assert lat == float("inf")

    def test_cost_score_normalized_by_max_cost(self):
        rows = [{
            "models": {
                "a": {"quality_score": 0.5, "cost_per_million": 10.0, "speed_score": 0.5,
                      "success": 1.0, "actual_cost": 0.01, "actual_latency_ms": 100},
                "b": {"quality_score": 0.5, "cost_per_million": 40.0, "speed_score": 0.5,
                      "success": 1.0, "actual_cost": 0.01, "actual_latency_ms": 100},
            },
        }]
        # With pure cost weights, the cheaper model (a) must win.
        sat, _, _ = _evaluate_candidate({"quality": 0.0, "cost": 1.0, "speed": 0.0}, rows, {})
        assert sat == 1.0


class TestTuneRoutingWeights:
    async def test_no_data_returns_reason(self):
        router = _router()
        result = await tune_routing_weights(router)
        assert result["tasks_tuned"] == []
        assert result["tasks_tuned_count"] == 0
        assert "reason" in result
        assert f"≥{MIN_SAMPLES_PER_TASK}" in result["reason"]
        assert router._set_cached_weights_calls == []

    async def test_insufficient_rows_not_tuned(self):
        registry = {"gpt-4o": _Spec()}
        data = {"default:code_generation": _rows(["gpt-4o"], 10)}
        result = await tune_routing_weights(_router(data, registry))
        # With task_types=None, under-threshold tasks are simply excluded
        # (the tuner reports the early-return reason instead).
        assert result["tasks_tuned"] == []
        assert result["tasks_tuned_count"] == 0
        assert "reason" in result
        assert result["reason"].startswith(f"No task types with ≥{MIN_SAMPLES_PER_TASK}")

    async def test_explicit_task_type_with_insufficient_rows_skipped(self):
        registry = {"gpt-4o": _Spec()}
        data = {"default:code_generation": _rows(["gpt-4o"], 10)}
        result = await tune_routing_weights(
            _router(data, registry), task_types=["code_generation"]
        )
        assert result["tasks_tuned"][0]["status"] == "skipped"
        assert "Only 10 samples" in result["tasks_tuned"][0]["reason"]
        assert result["tasks_tuned_count"] == 0

    async def test_other_tenant_data_ignored(self):
        registry = {"gpt-4o": _Spec()}
        data = {
            "default:code_generation": _rows(["gpt-4o"], MIN_SAMPLES_PER_TASK),
            "other:code_generation": _rows(["gpt-4o"], MIN_SAMPLES_PER_TASK),
        }
        result = await tune_routing_weights(_router(data, registry))
        # Only the default: task was tuned; other: never gathered.
        assert len(result["tasks_tuned"]) == 1

    async def test_rows_with_unregistered_models_dropped(self):
        registry = {"gpt-4o": _Spec()}
        data = {"default:code_generation": _rows(["missing-model"], MIN_SAMPLES_PER_TASK)}
        result = await tune_routing_weights(
            _router(data, registry), task_types=["code_generation"]
        )
        # All rows dropped at gather time → 0 samples → skipped.
        assert result["tasks_tuned"][0]["status"] == "skipped"
        assert "Only 0 samples" in result["tasks_tuned"][0]["reason"]

    async def test_tunes_and_writes_weights_back(self):
        registry = {"gpt-4o": _Spec(quality=0.9, cost=10.0, speed=0.6)}
        data = {"default:code_generation": _rows(["gpt-4o"], MIN_SAMPLES_PER_TASK)}
        router = _router(data, registry)
        result = await tune_routing_weights(router)

        tuned = result["tasks_tuned"][0]
        assert tuned["status"] == "tuned"
        assert tuned["samples"] == MIN_SAMPLES_PER_TASK
        assert tuned["candidates_evaluated"] == N_CANDIDATES + 1  # warm-start + random
        assert tuned["pareto_front_size"] >= 1
        assert set(tuned["best_weights"]) == {"quality", "cost", "speed"}
        assert sum(tuned["best_weights"].values()) == pytest.approx(1.0)
        assert tuned["objectives"]["satisfaction"] >= 0.0
        assert tuned["previous_weights"] == DEFAULT_TASK_WEIGHTS["code_generation"]

        # Winner written back to the live router.
        assert len(router._set_cached_weights_calls) == 1
        key, weights, tenant = router._set_cached_weights_calls[0]
        assert key == "default:code_generation"
        assert tenant == "default"
        assert weights == tuned["best_weights"]
        assert result["tasks_tuned_count"] == 1

    async def test_explicit_task_types_only_those(self):
        registry = {"gpt-4o": _Spec()}
        data = {
            "default:code_generation": _rows(["gpt-4o"], MIN_SAMPLES_PER_TASK),
            "default:question_answering": _rows(["gpt-4o"], MIN_SAMPLES_PER_TASK),
        }
        result = await tune_routing_weights(
            _router(data, registry), task_types=["question_answering"]
        )
        assert [t["task"] for t in result["tasks_tuned"]] == ["question_answering"]

    async def test_unknown_task_defaults_to_fallback_weights(self):
        registry = {"gpt-4o": _Spec()}
        data = {"default:weird_task": _rows(["gpt-4o"], MIN_SAMPLES_PER_TASK)}
        result = await tune_routing_weights(_router(data, registry))
        tuned = result["tasks_tuned"][0]
        assert tuned["previous_weights"] == DEFAULT_FALLBACK

    async def test_single_model_rows_keep_current_weights(self):
        """Each recorded feedback row carries exactly ONE model, so every
        candidate weight set scores it identically — the warm-started current
        weights (first candidate) must be preserved."""
        registry = {"gpt-4o": _Spec(quality=0.9, cost=10.0, speed=0.6)}
        data = {"default:code_generation": _rows(["gpt-4o"], MIN_SAMPLES_PER_TASK)}
        current = {"quality": 0.5, "cost": 0.2, "speed": 0.3}
        router = _router(data, registry, cache={"default:code_generation": current})
        result = await tune_routing_weights(router)
        tuned = result["tasks_tuned"][0]
        assert tuned["best_weights"] == current
        assert router._set_cached_weights_calls[0][1] == current

    async def test_multi_model_feedback_shapes_weights(self):
        """Rows that record BOTH candidates let weights matter: a task whose
        successes come from the expensive quality leader tunes toward quality."""
        rng = random.Random(7)
        registry = {
            "quality-leader": _Spec(quality=0.95, cost=50.0, speed=0.4),
            "cheap-leader": _Spec(quality=0.3, cost=1.0, speed=0.95),
        }
        rows = []
        for i in range(MIN_SAMPLES_PER_TASK):
            # quality-leader always succeeds; cheap-leader only half the time.
            rows.append(_FB("quality-leader", success=True, cost=0.5, latency=400))
            rows.append(_FB("cheap-leader", success=rng.random() < 0.5, cost=0.01, latency=150))
        data = {"default:reasoning": rows}
        result = await tune_routing_weights(_router(data, registry))
        tuned = result["tasks_tuned"][0]
        assert tuned["status"] == "tuned"
        assert tuned["best_weights"]["quality"] > tuned["best_weights"]["cost"]

    async def test_two_tasks_tuned(self):
        registry = {"gpt-4o": _Spec()}
        data = {
            "default:code_generation": _rows(["gpt-4o"], MIN_SAMPLES_PER_TASK),
            "default:tool_use": _rows(["gpt-4o"], MIN_SAMPLES_PER_TASK),
        }
        router = _router(data, registry)
        result = await tune_routing_weights(router)
        assert result["tasks_tuned_count"] == 2
        assert len(result["tasks_tuned"]) == 2
        assert len(router._set_cached_weights_calls) == 2
