"""Coverage wave 81 — core/byok_competitive_endpoints.py (97% → ~100%).

Closes the remaining holes: get_cost_optimizer double-checked-lock singleton
construction, all seven endpoints' success + error paths, provider-intelligence
budget/premium/reasoning/rising recommendation branches + relative-cost tiers,
value-proposition advantage branches, workflow-optimization edge cases
(default step names, daily frequency, zero-current-cost, missing provider
fallback), and market-insights rising/high-cost strategic recommendations.
"""
from dataclasses import dataclass
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.byok_competitive_endpoints as bce
from core.byok_cost_optimizer import (
    BYOKCostOptimizer,
    CompetitiveInsight,
    CostOptimizationRecommendation,
    UsagePattern,
)
from core.byok_endpoints import BYOKManager


@dataclass
class _Usage:
    """asdict()-able usage-stat stand-in for provider-intelligence/VP paths."""
    total_requests: int
    cost_accumulated: float


def _usage_pattern(user_id="u1"):
    return UsagePattern(
        user_id=user_id,
        task_distribution={"general": 40, "chat": 30, "code": 20, "analysis": 10},
        peak_hours=[9, 10, 14],
        preferred_providers={"deepseek": 60.0, "openai": 40.0},
        monthly_budget=50.0,
        cost_sensitivity="medium",
        quality_preference="balanced",
    )


def _recommendation(provider="deepseek", confidence=0.9, reasoning="cheaper",
                    savings=0.5, pct=40.0):
    return CostOptimizationRecommendation(
        task_type="general",
        current_provider="openai",
        recommended_provider=provider,
        estimated_savings=savings,
        savings_percentage=pct,
        reasoning=reasoning,
        confidence=confidence,
        alternative_providers=[{"provider": "moonshot", "savings": 0.2}],
    )


@pytest.fixture
def manager():
    m = Mock(spec=BYOKManager)
    m.usage_stats = {"openai": _Usage(total_requests=10, cost_accumulated=100.0),
                     "deepseek": _Usage(total_requests=5, cost_accumulated=50.0)}
    m.providers = {
        "openai": Mock(cost_per_token=0.00001),
        "deepseek": Mock(cost_per_token=0.000001),
    }
    return m


@pytest.fixture
def optimizer(manager):
    opt = BYOKCostOptimizer(manager)
    opt.usage_patterns["u1"] = _usage_pattern()
    return opt


@pytest.fixture
def client(optimizer):
    app = FastAPI()
    app.include_router(bce.router)
    app.dependency_overrides[bce.get_cost_optimizer] = lambda: optimizer
    return TestClient(app)


def _report(**overrides):
    providers = {
        "openai": {
            "market_trend": "stable", "market_position": "premium",
            "quality_ranking": 1, "cost_ranking": 4,
            "cost_efficiency_score": 65, "quality_score": 95, "has_keys": True,
        },
        "deepseek": {
            "market_trend": "rising", "market_position": "budget",
            "quality_ranking": 2, "cost_ranking": 1,
            "cost_efficiency_score": 95, "quality_score": 85, "has_keys": True,
        },
    }
    market = {
        "providers_with_keys": 2,
        "average_quality_score": 90.0,
        "average_cost_efficiency": 80.0,
        "market_segments": {"budget": 2, "premium": 1},
    }
    report = {"providers": providers, "market_overview": market}
    report.update(overrides)
    return report


class TestSingleton:
    def test_get_cost_optimizer_creates_and_caches(self, manager):
        old = bce._cost_optimizer
        bce._cost_optimizer = None
        try:
            first = bce.get_cost_optimizer(manager)
            second = bce.get_cost_optimizer(manager)
            assert isinstance(first, BYOKCostOptimizer)
            assert first is second
        finally:
            bce._cost_optimizer = old

    def test_get_cost_optimizer_returns_existing(self, manager):
        old = bce._cost_optimizer
        bce._cost_optimizer = "sentinel"
        try:
            assert bce.get_cost_optimizer(manager) == "sentinel"
        finally:
            bce._cost_optimizer = old


class TestCompetitiveAnalysis:
    def test_success(self, client, optimizer):
        optimizer.get_competitive_analysis_report = Mock(return_value=_report())
        resp = client.get("/api/v1/byok/competitive-analysis")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["report"]["market_overview"]["providers_with_keys"] == 2
        assert "generated_at" in body

    def test_error_500(self, client, optimizer):
        optimizer.get_competitive_analysis_report = Mock(side_effect=RuntimeError("boom"))
        resp = client.get("/api/v1/byok/competitive-analysis")
        assert resp.status_code == 500


class TestOptimizeCosts:
    def test_existing_pattern_skips_analysis(self, client, optimizer):
        optimizer.get_cost_optimization_recommendations = Mock(
            return_value=_recommendation())
        optimizer.analyze_user_usage_pattern = Mock()
        resp = client.post("/api/v1/byok/optimize-costs", json={
            "user_id": "u1", "task_type": "code", "context": {"x": 1}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["recommendation"]["recommended_provider"] == "deepseek"
        assert body["user_pattern"]["user_id"] == "u1"
        optimizer.analyze_user_usage_pattern.assert_not_called()
        optimizer.get_cost_optimization_recommendations.assert_called_once_with(
            "u1", "code", {"x": 1})

    def test_new_user_analyzed(self, client, optimizer):
        optimizer.get_cost_optimization_recommendations = Mock(
            return_value=_recommendation())

        def _analyze(uid):
            optimizer.usage_patterns[uid] = _usage_pattern(uid)
            return optimizer.usage_patterns[uid]

        optimizer.analyze_user_usage_pattern = Mock(side_effect=_analyze)
        resp = client.post("/api/v1/byok/optimize-costs", json={"user_id": "new"})
        assert resp.status_code == 200
        optimizer.analyze_user_usage_pattern.assert_called_once_with("new")
        assert resp.json()["user_pattern"]["user_id"] == "new"

    def test_default_user_id(self, client, optimizer):
        optimizer.get_cost_optimization_recommendations = Mock(
            return_value=_recommendation())
        resp = client.post("/api/v1/byok/optimize-costs", json={})
        assert resp.status_code == 200
        assert resp.json()["user_pattern"]["user_id"] == "default"

    def test_error_500(self, client, optimizer):
        optimizer.get_cost_optimization_recommendations = Mock(
            side_effect=RuntimeError("boom"))
        resp = client.post("/api/v1/byok/optimize-costs", json={})
        assert resp.status_code == 500


class TestSimulateSavings:
    def test_defaults(self, client, optimizer):
        optimizer.simulate_cost_savings = Mock(return_value={"savings": 12.5})
        resp = client.post("/api/v1/byok/simulate-savings", json={})
        assert resp.status_code == 200
        assert resp.json()["simulation"] == {"savings": 12.5}
        optimizer.simulate_cost_savings.assert_called_once_with("default", 6, 0.8)

    def test_custom_values(self, client, optimizer):
        optimizer.simulate_cost_savings = Mock(return_value={})
        resp = client.post("/api/v1/byok/simulate-savings", json={
            "user_id": "u1", "months": 12, "adoption_rate": 0.5})
        assert resp.status_code == 200
        optimizer.simulate_cost_savings.assert_called_once_with("u1", 12, 0.5)

    def test_error_500(self, client, optimizer):
        optimizer.simulate_cost_savings = Mock(side_effect=RuntimeError("boom"))
        resp = client.post("/api/v1/byok/simulate-savings", json={})
        assert resp.status_code == 500


class TestValueProposition:
    def test_full_advantages(self, client, optimizer):
        report = _report()
        report["market_overview"]["providers_with_keys"] = 3
        optimizer.get_competitive_analysis_report = Mock(return_value=report)
        resp = client.get("/api/v1/byok/value-proposition")
        assert resp.status_code == 200
        vp = resp.json()["value_proposition"]
        advantages = vp["competitive_advantages"]
        assert "Unique access to both budget and premium AI providers" in advantages
        assert "Superior cost efficiency compared to single-provider platforms" in advantages
        assert "Multi-provider redundancy and optimization" in advantages
        assert vp["metrics"]["active_providers"] == 3
        assert vp["metrics"]["total_available"] == 2
        assert vp["metrics"]["estimated_monthly_savings"] == 22.5
        assert vp["metrics"]["average_quality_score"] == 90.0
        assert len(vp["byok_advantages"]) == 6

    def test_no_advantages(self, client, optimizer):
        optimizer.get_competitive_analysis_report = Mock(return_value=_report(
            providers={"openai": {
                "market_trend": "stable", "market_position": "premium",
                "quality_ranking": 1, "cost_ranking": 4,
                "cost_efficiency_score": 50, "quality_score": 95,
                "has_keys": False}},
            market_overview={"providers_with_keys": 1,
                             "average_quality_score": 90.0,
                             "average_cost_efficiency": 60.0,
                             "market_segments": {}},
        ))
        resp = client.get("/api/v1/byok/value-proposition")
        vp = resp.json()["value_proposition"]
        assert vp["competitive_advantages"] == []
        assert vp["metrics"]["active_providers"] == 1
        # savings come from the manager's usage stats, independent of the report
        assert vp["metrics"]["estimated_monthly_savings"] == 22.5

    def test_error_500(self, client, optimizer):
        optimizer.get_competitive_analysis_report = Mock(side_effect=RuntimeError("boom"))
        resp = client.get("/api/v1/byok/value-proposition")
        assert resp.status_code == 500


class TestProviderIntelligence:
    def test_budget_provider(self, client, optimizer):
        optimizer.byok_manager.get_provider_status = Mock(return_value={
            "provider": {"cost_per_token": 0.000001}})
        resp = client.get("/api/v1/byok/provider-intelligence/moonshot")
        assert resp.status_code == 200
        intel = resp.json()["intelligence"]
        assert "Ideal for high-volume, routine tasks" in intel["recommendations"]
        assert "Data processing" in intel["best_use_cases"]
        assert "Excellent for multi-step problem solving" in intel["recommendations"]
        assert "Emerging provider with improving capabilities" in intel["recommendations"]
        assert intel["cost_analysis"]["relative_cost"] == "Low"

    def test_premium_provider(self, client, optimizer):
        optimizer.byok_manager.get_provider_status = Mock(return_value={
            "provider": {"cost_per_token": 0.00002}})
        resp = client.get("/api/v1/byok/provider-intelligence/openai")
        intel = resp.json()["intelligence"]
        assert "Best for critical, complex tasks" in intel["recommendations"]
        assert "Complex reasoning" in intel["best_use_cases"]
        assert intel["cost_analysis"]["relative_cost"] == "Medium"

    def test_high_cost_provider(self, client, optimizer):
        optimizer.byok_manager.get_provider_status = Mock(return_value={
            "provider": {"cost_per_token": 0.00005}})
        resp = client.get("/api/v1/byok/provider-intelligence/anthropic")
        assert resp.json()["intelligence"]["cost_analysis"]["relative_cost"] == "High"

    def test_usage_stats_none(self, client, optimizer):
        optimizer.byok_manager.get_provider_status = Mock(return_value={
            "provider": {"cost_per_token": 0.000001}})
        optimizer.byok_manager.usage_stats = {}
        resp = client.get("/api/v1/byok/provider-intelligence/moonshot")
        assert resp.json()["intelligence"]["usage_stats"] is None

    def test_not_found_404(self, client, optimizer):
        optimizer.byok_manager.get_provider_status = Mock(return_value={
            "provider": {"cost_per_token": 0.0}})
        resp = client.get("/api/v1/byok/provider-intelligence/unknown")
        assert resp.status_code == 404

    def test_value_error_404(self, client, optimizer):
        optimizer.byok_manager.get_provider_status = Mock(
            side_effect=ValueError("bad"))
        resp = client.get("/api/v1/byok/provider-intelligence/openai")
        assert resp.status_code == 404

    def test_error_500(self, client, optimizer):
        optimizer.byok_manager.get_provider_status = Mock(
            side_effect=RuntimeError("boom"))
        resp = client.get("/api/v1/byok/provider-intelligence/openai")
        assert resp.status_code == 500


class TestWorkflowOptimization:
    def _steps(self):
        return {"user_id": "u1", "id": "wf-1", "steps": [
            {"name": "extract", "task_type": "code", "estimated_tokens": 1000,
             "current_provider": "openai"},
            {"name": "notify", "task_type": "chat", "estimated_tokens": 500},
        ]}

    def test_success(self, client, optimizer):
        optimizer.get_cost_optimization_recommendations = Mock(
            return_value=_recommendation())
        resp = client.post("/api/v1/byok/workflow-optimization",
                           json=self._steps())
        assert resp.status_code == 200
        body = resp.json()
        assert body["workflow_id"] == "wf-1"
        assert len(body["optimizations"]) == 2
        assert body["optimizations"][0]["step_name"] == "extract"
        assert body["optimizations"][0]["recommended_provider"] == "deepseek"
        assert body["optimizations"][0]["confidence"] == 0.9
        assert body["optimizations"][0]["reasoning"] == "cheaper"
        assert body["summary"]["steps_optimized"] == 2
        assert body["summary"]["total_current_cost"] > 0
        assert body["summary"]["total_optimized_cost"] > 0
        assert body["summary"]["total_savings_percentage"] > 0
        assert any("Switch to deepseek for extract" in r
                   for r in body["recommendations"])

    def test_no_steps_400(self, client):
        resp = client.post("/api/v1/byok/workflow-optimization",
                           json={"steps": []})
        assert resp.status_code == 400

    def test_default_step_name_and_provider(self, client, optimizer):
        optimizer.get_cost_optimization_recommendations = Mock(
            return_value=_recommendation())
        resp = client.post("/api/v1/byok/workflow-optimization", json={
            "steps": [{"estimated_tokens": 100}]})
        opt = resp.json()["optimizations"][0]
        assert opt["step_name"] == "step_0"
        assert opt["current_provider"] == "openai"

    def test_daily_frequency_multiplies_savings(self, client, optimizer):
        optimizer.get_cost_optimization_recommendations = Mock(
            return_value=_recommendation())
        resp = client.post("/api/v1/byok/workflow-optimization", json={
            "frequency": "daily",
            "steps": [{"estimated_tokens": 1000, "current_provider": "openai"}]})
        summary = resp.json()["summary"]
        assert summary["estimated_monthly_savings"] == summary["total_savings"] * 30

    def test_zero_current_cost_zero_percentage(self, client, optimizer):
        optimizer.get_cost_optimization_recommendations = Mock(
            return_value=_recommendation())
        optimizer.byok_manager.providers = {"deepseek": Mock(cost_per_token=0.000001)}
        resp = client.post("/api/v1/byok/workflow-optimization", json={
            "steps": [{"estimated_tokens": 0, "current_provider": "missing"}]})
        opt = resp.json()["optimizations"][0]
        assert opt["savings_percentage"] == 0.0
        assert opt["current_cost"] == 0.0

    def test_error_500(self, client, optimizer):
        optimizer.get_cost_optimization_recommendations = Mock(
            side_effect=RuntimeError("boom"))
        resp = client.post("/api/v1/byok/workflow-optimization",
                           json=self._steps())
        assert resp.status_code == 500


class TestMarketInsights:
    def test_rising_and_high_cost_recommendations(self, client, optimizer):
        optimizer.get_competitive_analysis_report = Mock(return_value=_report())
        resp = client.get("/api/v1/byok/market-insights")
        assert resp.status_code == 200
        insights = resp.json()["insights"]
        assert insights["provider_trends"]["deepseek"]["trend"] == "rising"
        assert insights["market_segments"] == {"budget": 2, "premium": 1}
        assert insights["cost_trends"]["most_cost_effective"] == "deepseek"
        assert insights["quality_trends"]["highest_quality"] == "openai"
        types = [r["type"] for r in insights["strategic_recommendations"]]
        assert "opportunity" in types
        assert "cost_optimization" in types

    def test_no_rising_no_high_cost(self, client, optimizer):
        optimizer.get_competitive_analysis_report = Mock(return_value=_report(
            providers={"openai": {
                "market_trend": "declining", "market_position": "premium",
                "quality_ranking": 1, "cost_ranking": 4,
                "cost_efficiency_score": 80, "quality_score": 95,
                "has_keys": False}},
        ))
        resp = client.get("/api/v1/byok/market-insights")
        insights = resp.json()["insights"]
        assert insights["strategic_recommendations"] == []

    def test_empty_providers(self, client, optimizer):
        optimizer.get_competitive_analysis_report = Mock(return_value=_report(
            providers={},
            market_overview={"providers_with_keys": 0,
                             "average_quality_score": 0.0,
                             "average_cost_efficiency": 0.0,
                             "market_segments": {}},
        ))
        resp = client.get("/api/v1/byok/market-insights")
        insights = resp.json()["insights"]
        assert insights["cost_trends"]["most_cost_effective"] is None
        assert insights["quality_trends"]["highest_quality"] is None

    def test_error_500(self, client, optimizer):
        optimizer.get_competitive_analysis_report = Mock(side_effect=RuntimeError("boom"))
        resp = client.get("/api/v1/byok/market-insights")
        assert resp.status_code == 500
