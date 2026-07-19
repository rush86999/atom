import time
import pytest
from unittest.mock import MagicMock
from pathlib import Path

from core.learning_llm_router import (
    LearningBasedRouter, ModelSpec, RoutingFeedback, ModelCapability
)
from core.sandbox_tripwire import check_python_ast, check_js_ast
from core.sandbox_transaction import SandboxTransaction

@pytest.mark.asyncio
async def test_get_routing_statistics_includes_ema_scores(monkeypatch):
    monkeypatch.setenv("ATOM_EMA_ROUTER_ENABLED", "true")
    mock_db = MagicMock()
    router = LearningBasedRouter(db=mock_db)
    cand = ModelSpec(
        model_id="gpt-4o",
        provider="openai",
        model_name="gpt-4o",
        capabilities={ModelCapability.REASONING, ModelCapability.CODE_GENERATION},
        cost_per_million=10.0,
        quality_score=0.9,
        speed_score=0.8,
        context_window=128000,
        supports_cache=True,
        tier="tier_5_heavy",
    )
    router._model_registry["gpt-4o"] = cand
    
    fb = RoutingFeedback(
        routing_result_id="r1",
        tenant_id="chat-tenant",
        task_type="question_answering",
        model_id="gpt-4o",
        success=True,
        quality_satisfied=True,
        cost_within_budget=True,
        actual_latency_ms=120.0,
        actual_cost=0.002,
    )
    router._update_ema_scores(fb)
    
    stats = await router.get_routing_statistics("chat-tenant")
    assert stats["ema_enabled"] is True
    assert "gpt-4o" in stats["ema_scores"]
    assert stats["ema_scores"]["gpt-4o"]["samples"] == 1
    assert stats["ema_scores"]["gpt-4o"]["avg_latency_ms"] == 120.0


def test_ast_tripwire_expanded_reflection_and_js():
    # Test Python dynamic imports & getattr reflection
    res1 = check_python_ast("import importlib; importlib.import_module('os')")
    assert res1 is not None and "importlib" in res1
    
    res2 = check_python_ast("getattr(os, 'system')('ls')")
    assert res2 is not None and "getattr" in res2
    
    res3 = check_python_ast("__import__('os').system('ls')")
    assert res3 is not None and "__import__" in res3

    # Test JS string AST scanning
    res4 = check_js_ast("const secret = process.env.AWS_SECRET_ACCESS_KEY;")
    assert res4 is not None and "process.env" in res4

    res5 = check_js_ast("function test() { eval('console.log(1)'); }")
    assert res5 is not None and "eval" in res5


def test_sandbox_transaction_resource_caps_timeout(tmp_path):
    tx_dir = tmp_path / "workspace"
    tx_dir.mkdir()
    (tx_dir / "file.txt").write_text("initial")

    # Timeout breach test
    with pytest.raises(TimeoutError):
        with SandboxTransaction(tx_dir, timeout_seconds=0.1):
            time.sleep(0.2)
            (tx_dir / "file.txt").write_text("modified")

    # Verify state rolled back
    assert (tx_dir / "file.txt").read_text() == "initial"


def test_sandbox_transaction_resource_caps_memory(tmp_path):
    tx_dir = tmp_path / "workspace"
    tx_dir.mkdir()
    (tx_dir / "file.txt").write_text("small")

    # Memory/bytes size cap breach test (cap at 100 bytes)
    with pytest.raises(MemoryError):
        with SandboxTransaction(tx_dir, max_bytes=100):
            (tx_dir / "file.txt").write_text("A" * 500)

    # Verify state rolled back
    assert (tx_dir / "file.txt").read_text() == "small"
