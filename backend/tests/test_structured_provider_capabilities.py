"""Offline wire-boundary regressions for structured-provider capabilities.

The structured path has two documented transports: Instructor's forced
function-call scaffold (``tools`` + one synthetic tool + forced
``tool_choice``) and its schema-in-prompt JSON mode. Which one is legal is a
capability of ONE exact provider route, not something to discover by paying the
same HTTP 400 on every stage — and not something a model's brand name proves.

These tests use a REAL ``openai.OpenAI`` client over ``httpx.MockTransport``
and the real Instructor wrapper, so they assert the constructed outbound SDK
payload rather than a forwarded keyword. The twins implement the documented
behavior:

* OpenAI accepts forced/named tool choice; it has NO declaration, so the
  historical payload — including the legacy OpenRouter-style ``reasoning``
  object when reasoning is disabled — is unchanged;
* the two native DeepSeek ids the first-party endpoint reported as served
  enable thinking by default, reject forced/named tool choice while it is on,
  and accept ``reasoning_effort: "none"``; native docs list ``logprobs``;
* the exact OpenCode Go ``deepseek-v4-pro`` route captures the documented
  rejection + JSON-mode success; that is the ONLY attested transport there.
  The gateway's thinking-switch forwarding was never captured, so no
  ``reasoning_effort``/``thinking``/OpenRouter ``reasoning`` extension is
  invented for it, even when the caller disables reasoning; no other
  Go/DeepSeek model, and no other gateway OR endpoint under the same label,
  inherits it;
* an unknown, future or legacy route gets the historical payload and the
  existing typed-error recovery (one changed retry, then a pair memo — never
  an identical repeat).

Attestation is bound to the configured SDK base URL, not to the provider
label. The tests exercise that with real clients over ``MockTransport``:
official DeepSeek/Go base URLs take the declared payload; ``OPENCODE_BASE_URL``
overrides (Zen, custom host, loopback), missing endpoints, and hostname
look-alikes take the legacy payload and reactive recovery.

No live provider, model, key or network call is used.
"""
from __future__ import annotations

import asyncio
import json
import os

os.environ.setdefault("TESTING", "1")

import httpx
import openai
import pytest
from pydantic import BaseModel
from unittest.mock import MagicMock

from core.llm.byok_handler import AwaitableResult, BYOKHandler
from tests.test_oracle_mini_app_host_mutations import host  # noqa: F401
from tests.test_reasoning_mandatory_retry import _handler as _minimal_handler


class _WireProbe(BaseModel):
    value: str


#: Server-owned official base URLs used by the real SDK clients below. Tests
#: never add a localhost/test URL to the attested catalogue: overrides and
#: look-alikes must go through the same legacy path as production.
_NATIVE_ENDPOINT = "https://api.deepseek.com/v1"
_NATIVE_ENDPOINT_ALIAS = "https://api.deepseek.com"
_GO_ENDPOINT = "https://opencode.ai/inference/go/openai/v1"


def _completion_body(body: dict, content: dict, model: str) -> dict:
    """A valid OpenAI-compatible completion for whichever mode was sent."""
    if body.get("tools"):
        tool_name = (
            (body["tools"][0].get("function") or {}).get("name") or "response")
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_wire",
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(content),
                },
            }],
        }
        finish = "tool_calls"
    else:
        message = {"role": "assistant", "content": json.dumps(content)}
        finish = "stop"
    return {
        "id": "chatcmpl-wire", "object": "chat.completion", "created": 1,
        "model": model,
        "choices": [{
            "index": 0, "finish_reason": finish, "message": message,
        }],
        "usage": {
            "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
        },
    }


def _error(status: int, message: str) -> httpx.Response:
    return httpx.Response(status, json={
        "error": {
            "message": message,
            "type": "invalid_request_error",
            "code": "invalid_request_error",
        },
    })


def _client(responder, provider_id: str,
            base_url: str | None = None) -> openai.OpenAI:
    transport = httpx.MockTransport(responder)
    if base_url is None:
        base_url = _NATIVE_ENDPOINT if provider_id == "deepseek" else (
            _GO_ENDPOINT
            if provider_id == "opencode-go" else "http://localhost:11434/v1")
    return openai.OpenAI(
        base_url=base_url, api_key="offline-test",
        http_client=httpx.Client(transport=transport))


def _handler_for(provider_id: str, model: str, responder,
                 *, base_url: str | None = None) -> BYOKHandler:
    handler = _minimal_handler()
    handler.get_ranked_providers = MagicMock(
        return_value=AwaitableResult([(provider_id, model)]))
    handler.clients = {
        provider_id: _client(responder, provider_id, base_url=base_url)}
    handler.async_clients = {}
    # The wire tests double the accounting boundary; the durable ledger
    # contract has its own regression below with the full scratch handler.
    handler._admit_physical_attempt = MagicMock(return_value=0.0)
    handler._settle_physical_response = MagicMock(return_value=0.0)
    return handler


def _clear_pair_memos(provider_id: str, model: str) -> None:
    from core.llm import byok_handler as bh

    pair = f"{provider_id}/{model}"
    bh._REASONING_MANDATORY.discard(pair)
    bh._TOOLCHOICE_UNSUPPORTED.discard(pair)
    bh._THINKING_SWITCH_UNSUPPORTED.discard(pair)
    bh._AUTH_FAILED.discard(pair)
    bh._MODEL_TEMPERATURE.pop(pair, None)
    bh._STRUCTURED_PROTOCOL_UNSUPPORTED.discard(pair)
    bh._LOGPROBS_UNSUPPORTED.discard(pair)
    bh._PROVIDER_COOLDOWN_UNTIL.pop(provider_id, None)


def _call(handler, *, disable_reasoning: bool, messages=None):
    kwargs = {}
    if messages is not None:
        kwargs["messages"] = messages
    return asyncio.run(handler.generate_structured_response(
        prompt="Return the requested object.",
        system_instruction="You return only the requested JSON object.",
        response_model=_WireProbe,
        task_type="planning",
        temperature=0.0,
        disable_reasoning=disable_reasoning,
        allow_moa=False,
        max_tokens=1000,
        **kwargs,
    ))


# ---------------------------------------------------------------------------
# Exact-route declarations: what is sourced, and what is deliberately NOT
# ---------------------------------------------------------------------------
def test_contract_resolution_is_exact_and_sourced():
    from core.llm.wire_capabilities import (
        declared_routes,
        resolve_structured_wire_contract,
    )

    # The catalogue itself is pinned: three exact routes, no family expansion.
    declared = {
        (d.provider_id, d.model_id): d for d in declared_routes()}
    assert set(declared) == {
        ("deepseek", "deepseek-flash"),
        ("deepseek", "deepseek-v4-pro"),
        ("opencode-go", "deepseek-v4-pro"),
    }
    # Attestation is bound to the official endpoint, not only to the label.
    for model in ("deepseek-flash", "deepseek-v4-pro"):
        assert _NATIVE_ENDPOINT in declared[
            ("deepseek", model)].attested_endpoints
        assert _NATIVE_ENDPOINT_ALIAS in declared[
            ("deepseek", model)].attested_endpoints
    assert declared[("opencode-go", "deepseek-v4-pro")].attested_endpoints == (
        _GO_ENDPOINT,)

    # The exact Go route with served evidence (2026-10-18), on the Go endpoint.
    gateway = resolve_structured_wire_contract(
        "opencode-go", "deepseek-v4-pro", configured_endpoint=_GO_ENDPOINT)
    assert gateway is not None
    assert gateway.protocol == "json"
    assert gateway.supports_logprobs is False
    assert gateway.observed_on == "2026-10-18"
    # The gateway's forwarding/rejection of the native switch was never
    # captured, so the declaration carries no switch at all.
    assert gateway.thinking_disable_extra is None
    assert gateway.thinking_disable_key is None

    # The two native identifiers the first-party endpoint reported as served.
    for model in ("deepseek-flash", "deepseek-v4-pro"):
        native = resolve_structured_wire_contract(
            "deepseek", model, configured_endpoint=_NATIVE_ENDPOINT)
        assert native is not None, model
        assert native.protocol == "tools", model
        assert native.requires_thinking_disabled is True, model
        # Native DeepSeek's current docs list logprobs; only the Go route has
        # a conservative skip. No family-wide claim is made.
        assert native.supports_logprobs is True, model
        assert native.observed_on == "2026-09-16", model

    # Identifier normalization is case/whitespace only.
    assert resolve_structured_wire_contract(
        " OpenCode-Go ", " DeepSeek-V4-Pro ",
        configured_endpoint=_GO_ENDPOINT).protocol == "json"

    # An UNVERIFIED future id on a declared gateway inherits NOTHING from the
    # brand token.
    assert resolve_structured_wire_contract(
        "opencode-go", "deepseek-unannounced-synthetic-v999",
        configured_endpoint=_GO_ENDPOINT) is None
    # Nor does a legacy/native distill id inherit the native v4 cohort.
    assert resolve_structured_wire_contract(
        "deepseek", "deepseek-r1-distill-synthetic",
        configured_endpoint=_NATIVE_ENDPOINT) is None
    # Nor does the Go Flash route inherit the v4-pro declaration.
    assert resolve_structured_wire_contract(
        "opencode-go", "deepseek-v4.1-flash",
        configured_endpoint=_GO_ENDPOINT) is None
    # A date/snapshot tail is NOT stripped into the declared id.
    assert resolve_structured_wire_contract(
        "opencode-go", "deepseek-v4-pro-20261018",
        configured_endpoint=_GO_ENDPOINT) is None
    # A vendor-path tail is NOT matched against a first-party id.
    assert resolve_structured_wire_contract(
        "deepseek", "deepseek/deepseek-v4-pro",
        configured_endpoint=_NATIVE_ENDPOINT) is None
    # Go evidence is never transplanted to another gateway/provider.
    assert resolve_structured_wire_contract(
        "opencode", "deepseek/deepseek-v4-pro",
        configured_endpoint="https://opencode.ai/zen/v1") is None
    assert resolve_structured_wire_contract(
        "zen", "deepseek-v4-pro",
        configured_endpoint="https://opencode.ai/zen/v1") is None
    assert resolve_structured_wire_contract(
        "openrouter", "deepseek/deepseek-v4-pro",
        configured_endpoint="https://openrouter.ai/api/v1") is None
    assert resolve_structured_wire_contract(
        "mystery-provider", "mystery-model",
        configured_endpoint="https://example.test/v1") is None
    assert resolve_structured_wire_contract(
        "deepseek", "", configured_endpoint=_NATIVE_ENDPOINT) is None


def test_contract_requires_the_actual_configured_wire_endpoint():
    """A provider/model label is not an endpoint, and no field can claim one."""
    from core.llm.wire_capabilities import resolve_structured_wire_contract

    def _resolve(provider, model, endpoint):
        return resolve_structured_wire_contract(
            provider, model, configured_endpoint=endpoint)

    # Positive controls: documented official paths (incl. the /v1 alias and a
    # trailing slash / explicit 443) are the attested endpoint.
    for model in ("deepseek-flash", "deepseek-v4-pro"):
        for endpoint in (
                _NATIVE_ENDPOINT,
                _NATIVE_ENDPOINT_ALIAS,
                _NATIVE_ENDPOINT + "/",
                "https://api.deepseek.com:443/v1"):
            assert _resolve("deepseek", model, endpoint) is not None, (
                model, endpoint)
    assert _resolve(
        "opencode-go", "deepseek-v4-pro", _GO_ENDPOINT) is not None

    # Missing/blank/unparseable endpoint: legacy behavior, never an inference.
    for missing in (None, "", "   ", "not-a-url", "api.deepseek.com/v1"):
        assert _resolve("deepseek", "deepseek-v4-pro", missing) is None, missing
        assert _resolve(
            "opencode-go", "deepseek-v4-pro", missing) is None, missing

    # A label repointed by OPENCODE_BASE_URL at Zen, a custom host or loopback
    # did not serve the attested route.
    for overridden in (
            "https://opencode.ai/zen/v1",
            "https://opencode.ai/zen/go/v1",
            "https://custom-gateway.example/v1",
            "http://127.0.0.1:11434/v1",
            "http://localhost:8080/v1",
    ):
        assert _resolve(
            "opencode-go", "deepseek-v4-pro", overridden) is None, overridden
    # Neither did a native DeepSeek label repointed at another host/path.
    for overridden in (
            "https://api.deepseek.com/v2",
            "http://api.deepseek.com/v1",
            "https://deepseek.example/v1",
    ):
        assert _resolve(
            "deepseek", "deepseek-v4-pro", overridden) is None, overridden

    # Hostname look-alikes, userinfo, queries, fragments and path suffixes are
    # NOT the official endpoint.
    for lookalike in (
            "https://api.deepseek.com.evil.test/v1",
            "https://api.deepseek.com@evil.test/v1",
            "https://api.deepseek.com/v1/evil",
            "https://api.deepseek.com/v1?x=1",
            "https://api.deepseek.com/v1#fragment",
            "https://opencode.ai.evil.test/inference/go/openai/v1",
            "https://opencode.ai@evil.test/inference/go/openai/v1",
            "https://opencode.ai/inference/go/openai/v2",
    ):
        assert _resolve(
            "deepseek", "deepseek-v4-pro", lookalike) is None, lookalike
        assert _resolve(
            "opencode-go", "deepseek-v4-pro", lookalike) is None, lookalike

    # Go Flash stays unknown even on the official Go endpoint.
    assert _resolve(
        "opencode-go", "deepseek-v4.1-flash", _GO_ENDPOINT) is None


def _deepseek_twin(
    request: httpx.Request,
    model: str,
    *,
    expect_protocol: str,
) -> httpx.Response:
    """Documented DeepSeek behavior for an OpenAI-compatible chat request.

    - unknown extension fields are rejected (the OpenRouter ``reasoning``
      object is not part of DeepSeek's schema);
    - thinking is on unless ``reasoning_effort`` is ``none``;
    - forced/named tool_choice is rejected while thinking is on;
    - JSON output uses ``response_format={"type": "json_object"}``.
    """
    body = json.loads(request.content)
    if "reasoning" in body:
        return _error(
            400, "Unrecognized request argument supplied: reasoning")
    if expect_protocol == "tools":
        if not body.get("tools"):
            return _error(400, "tools are required for this route")
        if body.get("tool_choice") in (None, "auto", "none"):
            return _error(400, "a forced tool_choice is required")
        if body.get("reasoning_effort") != "none":
            return _error(
                400, "Thinking mode does not support this tool_choice")
    else:
        if body.get("tools"):
            return _error(
                400, "Thinking mode does not support this tool_choice")
        if body.get("response_format") != {"type": "json_object"}:
            return _error(400, "response_format json_object is required")
    return httpx.Response(200, json=_completion_body(
        body, {"value": model + "-ok"}, model))


def test_openai_twin_keeps_forced_tool_choice_unchanged():
    provider, model = "openai", "gpt-4o"
    _clear_pair_memos(provider, model)
    seen: list[dict] = []

    def _responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        assert body.get("tools"), body
        assert body.get("tool_choice") not in (None, "auto", "none"), body
        # No DeepSeek-only thinking control is invented for an OpenAI route.
        assert "reasoning_effort" not in body, body
        assert "thinking" not in body, body
        return httpx.Response(200, json=_completion_body(
            body, {"value": "openai-ok"}, model))

    handler = _handler_for(provider, model, _responder)
    # OpenAI is the undeclared-route control: historical behavior stays.
    result = _call(handler, disable_reasoning=False)
    assert isinstance(result, _WireProbe), result
    assert result.value == "openai-ok"
    assert len(seen) == 1, seen


def test_openai_legacy_reasoning_object_is_unchanged_when_disabled():
    """The resolver returning None does NOT suppress the legacy extension.

    The pre-existing OpenRouter-style ``reasoning`` object is still sent to an
    undeclared route (OpenAI included) when the caller disables reasoning.
    Only declared routes switch to a vendor-documented control.
    """
    provider, model = "openai", "gpt-4o"
    _clear_pair_memos(provider, model)
    seen: list[dict] = []

    def _responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        assert body.get("tools"), body
        assert body.get("reasoning") == {
            "enabled": False, "exclude": True}, body
        assert "reasoning_effort" not in body, body
        return httpx.Response(200, json=_completion_body(
            body, {"value": "openai-legacy-ok"}, model))

    handler = _handler_for(provider, model, _responder)
    result = _call(handler, disable_reasoning=True)
    assert isinstance(result, _WireProbe), result
    assert result.value == "openai-legacy-ok"
    assert len(seen) == 1, seen


@pytest.mark.parametrize("model", ["deepseek-flash", "deepseek-v4-pro"])
def test_native_deepseek_twin_disables_thinking_for_forced_tool_choice(
        monkeypatch, model):
    monkeypatch.setenv("ATOM_SC_SOFT", "true")
    provider = "deepseek"
    _clear_pair_memos(provider, model)
    seen: list[dict] = []

    def _responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        return _deepseek_twin(request, model, expect_protocol="tools")

    handler = _handler_for(provider, model, _responder)
    # The switch is protocol-required, not caller-requested.
    result = _call(handler, disable_reasoning=False)
    assert isinstance(result, _WireProbe), result
    assert result.value == model + "-ok"
    assert len(seen) == 1, seen
    assert seen[0].get("reasoning_effort") == "none", seen[0]
    assert seen[0].get("tool_choice") not in (None, "auto", "none"), seen[0]
    assert "reasoning" not in seen[0], seen[0]
    # Current native DeepSeek documents logprobs; the optional weighting is
    # retained there.
    assert seen[0].get("logprobs") is True, seen[0]


def test_unverified_legacy_model_keeps_the_legacy_wire(monkeypatch):
    """A legacy distill id must not inherit a current DeepSeek declaration."""
    monkeypatch.setenv("ATOM_SC_SOFT", "true")
    provider, model = "openrouter", "deepseek/deepseek-r1-distill-synthetic"
    _clear_pair_memos(provider, model)
    seen: list[dict] = []

    def _responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if "reasoning" in body:
            # Legacy route: first attempt is the historical OpenRouter
            # reasoning extension, and the existing recovery drops it once.
            return _error(
                400, "Unrecognized request argument supplied: reasoning")
        assert "reasoning_effort" not in body, body
        assert body.get("tools"), body
        return httpx.Response(200, json=_completion_body(
            body, {"value": "legacy-native-ok"}, model))

    handler = _handler_for(provider, model, _responder)
    result = _call(handler, disable_reasoning=True)
    assert isinstance(result, _WireProbe), result
    assert result.value == "legacy-native-ok"
    assert len(seen) == 2, seen
    assert seen[0].get("reasoning") == {
        "enabled": False, "exclude": True}, seen[0]
    assert "reasoning_effort" not in seen[0], seen[0]
    assert "reasoning" not in seen[1], seen[1]
    from core.llm import byok_handler as bh
    assert f"{provider}/{model}" in bh._REASONING_MANDATORY


def test_opencode_go_deepseek_twin_is_json_only_without_any_reasoning_extension(
        monkeypatch):
    """The Go attestation is JSON mode only — no switch was ever proven."""
    monkeypatch.setenv("ATOM_SC_SOFT", "true")
    provider, model = "opencode-go", "deepseek-v4-pro"
    _clear_pair_memos(provider, model)
    messages = [
        {"role": "system", "content": "You return only JSON."},
        {"role": "user", "content": "first user turn"},
        {"role": "assistant", "content": "prior assistant answer"},
        {"role": "user", "content": "second user turn"},
    ]
    seen: list[dict] = []

    def _responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if "logprobs" in body:
            return _error(
                400, '"logprobs" is not supported by this endpoint')
        # The exact Go v4-pro route rejected forced tool_choice in thinking
        # mode live; JSON output is documented upstream and has working live
        # evidence on this exact route.
        return _deepseek_twin(request, model, expect_protocol="json")

    handler = _handler_for(provider, model, _responder)
    result = _call(handler, disable_reasoning=True, messages=messages)
    assert isinstance(result, _WireProbe), result
    assert result.value == model + "-ok"
    assert len(seen) == 1, seen
    body = seen[0]
    assert "tools" not in body, body
    assert body.get("response_format") == {"type": "json_object"}, body
    # disable_reasoning=True must NOT transplant the native DeepSeek switch,
    # the vendor object form, or the legacy OpenRouter extension onto the
    # gateway: none of them is attested there.
    for invented in ("reasoning_effort", "thinking", "reasoning"):
        assert invented not in body, body
    # Conservative optional-logprobs policy for this exact route.
    assert "logprobs" not in body, body
    # Full ordered message history reaches the actual JSON request, and the
    # parsed reply is schema-validated by Instructor.
    wire_messages = body.get("messages") or []
    roles = [m.get("role") for m in wire_messages if isinstance(m, dict)]
    assert roles == ["system", "user", "assistant", "user"], roles
    contents = "\n".join(
        str(m.get("content") or "") for m in wire_messages
        if isinstance(m, dict))
    for expected in (
            "first user turn", "prior assistant answer", "second user turn"):
        assert expected in contents, contents


# ---------------------------------------------------------------------------
# Full caller message history survives the protocol correction
# ---------------------------------------------------------------------------
def test_gateway_json_mode_preserves_complete_message_history(monkeypatch):
    monkeypatch.setenv("ATOM_SC_SOFT", "true")
    provider, model = "opencode-go", "deepseek-v4-pro"
    _clear_pair_memos(provider, model)
    messages = [
        {"role": "system", "content": "You return only JSON."},
        {"role": "user", "content": "first user turn"},
        {"role": "assistant", "content": "prior assistant answer"},
        {"role": "user", "content": "second user turn"},
    ]
    seen: list[dict] = []

    def _responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        return _deepseek_twin(request, model, expect_protocol="json")

    handler = _handler_for(provider, model, _responder)
    result = _call(handler, disable_reasoning=True, messages=messages)
    assert isinstance(result, _WireProbe), result
    assert len(seen) == 1, seen
    wire_messages = seen[0].get("messages") or []
    roles = [m.get("role") for m in wire_messages if isinstance(m, dict)]
    assert roles == ["system", "user", "assistant", "user"], roles
    contents = "\n".join(
        str(m.get("content") or "") for m in wire_messages
        if isinstance(m, dict))
    for expected in (
            "first user turn", "prior assistant answer", "second user turn"):
        assert expected in contents, contents


# ---------------------------------------------------------------------------
# A declared documented switch can still be rejected: one changed retry, memo
# ---------------------------------------------------------------------------
def test_native_documented_switch_rejection_is_dropped_once_and_memoized(
        monkeypatch):
    """A valid documented field may still be unknown to an implementation.

    The native declaration carries the sourced ``reasoning_effort="none"``
    switch; a native-compatible endpoint that rejects the field must get ONE
    changed retry (JSON, switch dropped) and the pair memo, never an identical
    repeat. This is the reactive-recovery path that used to be exercised
    through the unproven Go switch.
    """
    monkeypatch.setenv("ATOM_SC_SOFT", "true")
    provider, model = "deepseek", "deepseek-v4-pro"
    _clear_pair_memos(provider, model)
    messages = [
        {"role": "system", "content": "You return only JSON."},
        {"role": "user", "content": "first user turn"},
        {"role": "assistant", "content": "prior assistant answer"},
        {"role": "user", "content": "second user turn"},
    ]
    bodies: list[dict] = []

    def _responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if body.get("reasoning_effort") is not None:
            return _error(
                400, "Unrecognized request argument supplied: reasoning_effort")
        assert "tools" not in body, body
        assert body.get("response_format") == {"type": "json_object"}, body
        return httpx.Response(200, json=_completion_body(
            body, {"value": "native-switch-retry-ok"}, model))

    handler = _handler_for(provider, model, _responder)
    result = _call(handler, disable_reasoning=True, messages=messages)
    assert isinstance(result, _WireProbe), result
    assert result.value == "native-switch-retry-ok"
    assert len(bodies) == 2, bodies
    assert bodies[0].get("tools"), bodies[0]
    assert bodies[0].get("tool_choice") not in (None, "auto", "none"), bodies[0]
    assert bodies[0].get("reasoning_effort") == "none", bodies[0]
    assert bodies[0].get("logprobs") is True, bodies[0]
    # The retry is a DIFFERENT supported payload (JSON, switch dropped), not
    # an identical repeat. Native logprobs remains documented.
    assert "reasoning_effort" not in bodies[1], bodies[1]
    assert bodies[1].get("response_format") == {"type": "json_object"}, bodies[1]
    assert bodies[1].get("logprobs") is True, bodies[1]
    from core.llm import byok_handler as bh
    assert f"{provider}/{model}" in bh._THINKING_SWITCH_UNSUPPORTED
    # Full ordered history survives both the first request and the recovery.
    for body in bodies:
        wire_messages = body.get("messages") or []
        roles = [m.get("role") for m in wire_messages
                 if isinstance(m, dict)]
        assert roles == ["system", "user", "assistant", "user"], roles

    # The memo prevents paying the same deterministic 400 again, and the
    # handler starts in the supported JSON protocol without the switch.
    result2 = _call(handler, disable_reasoning=True, messages=messages)
    assert isinstance(result2, _WireProbe), result2
    assert len(bodies) == 3, bodies
    assert "reasoning_effort" not in bodies[2], bodies[2]
    assert "tools" not in bodies[2], bodies[2]
    assert bodies[2].get("response_format") == {"type": "json_object"}, bodies[2]
    _clear_pair_memos(provider, model)


# ---------------------------------------------------------------------------
# Unverified future model on the Go gateway: nothing is inherited
# ---------------------------------------------------------------------------
def test_unverified_future_model_on_go_gateway_keeps_legacy_payload(monkeypatch):
    monkeypatch.setenv("ATOM_SC_SOFT", "true")
    provider, model = "opencode-go", "deepseek-unannounced-synthetic-v999"
    _clear_pair_memos(provider, model)
    messages = [
        {"role": "system", "content": "You return only JSON."},
        {"role": "user", "content": "first user turn"},
        {"role": "assistant", "content": "prior assistant answer"},
        {"role": "user", "content": "second user turn"},
    ]
    seen: list[dict] = []

    def _responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        # The unknown model's endpoint has no declaration. It gets the
        # historical tools + OpenRouter reasoning payload; the legacy
        # reasoning-mandatory recovery drops that field once. Nothing selects
        # JSON mode or a vendor thinking switch speculatively.
        if "reasoning" in body:
            return _error(
                400, "Unrecognized request argument supplied: reasoning")
        assert body.get("tools"), body
        assert "reasoning_effort" not in body, body
        return httpx.Response(200, json=_completion_body(
            body, {"value": "future-model-ok"}, model))

    handler = _handler_for(provider, model, _responder)
    result = _call(handler, disable_reasoning=True, messages=messages)
    assert isinstance(result, _WireProbe), result
    assert result.value == "future-model-ok"
    assert len(seen) == 2, seen
    assert seen[0].get("reasoning") == {
        "enabled": False, "exclude": True}, seen[0]
    assert "reasoning_effort" not in seen[0], seen[0]
    assert "response_format" not in seen[0], seen[0]
    assert "reasoning" not in seen[1], seen[1]
    # Full ordered history survives the recovery on BOTH attempts.
    for body in seen:
        wire_messages = body.get("messages") or []
        roles = [m.get("role") for m in wire_messages
                 if isinstance(m, dict)]
        assert roles == ["system", "user", "assistant", "user"], roles


# ---------------------------------------------------------------------------
# Unverified gateway: Go evidence is not transplanted
# ---------------------------------------------------------------------------
def test_unverified_gateway_does_not_inherit_go_route(monkeypatch):
    monkeypatch.setenv("ATOM_SC_SOFT", "true")
    provider, model = "opencode", "deepseek-v4-pro"
    _clear_pair_memos(provider, model)
    seen: list[dict] = []

    def _responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if body.get("tools") and body.get("tool_choice") not in (
                None, "auto", "none"):
            return _error(
                400, "Thinking mode does not support this tool_choice")
        return httpx.Response(200, json=_completion_body(
            body, {"value": "unverified-gateway-ok"}, model))

    handler = _handler_for(provider, model, _responder)
    result = _call(handler, disable_reasoning=True)
    assert isinstance(result, _WireProbe), result
    assert result.value == "unverified-gateway-ok"
    assert len(seen) == 2, seen
    # No JSON declaration and no vendor thinking switch: the historical
    # payload is used, then the pre-existing tool_choice recovery.
    assert seen[0].get("tools"), seen[0]
    assert seen[0].get("reasoning") == {
        "enabled": False, "exclude": True}, seen[0]
    assert "reasoning_effort" not in seen[0], seen[0]
    assert "tools" not in seen[1], seen[1]
    from core.llm import byok_handler as bh
    assert f"{provider}/{model}" in bh._TOOLCHOICE_UNSUPPORTED
    _clear_pair_memos(provider, model)


# ---------------------------------------------------------------------------
# Endpoint binding: a declared LABEL on a different endpoint is legacy
# ---------------------------------------------------------------------------
class _LegacyEndpointTwin:
    """Endpoint that only knows the historical payload + reactive recovery.

    It actively rejects the declared extensions (``reasoning_effort`` for a
    native declaration and JSON mode chosen from the start), so a body that
    arrives with them proves an attestation leaked across endpoints.
    """

    def __init__(self, model: str):
        self.model = model
        self.bodies: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.bodies.append(body)
        if body.get("reasoning_effort") is not None:
            return _error(
                400, "Unrecognized request argument supplied: reasoning_effort")
        if "reasoning" in body:
            return _error(
                400, "Unrecognized request argument supplied: reasoning")
        if body.get("tools") and body.get("tool_choice") not in (
                None, "auto", "none"):
            return _error(
                400, "Thinking mode does not support this tool_choice")
        if body.get("tools"):
            return _error(400, "tools are not accepted on this endpoint")
        if body.get("response_format") == {"type": "json_object"}:
            return httpx.Response(200, json=_completion_body(
                body, {"value": "legacy-endpoint-ok"}, self.model))
        return _error(400, "unexpected request shape")


@pytest.mark.parametrize("overridden", [
    "https://opencode.ai/zen/v1",
    "https://opencode.ai/zen/go/v1",
    "https://custom-gateway.example/v1",
    "http://127.0.0.1:11434/v1",
    "http://localhost:8080/v1",
])
def test_overridden_go_label_does_not_inherit_go_contract(
        monkeypatch, overridden):
    """OPENCODE_BASE_URL can repoint the label; the endpoint did not serve it."""
    monkeypatch.setenv("ATOM_SC_SOFT", "true")
    provider, model = "opencode-go", "deepseek-v4-pro"
    _clear_pair_memos(provider, model)
    twin = _LegacyEndpointTwin(model)
    handler = _handler_for(provider, model, twin, base_url=overridden)

    result = _call(handler, disable_reasoning=True)
    assert isinstance(result, _WireProbe), result
    assert result.value == "legacy-endpoint-ok"
    # Historical payload first: tools + the legacy reasoning object + the
    # historical soft-SC logprobs field. NOT JSON mode, NOT reasoning_effort.
    assert len(twin.bodies) == 3, twin.bodies
    assert twin.bodies[0].get("tools"), twin.bodies[0]
    assert twin.bodies[0].get("reasoning") == {
        "enabled": False, "exclude": True}, twin.bodies[0]
    assert "reasoning_effort" not in twin.bodies[0], twin.bodies[0]
    assert twin.bodies[0].get("logprobs") is True, twin.bodies[0]
    # Then the two pre-existing reactive corrections, each a DIFFERENT payload:
    # drop the rejected reasoning object, then switch to JSON after the
    # thinking-mode tool_choice rejection. This is legacy recovery, not the
    # declared Go JSON contract from the start.
    assert "reasoning" not in twin.bodies[1], twin.bodies[1]
    assert twin.bodies[1].get("tools"), twin.bodies[1]
    assert "tools" not in twin.bodies[2], twin.bodies[2]
    assert twin.bodies[2].get("response_format") == {
        "type": "json_object"}, twin.bodies[2]
    from core.llm import byok_handler as bh
    assert f"{provider}/{model}" in bh._REASONING_MANDATORY
    assert f"{provider}/{model}" in bh._TOOLCHOICE_UNSUPPORTED
    # The unsupported-thinking-switch memo does not exist for this pair (the
    # declared switch was never sent), so it cannot affect this endpoint.
    assert f"{provider}/{model}" not in bh._THINKING_SWITCH_UNSUPPORTED
    _clear_pair_memos(provider, model)


@pytest.mark.parametrize("lookalike", [
    "https://api.deepseek.com.evil.test/v1",
])
def test_hostname_lookalike_native_endpoint_keeps_legacy_wire(
        monkeypatch, lookalike):
    """An exact host match is required; a look-alike is an unknown endpoint."""
    monkeypatch.delenv("ATOM_SC_SOFT", raising=False)
    provider, model = "deepseek", "deepseek-v4-pro"
    _clear_pair_memos(provider, model)
    twin = _LegacyEndpointTwin(model)
    handler = _handler_for(provider, model, twin, base_url=lookalike)

    result = _call(handler, disable_reasoning=False)
    assert isinstance(result, _WireProbe), result
    assert result.value == "legacy-endpoint-ok"
    # Legacy first attempt: forced tool choice, WITHOUT the native
    # reasoning_effort switch. The existing tool_choice recovery then moves to
    # JSON. A declared native contract would have put reasoning_effort on the
    # first body; the twin rejects it, so this asserts no leak.
    assert len(twin.bodies) == 2, twin.bodies
    assert twin.bodies[0].get("tools"), twin.bodies[0]
    assert "reasoning_effort" not in twin.bodies[0], twin.bodies[0]
    assert "response_format" not in twin.bodies[0], twin.bodies[0]
    assert "tools" not in twin.bodies[1], twin.bodies[1]
    assert twin.bodies[1].get("response_format") == {
        "type": "json_object"}, twin.bodies[1]
    from core.llm import byok_handler as bh
    assert f"{provider}/{model}" in bh._TOOLCHOICE_UNSUPPORTED
    assert f"{provider}/{model}" not in bh._THINKING_SWITCH_UNSUPPORTED
    _clear_pair_memos(provider, model)


def test_existing_thinking_switch_memo_cannot_affect_undeclared_endpoint(
        monkeypatch):
    """The process memo is scoped to the declared endpoint, never to a label.

    A previous official-native call can leave
    ``_THINKING_SWITCH_UNSUPPORTED`` for ``deepseek/deepseek-v4-pro``. A later
    client whose base URL is a hostname look-alike has NO contract (endpoint
    mismatch), so the memo must not force JSON mode before the first request.
    This is the route where the memo would matter: the native declaration has
    ``requires_thinking_disabled=True``.
    """
    monkeypatch.delenv("ATOM_SC_SOFT", raising=False)
    provider, model = "deepseek", "deepseek-v4-pro"
    _clear_pair_memos(provider, model)
    from core.llm import byok_handler as bh
    bh._THINKING_SWITCH_UNSUPPORTED.add(f"{provider}/{model}")
    twin = _LegacyEndpointTwin(model)
    handler = _handler_for(
        provider, model, twin,
        base_url="https://api.deepseek.com.evil.test/v1")

    result = _call(handler, disable_reasoning=False)
    assert isinstance(result, _WireProbe), result
    assert result.value == "legacy-endpoint-ok"
    # First body is the historical TOOLS payload, NOT the memo-selected JSON.
    assert len(twin.bodies) >= 1, twin.bodies
    assert twin.bodies[0].get("tools"), twin.bodies[0]
    assert "response_format" not in twin.bodies[0], twin.bodies[0]
    assert "reasoning_effort" not in twin.bodies[0], twin.bodies[0]
    # The existing tool_choice recovery still moves to JSON afterwards.
    assert "tools" not in twin.bodies[-1], twin.bodies[-1]
    assert twin.bodies[-1].get("response_format") == {
        "type": "json_object"}, twin.bodies[-1]
    _clear_pair_memos(provider, model)


# ---------------------------------------------------------------------------
# Unknown twin: historical behavior + one bounded typed-error recovery
# ---------------------------------------------------------------------------
class _UnknownTwin:
    """Unknown endpoint: rejects forced tool_choice in thinking mode."""

    def __init__(self, model: str):
        self.model = model
        self.bodies: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.bodies.append(body)
        if body.get("tools") and body.get("tool_choice") not in (
                None, "auto", "none"):
            return _error(
                400, "Thinking mode does not support this tool_choice")
        return httpx.Response(200, json=_completion_body(
            body, {"value": "unknown-ok"}, self.model))


def test_unknown_twin_legacy_shape_recovers_once_and_memoizes():
    provider, model = "mystery-provider", "mystery-model"
    _clear_pair_memos(provider, model)
    twin = _UnknownTwin(model)
    handler = _handler_for(provider, model, twin)

    result = _call(handler, disable_reasoning=True)
    assert isinstance(result, _WireProbe), result
    assert result.value == "unknown-ok"
    assert len(twin.bodies) == 2, twin.bodies
    # First attempt is the historical tools + OpenRouter reasoning payload.
    assert twin.bodies[0].get("tools")
    assert twin.bodies[0].get("reasoning") == {
        "enabled": False, "exclude": True}
    # The retry is a DIFFERENT supported payload (JSON mode), not an
    # identical repeat of the rejected request.
    assert "tools" not in twin.bodies[1]
    from core.llm import byok_handler as bh
    assert f"{provider}/{model}" in bh._TOOLCHOICE_UNSUPPORTED

    # The pair memo prevents the same deterministic 400 on the next call.
    result2 = _call(handler, disable_reasoning=True)
    assert isinstance(result2, _WireProbe), result2
    assert len(twin.bodies) == 3, twin.bodies
    assert "tools" not in twin.bodies[2]
    _clear_pair_memos(provider, model)


# ---------------------------------------------------------------------------
# Physical-attempt budget/settlement across Instructor's internal retry
# ---------------------------------------------------------------------------
def test_instructor_retry_admits_and_settles_each_physical_request(
        host, monkeypatch, tmp_path):
    from tests.test_goal9_physical_attempts import (
        _attempt_rows,
        _make_handler,
        _reservation_pricing,
        _seed,
    )

    provider, model = "opencode-go", "deepseek-v4-pro"
    _clear_pair_memos(provider, model)
    monkeypatch.setenv("ATOM_SC_SOFT", "true")
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    # Never let the construction-time pricing singleton reach the network in
    # an offline regression: the sync initializer refreshes provider catalogs.
    from core.llm import byok_handler as _bh
    monkeypatch.setattr(
        _bh, "get_pricing_fetcher_initialized_sync",
        lambda *a, **k: _bh.get_pricing_fetcher())
    handler = _make_handler(
        monkeypatch, tmp_path, {provider: [model]})
    bodies: list[dict] = []

    def _responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if len(bodies) == 1:
            # Valid JSON but schema-invalid: Instructor re-asks once.
            return httpx.Response(200, json=_completion_body(
                body, {"wrong": "missing value"}, model))
        return httpx.Response(200, json=_completion_body(
            body, {"value": "settled-ok"}, model))

    handler.clients[provider] = _client(_responder, provider)

    result = asyncio.run(handler.generate_structured_response(
        prompt="Return the requested object.",
        system_instruction="You return only the requested JSON object.",
        response_model=_WireProbe,
        task_type="planning",
        temperature=0.0,
        disable_reasoning=True,
        provider_model=(provider, model),
        allow_moa=False,
        max_tokens=1000,
    ))
    assert isinstance(result, _WireProbe), result
    assert result.value == "settled-ok"
    assert len(bodies) == 2, bodies
    for body in bodies:
        assert "tools" not in body, body
        assert body.get("response_format") == {"type": "json_object"}, body
        # The Go declaration is JSON-only: no native switch, vendor object
        # form, or OpenRouter extension is invented, even with
        # disable_reasoning=True.
        for invented in ("reasoning_effort", "thinking", "reasoning"):
            assert invented not in body, body
        # The optional soft-SC weighting field is skipped on this route.
        assert "logprobs" not in body, body

    rows = _attempt_rows(host)
    assert len(rows) == 2, [r.attempt_id for r in rows]
    assert len({r.attempt_id for r in rows}) == 2
    assert len({r.request_id for r in rows}) == 1
    for row in rows:
        # Each physical request was admitted before dispatch and settled
        # after its own response; the successful settlement clears the
        # reservation and records the actual cost.
        assert row.reservation_status == "settled", (
            row.attempt_id, row.reservation_status)
        assert row.billed is True, (row.attempt_id, row.billed)
        assert float(row.cost_usd or 0.0) > 0.0, (
            row.attempt_id, row.cost_usd)
    _clear_pair_memos(provider, model)
