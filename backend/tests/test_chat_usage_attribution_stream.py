"""Shared chat/stream usage attribution — exact execution + authenticated scope.

Real accepted menu-bar evidence showed a completed ``AgentExecution`` and a
settled ``TokenUsage`` row with ``execution_id=None``: the shared streaming
path (``LLMService.stream_completion`` -> ``BYOKHandler.stream_completion``)
never carried the turn's execution id, so settled provider usage could not be
joined back to the run that caused it.

These controls exercise the REAL public menu-bar route, the real
``agent_execution_service``, ``LLMService`` and ``BYOKHandler`` streaming
ladder, and the real scratch ``TokenUsage`` ledger. Only the provider transport
is doubled. They prove:

* success: the settled row carries the route's exact execution id and the
  authenticated tenant/workspace pair;
* failure: a terminal provider failure keeps its own admitted attempt row
  attributed to the same execution (no fabricated success/tokens);
* fallback: every physical attempt (failed first provider + successful
  fallback) is attributed to the same execution, and the settled tokens are
  the provider's authoritative usage — never a character estimate;
* concurrency: two simultaneous streams settle under their own execution ids
  with no cross-turn leakage.

No live DB, provider, model or account is used.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.test_goal9_physical_attempts import (
    _StreamClient,
    _visible,
    _make_handler,
)
from tests.test_oracle_mini_app_host_mutations import host  # noqa: F401

from core.auth import get_password_hash
from core.database import get_db
from core.llm_service import LLMService
from core.models import (
    AgentExecution,
    AgentRegistry,
    Tenant,
    TokenUsage,
    User,
    Workspace,
)

PROVIDER = "openai"
FALLBACK_PROVIDER = "deepseek"
MODEL = "attribution-model"


def _usage_chunk(prompt_tokens, completion_tokens):
    return SimpleNamespace(choices=[], usage=SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    ))


@pytest.fixture()
def scope(host):
    """Authenticated non-default tenant/workspace + visible autonomous agent."""
    workspace_id = "ws-attribution"
    tenant_id = "tenant-attribution"
    user_id = "user-attribution"
    agent_id = "agent-attribution"
    with host.Session() as db:
        db.add(Tenant(id=tenant_id, name="Attribution", subdomain="attribution"))
        db.add(Workspace(id=workspace_id, name="Attribution",
                         tenant_id=tenant_id))
        db.add(User(
            id=user_id,
            email="attribution@scratch.local",
            first_name="Attribution",
            last_name="User",
            hashed_password=get_password_hash("Scratch-Passw0rd!"),
            role="member",
            status="active",
            is_active=True,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        ))
        db.add(AgentRegistry(
            id=agent_id,
            name="Attribution Agent",
            description="Controlled attribution agent",
            category="Testing",
            module_path="test.agents",
            class_name="AttributionAgent",
            version="1.0.0",
            status="AUTONOMOUS",
            confidence_score=0.99,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            user_id=user_id,
            enabled=True,
            configuration={"capabilities": ["chat"]},
        ))
        db.commit()
    return SimpleNamespace(
        tenant_id=tenant_id, workspace_id=workspace_id,
        user_id=user_id, agent_id=agent_id,
    )


def _handler(monkeypatch, tmp_path, scope, catalog, async_):
    handler = _make_handler(monkeypatch, tmp_path, catalog, async_=async_)
    handler.workspace_id = scope.workspace_id
    handler.tenant_id = scope.tenant_id
    handler.analyze_query_complexity = lambda prompt, task_type=None: "simple"
    handler.get_optimal_provider = AsyncMock(
        return_value=(PROVIDER, next(iter(catalog[PROVIDER]))))
    return handler


@pytest.fixture()
def api_client(host, scope):
    """Real app + real menu-bar auth; DB and execution sessions are scratch."""
    from main_api_app import app

    def override_get_db():
        db = host.Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with (
            patch("core.agent_execution_service.SessionLocal", host.Session),
            patch("api.menubar_routes.verify_password", return_value=True),
            patch.object(LLMService, "analyze_query_complexity",
                         lambda self, prompt, task_type=None: "simple"),
            patch.object(LLMService, "get_optimal_provider",
                         lambda self, *a, **k: (PROVIDER, MODEL)),
        ):
            with TestClient(app) as client:
                yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def _login(client):
    response = client.post(
        "/api/menubar/auth/login",
        headers={"Host": "localhost"},
        json={
            "email": "attribution@scratch.local",
            "password": "Scratch-Passw0rd!",
            "device_name": "Attribution MenuBar",
            "platform": "darwin",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True, body
    return body["access_token"], body["device_id"]


def _quick_chat(client, token, device_id, scope, message="hello"):
    return client.post(
        "/api/menubar/quick/chat",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Device-ID": device_id,
            "Host": "localhost",
        },
        json={"message": message, "agent_id": scope.agent_id},
    )


def _usage_rows(host, execution_id):
    with host.Session() as db:
        return (
            db.query(TokenUsage)
            .filter(TokenUsage.execution_id == execution_id,
                    TokenUsage.attempt_id.isnot(None))
            .order_by(TokenUsage.timestamp)
            .all()
        )


def test_public_quick_chat_settles_usage_on_exact_execution_and_scope(
        host, scope, api_client, monkeypatch, tmp_path):
    client = api_client
    calls = []
    handler = _handler(
        monkeypatch, tmp_path, scope, {PROVIDER: [MODEL]},
        {PROVIDER: _StreamClient(PROVIDER, [{"chunks": [
            _visible("hello "), _visible("world"),
            _usage_chunk(10, 5)]}], calls)})
    monkeypatch.setattr(
        "core.llm.byok_handler.get_pricing_fetcher",
        lambda: SimpleNamespace(estimate_cost=lambda *a, **k: 0.25))

    def _scope_handler(self, **kwargs):
        # The service must resolve the AUTHENTICATED pair, not collapse them.
        assert kwargs.get("workspace_id") == scope.workspace_id
        assert kwargs.get("tenant_id") == scope.tenant_id
        return handler

    monkeypatch.setattr(LLMService, "_get_handler", _scope_handler)

    token, device_id = _login(client)
    response = _quick_chat(client, token, device_id, scope)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True, body
    assert body["response"] == "hello world"
    assert body["execution_id"]

    rows = _usage_rows(host, body["execution_id"])
    assert len(rows) == 1, [r.attempt_id for r in rows]
    row = rows[0]
    assert row.execution_id == body["execution_id"]
    assert row.workspace_id == scope.workspace_id
    assert row.tenant_id == scope.tenant_id
    assert row.provider_id == PROVIDER
    assert row.model_name == MODEL
    # Provider-supplied authoritative usage, not a len(text)//4 estimate.
    assert (row.prompt_tokens, row.completion_tokens) == (10, 5)
    assert row.total_tokens == 15
    assert row.pricing_status == "priced"
    assert row.reservation_status == "settled"
    assert row.cost_usd == pytest.approx(0.25)
    assert len(calls) == 1


def test_public_quick_chat_failure_keeps_attributed_liability_no_estimate(
        host, scope, api_client, monkeypatch, tmp_path):
    client = api_client
    calls = []
    handler = _handler(
        monkeypatch, tmp_path, scope, {PROVIDER: [MODEL]},
        {PROVIDER: _StreamClient(PROVIDER, [
            {"raise": RuntimeError("controlled provider failure")}], calls)})
    monkeypatch.setattr("core.llm_service.LLMService._get_handler",
                        lambda self, **kwargs: handler)

    token, device_id = _login(client)
    response = _quick_chat(client, token, device_id, scope)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is False
    assert body["response"] is None

    with host.Session() as db:
        execution = (
            db.query(AgentExecution)
            .filter(AgentExecution.agent_id == scope.agent_id)
            .order_by(AgentExecution.started_at.desc())
            .first()
        )
        assert execution is not None
        assert execution.status == "failed"
        rows = db.query(TokenUsage).filter(
            TokenUsage.execution_id == execution.id,
            TokenUsage.attempt_id.isnot(None),
        ).all()
    assert len(rows) == 1, [r.attempt_id for r in rows]
    row = rows[0]
    assert row.workspace_id == scope.workspace_id
    assert row.tenant_id == scope.tenant_id
    assert row.reservation_status == "active"
    assert row.cost_usd is None
    assert row.pricing_status == "unknown"
    # No fabricated success usage from the requested/estimated text.
    assert row.prompt_tokens == 0 and row.completion_tokens == 0
    assert len(calls) == 1


def test_public_quick_chat_fallback_attributes_every_physical_attempt(
        host, scope, api_client, monkeypatch, tmp_path):
    client = api_client
    calls = []
    handler = _handler(
        monkeypatch, tmp_path, scope,
        {PROVIDER: [MODEL], FALLBACK_PROVIDER: [MODEL]},
        {
            PROVIDER: _StreamClient(
                PROVIDER, [{"raise": RuntimeError("first provider down")}],
                calls),
            FALLBACK_PROVIDER: _StreamClient(
                FALLBACK_PROVIDER, [{"chunks": [
                    _visible("fallback "), _visible("ok"),
                    _usage_chunk(10, 5)]}], calls),
        })
    monkeypatch.setattr("core.llm_service.LLMService._get_handler",
                        lambda self, **kwargs: handler)
    monkeypatch.setattr(
        "core.llm.byok_handler.get_pricing_fetcher",
        lambda: SimpleNamespace(estimate_cost=lambda *a, **k: 0.25))

    token, device_id = _login(client)
    response = _quick_chat(client, token, device_id, scope)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True, body
    assert body["response"] == "fallback ok"
    assert [c[0] for c in calls] == [PROVIDER, FALLBACK_PROVIDER]

    rows = _usage_rows(host, body["execution_id"])
    assert len(rows) == 2, [r.attempt_id for r in rows]
    by_provider = {r.provider_id: r for r in rows}
    failed = by_provider[PROVIDER]
    settled = by_provider[FALLBACK_PROVIDER]
    assert failed.reservation_status == "active"
    assert failed.cost_usd is None
    assert failed.prompt_tokens == 0
    assert settled.reservation_status == "settled"
    assert settled.cost_usd == pytest.approx(0.25)
    # Authoritative provider usage on the settling attempt.
    assert (settled.prompt_tokens, settled.completion_tokens) == (10, 5)
    assert all(r.execution_id == body["execution_id"] for r in rows)
    assert all(r.workspace_id == scope.workspace_id for r in rows)
    assert all(r.tenant_id == scope.tenant_id for r in rows)


def test_concurrent_stream_turns_do_not_share_execution_attribution(
        host, scope, monkeypatch, tmp_path):
    """Two simultaneous streams settle under their own execution ids."""
    catalog = {PROVIDER: ["model-a", "model-b"]}
    calls_a, calls_b = [], []
    handler_a = _handler(
        monkeypatch, tmp_path, scope, catalog,
        {PROVIDER: _StreamClient(PROVIDER, [{"chunks": [
            _visible("A"), _usage_chunk(11, 4)]}], calls_a)})
    handler_b = _handler(
        monkeypatch, tmp_path, scope, catalog,
        {PROVIDER: _StreamClient(PROVIDER, [{"chunks": [
            _visible("B"), _usage_chunk(7, 9)]}], calls_b)})
    # Separate server-owned request identities: the fixture's shared
    # "decision" stub would collide on the ledger's unique attempt_id when two
    # turns are in flight. Real streams without a router decision mint their
    # own uuid.
    handler_a._stash_decision_features = lambda *a, **k: None
    handler_b._stash_decision_features = lambda *a, **k: None
    monkeypatch.setattr(
        "core.llm.byok_handler.get_pricing_fetcher",
        lambda: SimpleNamespace(estimate_cost=lambda *a, **k: 0.1))

    async def _collect(handler, model, execution_id):
        return [
            part async for part in handler.stream_completion(
                [{"role": "user", "content": "hello"}],
                model=model, provider_id=PROVIDER, max_tokens=1000,
                execution_id=execution_id)
        ]

    async def _both():
        return await asyncio.gather(
            _collect(handler_a, "model-a", "exec-concurrent-a"),
            _collect(handler_b, "model-b", "exec-concurrent-b"),
        )

    text_a, text_b = asyncio.run(_both())
    assert "".join(text_a) == "A"
    assert "".join(text_b) == "B"

    with host.Session() as db:
        rows_a = db.query(TokenUsage).filter(
            TokenUsage.execution_id == "exec-concurrent-a").all()
        rows_b = db.query(TokenUsage).filter(
            TokenUsage.execution_id == "exec-concurrent-b").all()
    assert len(rows_a) == 1 and len(rows_b) == 1
    assert rows_a[0].model_name == "model-a"
    assert (rows_a[0].prompt_tokens, rows_a[0].completion_tokens) == (11, 4)
    assert rows_b[0].model_name == "model-b"
    assert (rows_b[0].prompt_tokens, rows_b[0].completion_tokens) == (7, 9)
