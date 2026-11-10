"""Focused CI-repair contract for ordinary BYOK dispatch attribution.

The c3 backend-core failure was a real `NameError` in the ordinary
`generate_response` path: the durable pre-dispatch intent referenced
`execution_id` before the consumer contract had that parameter. These twins
drive the real doubled ordinary transport with a real scratch TokenUsage
ledger and assert the optional execution context is either absent (None) or
used exactly, with no hidden provider fallback when the intent cannot persist.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.test_oracle_mini_app_host_mutations import host
from tests._llm_route_catalog import install_route_catalog
from core.budget_enforcement_service import BudgetEnforcementService
from core.llm.byok_handler import AwaitableResult, BYOKHandler
from core.models import Tenant, TenantSetting, TokenUsage, Workspace
from core.spend_aggregation_service import (
    BudgetReservationRefused,
    SpendAggregationService,
    begin_llm_usage,
    clear_settlement_failure,
    record_llm_usage,
)


def _response(content: str):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.choices[0].finish_reason = "stop"
    response.usage = MagicMock()
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 5
    return response


@pytest.fixture
def ordinary_handler(host, monkeypatch, tmp_path):
    manager = MagicMock()
    manager.is_configured.return_value = True
    manager.get_api_key.return_value = "scratch-key"
    manager.get_tenant_api_key.return_value = "scratch-key"
    monkeypatch.setattr(
        "core.llm.byok_handler.get_byok_manager", lambda: manager)
    install_route_catalog(monkeypatch, tmp_path, {
        "opencode-go": ["deepseek-v4-flash", "deepseek-v4-flash-free"],
        "openai": ["gpt-4o"],
    })
    tenant_id = "tenant-goal9-ci-scope"
    workspace_id = "ws-goal9-ci-scope"
    with host.Session() as db:
        db.add(Tenant(id=tenant_id, name=tenant_id, subdomain="goal9-ci-scope"))
        db.add(Workspace(id=workspace_id, name=workspace_id,
                         tenant_id=tenant_id))
        db.commit()
    handler = BYOKHandler()
    handler.workspace_id = workspace_id
    handler.tenant_id = tenant_id
    handler.clients = {"opencode-go": MagicMock()}
    handler.async_clients = {}
    handler.get_ranked_providers = lambda *a, **k: AwaitableResult(
        [("opencode-go", "deepseek-v4-flash")])
    handler.clients["opencode-go"].chat.completions.create.return_value = (
        _response("ordinary ok"))
    return handler


def _latest_usage(host):
    with host.Session() as db:
        return db.query(TokenUsage).filter(
            TokenUsage.provider_id == "opencode-go",
            TokenUsage.model_name == "deepseek-v4-flash",
        ).order_by(TokenUsage.timestamp.desc()).first()


def test_generate_response_without_execution_context_uses_none(
        host, ordinary_handler):
    result = asyncio.run(ordinary_handler.generate_response(
        prompt="What is 2+2?",
        system_instruction="You are helpful",
        temperature=0.7,
    ))
    assert result == "ordinary ok"
    assert ordinary_handler.clients[
        "opencode-go"].chat.completions.create.call_count == 1
    row = _latest_usage(host)
    assert row is not None
    assert row.execution_id is None
    assert row.attempt_id
    assert row.workspace_id == "ws-goal9-ci-scope"
    assert row.tenant_id == "tenant-goal9-ci-scope"


def test_generate_response_with_execution_context_attribution(
        host, ordinary_handler):
    result = asyncio.run(ordinary_handler.generate_response(
        prompt="What is 2+2?",
        system_instruction="You are helpful",
        execution_id="exec-ci-123",
    ))
    assert result == "ordinary ok"
    row = _latest_usage(host)
    assert row is not None
    assert row.execution_id == "exec-ci-123"
    assert row.workspace_id == "ws-goal9-ci-scope"
    assert row.tenant_id == "tenant-goal9-ci-scope"


def test_intent_failure_does_not_fallback_to_second_provider(
        host, ordinary_handler, monkeypatch):
    ordinary_handler.clients["openai"] = MagicMock()
    ordinary_handler.clients["openai"].chat.completions.create.return_value = (
        _response("hidden fallback"))
    ordinary_handler.get_ranked_providers = lambda *a, **k: AwaitableResult([
        ("opencode-go", "deepseek-v4-flash"),
        ("openai", "gpt-4o"),
    ])
    from core import spend_aggregation_service as spend_module

    def _intent_down(*args, **kwargs):
        raise RuntimeError("intent store unavailable")

    monkeypatch.setattr(spend_module, "begin_llm_usage", _intent_down)
    try:
        result = asyncio.run(ordinary_handler.generate_response(
            prompt="What is 2+2?",
            system_instruction="You are helpful",
        ))
    except Exception:
        result = None
    assert result != "hidden fallback"
    assert ordinary_handler.clients[
        "opencode-go"].chat.completions.create.call_count == 0
    assert ordinary_handler.clients[
        "openai"].chat.completions.create.call_count == 0
    with host.Session() as db:
        assert db.query(TokenUsage).filter(
            TokenUsage.attempt_id.isnot(None)).count() == 0


def test_two_ordinary_successes_settle_ledger_once(
        host, ordinary_handler, monkeypatch):
    from core.llm import byok_handler

    tenant_id = ordinary_handler.tenant_id
    workspace_id = ordinary_handler.workspace_id
    monkeypatch.setattr(
        byok_handler, "get_pricing_fetcher",
        lambda: SimpleNamespace(estimate_cost=lambda *a, **k: 0.25))
    client = ordinary_handler.clients["opencode-go"]
    client.chat.completions.create.return_value = _response(
        "independent ordinary")

    for prompt in ("First independent call", "Second independent call"):
        assert asyncio.run(ordinary_handler.generate_response(prompt)) == (
            "independent ordinary")
    assert client.chat.completions.create.call_count == 2

    with host.Session() as db:
        rows = db.query(TokenUsage).filter(
            TokenUsage.tenant_id == tenant_id).all()
        assert len(rows) == 2
        assert len({r.attempt_id for r in rows}) == 2
        assert len({r.request_id for r in rows}) == 2
        assert all(r.billed is True for r in rows)
        assert all(r.cost_usd == pytest.approx(0.25) for r in rows)
        assert all(r.pricing_status == "priced" for r in rows)
        assert all(
            r.prompt_tokens == 10 and r.completion_tokens == 5 for r in rows)
        assert all(r.execution_id is None for r in rows)
        assert all(r.workspace_id == workspace_id for r in rows)
        assert all(r.reservation_status == "settled" for r in rows)
        assert all(r.reserved_cost_usd == pytest.approx(0.0) for r in rows)
        first = rows[0]

    with host.Session() as db:
        spend = SpendAggregationService(db).update_tenant_spend(
            tenant_id, persist=False)
    assert spend["current_spend_usd"] == pytest.approx(0.5)

    replay_id = record_llm_usage(
        provider_id=first.provider_id,
        model_name=first.model_name,
        prompt_tokens=10,
        completion_tokens=5,
        cost_usd=0.25,
        agent_id=first.agent_id,
        workspace_id=first.workspace_id,
        tenant_id=first.tenant_id,
        execution_id=first.execution_id,
        chain_id=first.chain_id,
        request_id=first.request_id,
        attempt_id=first.attempt_id,
    )
    assert replay_id == first.id
    with host.Session() as db:
        assert db.query(TokenUsage).filter(
            TokenUsage.tenant_id == tenant_id).count() == 2


def test_missing_usage_is_uncertain_liability_not_released(
        host, ordinary_handler, monkeypatch):
    from core.llm import byok_handler

    tenant_id = ordinary_handler.tenant_id
    monkeypatch.setattr(
        byok_handler, "get_pricing_fetcher",
        lambda: SimpleNamespace(estimate_cost=lambda *a, **k: 0.25))
    ordinary_handler.clients[
        "opencode-go"].chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(
                    content="no usage", reasoning_content=None),
                finish_reason="stop")])
    assert asyncio.run(ordinary_handler.generate_response(
        "No usage in response")) == "no usage"
    with host.Session() as db:
        row = db.query(TokenUsage).filter(
            TokenUsage.tenant_id == tenant_id).one()
        assert row.billed is True
        assert row.cost_usd is None
        assert row.pricing_status == "unknown"
        assert row.prompt_tokens == 0
        assert row.completion_tokens == 0
        assert row.reservation_status == "uncertain"
        assert row.reserved_cost_usd and row.reserved_cost_usd > 0


def test_success_settlement_failure_keeps_reserved_liability_across_restart(
        host, ordinary_handler, monkeypatch):
    from core.llm import byok_handler
    from core import spend_aggregation_service as spend_module

    tenant_id = ordinary_handler.tenant_id
    workspace_id = ordinary_handler.workspace_id
    with host.Session() as db:
        db.add(TenantSetting(
            tenant_id=tenant_id,
            setting_key="billing",
            setting_value=json.dumps({
                "budget_limit_usd": 100,
                "enforcement": {"mode": "hard_stop"},
            })))
        db.add(TokenUsage(
            agent_id=None, workspace_id=workspace_id, tenant_id=tenant_id,
            model_name="controlled-seed", cost_usd=98.0,
            pricing_status="priced", reservation_status="none",
            timestamp=datetime.now()))
        db.commit()
    monkeypatch.setattr(
        byok_handler, "get_pricing_fetcher",
        lambda: SimpleNamespace(estimate_cost=lambda *a, **k: 1.6))
    ordinary_handler.clients["opencode-go"].chat.completions.create.return_value = (
        _response("settlement failure still returns"))

    def _settlement_down(*args, **kwargs):
        raise RuntimeError("controlled settlement write failure")

    monkeypatch.setattr(
        spend_module, "record_llm_usage", _settlement_down)
    assert asyncio.run(ordinary_handler.generate_response(
        "settlement failure")) == "settlement failure still returns"

    with host.Session() as db:
        row = db.query(TokenUsage).filter(
            TokenUsage.tenant_id == tenant_id,
            TokenUsage.attempt_id.isnot(None)).one()
        assert row.billed is False
        assert row.cost_usd is None
        assert row.reservation_status == "active"
        assert row.reserved_cost_usd == pytest.approx(2.0)

    clear_settlement_failure()
    with host.Session() as db:
        refused = BudgetEnforcementService(
            db).check_budget_before_action_sync(
                tenant_id, "ci-agent", "llm")
        assert refused["allowed"] is False
    with pytest.raises(BudgetReservationRefused):
        begin_llm_usage(
            provider_id="opencode-go", model_name="deepseek-v4-flash",
            agent_id=None, workspace_id=workspace_id, tenant_id=tenant_id,
            request_id="post-failure", attempt_id="post-failure",
            reserved_cost_usd=0.01, enforce_budget=True)

    engine = create_engine(str(host.engine.url))
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        row = db.query(TokenUsage).filter(
            TokenUsage.tenant_id == tenant_id,
            TokenUsage.reservation_status == "active").one()
        assert row.billed is False
        assert row.reserved_cost_usd == pytest.approx(2.0)
        refused = BudgetEnforcementService(
            db).check_budget_before_action_sync(
                tenant_id, "ci-agent", "llm")
        assert refused["allowed"] is False
    engine.dispose()


def test_concurrent_ordinary_cap_90_plus_7_plus_7(
        host, ordinary_handler, monkeypatch):
    """Two real ordinary consumers race at 90/100 with 7-bound attempts:
    exactly one provider call, one settled 7, committed 97, no overspend."""
    import threading

    from core.llm import byok_handler

    tenant_id = ordinary_handler.tenant_id
    workspace_id = ordinary_handler.workspace_id
    with host.Session() as db:
        db.add(TenantSetting(
            tenant_id=tenant_id,
            setting_key="billing",
            setting_value=json.dumps({
                "budget_limit_usd": 100,
                "enforcement": {"mode": "hard_stop"},
            })))
        db.add(TokenUsage(
            agent_id=None, workspace_id=workspace_id, tenant_id=tenant_id,
            model_name="controlled-seed", cost_usd=90.0,
            pricing_status="priced", reservation_status="none",
            timestamp=datetime.now()))
        db.commit()
    monkeypatch.setenv("ATOM_LLM_RESERVATION_MARGIN", "1.0")
    monkeypatch.setattr(
        byok_handler, "get_pricing_fetcher",
        lambda: SimpleNamespace(estimate_cost=lambda *a, **k: 7.0))
    client = ordinary_handler.clients["opencode-go"]
    client.chat.completions.create.return_value = _response("winner")
    barrier = threading.Barrier(2)
    results = []

    def _run():
        barrier.wait(timeout=10)
        try:
            results.append(("returned", asyncio.run(
                ordinary_handler.generate_response("concurrent ordinary"))))
        except Exception as exc:  # pragma: no cover - diagnostic
            results.append(("raised", type(exc).__name__))

    threads = [threading.Thread(target=_run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=25)
    assert [t.is_alive() for t in threads] == [False, False]
    assert client.chat.completions.create.call_count == 1, results
    assert sum(1 for r in results if r[0] == "returned" and r[1] == "winner") == 1
    with host.Session() as db:
        rows = db.query(TokenUsage).filter(
            TokenUsage.tenant_id == tenant_id,
            TokenUsage.attempt_id.isnot(None)).all()
        assert len(rows) == 1
        assert rows[0].billed is True
        assert rows[0].cost_usd == pytest.approx(7.0)
        spend = SpendAggregationService(db).update_tenant_spend(
            tenant_id, persist=False)
    assert spend["current_spend_usd"] == pytest.approx(97.0)
    assert spend["reserved_spend_usd"] == pytest.approx(0.0)
    assert spend["committed_spend_usd"] == pytest.approx(97.0)
