# -*- coding: utf-8 -*-
"""Round 80 — zero-coverage gap: core/byok_competitive_endpoints.py.

All seven routes on the BYOK competitive router are exercised with a fake
cost optimizer (dependency override) so no real BYOK manager / keys are
needed. Covers happy paths, 404s, 400 validation and the error path (500).
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.byok_competitive_endpoints import router, get_cost_optimizer


@dataclass
class FakeRecommendation:
    task_type: str
    current_provider: str
    recommended_provider: str
    estimated_savings: float
    savings_percentage: float
    reasoning: str
    confidence: float
    alternative_providers: list = field(default_factory=list)


@dataclass
class FakeUsagePattern:
    user_id: str
    task_distribution: dict = field(default_factory=lambda: {"general": 100})
    peak_hours: list = field(default_factory=list)
    preferred_providers: dict = field(default_factory=dict)
    monthly_budget: float = 50.0
    cost_sensitivity: str = "medium"
    quality_preference: str = "balanced"


@dataclass
class FakeInsight:
    provider_id: str
    market_position: str
    unique_features: list
    best_for_tasks: list
    cost_efficiency_score: float
    quality_score: float
    reliability_score: float
    market_trend: str


@dataclass
class FakeUsage:
    provider_id: str
    total_requests: int = 10
    successful_requests: int = 9
    failed_requests: int = 1
    total_tokens_used: int = 5000
    cost_accumulated: float = 12.5


@dataclass
class FakeProvider:
    id: str
    name: str
    description: str = ""
    api_key_env_var: str = "X"
    cost_per_token: float = 0.00001
    is_active: bool = True


class FakeManager:
    def __init__(self):
        self.usage_stats = {
            "openai": FakeUsage("openai", cost_accumulated=100.0),
            "deepseek": FakeUsage("deepseek", cost_accumulated=10.0),
        }
        self.providers = {
            "openai": FakeProvider("openai", "OpenAI", cost_per_token=0.00003),
            "deepseek": FakeProvider("deepseek", "DeepSeek", cost_per_token=0.000005),
            "moonshot": FakeProvider("moonshot", "Moonshot", cost_per_token=0.000002),
        }

    def get_provider_status(self, provider_id):
        if provider_id not in self.providers:
            raise ValueError(f"Provider {provider_id} not found")
        return {"provider": asdict(self.providers[provider_id]), "status": "active"}


class FakeCostOptimizer:
    def __init__(self):
        self.byok_manager = FakeManager()
        self.usage_patterns = {}
        self.competitive_insights = {
            "openai": FakeInsight("openai", "premium", ["Reasoning"], ["code", "complex_reasoning"], 65, 95, 90, "stable"),
            "deepseek": FakeInsight("deepseek", "budget", ["Cheap"], ["code", "math", "reasoning"], 95, 85, 80, "rising"),
            "moonshot": FakeInsight("moonshot", "budget", ["Kimi"], ["general"], 90, 80, 75, "rising"),
        }
        self._analysis_calls = 0
        self._analysis_raises = False

    def analyze_user_usage_pattern(self, user_id, days=30):
        self.usage_patterns[user_id] = FakeUsagePattern(user_id=user_id)
        return self.usage_patterns[user_id]

    def get_cost_optimization_recommendations(self, user_id, task_type="general", context=None):
        if task_type == "code":
            return FakeRecommendation(task_type, "openai", "deepseek", 2.0, 40.0,
                                      "DeepSeek is cheaper", 0.9)
        return FakeRecommendation(task_type, "openai", "moonshot", 1.0, 25.0,
                                  "Moonshot is cheaper", 0.8)

    def get_competitive_analysis_report(self):
        self._analysis_calls += 1
        if self._analysis_raises:
            raise RuntimeError("boom")
        return {
            "generated_at": datetime.now().isoformat(),
            "providers": {
                "openai": {"market_position": "premium", "market_trend": "stable",
                           "quality_score": 95, "cost_efficiency_score": 65,
                           "quality_ranking": 1, "cost_ranking": 3, "has_keys": True},
                "deepseek": {"market_position": "budget", "market_trend": "rising",
                             "quality_score": 85, "cost_efficiency_score": 95,
                             "quality_ranking": 2, "cost_ranking": 1, "has_keys": True},
                "moonshot": {"market_position": "budget", "market_trend": "rising",
                             "quality_score": 80, "cost_efficiency_score": 90,
                             "quality_ranking": 3, "cost_ranking": 2, "has_keys": True},
            },
            "market_overview": {
                "total_providers": 3,
                "providers_with_keys": 3,
                "average_quality_score": 86.7,
                "average_cost_efficiency": 83.3,
                "market_segments": {"budget": 2, "mid_range": 0, "premium": 1},
            },
            "recommendations": [],
        }

    def simulate_cost_savings(self, user_id, months, adoption_rate):
        if user_id not in self.usage_patterns:
            self.analyze_user_usage_pattern(user_id)
        return {
            "user_id": user_id,
            "simulation_period_months": months,
            "adoption_rate": adoption_rate,
            "current_monthly_cost": 50.0,
            "optimized_monthly_cost": 37.5,
            "monthly_savings": 12.5,
            "total_projected_savings": 75.0,
            "savings_percentage": 25.0,
            "task_breakdown": {},
        }


@pytest.fixture()
def optimizer():
    return FakeCostOptimizer()


@pytest.fixture()
def client(optimizer):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_cost_optimizer] = lambda: optimizer
    with TestClient(app) as c:
        yield c


class TestCompetitiveAnalysis:
    def test_returns_report(self, client, optimizer):
        resp = client.get("/api/v1/byok/competitive-analysis")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["report"]["market_overview"]["total_providers"] == 3
        assert "generated_at" in body

    def test_internal_error_becomes_500(self, client, optimizer):
        optimizer._analysis_raises = True
        resp = client.get("/api/v1/byok/competitive-analysis")
        assert resp.status_code == 500
        assert "Internal error" in resp.json()["detail"]


class TestOptimizeCosts:
    def test_unknown_user_gets_pattern_analyzed(self, client, optimizer):
        resp = client.post("/api/v1/byok/optimize-costs", json={"user_id": "u1", "task_type": "code"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["recommendation"]["recommended_provider"] == "deepseek"
        assert body["user_pattern"]["user_id"] == "u1"
        assert "u1" in optimizer.usage_patterns

    def test_known_user_skips_analysis(self, client, optimizer):
        optimizer.analyze_user_usage_pattern("u2")
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(optimizer, "analyze_user_usage_pattern",
                       lambda *a, **k: pytest.fail("should not re-analyze"))
            resp = client.post("/api/v1/byok/optimize-costs", json={"user_id": "u2"})
        assert resp.status_code == 200
        assert resp.json()["recommendation"]["task_type"] == "general"

    def test_defaults_applied(self, client):
        resp = client.post("/api/v1/byok/optimize-costs", json={})
        assert resp.status_code == 200
        assert resp.json()["user_pattern"]["user_id"] == "default"


class TestSimulateSavings:
    def test_simulation_response(self, client):
        resp = client.post("/api/v1/byok/simulate-savings", json={"user_id": "u1", "months": 6, "adoption_rate": 0.8})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["simulation"]["simulation_period_months"] == 6
        assert body["simulation"]["adoption_rate"] == 0.8
        assert body["simulation"]["total_projected_savings"] == 75.0

    def test_defaults(self, client):
        resp = client.post("/api/v1/byok/simulate-savings", json={})
        assert resp.status_code == 200
        sim = resp.json()["simulation"]
        assert sim["simulation_period_months"] == 6
        assert sim["adoption_rate"] == 0.8


class TestValueProposition:
    def test_value_proposition(self, client):
        resp = client.get("/api/v1/byok/value-proposition")
        assert resp.status_code == 200
        body = resp.json()
        vp = body["value_proposition"]
        assert len(vp["byok_advantages"]) == 6
        assert "Unique access to both budget and premium AI providers" in vp["competitive_advantages"]
        assert "Multi-provider redundancy and optimization" in vp["competitive_advantages"]
        assert vp["metrics"]["active_providers"] == 3
        assert vp["metrics"]["total_available"] == 3
        assert vp["metrics"]["average_quality_score"] == 86.7
        assert vp["metrics"]["average_cost_efficiency"] == 83.3
        assert vp["metrics"]["estimated_monthly_savings"] == 16.5  # 15% of 110.0
        assert len(vp["market_differentiators"]) == 5

    def test_error_path_500(self, client, optimizer):
        optimizer._analysis_raises = True
        resp = client.get("/api/v1/byok/value-proposition")
        assert resp.status_code == 500


class TestProviderIntelligence:
    def test_premium_provider(self, client):
        resp = client.get("/api/v1/byok/provider-intelligence/openai")
        assert resp.status_code == 200
        body = resp.json()
        intel = body["intelligence"]
        assert body["provider_id"] == "openai"
        assert intel["provider_info"]["name"] == "OpenAI"
        assert "Best for critical, complex tasks" in intel["recommendations"]
        assert "Complex reasoning" in intel["best_use_cases"]
        assert intel["cost_analysis"]["relative_cost"] == "High"
        assert intel["usage_stats"]["cost_accumulated"] == 100.0

    def test_budget_rising_provider(self, client):
        resp = client.get("/api/v1/byok/provider-intelligence/deepseek")
        assert resp.status_code == 200
        intel = resp.json()["intelligence"]
        assert "Ideal for high-volume, routine tasks" in intel["recommendations"]
        assert "Emerging provider with improving capabilities" in intel["recommendations"]
        assert intel["cost_analysis"]["relative_cost"] == "Low"

    def test_unknown_provider_404(self, client):
        resp = client.get("/api/v1/byok/provider-intelligence/not-a-provider")
        assert resp.status_code == 404

    def test_missing_insight_404(self, client, optimizer):
        manager = optimizer.byok_manager
        manager.providers["ghost"] = FakeProvider("ghost", "Ghost", cost_per_token=0.00001)
        resp = client.get("/api/v1/byok/provider-intelligence/ghost")
        assert resp.status_code == 404


class TestWorkflowOptimization:
    def test_multi_step_workflow(self, client):
        resp = client.post("/api/v1/byok/workflow-optimization", json={
            "id": "wf-1",
            "user_id": "u1",
            "steps": [
                {"name": "parse", "task_type": "general", "estimated_tokens": 1000, "current_provider": "openai"},
                {"name": "codegen", "task_type": "code", "estimated_tokens": 1000, "current_provider": "openai"},
            ],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["optimizations"]) == 2
        summary = body["summary"]
        assert summary["steps_optimized"] == 2
        assert summary["total_savings"] > 0
        assert summary["total_savings_percentage"] > 0
        codegen = body["optimizations"][1]
        assert codegen["recommended_provider"] == "deepseek"
        # Savings % is computed from real per-token costs in the endpoint:
        # openai 0.00003 → deepseek 0.000005 per token.
        assert codegen["savings_percentage"] == pytest.approx(83.33, abs=0.01)
        assert any("Switch to deepseek for codegen" in r for r in body["recommendations"])

    def test_daily_frequency_multiplies_monthly_savings(self, client):
        resp = client.post("/api/v1/byok/workflow-optimization", json={
            "id": "wf-2", "frequency": "daily",
            "steps": [{"name": "s1", "task_type": "general", "estimated_tokens": 1000, "current_provider": "openai"}],
        })
        body = resp.json()
        daily = body["summary"]["total_savings"]
        assert body["summary"]["estimated_monthly_savings"] == pytest.approx(daily * 30)

    def test_empty_steps_400(self, client):
        resp = client.post("/api/v1/byok/workflow-optimization", json={"id": "wf-3", "steps": []})
        assert resp.status_code == 400

    def test_error_path_500(self, client, optimizer):
        def boom(*a, **k):
            raise RuntimeError("boom")
        optimizer.get_cost_optimization_recommendations = boom
        resp = client.post("/api/v1/byok/workflow-optimization", json={
            "steps": [{"name": "s1", "task_type": "general"}],
        })
        assert resp.status_code == 500


class TestMarketInsights:
    def test_insights_structure(self, client):
        resp = client.get("/api/v1/byok/market-insights")
        assert resp.status_code == 200
        insights = resp.json()["insights"]
        assert insights["provider_trends"]["deepseek"]["trend"] == "rising"
        assert insights["market_segments"] == {"budget": 2, "mid_range": 0, "premium": 1}
        assert insights["cost_trends"]["most_cost_effective"] == "deepseek"
        assert insights["cost_trends"]["cost_leaders"][:3]
        assert insights["quality_trends"]["highest_quality"] == "openai"
        assert insights["quality_trends"]["quality_leaders"][0] == "openai"

    def test_rising_provider_recommendation(self, client):
        resp = client.get("/api/v1/byok/market-insights")
        insights = resp.json()["insights"]
        recommendations = insights["strategic_recommendations"]
        assert any(r["type"] == "opportunity" and "deepseek" in r["description"] for r in recommendations)
        assert any(r["type"] == "cost_optimization" and r["priority"] == "high" for r in recommendations)

    def test_error_path_500(self, client, optimizer):
        optimizer._analysis_raises = True
        resp = client.get("/api/v1/byok/market-insights")
        assert resp.status_code == 500
