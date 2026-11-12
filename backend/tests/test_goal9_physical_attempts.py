"""Goal 9 per-physical-attempt admission controls (doubled consumers).

Every physical paid transport attempt — streaming initial/self-heal/paid/
reasoning-budget retry/route hop, gateway ``chat_completion``
temperature/self-heal/paid retry, and ordinary ``generate_response`` nested
retries — must carry its own server-owned attempt identity, actual route
binding, conservative authorized bound before dispatch, and a durable
actual/unknown settlement after it.

Failure-first: the retained negative shows the pre-repair behavior (one
request-level reservation shared by several physical dispatches, or no
reservation at all for a nested retry). All transport is doubled; ledger and
policy are the real scratch SQLite store. No live provider/model/DB.

This module is also the hosted-CI entry point for the curated OpenCode free
catalog admission controls (provider-qualified zero bound, cross-provider and
unknown-suffix refusals, free->paid separate reservation, and the
present-but-unusable price / conflicting-settlement boundaries), so those
controls run in the same selected lane as the physical-attempt twins.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests._llm_route_catalog import install_route_catalog
from tests.test_oracle_mini_app_host_mutations import host
from tests.test_opencode_go_provider import _insufficient_balance_error
from core.dynamic_pricing_fetcher import DynamicPricingFetcher
from core.llm.byok_handler import (
    AllProvidersFailedError,
    BYOKHandler,
    _opencode_paid_fallback_model,
)
from core.llm.opencode_catalog import (
    OPCODE_KNOWN_FREE_MODELS,
    OPCODE_KNOWN_PRICES,
)
from core.models import Tenant, TenantSetting, TokenUsage, Workspace

TENANT = "tenant-goal9-physical"
WORKSPACE = "ws-goal9-physical"


@pytest.fixture(autouse=True)
def _clean_transport_state():
    """Provider failures/cooldowns/temperature memos are process-wide."""
    from core.llm import byok_handler as bh
    from core.spend_aggregation_service import clear_settlement_failure

    saved_temperatures = dict(bh._MODEL_TEMPERATURE)
    clear_settlement_failure()
    BYOKHandler.invalidate_provider_failures()
    yield
    BYOKHandler.invalidate_provider_failures()
    # The temperature-lock retry memoizes a per-pair value; leaking it would
    # change an unrelated consumer's expected temperature in the same process.
    bh._MODEL_TEMPERATURE.clear()
    bh._MODEL_TEMPERATURE.update(saved_temperatures)
    # Deliberate settlement-failure controls set a process marker that would
    # otherwise make unrelated consumers fail closed.
    clear_settlement_failure()


# --------------------------------------------------------------------------
# scratch ledger / policy
# --------------------------------------------------------------------------
def _seed(host, *, spend=90.0, limit=100.0):
    with host.Session() as db:
        db.add(Tenant(id=TENANT, name=TENANT, subdomain="goal9-physical"))
        db.add(Workspace(id=WORKSPACE, name=WORKSPACE, tenant_id=TENANT))
        db.add(TenantSetting(
            tenant_id=TENANT, setting_key="billing",
            setting_value=json.dumps({
                "budget_limit_usd": limit,
                "enforcement": {"mode": "hard_stop"},
            })))
        if spend:
            db.add(TokenUsage(
                agent_id=None, workspace_id=WORKSPACE, tenant_id=TENANT,
                model_name="controlled-seed", cost_usd=spend,
                pricing_status="priced", reservation_status="none",
                timestamp=datetime.now()))
        db.commit()


def _attempt_rows(host):
    with host.Session() as db:
        return (
            db.query(TokenUsage)
            .filter(TokenUsage.tenant_id == TENANT,
                    TokenUsage.attempt_id.isnot(None))
            .order_by(TokenUsage.timestamp)
            .all()
        )


def _make_handler(monkeypatch, tmp_path, catalog, *, sync=None, async_=None):
    manager = MagicMock()
    manager.is_configured.return_value = False
    manager.get_api_key.return_value = None
    with patch("core.llm.byok_handler.get_byok_manager",
               return_value=manager), \
         patch("core.llm.byok_handler.get_db_session",
               return_value=MagicMock()):
        handler = BYOKHandler()
    install_route_catalog(monkeypatch, tmp_path, catalog)
    handler.clients = dict(sync or {})
    handler.async_clients = dict(async_ or {})
    handler.workspace_id = WORKSPACE
    handler.tenant_id = TENANT
    handler._record_outcome_feedback = AsyncMock()
    handler._stash_decision_features = MagicMock(return_value="decision")
    handler._provider_models_cached = lambda pid: []
    return handler


def _pricing(monkeypatch, fn):
    monkeypatch.setattr(
        "core.llm.byok_handler.get_pricing_fetcher",
        lambda: SimpleNamespace(estimate_cost=fn))


def _reservation_pricing(monkeypatch, *, bound_at=7.0, reserve_output=1000,
                         actual=7.0):
    """Reserve ``bound_at`` for the request cap, settle ``actual`` for usage."""
    def _estimate(model, input_tokens, output_tokens):
        if int(output_tokens or 0) == int(reserve_output):
            return bound_at / 1.25
        return actual
    _pricing(monkeypatch, _estimate)


# --------------------------------------------------------------------------
# doubled transports
# --------------------------------------------------------------------------
class _ScriptedStream:
    def __init__(self, chunks, fail_after=None, fail_exc=None):
        self._chunks = list(chunks)
        self._index = 0
        self._fail_after = fail_after
        self._fail_exc = fail_exc or RuntimeError("stream cut mid-way")

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._fail_after is not None and self._index >= self._fail_after:
            self._fail_after = None
            raise self._fail_exc
        if self._index >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


def _visible(text):
    return SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(content=text, reasoning=None),
        finish_reason="stop")])


def _reasoning_length():
    return SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(content=None, reasoning="hidden"),
        finish_reason="length")])


class _StreamClient:
    def __init__(self, provider_id, script, calls):
        self._provider_id = provider_id
        self._script = list(script)
        self._calls = calls
        self.chat = SimpleNamespace(completions=SimpleNamespace(
            create=self._create))

    async def _create(self, **kwargs):
        self._calls.append((self._provider_id, kwargs.get("model"), kwargs))
        if not self._script:
            raise RuntimeError("unexpected physical dispatch")
        action = self._script.pop(0)
        if action.get("raise") is not None:
            raise action["raise"]
        return _ScriptedStream(
            action.get("chunks") or [],
            fail_after=action.get("fail_after"),
            fail_exc=action.get("fail_exc"))


def _response(content="ok"):
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(
                content=content, tool_calls=None, function_call=None,
                reasoning_content=None),
            finish_reason="stop",
        )],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


class _ChatClient:
    def __init__(self, script, calls):
        self._script = list(script)
        self._calls = calls
        self.chat = SimpleNamespace(completions=SimpleNamespace(
            create=AsyncMock(side_effect=self._next)))

    def _next(self, **kwargs):
        self._calls.append(kwargs)
        if not self._script:
            raise RuntimeError("unexpected physical dispatch")
        action = self._script.pop(0)
        if action.get("raise") is not None:
            raise action["raise"]
        return action["response"]


def _stream(handler, model, provider_id, **kwargs):
    messages = kwargs.pop("messages", None) or [
        {"role": "user", "content": "hello"}]

    async def _collect():
        return [part async for part in handler.stream_completion(
            messages,
            model=model, provider_id=provider_id,
            max_tokens=kwargs.pop("max_tokens", 1000), **kwargs)]
    return asyncio.run(_collect())


# --------------------------------------------------------------------------
# failure-first: second physical attempt must refuse before dispatch at cap
# --------------------------------------------------------------------------
def test_stream_second_paid_attempt_refused_before_second_provider(
        host, monkeypatch, tmp_path):
    """90/100: first attempt reserves 7 and fails; the second reservation
    (90+7+7) must refuse before the second provider is dispatched."""
    _seed(host, spend=90.0)
    _reservation_pricing(monkeypatch)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path,
        {"openai": ["shared-model"], "deepseek": ["shared-model"]},
        async_={
            "openai": _StreamClient(
                "openai", [{"raise": RuntimeError("controlled failure")}],
                calls),
            "deepseek": _StreamClient(
                "deepseek", [{"chunks": [_visible("SECOND")]}], calls),
        })
    text = "".join(_stream(handler, "shared-model", "openai"))
    assert [c[0] for c in calls] == ["openai"], (
        f"second provider dispatched before admission: {calls}")
    assert "SECOND" not in text
    rows = _attempt_rows(host)
    assert len(rows) == 1, [r.attempt_id for r in rows]
    assert rows[0].reservation_status == "active"
    assert float(rows[0].reserved_cost_usd) == pytest.approx(7.0)


def test_chat_second_provider_refused_before_dispatch_at_cap(
        host, monkeypatch, tmp_path):
    _seed(host, spend=90.0)
    _reservation_pricing(monkeypatch)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path,
        {"openai": ["shared-model"], "deepseek": ["shared-model"]},
        async_={
            "openai": _ChatClient(
                [{"raise": RuntimeError("controlled failure")}], calls),
            "deepseek": _ChatClient(
                [{"response": _response("SECOND")}], calls),
        })
    with pytest.raises(Exception):
        asyncio.run(handler.chat_completion(
            [{"role": "user", "content": "hello"}],
            "shared-model", "openai", max_tokens=1000))
    assert len(calls) == 1, calls
    rows = _attempt_rows(host)
    assert len(rows) == 1, [r.attempt_id for r in rows]
    assert rows[0].reservation_status == "active"
    assert float(rows[0].reserved_cost_usd) == pytest.approx(7.0)


# --------------------------------------------------------------------------
# failure-first: nested retries need their own attempt/route/settlement
# --------------------------------------------------------------------------
def test_chat_temperature_retry_gets_own_intent_and_settlement(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _ChatClient([
            {"raise": RuntimeError("invalid temperature: only 1 is allowed")},
            {"response": _response("locked retry")},
        ], calls)})
    result = asyncio.run(handler.chat_completion(
        [{"role": "user", "content": "hello"}], "gpt-4o", "openai",
        max_tokens=1000))
    assert result["choices"][0]["message"]["content"] == "locked retry"
    assert len(calls) == 2, calls
    rows = _attempt_rows(host)
    assert len(rows) == 2, [r.attempt_id for r in rows]
    assert len({r.attempt_id for r in rows}) == 2
    assert len({r.request_id for r in rows}) == 1, "same job binding"
    retry = [r for r in rows if r.reservation_status == "settled"]
    assert len(retry) == 1
    assert retry[0].cost_usd == pytest.approx(0.25)


def test_chat_selfheal_retry_gets_own_intent_and_settlement(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    monkeypatch.setattr(
        "core.llm.routing.request_healer.get_request_healer",
        lambda: SimpleNamespace(heal=lambda *a, **k: SimpleNamespace(
            patched_kwargs={"model": "gpt-4o",
                            "messages": [{"role": "user", "content": "hello"}],
                            "temperature": 1,
                            "max_tokens": 1000},
            rule="param-rename", patched_keys=["max_completion_tokens"])))
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _ChatClient([
            {"raise": RuntimeError("unsupported parameter")},
            {"response": _response("healed")},
        ], calls)})
    result = asyncio.run(handler.chat_completion(
        [{"role": "user", "content": "hello"}], "gpt-4o", "openai",
        max_tokens=1000))
    assert result["choices"][0]["message"]["content"] == "healed"
    assert len(calls) == 2
    rows = _attempt_rows(host)
    assert len(rows) == 2, [r.attempt_id for r in rows]
    assert len({r.request_id for r in rows}) == 1
    assert any(r.reservation_status == "settled" for r in rows)


def test_chat_paid_substitution_gets_own_route_intent(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path,
        {"opencode-go": ["deepseek-v4-flash-free", "deepseek-v4-flash"]},
        async_={"opencode-go": _ChatClient([
            {"raise": _insufficient_balance_error()},
            {"response": _response("paid answer")},
        ], calls)})
    result = asyncio.run(handler.chat_completion(
        [{"role": "user", "content": "hello"}],
        "deepseek-v4-flash-free", "opencode-go", max_tokens=1000))
    assert result["choices"][0]["message"]["content"] == "paid answer"
    assert [c["model"] for c in calls] == [
        "deepseek-v4-flash-free", "deepseek-v4-flash"], calls
    rows = _attempt_rows(host)
    assert len(rows) == 2, [r.attempt_id for r in rows]
    by_model = {r.model_name: r for r in rows}
    assert set(by_model) == {"deepseek-v4-flash-free", "deepseek-v4-flash"}
    assert by_model["deepseek-v4-flash"].reservation_status == "settled"
    assert float(by_model["deepseek-v4-flash-free"].reserved_cost_usd) > 0


def test_stream_selfheal_gets_own_intent(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    monkeypatch.setattr(
        "core.llm.routing.request_healer.get_request_healer",
        lambda: SimpleNamespace(heal=lambda *a, **k: SimpleNamespace(
            patched_kwargs={"model": "gpt-4o",
                            "messages": [{"role": "user", "content": "hello"}],
                            "temperature": 1,
                            "max_tokens": 1000,
                            "stream": True},
            rule="param-rename", patched_keys=["max_tokens"])))
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _StreamClient("openai", [
            {"raise": RuntimeError("unsupported parameter")},
            {"chunks": [_visible("HEALED")]},
        ], calls)})
    text = "".join(_stream(handler, "gpt-4o", "openai"))
    assert text == "HEALED"
    assert len(calls) == 2
    rows = _attempt_rows(host)
    assert len(rows) == 2, [r.attempt_id for r in rows]
    assert len({r.request_id for r in rows}) == 1


def test_stream_paid_substitution_gets_own_route_intent(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path,
        {"opencode-go": ["deepseek-v4-flash-free", "deepseek-v4-flash"]},
        async_={"opencode-go": _StreamClient("opencode-go", [
            {"raise": _insufficient_balance_error()},
            {"chunks": [_visible("PAID")]},
        ], calls)})
    text = "".join(_stream(
        handler, "deepseek-v4-flash-free", "opencode-go"))
    assert text == "PAID"
    assert [c[1] for c in calls] == [
        "deepseek-v4-flash-free", "deepseek-v4-flash"], calls
    rows = _attempt_rows(host)
    assert {r.model_name for r in rows} == {
        "deepseek-v4-flash-free", "deepseek-v4-flash"}, (
            [r.model_name for r in rows])


def test_stream_reasoning_budget_retry_gets_own_larger_bound(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _pricing(monkeypatch, lambda model, i, o: float(o) / 1000.0)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _StreamClient("openai", [
            {"chunks": [_reasoning_length()]},
            {"chunks": [_visible("BIGGER")]},
        ], calls)})
    text = "".join(_stream(handler, "gpt-4o", "openai", max_tokens=100))
    assert text == "BIGGER"
    assert len(calls) == 2
    rows = _attempt_rows(host)
    assert len(rows) == 2, [r.attempt_id for r in rows]
    first, second = sorted(rows, key=lambda r: float(r.reserved_cost_usd))
    assert float(second.reserved_cost_usd) > float(first.reserved_cost_usd)


def test_stream_route_hop_has_unique_attempts_same_request(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path,
        {"openai": ["gpt-4o"], "deepseek": ["deepseek-chat"]},
        async_={
            "openai": _StreamClient(
                "openai", [{"raise": RuntimeError("controlled failure")}],
                calls),
            "deepseek": _StreamClient(
                "deepseek", [{"chunks": [_visible("ROUTE")]}], calls),
        })
    text = "".join(_stream(
        handler, "gpt-4o", "openai",
        fallback_routes=[("deepseek", "deepseek-chat")]))
    assert text == "ROUTE"
    assert len(calls) == 2
    rows = _attempt_rows(host)
    assert len(rows) == 2, [r.attempt_id for r in rows]
    assert len({r.attempt_id for r in rows}) == 2
    assert len({r.request_id for r in rows}) == 1


def test_generate_response_temperature_retry_gets_own_intent(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    calls = []
    client = MagicMock()
    script = [
        RuntimeError("invalid temperature: only 1 is allowed"),
        _response("ordinary locked"),
    ]

    def _next(**kwargs):
        calls.append(kwargs)
        action = script.pop(0)
        if isinstance(action, Exception):
            raise action
        return action

    client.chat.completions.create.side_effect = _next
    handler = _make_handler(
        monkeypatch, tmp_path, {"opencode-go": ["deepseek-v4-flash"]},
        sync={"opencode-go": client})
    handler.get_ranked_providers = lambda *a, **k: _AwaitableResult(
        [("opencode-go", "deepseek-v4-flash")])
    result = asyncio.run(handler.generate_response("hello"))
    assert result == "ordinary locked"
    assert len(calls) == 2
    rows = _attempt_rows(host)
    assert len(rows) == 2, [r.attempt_id for r in rows]
    assert len({r.request_id for r in rows}) == 1
    assert any(r.reservation_status == "settled" for r in rows)


class _AwaitableResult:
    def __init__(self, value):
        self._value = value

    def __await__(self):
        async def _inner():
            return self._value
        return _inner().__await__()


def test_generate_response_tier_fallback_gets_own_route_intent(
        host, monkeypatch, tmp_path):
    """Free->paid tier substitution is a new physical attempt on a new model."""
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    calls = []
    client = MagicMock()
    script = [_insufficient_balance_error(), _response("tier paid")]

    def _next(**kwargs):
        calls.append(kwargs.get("model"))
        action = script.pop(0)
        if isinstance(action, Exception):
            raise action
        return action

    client.chat.completions.create.side_effect = _next
    handler = _make_handler(
        monkeypatch, tmp_path,
        {"opencode-go": ["deepseek-v4-flash-free", "deepseek-v4-flash"]},
        sync={"opencode-go": client})
    handler.get_ranked_providers = lambda *a, **k: _AwaitableResult(
        [("opencode-go", "deepseek-v4-flash-free")])
    result = asyncio.run(handler.generate_response("hello"))
    assert result == "tier paid"
    assert calls == ["deepseek-v4-flash-free", "deepseek-v4-flash"], calls
    rows = _attempt_rows(host)
    assert len(rows) == 2, [r.attempt_id for r in rows]
    assert len({r.request_id for r in rows}) == 1
    assert {r.model_name for r in rows} == {
        "deepseek-v4-flash-free", "deepseek-v4-flash"}


def test_generate_response_selfheal_gets_own_intent(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    monkeypatch.setattr(
        "core.llm.routing.request_healer.get_request_healer",
        lambda: SimpleNamespace(heal=lambda *a, **k: SimpleNamespace(
            patched_kwargs={"model": "gpt-4o",
                            "messages": [{"role": "user", "content": "hello"}],
                            "temperature": 0.7,
                            "max_tokens": 1000},
            rule="param-rename", patched_keys=["max_tokens"])))
    calls = []
    client = MagicMock()
    script = [RuntimeError("unsupported parameter"), _response("healed")]

    def _next(**kwargs):
        calls.append(kwargs.get("model"))
        action = script.pop(0)
        if isinstance(action, Exception):
            raise action
        return action

    client.chat.completions.create.side_effect = _next
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        sync={"openai": client})
    handler.get_ranked_providers = lambda *a, **k: _AwaitableResult(
        [("openai", "gpt-4o")])
    result = asyncio.run(handler.generate_response("hello"))
    assert result == "healed"
    assert calls == ["gpt-4o", "gpt-4o"]
    rows = _attempt_rows(host)
    assert len(rows) == 2, [r.attempt_id for r in rows]
    assert len({r.request_id for r in rows}) == 1


def test_chat_sweep_gets_unique_attempts_same_request(
        host, monkeypatch, tmp_path):
    """The catalogue sweep is another physical attempt, not a free replay."""
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path,
        {"openai": ["shared-model"], "deepseek": ["deepseek-chat"]},
        async_={
            "openai": _ChatClient(
                [{"raise": RuntimeError("controlled failure")}], calls),
            "deepseek": _ChatClient(
                [{"response": _response("SWEEP")}], calls),
        })
    # Both providers are visible to the fallback order; deepseek does not
    # serve the fixed model, so only the sweep can reach its own model.
    handler.clients = {"openai": object(), "deepseek": object()}
    result = asyncio.run(handler.chat_completion(
        [{"role": "user", "content": "hello"}], "shared-model", "openai",
        max_tokens=1000))
    assert result["choices"][0]["message"]["content"] == "SWEEP"
    assert len(calls) == 2, calls
    rows = _attempt_rows(host)
    assert len(rows) == 2, [r.attempt_id for r in rows]
    assert len({r.attempt_id for r in rows}) == 2
    assert len({r.request_id for r in rows}) == 1
    assert {r.model_name for r in rows} == {"shared-model", "deepseek-chat"}


# --------------------------------------------------------------------------
# valid twins: settlement, known free, unknown liability
# --------------------------------------------------------------------------
def test_chat_success_at_cap_settles_actual_97(
        host, monkeypatch, tmp_path):
    _seed(host, spend=90.0)
    _reservation_pricing(monkeypatch, bound_at=7.0, actual=7.0)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _ChatClient(
            [{"response": _response("paid ok")}], calls)})
    result = asyncio.run(handler.chat_completion(
        [{"role": "user", "content": "hello"}], "gpt-4o", "openai",
        max_tokens=1000))
    assert result["choices"][0]["message"]["content"] == "paid ok"
    rows = _attempt_rows(host)
    assert len(rows) == 1
    assert rows[0].reservation_status == "settled"
    assert rows[0].cost_usd == pytest.approx(7.0)
    with host.Session() as db:
        from core.spend_aggregation_service import SpendAggregationService
        spend = SpendAggregationService(db).update_tenant_spend(
            TENANT, persist=False, include_liabilities=True)
    assert spend["current_spend_usd"] == pytest.approx(97.0)


def test_stream_success_retains_unknown_liability(
        host, monkeypatch, tmp_path):
    _seed(host, spend=90.0)
    _reservation_pricing(monkeypatch, bound_at=7.0, actual=7.0)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _StreamClient(
            "openai", [{"chunks": [_visible("STREAMED")]}], calls)})
    text = "".join(_stream(handler, "gpt-4o", "openai"))
    assert text == "STREAMED"
    rows = _attempt_rows(host)
    assert len(rows) == 1
    assert rows[0].billed is True
    assert rows[0].cost_usd is None
    assert rows[0].pricing_status == "unknown"
    assert rows[0].reservation_status == "uncertain"
    assert float(rows[0].reserved_cost_usd) == pytest.approx(7.0)


def test_stream_known_free_numeric_zero_is_supported(
        host, monkeypatch, tmp_path):
    _seed(host, spend=90.0)
    _pricing(monkeypatch, lambda *a, **k: 0.0)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _StreamClient(
            "openai", [{"chunks": [_visible("LOCAL")]}], calls)})
    text = "".join(_stream(handler, "gpt-4o", "openai"))
    assert text == "LOCAL"
    rows = _attempt_rows(host)
    assert len(rows) == 1
    assert rows[0].reservation_status == "settled"
    assert rows[0].pricing_status == "free"
    assert float(rows[0].reserved_cost_usd or 0.0) == 0.0


# --------------------------------------------------------------------------
# replay / restart / scope binding of one physical attempt
# --------------------------------------------------------------------------
def test_physical_attempt_replay_idempotent_and_conflict_refused(
        host, monkeypatch, tmp_path):
    from core.spend_aggregation_service import record_llm_usage

    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _ChatClient(
            [{"response": _response("settled once")}], calls)})
    asyncio.run(handler.chat_completion(
        [{"role": "user", "content": "hello"}], "gpt-4o", "openai",
        max_tokens=1000))
    rows = _attempt_rows(host)
    assert len(rows) == 1
    row = rows[0]
    replay = record_llm_usage(
        provider_id=row.provider_id, model_name=row.model_name,
        prompt_tokens=row.prompt_tokens, completion_tokens=row.completion_tokens,
        cost_usd=row.cost_usd, agent_id=row.agent_id,
        workspace_id=row.workspace_id, tenant_id=row.tenant_id,
        execution_id=row.execution_id, chain_id=row.chain_id,
        request_id=row.request_id, attempt_id=row.attempt_id)
    assert replay == row.id
    assert len(_attempt_rows(host)) == 1
    with pytest.raises(Exception):
        record_llm_usage(
            provider_id=row.provider_id, model_name=row.model_name,
            prompt_tokens=row.prompt_tokens + 1,
            completion_tokens=row.completion_tokens + 1,
            cost_usd=row.cost_usd, agent_id=row.agent_id,
            workspace_id=row.workspace_id, tenant_id=row.tenant_id,
            request_id=row.request_id, attempt_id=row.attempt_id)
    with host.Session() as db:
        assert db.query(TokenUsage).filter(
            TokenUsage.attempt_id == row.attempt_id).count() == 1


def test_failed_physical_attempt_survives_restart_as_liability(
        host, monkeypatch, tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.spend_aggregation_service import (
        BudgetReservationRefused, begin_llm_usage)

    _seed(host, spend=90.0)
    _reservation_pricing(monkeypatch)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _ChatClient(
            [{"raise": RuntimeError("provider may have charged")}], calls)})
    with pytest.raises(Exception):
        asyncio.run(handler.chat_completion(
            [{"role": "user", "content": "hello"}], "gpt-4o", "openai",
            max_tokens=1000))
    assert len(calls) == 1
    engine = create_engine(str(host.engine.url))
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with Session() as db:
            row = db.query(TokenUsage).filter(
                TokenUsage.tenant_id == TENANT,
                TokenUsage.attempt_id.isnot(None)).one()
            assert row.reservation_status == "active"
            assert float(row.reserved_cost_usd) == pytest.approx(7.0)
            with pytest.raises(BudgetReservationRefused):
                begin_llm_usage(
                    provider_id="openai", model_name="gpt-4o",
                    workspace_id=WORKSPACE, tenant_id=TENANT,
                    request_id="post-restart", attempt_id="post-restart",
                    reserved_cost_usd=7.0, enforce_budget=True)
    finally:
        engine.dispose()


def test_attempt_settlement_refuses_cross_scope_binding(
        host, monkeypatch, tmp_path):
    from core.spend_aggregation_service import record_llm_usage

    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _ChatClient(
            [{"response": _response("scoped")}], calls)})
    asyncio.run(handler.chat_completion(
        [{"role": "user", "content": "hello"}], "gpt-4o", "openai",
        max_tokens=1000))
    row = _attempt_rows(host)[0]
    with pytest.raises(Exception):
        record_llm_usage(
            provider_id=row.provider_id, model_name=row.model_name,
            prompt_tokens=row.prompt_tokens,
            completion_tokens=row.completion_tokens,
            cost_usd=row.cost_usd, agent_id=row.agent_id,
            workspace_id="ws-other-tenant", tenant_id="tenant-other",
            request_id=row.request_id, attempt_id=row.attempt_id)
    with host.Session() as db:
        fresh = db.query(TokenUsage).filter(
            TokenUsage.attempt_id == row.attempt_id).one()
        assert fresh.tenant_id == TENANT
        assert fresh.workspace_id == WORKSPACE


# --------------------------------------------------------------------------
# explicit refusals: pre-intent DB failure / invalid price
# --------------------------------------------------------------------------
@pytest.mark.parametrize("surface", ["stream", "chat"])
def test_preintent_db_failure_dispatches_nothing(
        host, monkeypatch, tmp_path, surface):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch)
    calls = []
    if surface == "stream":
        handler = _make_handler(
            monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
            async_={"openai": _StreamClient(
                "openai", [{"chunks": [_visible("NOPE")]}], calls)})
    else:
        handler = _make_handler(
            monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
            async_={"openai": _ChatClient(
                [{"response": _response("NOPE")}], calls)})
    from core import spend_aggregation_service as spend_module

    monkeypatch.setattr(
        spend_module, "begin_llm_usage",
        lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("intent store unavailable")))
    if surface == "stream":
        text = "".join(_stream(handler, "gpt-4o", "openai"))
        assert "budget authorization" in text.lower(), text
    else:
        with pytest.raises(Exception):
            asyncio.run(handler.chat_completion(
                [{"role": "user", "content": "hello"}], "gpt-4o",
                "openai", max_tokens=1000))
    assert calls == []
    assert _attempt_rows(host) == []


@pytest.mark.parametrize("surface", ["stream", "chat"])
@pytest.mark.parametrize("price", [-1.0, float("nan"), float("inf")])
def test_invalid_price_hardstop_zero_dispatch(
        host, monkeypatch, tmp_path, surface, price):
    _seed(host, spend=0.0)
    _pricing(monkeypatch, lambda *a, **k: price)
    calls = []
    if surface == "stream":
        handler = _make_handler(
            monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
            async_={"openai": _StreamClient(
                "openai", [{"chunks": [_visible("NOPE")]}], calls)})
        text = "".join(_stream(handler, "gpt-4o", "openai"))
        assert "budget authorization" in text.lower(), text
    else:
        handler = _make_handler(
            monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
            async_={"openai": _ChatClient(
                [{"response": _response("NOPE")}], calls)})
        with pytest.raises(Exception):
            asyncio.run(handler.chat_completion(
                [{"role": "user", "content": "hello"}], "gpt-4o",
                "openai", max_tokens=1000))
    assert calls == []
    assert _attempt_rows(host) == []


# --------------------------------------------------------------------------
# SDK hidden retries: one admission == one physical HTTP request
# --------------------------------------------------------------------------
def test_provider_clients_disable_sdk_hidden_retries():
    """The OpenAI SDK retries 5xx/429/connection errors by default.

    Those are physical requests that no reservation covers, and they create a
    second retry owner. Every handler client construction must disable them so
    the application ladder remains the only retry owner.
    """
    import inspect

    from core.llm import byok_handler as bh

    src = inspect.getsource(bh)
    assert bh._SDK_MAX_RETRIES == 0
    # 7 construction sites: lux sync/async, ollama sync/async, the shared
    # provider client_kwargs dict, and registered-local sync/async.
    assert src.count("_SDK_MAX_RETRIES") == 8
    assert src.count("max_retries=_SDK_MAX_RETRIES") == 6
    assert '"max_retries": _SDK_MAX_RETRIES' in src


# --------------------------------------------------------------------------
# multimodal: no proven image bound -> explicit unknown, never a guess
# --------------------------------------------------------------------------
_IMAGE_MESSAGES = [{
    "role": "user",
    "content": [
        {"type": "text", "text": "what is this"},
        {"type": "image_url",
         "image_url": {"url": "data:image/png;base64,AAAA"}},
    ],
}]


def test_authoritative_zero_price_image_retains_free_route(
        host, monkeypatch, tmp_path):
    """Configured numeric-zero pricing is authoritative: images cost 0 too.

    A fixed per-image token guess is still forbidden; the price contract
    decides. At $0/token the image token count cannot change the cost, so a
    genuinely free route must not be refused or downgraded to unknown.
    """
    _seed(host, spend=90.0)
    _pricing(monkeypatch, lambda *a, **k: 0.0)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _ChatClient(
            [{"response": _response("FREE IMAGE")}], calls)})
    result = asyncio.run(handler.chat_completion(
        _IMAGE_MESSAGES, "gpt-4o", "openai", max_tokens=1000))
    assert result["choices"][0]["message"]["content"] == "FREE IMAGE"
    assert len(calls) == 1
    rows = _attempt_rows(host)
    assert len(rows) == 1
    assert rows[0].pricing_status == "free"
    assert rows[0].reservation_status == "settled"
    assert float(rows[0].reserved_cost_usd or 0.0) == 0.0
    assert rows[0].cost_usd == pytest.approx(0.0)


def test_authoritative_zero_price_image_streams_free(
        host, monkeypatch, tmp_path):
    _seed(host, spend=90.0)
    _pricing(monkeypatch, lambda *a, **k: 0.0)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _StreamClient(
            "openai", [{"chunks": [_visible("FREE STREAM IMAGE")]}],
            calls)})
    text = "".join(_stream(
        handler, "gpt-4o", "openai", messages=_IMAGE_MESSAGES))
    assert text == "FREE STREAM IMAGE"
    rows = _attempt_rows(host)
    assert len(rows) == 1
    assert rows[0].pricing_status == "free"
    assert rows[0].reservation_status == "settled"
    assert float(rows[0].reserved_cost_usd or 0.0) == 0.0


def test_image_data_url_does_not_inflate_the_text_bound(
        host, monkeypatch, tmp_path):
    """Image accounting is never fabricated from base64 bytes."""
    from core.llm.byok_handler import BYOKHandler, _serialized_payload_for_bound

    _seed(host, spend=0.0)
    recorded = {}

    def _estimate(model, input_tokens, output_tokens):
        recorded["input_tokens"] = input_tokens
        return 1.0

    _pricing(monkeypatch, _estimate)
    handler = object.__new__(BYOKHandler)
    huge = "A" * (1024 * 1024)
    payload = [{"role": "user", "content": [
        {"type": "text", "text": "describe"},
        {"type": "image_url",
         "image_url": {"url": f"data:image/png;base64,{huge}"}},
    ]}]
    serialized = _serialized_payload_for_bound(payload)
    assert huge not in serialized
    assert "<inline-image>" in serialized
    handler._estimate_reservation_bound(
        "openai", "controlled-image-model", [serialized], 100)
    with_huge = recorded["input_tokens"]
    small = _serialized_payload_for_bound([{"role": "user", "content": [
        {"type": "text", "text": "describe"},
        {"type": "image_url",
         "image_url": {"url": "data:image/png;base64,AA"}},
    ]}])
    handler._estimate_reservation_bound(
        "openai", "controlled-image-model", [small], 100)
    assert recorded["input_tokens"] == with_huge


def test_observe_image_authoritative_usage_settles_actual(
        host, monkeypatch, tmp_path):
    """Provider input-token usage (which aggregates image tokens) is exact."""
    _seed(host, spend=0.0, limit=0.0)  # observe/no-limit
    _reservation_pricing(monkeypatch, bound_at=7.0, actual=7.0)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _ChatClient(
            [{"response": _response("IMAGE ANSWER")}], calls)})
    asyncio.run(handler.chat_completion(
        _IMAGE_MESSAGES, "gpt-4o", "openai", max_tokens=1000))
    rows = _attempt_rows(host)
    assert len(rows) == 1
    row = rows[0]
    assert row.cost_usd == pytest.approx(7.0)
    assert row.pricing_status == "priced"
    assert row.reservation_status == "settled"
    assert row.prompt_tokens == 10 and row.completion_tokens == 5


def test_observe_image_image_token_detail_is_consumed(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0, limit=0.0)
    _reservation_pricing(monkeypatch, bound_at=7.0, actual=7.0)
    response = _response("IMAGE DETAIL")
    response.usage.prompt_tokens_details = SimpleNamespace(image_tokens=10)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _ChatClient([{"response": response}], calls)})
    asyncio.run(handler.chat_completion(
        _IMAGE_MESSAGES, "gpt-4o", "openai", max_tokens=1000))
    row = _attempt_rows(host)[0]
    assert row.cost_usd == pytest.approx(7.0)
    assert row.pricing_status == "priced"


def test_observe_image_malformed_image_detail_stays_unknown(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0, limit=0.0)
    _reservation_pricing(monkeypatch, bound_at=7.0, actual=7.0)
    response = _response("IMAGE BAD DETAIL")
    response.usage.prompt_tokens_details = SimpleNamespace(image_tokens=-1)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _ChatClient([{"response": response}], calls)})
    asyncio.run(handler.chat_completion(
        _IMAGE_MESSAGES, "gpt-4o", "openai", max_tokens=1000))
    row = _attempt_rows(host)[0]
    assert row.cost_usd is None
    assert row.pricing_status == "unknown"
    assert row.reservation_status == "uncertain"


def test_observe_image_without_usage_stays_unknown(
        host, monkeypatch, tmp_path):
    """Absent usage detail is never an image zero."""
    _seed(host, spend=0.0, limit=0.0)
    _reservation_pricing(monkeypatch, bound_at=7.0, actual=7.0)
    response = SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(
                content="NO USAGE", tool_calls=None, function_call=None,
                reasoning_content=None),
            finish_reason="stop")])
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _ChatClient([{"response": response}], calls)})
    asyncio.run(handler.chat_completion(
        _IMAGE_MESSAGES, "gpt-4o", "openai", max_tokens=1000))
    row = _attempt_rows(host)[0]
    assert row.cost_usd is None
    assert row.pricing_status == "unknown"
    assert row.reservation_status == "uncertain"


def test_paid_image_still_refuses_under_hardstop(
        host, monkeypatch, tmp_path):
    """A positive configured price keeps the explicit-unknown image refusal."""
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=7.0, actual=7.0)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _ChatClient(
            [{"response": _response("MUST NOT RUN")}], calls)})
    with pytest.raises(Exception):
        asyncio.run(handler.chat_completion(
            _IMAGE_MESSAGES, "gpt-4o", "openai", max_tokens=1000))
    assert calls == []
    assert _attempt_rows(host) == []


def test_multimodal_hardstop_refuses_without_fabricated_image_bound(
        host, monkeypatch, tmp_path):
    _seed(host, spend=10.0)
    _reservation_pricing(monkeypatch, bound_at=7.0, actual=7.0)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _ChatClient(
            [{"response": _response("IMAGE ANSWER")}], calls)})
    with pytest.raises(Exception):
        asyncio.run(handler.chat_completion(
            _IMAGE_MESSAGES, "gpt-4o", "openai", max_tokens=1000))
    assert calls == [], "no dispatch without a proven image bound"
    # The refusal happens inside the admission transaction, which rolls back:
    # no reservation row and no physical dispatch.
    assert _attempt_rows(host) == []


def test_multimodal_observe_admits_with_unknown_liability(
        host, monkeypatch, tmp_path):
    _seed(host, spend=10.0, limit=0.0)
    _reservation_pricing(monkeypatch, bound_at=7.0, actual=7.0)
    calls = []
    handler = _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]},
        async_={"openai": _ChatClient(
            [{"response": _response("IMAGE ANSWER")}], calls)})
    result = asyncio.run(handler.chat_completion(
        _IMAGE_MESSAGES, "gpt-4o", "openai", max_tokens=1000))
    assert result["choices"][0]["message"]["content"] == "IMAGE ANSWER"
    assert len(calls) == 1
    rows = _attempt_rows(host)
    assert len(rows) == 1
    # The doubled provider reported complete usage, which is authoritative
    # for the image-bearing attempt; observe mode settles it exactly.
    assert rows[0].pricing_status == "priced"
    assert rows[0].reservation_status == "settled"
    assert rows[0].cost_usd == pytest.approx(7.0)


# --------------------------------------------------------------------------
# conservative payload/tokenizer bound
# --------------------------------------------------------------------------
def test_bound_uses_byte_upper_for_every_text_model(
        host, monkeypatch, tmp_path):
    """No provider brand is tokenizer proof: every text model uses bytes.

    The second ``count_tokens`` value means ``estimated`` (True = heuristic),
    not ``exact``; a heuristic count is never a bound. Root owns the finite
    estimated-flag corrective commit on the atomic branch; this control only
    asserts the physical-attempt bound never guesses smaller than UTF-8 bytes.
    """
    from core.llm import prompt_budget

    _seed(host, spend=0.0)
    _pricing(monkeypatch, lambda model, i, o: (i + o) * 0.000001)
    handler = _make_handler(monkeypatch, tmp_path, {})
    text = "日本語テキストです" * 20
    byte_upper = len(text.encode("utf-8"))
    literal_floor = (byte_upper + 256 + 8 + 10) * 0.000001 * 1.25
    for provider, model in (("openrouter", "vendor/unknown-model"),
                            ("openai", "gpt-4o")):
        for flag in (True, False):
            monkeypatch.setattr(
                prompt_budget, "count_tokens",
                lambda text, _flag=flag: (1, _flag))
            bound = handler._estimate_reservation_bound(
                provider, model, [text], 10)
            assert bound == pytest.approx(literal_floor, rel=1e-6), (
                provider, model, flag)


def test_bound_counts_serialized_payload_and_schema(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _pricing(monkeypatch, lambda model, i, o: (i + o) * 0.000001)
    handler = _make_handler(monkeypatch, tmp_path, {})
    messages = [
        {"role": "system", "content": "x" * 10},
        {"role": "user", "content": "y" * 10},
    ]
    payload = json.dumps(messages)
    without_schema = handler._estimate_reservation_bound(
        "openrouter", "vendor/model", [payload], 10)
    with_schema = handler._estimate_reservation_bound(
        "openrouter", "vendor/model", [payload], 10,
        schema_text="s" * 500)
    assert with_schema > without_schema
    # The serialized message shape (roles/braces), not just content, is counted.
    assert without_schema >= (
        len(payload.encode("utf-8")) + 256 + 8 + 10) * 0.000001 * 1.25


# --------------------------------------------------------------------------
# curated OpenCode free-candidate hard-stop admission
# --------------------------------------------------------------------------
# The shared OpenCode Zen catalog records a real, provider-qualified free
# candidate (``opencode-go/deepseek-v4.1-flash-free``) in
# ``OPCODE_KNOWN_FREE_MODELS`` while deliberately keeping it OUT of the ranking
# price table (``OPCODE_KNOWN_PRICES``). The free fact is therefore present in
# the trusted provider catalog and absent from the pricing catalog.
#
# ``_estimate_reservation_bound`` consults only the pricing catalog. Under
# ``hard_stop`` an absent price is unknown (the documented "absence is never
# free" contract), so the trusted free route used to be refused before
# dispatch even though ``opencode-go`` is configured and the route catalog says
# it serves the model. These controls pin the expected provider-qualified
# outcome:
#
# * the curated ``(opencode-go, <curated-free-model>)`` route is admitted with
#   an explicit zero reservation (the catalog's free fact is authoritative for
#   THIS provider route — it is not inferred from an absent price);
# * the same model name on another provider is still unknown and refuses;
# * an uncurated ``-free`` suffix is still unknown and refuses;
# * the OpenCode free->paid fallback keeps a SEPARATE paid reservation/attempt;
# * a PRESENT but partial/invalid price row stays unknown: it is not the absent
#   price that licenses the curated free fact, and a static ``MODEL_COSTS``
#   fallback must not mask the malformed explicit material;
# * a known-free attempt whose settlement resolves a conflicting positive cost
#   keeps that real spend instead of rewriting it to ``$0``.
#
# The controls matter: a fix keyed on the model name alone (or on the ``-free``
# suffix) would make the other-provider/unknown-suffix controls pass at $0 too,
# which is exactly the cross-provider mispricing this regression forbids.
#
# Everything is doubled: a scratch SQLite ledger/route catalog and fake SDK
# clients. No real provider, live DB, credential, network fetch or spend.
PROVIDER = "opencode-go"
OTHER_PROVIDER = "openrouter"
FREE_MODEL = "deepseek-v4.1-flash-free"
PAID_MODEL = "deepseek-v4.1-flash"
UNKNOWN_FREE_MODEL = "stealth-unlisted-model-free"


@pytest.fixture()
def scratch_pricing(monkeypatch):
    """Real estimate semantics over a scratch, curated-only price catalog.

    Only the real ``OPCODE_KNOWN_PRICES`` slice is seeded. The curated free
    candidate is deliberately absent, exactly as production
    ``fetch_opencode_pricing`` excludes free models from the ranking catalog.
    This is a scratch object: no disk cache, global mutation or live fetch.
    """
    fetcher = object.__new__(DynamicPricingFetcher)
    fetcher.pricing_cache = dict(fetcher._opencode_static_fallback())

    # The reproduction precondition: curated free, not priced, no explicit 0/0.
    assert FREE_MODEL in OPCODE_KNOWN_FREE_MODELS
    assert FREE_MODEL not in OPCODE_KNOWN_PRICES
    assert FREE_MODEL not in fetcher.pricing_cache
    assert fetcher.get_model_price(FREE_MODEL) is None

    monkeypatch.setattr(
        "core.llm.byok_handler.get_pricing_fetcher", lambda: fetcher)
    return fetcher


def _handler(monkeypatch, tmp_path, provider_id, catalog, client):
    """Doubled handler: one fake provider client + explicit route catalog."""
    handler = _make_handler(
        monkeypatch, tmp_path, {provider_id: catalog},
        async_={provider_id: client})
    # Provider policy is a separate gate, not the subject of this regression.
    from core.llm.provider_policy import ProviderPolicy
    handler.provider_policy = ProviderPolicy(mode="unset")
    return handler


PRESENT_BUT_UNUSABLE_PRICES = [
    # Partial: output material is required for a positive output quantity.
    {"input_cost_per_token": 0.0},
    {"input_cost_per_token": 0.01},
    # Invalid: bools and a negative rate are not monetary material.
    {"input_cost_per_token": False, "output_cost_per_token": False},
    {"input_cost_per_token": -0.001, "output_cost_per_token": 0.001},
]


@pytest.mark.parametrize("material", PRESENT_BUT_UNUSABLE_PRICES)
def test_present_partial_or_invalid_price_is_not_curated_free(
        monkeypatch, tmp_path, scratch_pricing, material):
    """A present-but-unusable row stays unknown; it is not an absent price."""
    scratch_pricing.pricing_cache[FREE_MODEL] = dict(material)
    assert scratch_pricing.get_model_price(FREE_MODEL) == material

    handler = _handler(monkeypatch, tmp_path, PROVIDER, [FREE_MODEL], None)

    assert handler._estimate_reservation_bound(
        PROVIDER, FREE_MODEL, ["hello"], 1000) is None


def test_present_invalid_price_is_not_hidden_by_static_fallback(
        monkeypatch, tmp_path, scratch_pricing):
    """Malformed explicit material must not be masked by MODEL_COSTS."""
    from core.cost_config import get_llm_cost

    assert get_llm_cost("gpt-4o", 1000, 1000) is not None
    scratch_pricing.pricing_cache["gpt-4o"] = {
        "input_cost_per_token": 0.01,
    }

    handler = _handler(monkeypatch, tmp_path, "openai", ["gpt-4o"], None)

    assert handler._estimate_reservation_bound(
        "openai", "gpt-4o", ["hello"], 1000) is None


def test_known_free_settlement_preserves_conflicting_positive_cost(
        host, monkeypatch):
    """A positive settlement on a known-free attempt is real spend, not $0."""
    _seed(host, spend=90.0)

    class _PositivePricing:
        def estimate_cost(self, model, input_tokens, output_tokens):
            return 5.0

    monkeypatch.setattr(
        "core.llm.byok_handler.get_pricing_fetcher",
        lambda: _PositivePricing())
    handler = object.__new__(BYOKHandler)
    handler.workspace_id = WORKSPACE
    handler.tenant_id = TENANT

    cost = handler._settle_physical_response(
        provider_id=PROVIDER,
        model=PAID_MODEL,
        response=_response("PAID OK"),
        request_id="conflicting-positive",
        attempt_id="conflicting-positive-attempt",
        known_free=True,
    )

    assert cost == 5.0
    rows = _attempt_rows(host)
    assert len(rows) == 1
    assert rows[0].attempt_id == "conflicting-positive-attempt"
    assert float(rows[0].cost_usd) == 5.0


def _response_without_usage(content):
    """A successful paid reply whose usage is absent (unknown liability)."""
    response = _response(content)
    response.usage = None
    return response


def test_curated_opencode_free_candidate_admits_zero_under_hard_stop(
        host, monkeypatch, tmp_path, scratch_pricing):
    """The audit case: trusted free route must not be refused as unpriced."""
    _seed(host, spend=90.0)
    calls = []
    handler = _handler(
        monkeypatch, tmp_path, PROVIDER, [FREE_MODEL],
        _ChatClient([{"response": _response("FREE OK")}], calls))

    result = asyncio.run(handler.chat_completion(
        [{"role": "user", "content": "hello"}],
        FREE_MODEL, PROVIDER, max_tokens=1000))

    assert result["choices"][0]["message"]["content"] == "FREE OK"
    assert [call["model"] for call in calls] == [FREE_MODEL]

    rows = _attempt_rows(host)
    assert len(rows) == 1
    row = rows[0]
    assert row.provider_id == PROVIDER
    assert row.model_name == FREE_MODEL
    assert float(row.reserved_cost_usd or 0.0) == 0.0
    # Zero is the trusted free bound; it must not remain an open admission.
    assert row.reservation_status != "active"
    assert row.cost_usd is None or float(row.cost_usd) == 0.0


def test_same_free_model_name_on_other_provider_still_refuses(
        host, monkeypatch, tmp_path, scratch_pricing):
    """Trust is provider-qualified: the name alone buys nothing elsewhere."""
    _seed(host, spend=90.0)
    calls = []
    handler = _handler(
        monkeypatch, tmp_path, OTHER_PROVIDER, [FREE_MODEL],
        _ChatClient([{"response": _response("MUST NOT RUN")}], calls))

    with pytest.raises(AllProvidersFailedError) as excinfo:
        asyncio.run(handler.chat_completion(
            [{"role": "user", "content": "hello"}],
            FREE_MODEL, OTHER_PROVIDER, max_tokens=1000))

    assert "budget authorization is unavailable" in str(excinfo.value).lower()
    assert calls == []
    assert _attempt_rows(host) == []


def test_unknown_free_suffix_is_not_curated_trust(
        host, monkeypatch, tmp_path, scratch_pricing):
    """A ``-free`` suffix is not evidence of a curated free route."""
    _seed(host, spend=90.0)
    assert UNKNOWN_FREE_MODEL not in OPCODE_KNOWN_FREE_MODELS
    calls = []
    handler = _handler(
        monkeypatch, tmp_path, PROVIDER, [UNKNOWN_FREE_MODEL],
        _ChatClient([{"response": _response("MUST NOT RUN")}], calls))

    with pytest.raises(AllProvidersFailedError) as excinfo:
        asyncio.run(handler.chat_completion(
            [{"role": "user", "content": "hello"}],
            UNKNOWN_FREE_MODEL, PROVIDER, max_tokens=1000))

    assert "budget authorization is unavailable" in str(excinfo.value).lower()
    assert calls == []
    assert _attempt_rows(host) == []


def test_paid_free_fallback_keeps_a_separate_paid_reservation(
        host, monkeypatch, tmp_path, scratch_pricing):
    """Free allowance exhausted -> paid sibling, with its own attempt/bound."""
    _seed(host, spend=90.0)
    assert _opencode_paid_fallback_model(FREE_MODEL) == PAID_MODEL
    assert PAID_MODEL in OPCODE_KNOWN_PRICES

    calls = []
    client = _ChatClient(
        [
            {"raise": _insufficient_balance_error()},
            # No usage: the paid reservation remains visible after settlement
            # as the documented explicit-unknown liability.
            {"response": _response_without_usage("PAID OK")},
        ],
        calls,
    )
    handler = _handler(
        monkeypatch, tmp_path, PROVIDER, [FREE_MODEL, PAID_MODEL], client)

    # The real healer has no rule for a credit-exhaustion error; keep this
    # control focused on admission/accounting rather than healer behavior.
    monkeypatch.setattr(
        "core.llm.routing.request_healer.get_request_healer",
        lambda: SimpleNamespace(
            heal=lambda *a, **k: SimpleNamespace(patched_kwargs=None)))

    result = asyncio.run(handler.chat_completion(
        [{"role": "user", "content": "hello"}],
        FREE_MODEL, PROVIDER, max_tokens=1000))

    assert result["model"] == PAID_MODEL
    assert [call["model"] for call in calls] == [FREE_MODEL, PAID_MODEL]

    rows = _attempt_rows(host)
    assert len(rows) == 2, [row.attempt_id for row in rows]
    free_row, paid_row = rows

    assert free_row.model_name == FREE_MODEL
    assert float(free_row.reserved_cost_usd or 0.0) == 0.0

    assert paid_row.model_name == PAID_MODEL
    assert paid_row.attempt_id != free_row.attempt_id
    assert float(paid_row.reserved_cost_usd or 0.0) > 0.0
    assert paid_row.reservation_status == "uncertain"
