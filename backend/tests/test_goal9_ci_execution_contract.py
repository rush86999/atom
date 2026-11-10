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
    SpendAggregationService,
    clear_settlement_failure,
    record_llm_usage,
)

SUCCESS_TENANT = "tenant-goal9-success"
SUCCESS_WORKSPACE = "ws-goal9-success"


def _bind_success_scope(host, handler):
    with host.Session() as db:
        db.add(Tenant(
            id=SUCCESS_TENANT, name="Goal9 success",
            subdomain="goal9-success"))
        db.add(Workspace(
            id=SUCCESS_WORKSPACE, name="Goal9 success",
            tenant_id=SUCCESS_TENANT))
        db.commit()
    handler.workspace_id = SUCCESS_WORKSPACE
    handler.tenant_id = SUCCESS_TENANT


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
def ordinary_handler(monkeypatch, tmp_path):
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
    handler = BYOKHandler()
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
    assert row.workspace_id == "default"
    assert row.tenant_id == "default"


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
    assert row.workspace_id == "default"
    assert row.tenant_id == "default"


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

    _bind_success_scope(host, ordinary_handler)
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
            TokenUsage.tenant_id == SUCCESS_TENANT).all()
        assert len(rows) == 2
        assert len({r.attempt_id for r in rows}) == 2
        assert len({r.request_id for r in rows}) == 2
        assert all(r.billed is True for r in rows)
        assert all(r.cost_usd == pytest.approx(0.25) for r in rows)
        assert all(r.pricing_status == "priced" for r in rows)
        assert all(
            r.prompt_tokens == 10 and r.completion_tokens == 5 for r in rows)
        assert all(r.execution_id is None for r in rows)
        assert all(
            r.workspace_id == SUCCESS_WORKSPACE
            and r.tenant_id == SUCCESS_TENANT for r in rows)
        first = rows[0]

    with host.Session() as db:
        spend = SpendAggregationService(db).update_tenant_spend(
            SUCCESS_TENANT, persist=False)
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
            TokenUsage.tenant_id == SUCCESS_TENANT).count() == 2


def test_missing_usage_is_explicit_unknown(
        host, ordinary_handler, monkeypatch):
    _bind_success_scope(host, ordinary_handler)
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
            TokenUsage.tenant_id == SUCCESS_TENANT).one()
        assert row.billed is True
        assert row.cost_usd is None
        assert row.pricing_status == "unknown"
        assert row.prompt_tokens == 0
        assert row.completion_tokens == 0


def test_success_settlement_failure_retains_intent_across_restart(
        host, ordinary_handler, monkeypatch):
    _bind_success_scope(host, ordinary_handler)
    with host.Session() as db:
        db.add(TenantSetting(
            tenant_id=SUCCESS_TENANT,
            setting_key="billing",
            setting_value=json.dumps({
                "budget_limit_usd": 100,
                "enforcement": {"mode": "hard_stop"},
            })))
        db.commit()
    ordinary_handler.clients["opencode-go"].chat.completions.create.return_value = (
        _response("settle failure still returns"))
    from core import spend_aggregation_service as spend_module

    def _settlement_down(*args, **kwargs):
        raise RuntimeError("controlled settlement write failure")

    monkeypatch.setattr(
        spend_module, "record_llm_usage", _settlement_down)
    assert asyncio.run(ordinary_handler.generate_response(
        "settlement failure")) == "settle failure still returns"

    with host.Session() as db:
        row = db.query(TokenUsage).filter(
            TokenUsage.tenant_id == SUCCESS_TENANT).one()
        assert row.billed is False
        assert row.cost_usd is None
        assert row.pricing_status == "unknown"
        refused = BudgetEnforcementService(
            db).check_budget_before_action_sync(
                SUCCESS_TENANT, "ci-agent", "llm")
    assert refused["allowed"] is False
    assert refused.get("status_code") == "BUDGET_UNPRICED_USAGE"

    spend_module.clear_settlement_failure()
    engine = create_engine(str(host.engine.url))
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        refused = BudgetEnforcementService(
            db).check_budget_before_action_sync(
                SUCCESS_TENANT, "ci-agent", "llm")
    assert refused["allowed"] is False
    assert refused.get("status_code") == "BUDGET_UNPRICED_USAGE"
    engine.dispose()
