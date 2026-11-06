"""One request-owned retry-state contract for streaming.

The verifier probes for PR #664 showed two cross-frame leaks:

* a paid free->paid retry yielded visible text, then fell through to a ranked
  route and appended a second model's answer;
* the ranked-route recursive call reset ``_allow_ladder_sweep``, so a later
  hop started another catalogue sweep and re-issued an already-failed pair.

``_StreamRequestState`` is shared by every nested streaming frame. This file
generates the failure-location x content-stage x exhaustion table that pins
the contract: visible output stops all replay, automatic pairs are at most
once per request, the catalogue sweep is one-shot, and explicit same-pair
repairs stay bounded. All transport is doubled; catalogues and policy are
explicitly scoped per case.
"""
from __future__ import annotations

import asyncio
from collections import Counter
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.llm.byok_handler import BYOKHandler
from tests._llm_route_catalog import install_route_catalog
from tests.test_opencode_go_provider import _insufficient_balance_error


ERROR_TOKEN = (
    "\n\n[Error: All LLM providers failed. Please check your API key "
    "configuration and try again.]"
)


class _ScriptedStream:
    def __init__(self, chunks, fail_after=None):
        self._chunks = list(chunks)
        self._fail_after = fail_after
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._fail_after is not None and self._index >= self._fail_after:
            self._fail_after = None
            raise RuntimeError("stream cut mid-way")
        if self._index >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


class _ScriptedClient:
    """One provider client; the script index is request-wide."""

    def __init__(self, provider_id, script, calls):
        self._provider_id = provider_id
        self._script = script
        self._calls = calls
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        index = len(self._calls)
        self._calls.append((self._provider_id, kwargs["model"]))
        assert index < len(self._script), (
            f"unexpected dispatch #{index + 1}: {kwargs['model']}")
        action = self._script[index]
        if action.get("raise") is not None:
            raise action["raise"]
        return _ScriptedStream(
            action.get("chunks") or [], action.get("fail_after"))


def _visible(text, finish=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(
            delta=SimpleNamespace(content=text, reasoning=None),
            finish_reason=finish,
        )])


def _reasoning(text="hidden thinking"):
    return SimpleNamespace(
        choices=[SimpleNamespace(
            delta=SimpleNamespace(content=None, reasoning=text),
            finish_reason="stop",
        )])


def _content(text):
    return {"chunks": [_visible(text, "stop")]}


def _partial(text):
    return {"chunks": [_visible(text)], "fail_after": 1}


def _reasoning_only():
    return {"chunks": [_reasoning()]}


def _raise(exc):
    return {"raise": exc}


def _generic_failure():
    return _raise(RuntimeError("controlled model failure"))


def _quota_failure():
    return _raise(_insufficient_balance_error())


@pytest.fixture(autouse=True)
def _clean_retry_state(monkeypatch):
    """Cooldowns are process-wide by design; the matrix owns each request."""
    BYOKHandler.invalidate_provider_failures()
    monkeypatch.setattr(
        "core.llm.routing.request_healer.get_request_healer",
        lambda: SimpleNamespace(
            heal=lambda *a, **k: SimpleNamespace(
                patched_kwargs=None, rule=None, patched_keys=[])),
    )
    yield
    BYOKHandler.invalidate_provider_failures()


@pytest.fixture
def handler(monkeypatch):
    manager = Mock()
    manager.is_configured.return_value = False
    manager.get_api_key.return_value = None
    with patch("core.llm.byok_handler.get_byok_manager", return_value=manager), \
         patch("core.llm.byok_handler.get_db_session", return_value=Mock()):
        h = BYOKHandler()
    h.clients = {}
    h.async_clients = {}
    h._record_outcome_feedback = AsyncMock()
    return h


async def _collect(handler, model, provider_id, **kwargs):
    return [
        part async for part in handler.stream_completion(
            [{"role": "user", "content": "hello"}],
            model=model,
            provider_id=provider_id,
            max_tokens=100,
            **kwargs,
        )
    ]


def _run(handler, model, provider_id, **kwargs):
    return asyncio.run(_collect(handler, model, provider_id, **kwargs))


def _install_case(handler, monkeypatch, tmp_path, case):
    install_route_catalog(monkeypatch, tmp_path, case["catalog"])
    calls = []
    for provider_id in case["providers"]:
        client = _ScriptedClient(provider_id, case["script"], calls)
        handler.clients[provider_id] = client
        handler.async_clients[provider_id] = client
    return calls


def _feedback_successes(handler):
    return [
        call.kwargs.get("success")
        for call in handler._record_outcome_feedback.await_args_list
    ]


# Generated table: one row per (failure location, content stage, exhaustion).
# "exhaustion" is the number of automatic routes the request is allowed to
# reach; visible-partial rows must stop before the next route regardless.
CASES = [
    # --- initial attempt -------------------------------------------------
    pytest.param(dict(
        id="initial-zero-single", location="initial", content="zero",
        exhaustion="single", providers=["opencode-go"],
        model="model-a", provider_id="opencode-go",
        catalog={"opencode-go": ["model-a"]},
        script=[_generic_failure()],
        expected_calls=[("opencode-go", "model-a")],
        expected_text=ERROR_TOKEN, expect_error=True,
    ), id="initial-zero-single"),
    pytest.param(dict(
        id="initial-reasoning-single", location="initial",
        content="reasoning", exhaustion="single",
        providers=["opencode-go"], model="model-a",
        provider_id="opencode-go",
        catalog={"opencode-go": ["model-a"]},
        script=[_reasoning_only()],
        expected_calls=[("opencode-go", "model-a")],
        expected_text=ERROR_TOKEN, expect_error=True,
    ), id="initial-reasoning-single"),
    pytest.param(dict(
        id="initial-visible-single", location="initial", content="partial",
        exhaustion="single", providers=["opencode-go"],
        model="model-a", provider_id="opencode-go",
        catalog={"opencode-go": ["model-a"]},
        script=[_partial("INITIAL PARTIAL")],
        expected_calls=[("opencode-go", "model-a")],
        expected_text="INITIAL PARTIAL", expect_error=False,
    ), id="initial-visible-single"),

    # --- paid sibling retry ----------------------------------------------
    pytest.param(dict(
        id="paid-zero-two", location="paid_retry", content="zero",
        exhaustion="two", providers=["opencode-go"],
        model="deepseek-v4-flash-free", provider_id="opencode-go",
        catalog={"opencode-go": [
            "deepseek-v4-flash-free", "deepseek-v4-flash"]},
        script=[_quota_failure(), _generic_failure()],
        expected_calls=[
            ("opencode-go", "deepseek-v4-flash-free"),
            ("opencode-go", "deepseek-v4-flash"),
        ],
        expected_text=ERROR_TOKEN, expect_error=True,
    ), id="paid-zero-two"),
    pytest.param(dict(
        id="paid-reasoning-two", location="paid_retry", content="reasoning",
        exhaustion="two", providers=["opencode-go"],
        model="deepseek-v4-flash-free", provider_id="opencode-go",
        catalog={"opencode-go": [
            "deepseek-v4-flash-free", "deepseek-v4-flash"]},
        script=[_quota_failure(), _reasoning_only()],
        expected_calls=[
            ("opencode-go", "deepseek-v4-flash-free"),
            ("opencode-go", "deepseek-v4-flash"),
        ],
        expected_text=ERROR_TOKEN, expect_error=True,
    ), id="paid-reasoning-two"),
    pytest.param(dict(
        id="paid-visible-two", location="paid_retry", content="partial",
        exhaustion="two", providers=["opencode-go"],
        model="deepseek-v4-flash-free", provider_id="opencode-go",
        catalog={"opencode-go": [
            "deepseek-v4-flash-free", "deepseek-v4-flash"]},
        script=[_quota_failure(), _partial("PAID PARTIAL")],
        expected_calls=[
            ("opencode-go", "deepseek-v4-flash-free"),
            ("opencode-go", "deepseek-v4-flash"),
        ],
        expected_text="PAID PARTIAL", expect_error=False,
    ), id="paid-visible-two"),

    # --- self-heal retry -------------------------------------------------
    pytest.param(dict(
        id="heal-zero-two", location="self_heal", content="zero",
        exhaustion="two", providers=["openai"], model="gpt-4o",
        provider_id="openai", catalog={"openai": ["gpt-4o"]},
        heal=True,
        script=[_generic_failure(), _generic_failure()],
        expected_calls=[("openai", "gpt-4o"), ("openai", "gpt-4o")],
        expected_text=ERROR_TOKEN, expect_error=True,
    ), id="heal-zero-two"),
    pytest.param(dict(
        id="heal-reasoning-two", location="self_heal", content="reasoning",
        exhaustion="two", providers=["openai"], model="gpt-4o",
        provider_id="openai", catalog={"openai": ["gpt-4o"]},
        heal=True,
        script=[_generic_failure(), _reasoning_only()],
        expected_calls=[("openai", "gpt-4o"), ("openai", "gpt-4o")],
        expected_text=ERROR_TOKEN, expect_error=True,
    ), id="heal-reasoning-two"),
    pytest.param(dict(
        id="heal-visible-two", location="self_heal", content="partial",
        exhaustion="two", providers=["openai"], model="gpt-4o",
        provider_id="openai", catalog={"openai": ["gpt-4o"]},
        heal=True,
        script=[_generic_failure(), _partial("HEAL PARTIAL")],
        expected_calls=[("openai", "gpt-4o"), ("openai", "gpt-4o")],
        expected_text="HEAL PARTIAL", expect_error=False,
    ), id="heal-visible-two"),

    # --- provider loop fallback -----------------------------------------
    pytest.param(dict(
        id="provider-zero-two", location="provider_fallback", content="zero",
        exhaustion="two", providers=["openai", "deepseek"],
        model="shared-model", provider_id="openai",
        catalog={"openai": ["shared-model"],
                 "deepseek": ["shared-model"]},
        script=[_generic_failure(), _content("SECOND PROVIDER")],
        expected_calls=[
            ("openai", "shared-model"), ("deepseek", "shared-model")],
        expected_text="SECOND PROVIDER", expect_error=False,
    ), id="provider-zero-two"),
    pytest.param(dict(
        id="provider-reasoning-two", location="provider_fallback",
        content="reasoning", exhaustion="two",
        providers=["openai", "deepseek"], model="shared-model",
        provider_id="openai",
        catalog={"openai": ["shared-model"],
                 "deepseek": ["shared-model"]},
        script=[_reasoning_only(), _content("SECOND PROVIDER")],
        expected_calls=[
            ("openai", "shared-model"), ("deepseek", "shared-model")],
        expected_text="SECOND PROVIDER", expect_error=False,
    ), id="provider-reasoning-two"),
    pytest.param(dict(
        id="provider-visible-single", location="provider_fallback",
        content="partial", exhaustion="single",
        providers=["openai", "deepseek"], model="shared-model",
        provider_id="openai",
        catalog={"openai": ["shared-model"],
                 "deepseek": ["shared-model"]},
        script=[_partial("PROVIDER PARTIAL")],
        expected_calls=[("openai", "shared-model")],
        expected_text="PROVIDER PARTIAL", expect_error=False,
    ), id="provider-visible-single"),

    # --- ranked route fallback -------------------------------------------
    pytest.param(dict(
        id="ranked-zero-two", location="ranked_fallback", content="zero",
        exhaustion="two", providers=["openai", "deepseek"],
        model="gpt-4o", provider_id="openai",
        catalog={"openai": ["gpt-4o"], "deepseek": ["deepseek-chat"]},
        fallback_routes=[("deepseek", "deepseek-chat")],
        script=[_generic_failure(), _content("RANKED ANSWER")],
        expected_calls=[
            ("openai", "gpt-4o"), ("deepseek", "deepseek-chat")],
        expected_text="RANKED ANSWER", expect_error=False,
    ), id="ranked-zero-two"),
    pytest.param(dict(
        id="ranked-reasoning-two", location="ranked_fallback",
        content="reasoning", exhaustion="two",
        providers=["openai", "deepseek"], model="gpt-4o",
        provider_id="openai",
        catalog={"openai": ["gpt-4o"], "deepseek": ["deepseek-chat"]},
        fallback_routes=[("deepseek", "deepseek-chat")],
        script=[_reasoning_only(), _content("RANKED ANSWER")],
        expected_calls=[
            ("openai", "gpt-4o"), ("deepseek", "deepseek-chat")],
        expected_text="RANKED ANSWER", expect_error=False,
    ), id="ranked-reasoning-two"),
    pytest.param(dict(
        id="ranked-visible-single", location="ranked_fallback",
        content="partial", exhaustion="single",
        providers=["openai", "deepseek"], model="gpt-4o",
        provider_id="openai",
        catalog={"openai": ["gpt-4o"], "deepseek": ["deepseek-chat"]},
        fallback_routes=[("deepseek", "deepseek-chat")],
        script=[_partial("RANKED PARTIAL")],
        expected_calls=[("openai", "gpt-4o")],
        expected_text="RANKED PARTIAL", expect_error=False,
    ), id="ranked-visible-single"),

    # --- catalogue sweep -------------------------------------------------
    pytest.param(dict(
        id="sweep-zero-three", location="catalogue_sweep", content="zero",
        exhaustion="three", providers=["opencode-go"],
        model="model-z", provider_id="opencode-go",
        catalog={"opencode-go": ["model-a", "model-b", "model-z"]},
        script=[_generic_failure(), _generic_failure(),
                _generic_failure()],
        expected_calls=[
            ("opencode-go", "model-z"), ("opencode-go", "model-a"),
            ("opencode-go", "model-b")],
        expected_text=ERROR_TOKEN, expect_error=True,
    ), id="sweep-zero-three"),
    pytest.param(dict(
        id="sweep-reasoning-three", location="catalogue_sweep",
        content="reasoning", exhaustion="three",
        providers=["opencode-go"], model="model-z",
        provider_id="opencode-go",
        catalog={"opencode-go": ["model-a", "model-b", "model-z"]},
        script=[_generic_failure(), _reasoning_only(),
                _content("SWEEP ANSWER")],
        expected_calls=[
            ("opencode-go", "model-z"), ("opencode-go", "model-a"),
            ("opencode-go", "model-b")],
        expected_text="SWEEP ANSWER", expect_error=False,
    ), id="sweep-reasoning-three"),
    pytest.param(dict(
        id="sweep-visible-two", location="catalogue_sweep",
        content="partial", exhaustion="two",
        providers=["opencode-go"], model="model-z",
        provider_id="opencode-go",
        catalog={"opencode-go": ["model-a", "model-b", "model-z"]},
        script=[_generic_failure(), _partial("SWEEP PARTIAL")],
        expected_calls=[
            ("opencode-go", "model-z"), ("opencode-go", "model-a")],
        expected_text="SWEEP PARTIAL", expect_error=False,
    ), id="sweep-visible-two"),
]


@pytest.mark.parametrize("case", CASES)
def test_generated_stream_retry_state_matrix(
        case, handler, monkeypatch, tmp_path):
    calls = _install_case(handler, monkeypatch, tmp_path, case)
    if case.get("heal"):
        model = case["model"]
        monkeypatch.setattr(
            "core.llm.routing.request_healer.get_request_healer",
            lambda: SimpleNamespace(
                heal=lambda *a, **k: SimpleNamespace(
                    patched_kwargs={
                        "model": model,
                        "messages": [{"role": "user", "content": "hello"}],
                        "temperature": 0.7,
                        "max_tokens": 100,
                        "stream": True,
                    },
                    rule="test-repair",
                    patched_keys=["model"],
                )),
        )

    tokens = _run(
        handler,
        case["model"],
        case["provider_id"],
        fallback_routes=case.get("fallback_routes"),
    )
    text = "".join(tokens)

    assert calls == case["expected_calls"], (case["id"], calls)
    # Every automatic pair is reached at most once. Self-heal is the one
    # explicit same-pair repair and is expected to appear twice.
    if case["location"] == "self_heal":
        assert Counter(calls) == Counter(case["expected_calls"])
    else:
        assert max(Counter(calls).values()) == 1, (case["id"], calls)

    if case["expect_error"]:
        assert text == ERROR_TOKEN, (case["id"], text)
        assert all(
            success is not True
            for success in _feedback_successes(handler)
        ), (case["id"], _feedback_successes(handler))
    elif case["content"] == "partial":
        assert text == case["expected_text"], (case["id"], text)
        assert "All LLM providers failed" not in text
        # A transport-interrupted partial is a failure, never a synthetic
        # success for the model that produced it.
        assert all(
            success is not True
            for success in _feedback_successes(handler)
        ), (case["id"], _feedback_successes(handler))
    else:
        assert text == case["expected_text"], (case["id"], text)
        assert True in _feedback_successes(handler), (
            case["id"], _feedback_successes(handler))


def test_paid_retry_partial_never_dispatches_ranked_route(
        handler, monkeypatch, tmp_path):
    """Exact PR664 probe 1, kept as a named regression."""
    calls = _install_case(handler, monkeypatch, tmp_path, dict(
        providers=["opencode-go", "openai"],
        model="deepseek-v4-flash-free",
        provider_id="opencode-go",
        catalog={
            "opencode-go": ["deepseek-v4-flash-free", "deepseek-v4-flash"],
            "openai": ["gpt-4o"],
        },
        script=[_quota_failure(), _partial("PAID PARTIAL")],
    ))
    tokens = _run(
        handler, "deepseek-v4-flash-free", "opencode-go",
        fallback_routes=[("openai", "gpt-4o")],
        _allow_ladder_sweep=False,
    )
    text = "".join(tokens)
    assert text == "PAID PARTIAL", text
    assert calls == [
        ("opencode-go", "deepseek-v4-flash-free"),
        ("opencode-go", "deepseek-v4-flash"),
    ], calls


def test_sweep_budget_survives_ranked_fallback_recursion(
        handler, monkeypatch, tmp_path):
    """Exact PR664 probe 2, kept as a named regression."""
    calls = _install_case(handler, monkeypatch, tmp_path, dict(
        providers=["opencode-go"], model="model-z",
        provider_id="opencode-go",
        catalog={"opencode-go": ["model-a", "model-b", "model-z"]},
        script=[_generic_failure(), _generic_failure(),
                _generic_failure()],
    ))
    text = "".join(_run(handler, "model-z", "opencode-go"))
    assert "All LLM providers failed" in text
    assert calls == [
        ("opencode-go", "model-z"), ("opencode-go", "model-a"),
        ("opencode-go", "model-b")], calls
    assert max(Counter(calls).values()) == 1, calls


def test_unknown_catalogue_still_refuses_dispatch(
        handler, monkeypatch, tmp_path):
    """An undiscovered catalogue means no dispatch: production gate unchanged."""
    install_route_catalog(monkeypatch, tmp_path, {})
    calls = []
    client = _ScriptedClient(
        "openai", [_content("SHOULD NOT RUN")], calls)
    handler.clients = {"openai": client}
    handler.async_clients = {"openai": client}
    text = "".join(_run(handler, "gpt-4o", "openai"))
    assert calls == []
    assert text == ERROR_TOKEN


def test_local_only_still_refuses_cloud_route(handler, monkeypatch, tmp_path):
    """Local-only is a hard boundary, independent of the retry state."""
    install_route_catalog(monkeypatch, tmp_path, {"openai": ["gpt-4o"]})
    calls = []
    client = _ScriptedClient("openai", [_content("SHOULD NOT RUN")], calls)
    handler.clients = {"openai": client}
    handler.async_clients = {"openai": client}
    monkeypatch.setattr(
        "core.privsec.local_only_guard.get_local_only_guard",
        lambda: SimpleNamespace(is_local_only_enabled=lambda: True),
    )
    with pytest.raises(ValueError, match="No available providers"):
        _run(handler, "gpt-4o", "openai")
    assert calls == []
