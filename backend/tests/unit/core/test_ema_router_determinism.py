import os
import pytest
from unittest.mock import MagicMock
from core.learning_llm_router import (
    LearningBasedRouter, ModelSpec, RoutingRequest, RoutingFeedback, ModelCapability
)

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def ema_router(mock_db):
    router = LearningBasedRouter(db=mock_db)
    router._model_registry = {
        "gpt-4": ModelSpec(
            model_id="gpt-4",
            provider="openai",
            model_name="gpt-4",
            capabilities={ModelCapability.REASONING, ModelCapability.CODE_GENERATION},
            cost_per_million=10.0,
            quality_score=0.9,
            speed_score=0.5,
            context_window=8192,
            supports_cache=True,
            tier="premium"
        ),
        "gpt-3.5": ModelSpec(
            model_id="gpt-3.5",
            provider="openai",
            model_name="gpt-3.5",
            capabilities={ModelCapability.REASONING, ModelCapability.CODE_GENERATION},
            cost_per_million=2.0,
            quality_score=0.7,
            speed_score=0.8,
            context_window=4096,
            supports_cache=True,
            tier="standard"
        )
    }
    return router

def test_ema_scoring_disabled_by_default(ema_router, monkeypatch):
    monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", "false")
    req = RoutingRequest(tenant_id="t1", task_type="code_generation", estimated_tokens=100)
    candidates = list(ema_router._model_registry.values())
    res_normal = ema_router._score_candidates(candidates, req)
    assert len(res_normal) == 2
    
def test_ema_scoring_enabled(ema_router, monkeypatch):
    monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", "true")
    req = RoutingRequest(tenant_id="t1", task_type="code_generation", estimated_tokens=100)
    candidates = list(ema_router._model_registry.values())
    
    res_fallback = ema_router._score_candidates(candidates, req)
    assert len(res_fallback) == 2
    
    fb_cheap = RoutingFeedback(
        routing_result_id="r1",
        tenant_id="t1",
        model_id="gpt-3.5",
        task_type="code_generation",
        success=True,
        quality_satisfied=True,
        cost_within_budget=True,
        actual_latency_ms=100.0,
        actual_cost=0.0002
    )
    fb_expensive = RoutingFeedback(
        routing_result_id="r2",
        tenant_id="t1",
        model_id="gpt-4",
        task_type="code_generation",
        success=False,
        quality_satisfied=False,
        cost_within_budget=True,
        actual_latency_ms=800.0,
        actual_cost=0.001
    )
    
    ema_router._update_ema_scores(fb_cheap)
    ema_router._update_ema_scores(fb_expensive)
    
    key_cheap = "t1:code_generation:gpt-3.5"
    key_expensive = "t1:code_generation:gpt-4"
    assert ema_router._ema_scores[key_cheap]["success"] == 1.0
    assert ema_router._ema_scores[key_expensive]["success"] == 0.0
    
    res_ema = ema_router._score_candidates(candidates, req)
    assert res_ema[0][0].model_id == "gpt-3.5"
