"""ModelProtocolUnsupported pairs: JSON retry, memoization, cascade skip.

OpenCode Go serves models the structured path cannot use (live 2026-10-08
case-4 trial: opencode-go/claude-haiku-5-5, sweep-injected, answered
``400 {'type': 'ModelProtocolUnsupported'}`` to the instructor call). The
catalog-served pair gate passes — the gateway DOES serve the model — so
the structured cascade paid the doomed round trip on every sweep with no
memo and no recovery.

Three contracts pinned here (mirroring the reasoning-mandatory retries):
1. First occurrence in TOOLS mode retries ONCE in JSON mode.
2. A pair that rejects JSON mode too is memoized into
   _STRUCTURED_PROTOCOL_UNSUPPORTED and the cascade fails over.
3. A memoized pair is skipped BEFORE dispatch on later structured calls
   (streaming cascades keep it — that is a different protocol).
"""
from __future__ import annotations

import itertools
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("TESTING", "1")

_PROTO_MSG = (
    "Error code: 400 - {'type': 'error', 'error': {'type': "
    "'ModelProtocolUnsupported', 'message': 'Model does not support this "
    "protocol.'}}"
)


@pytest.fixture(autouse=True)
def _fake_instructor(monkeypatch):
    """Fake instructor that raises the protocol 400 per the pair's script.

    ``from_openai(client)`` builds a TOOLS-mode client;
    ``from_openai(client, mode=Mode.JSON)`` builds a JSON-mode one. Which
    one (and thus whether create() raises) follows the mode, exactly like
    the real gateway.
    """
    from core.llm import byok_handler

    calls: list = []

    def _make(mode: str, fail_tools: bool, fail_json: bool):
        def _create(**kwargs):
            calls.append((mode, kwargs))
            if mode == "tools" and fail_tools:
                raise RuntimeError(_PROTO_MSG)
            if mode == "json" and fail_json:
                raise RuntimeError(_PROTO_MSG)
            return SimpleNamespace(ok=True)
        return SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
        )

    state = {"fail_json": False}

    def _from_openai(client, mode=None):
        if mode is None:
            return _make("tools", True, state["fail_json"])
        return _make("json", True, state["fail_json"])

    fake_module = MagicMock()
    fake_module.from_openai.side_effect = _from_openai
    fake_module.Mode = SimpleNamespace(JSON="json")
    monkeypatch.setitem(sys.modules, "instructor", fake_module)
    monkeypatch.setattr(byok_handler, "instructor", fake_module, raising=False)
    monkeypatch.setattr(byok_handler, "INSTRUCTOR_AVAILABLE", True)

    fake_db = MagicMock()
    paid_workspace = SimpleNamespace(tenant_id="t-1")
    paid_tenant = SimpleNamespace(id="t-1", plan_type=SimpleNamespace(value="pro"))
    fake_db.query.return_value.filter.return_value.first.side_effect = itertools.cycle(
        [paid_workspace, paid_tenant]
    )

    class _Ctx:
        def __enter__(self):
            return fake_db

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(byok_handler, "get_db_session", lambda: _Ctx())
    monkeypatch.setattr(
        byok_handler, "_parse_structured_result",
        lambda *a, **k: "PARSED", raising=False,
    )
    state["_calls"] = calls
    return state


def _handler(ranked):
    from core.llm.byok_handler import AwaitableResult, BYOKHandler

    handler = BYOKHandler.__new__(BYOKHandler)
    handler.workspace_id = "ws-1"
    handler.tenant_id = "t-1"
    handler.db_session = MagicMock()
    handler.clients = {"opencode-go": MagicMock()}
    handler.async_clients = {}
    handler.governance = None
    handler._is_trial_restricted = lambda: False
    handler.byok_manager = MagicMock()
    handler.byok_manager.get_tenant_api_key = MagicMock(return_value=None)
    handler.analyze_query_complexity = MagicMock(
        return_value=MagicMock(value="standard"))
    handler.get_ranked_providers = MagicMock(
        return_value=AwaitableResult(list(ranked)))
    handler.get_context_window = MagicMock(return_value=8000)
    handler.truncate_to_context = MagicMock(side_effect=lambda p, *a, **k: p)
    from core.llm import byok_handler as bh
    bh._STRUCTURED_PROTOCOL_UNSUPPORTED.clear()
    bh._TOOLCHOICE_UNSUPPORTED.clear()
    # The unified dispatch gate consults the REAL route registry for
    # automatic candidates; synthetic pairs are unknown there and would be
    # refused BEFORE the protocol ladder this suite exercises. Catalog
    # admission is stubbed open — this suite pins PROTOCOL recovery; catalog
    # policy is pinned separately (preferred-route / fallback suites).
    handler._dispatch_catalog_admits = (
        lambda attempt_provider_id, model, requested=None,
        operation="text", explicit_route=None: True)
    return handler


def _call(handler):
    return handler.generate_structured_response(
        prompt="plan", system_instruction="json", response_model=object,
    )


@pytest.mark.asyncio
async def test_first_tools_failure_retries_once_in_json(_fake_instructor):
    handler = _handler([("opencode-go", "protocol-picky-model")])
    result = await _call(handler)

    modes = [m for m, _ in _fake_instructor["_calls"]]
    assert modes == ["tools", "json"], (
        "a ModelProtocolUnsupported pair must retry exactly once in JSON "
        f"mode; got {modes}")
    assert result is not None
    from core.llm import byok_handler as bh
    assert "opencode-go/protocol-picky-model" in bh._TOOLCHOICE_UNSUPPORTED


@pytest.mark.asyncio
async def test_json_failure_memoizes_and_skips_later(_fake_instructor):
    _fake_instructor["fail_json"] = True
    handler = _handler([
        ("opencode-go", "protocol-picky-model"),
        ("opencode-go", "protocol-fine-model"),
    ])
    await _call(handler)

    from core.llm import byok_handler as bh
    assert "opencode-go/protocol-picky-model" in (
        bh._STRUCTURED_PROTOCOL_UNSUPPORTED), (
        "a pair rejecting BOTH protocols must be memoized for skip")

    def _picky_calls():
        return [c for m, c in _fake_instructor["_calls"]
                if c.get("model") == "protocol-picky-model"]

    # Both modes paid exactly ONCE for the picky pair — no spin.
    _fake_instructor["_calls"].clear()
    await _call(handler)
    assert _picky_calls() == [], (
        "a memoized structured-protocol pair must not be dispatched at "
        "all on later structured calls")


@pytest.mark.asyncio
async def test_memoized_pair_is_skipped_before_dispatch(_fake_instructor):
    from core.llm import byok_handler as bh
    _fake_instructor["fail_json"] = False  # would succeed if wrongly tried
    handler = _handler([
        ("opencode-go", "protocol-picky-model"),
        ("opencode-go", "protocol-fine-model"),
    ])
    bh._STRUCTURED_PROTOCOL_UNSUPPORTED.add(
        "opencode-go/protocol-picky-model")
    result = await _call(handler)

    picky = [c for m, c in _fake_instructor["_calls"]
             if c.get("model") == "protocol-picky-model"]
    assert picky == [], (
        "the pre-memoized pair must be skipped before dispatch; got "
        f"{len(picky)} call(s)")
    assert result is not None, (
        "the fine candidate must still serve the structured call")
