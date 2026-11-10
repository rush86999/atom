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
from unittest.mock import MagicMock

import pytest

from tests.test_oracle_mini_app_host_mutations import host
from tests._llm_route_catalog import install_route_catalog
from core.llm.byok_handler import AwaitableResult, BYOKHandler
from core.models import Tenant, TokenUsage, Workspace


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
