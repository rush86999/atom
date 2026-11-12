"""Per-physical-attempt admission for the structured (instructor) path.

The structured cascade already re-entered its recovery loop with a fresh
attempt counter, but its reservation bound used only message text and it had
no multimodal policy. These controls pin the shared contract:

- a recoverable re-issue is a NEW physical attempt (own attempt id, same
  request binding, own reservation/settlement);
- an authoritative numeric-zero price keeps an image request free;
- a priced/unknown image request still refuses before dispatch under hard_stop;
- the request-level accounting refusal stops the cascade (no silent
  re-dispatch without a durable bound);
- a client that cannot be cloned/bound for per-physical admission refuses the
  dispatch before any admission (zero provider requests, no orphan
  reservation).
"""
from __future__ import annotations

import asyncio
import json
import socket
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

import pytest

from tests.test_goal9_physical_attempts import (
    _CloneableStructuredClient,
    _IMAGE_MESSAGES,
    _attempt_rows,
    _make_handler,
    _pricing,
    _reservation_pricing,
    _seed,
    host,
)
from core.chat_canvas_editor import CanvasEditPlan

pytest_plugins = ("tests.test_goal9_physical_attempts",)


def _plan():
    return CanvasEditPlan(wants_edit=True, updated_content_json='"ok"')


def _structured(handler, create, **kwargs):
    import core.llm.byok_handler as bh

    handler.clients["openai"] = _CloneableStructuredClient(create)

    def _fake_from_openai(client, **kw):
        return NS(chat=NS(completions=NS(
            create=client.chat.completions.create)))

    with patch.object(bh.instructor, "from_openai", _fake_from_openai):
        return asyncio.run(handler.generate_structured_response(
            prompt="update the valid-until date",
            system_instruction="You return only the requested JSON object.",
            response_model=CanvasEditPlan,
            task_type="planning",
            provider_model=("openai", "gpt-4o"),
            allow_moa=False,
            max_tokens=1000,
            **kwargs))


def _handler(monkeypatch, tmp_path):
    return _make_handler(
        monkeypatch, tmp_path, {"openai": ["gpt-4o"]})


def test_structured_recovery_retry_gets_own_attempt_and_settlement(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    handler = _handler(monkeypatch, tmp_path)
    create = MagicMock(side_effect=[
        RuntimeError("reasoning is mandatory for this model"),
        _plan(),
    ])
    result = _structured(handler, create, disable_reasoning=True)
    assert isinstance(result, CanvasEditPlan)
    assert create.call_count == 2
    rows = _attempt_rows(host)
    assert len(rows) == 2, [r.attempt_id for r in rows]
    assert len({r.attempt_id for r in rows}) == 2
    assert len({r.request_id for r in rows}) == 1
    # The failed first attempt keeps its reservation; the successful second
    # attempt settles once (unknown usage -> explicit unknown liability).
    assert sum(1 for r in rows if r.billed is True) == 1


def test_structured_zero_price_image_stays_free(
        host, monkeypatch, tmp_path):
    _seed(host, spend=90.0)
    _pricing(monkeypatch, lambda *a, **k: 0.0)
    handler = _handler(monkeypatch, tmp_path)
    create = MagicMock(return_value=_plan())
    result = _structured(handler, create, messages=_IMAGE_MESSAGES)
    assert isinstance(result, CanvasEditPlan)
    assert create.call_count == 1
    rows = _attempt_rows(host)
    assert len(rows) == 1
    assert rows[0].pricing_status == "free"
    assert rows[0].reservation_status == "settled"
    assert float(rows[0].reserved_cost_usd or 0.0) == 0.0


def test_structured_paid_image_refuses_before_dispatch(
        host, monkeypatch, tmp_path):
    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=7.0, actual=7.0)
    handler = _handler(monkeypatch, tmp_path)
    create = MagicMock(return_value=_plan())
    result = _structured(handler, create, messages=_IMAGE_MESSAGES)
    assert result is None
    assert create.call_count == 0
    assert _attempt_rows(host) == []


@pytest.fixture()
def denied_os_network(monkeypatch):
    """Make any real socket use a test failure, not a silent live fetch."""
    def _deny(*args, **kwargs):
        raise AssertionError(
            "OS network is denied for this control; use an in-process "
            "transport")

    monkeypatch.setattr(socket.socket, "connect", _deny, raising=False)
    monkeypatch.setattr(socket.socket, "connect_ex", _deny, raising=False)
    monkeypatch.setattr(socket, "create_connection", _deny)
    monkeypatch.setattr(socket, "getaddrinfo", _deny)
    monkeypatch.setattr(socket, "gethostbyname", _deny)


def test_unprofiled_structured_instructor_retry_admits_each_physical_call(
        host, monkeypatch, tmp_path, denied_os_network):
    """No capability profile -> Instructor keeps its default internal retry.

    The outer provider cascade and the request-recovery loop are unchanged:
    an unprofiled call still lets Instructor re-issue after a schema failure.
    What changed is the accounting boundary: the call-scoped admission covers
    the FIRST wire request only, and every Instructor-issued re-issue is its
    OWN physical attempt (own reservation/settlement under the same request
    binding). Two provider HTTP calls must therefore never share one
    reservation. This control uses the REAL Instructor + an in-process fake
    transport, not a mocked ``from_openai`` wrapper.
    """
    import httpx
    import openai

    from core.llm.capability_profiles import resolve_capability_profile

    assert resolve_capability_profile(None, "planning") is None

    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    handler = _handler(monkeypatch, tmp_path)

    async def _forced_rank(*args, **kwargs):
        # Ranking is not the subject here; keep it offline and deterministic.
        return [("openai", "gpt-4o")]

    async def _forced_optimal(*args, **kwargs):
        return ("openai", "gpt-4o")

    monkeypatch.setattr(handler, "get_ranked_providers", _forced_rank)
    monkeypatch.setattr(handler, "get_optimal_provider", _forced_optimal)

    physical_requests = []

    def _transport(request):
        physical_requests.append(request)
        # First call is schema-invalid, so Instructor re-issues internally.
        arguments = (
            {"wants_edit": "not-a-bool"}
            if len(physical_requests) == 1
            else {"wants_edit": True,
                  "updated_content_json": '"ok"'}
        )
        return httpx.Response(200, json={
            "id": f"chatcmpl-control-{len(physical_requests)}",
            "object": "chat.completion",
            "created": 1,
            "model": "gpt-4o",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_control",
                        "type": "function",
                        "function": {
                            "name": "CanvasEditPlan",
                            "arguments": json.dumps(arguments),
                        },
                    }],
                },
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        })

    scratch_client = openai.OpenAI(
        base_url="http://127.0.0.1:1/v1",
        api_key="scratch-no-credential",
        http_client=httpx.Client(transport=httpx.MockTransport(_transport)),
        # Match the handler's real clients: no hidden SDK retries. Any second
        # call observed below therefore belongs to Instructor itself.
        max_retries=0,
    )
    handler.clients["openai"] = scratch_client

    result = asyncio.run(handler.generate_structured_response(
        prompt="update the valid-until date",
        system_instruction="You return only the requested JSON object.",
        response_model=CanvasEditPlan,
        task_type="planning",
        provider_model=("openai", "gpt-4o"),
        allow_moa=False,
        max_tokens=1000))

    assert isinstance(result, CanvasEditPlan) and result.wants_edit is True
    assert len(physical_requests) == 2, (
        "unprofiled Instructor must keep its default internal retry: "
        f"{len(physical_requests)} physical calls")
    rows = _attempt_rows(host)
    assert len(rows) == 2, (
        "each physical Instructor call must have its own admission; got "
        f"{[(r.attempt_id, r.reservation_status) for r in rows]}")
    request_ids = {r.request_id for r in rows}
    assert len(request_ids) == 1, "both calls belong to the same job"
    request_id = request_ids.pop()
    assert {r.attempt_id for r in rows} == {
        f"{request_id}:1", f"{request_id}:2"}, (
        "the retry is a NEW physical attempt, not a reuse of attempt 1")
    assert all(r.reservation_status == "settled" for r in rows)
    assert all(r.billed is True for r in rows)
    assert [r.cost_usd for r in rows] == [
        pytest.approx(0.25), pytest.approx(0.25)]
    assert float(sum(r.cost_usd for r in rows)) == pytest.approx(0.5), (
        "both wire calls are charged; one settlement must not hide the other")


def test_structured_instructor_retry_refuses_before_second_wire_call(
        host, monkeypatch, tmp_path, denied_os_network):
    """A schema re-issue needs its OWN admission, not the first call's bound.

    The first physical call fits the hard_stop budget; its settlement then
    leaves no room for a second reservation. Instructor's internal re-issue
    must therefore be refused BEFORE the second wire request — the failure
    mode this control guards is a second dispatch hiding under the first
    reservation.
    """
    import httpx
    import openai

    _seed(host, spend=99.5)
    _reservation_pricing(monkeypatch, bound_at=0.4, actual=0.4)
    handler = _handler(monkeypatch, tmp_path)

    async def _forced_rank(*args, **kwargs):
        return [("openai", "gpt-4o")]

    async def _forced_optimal(*args, **kwargs):
        return ("openai", "gpt-4o")

    monkeypatch.setattr(handler, "get_ranked_providers", _forced_rank)
    monkeypatch.setattr(handler, "get_optimal_provider", _forced_optimal)

    physical_requests = []

    def _transport(request):
        physical_requests.append(request)
        # Always schema-invalid, so Instructor always wants to re-issue.
        return httpx.Response(200, json={
            "id": f"chatcmpl-refuse-{len(physical_requests)}",
            "object": "chat.completion",
            "created": 1,
            "model": "gpt-4o",
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_control",
                        "type": "function",
                        "function": {
                            "name": "CanvasEditPlan",
                            "arguments": json.dumps(
                                {"wants_edit": "not-a-bool"}),
                        },
                    }],
                },
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        })

    scratch_client = openai.OpenAI(
        base_url="http://127.0.0.1:1/v1",
        api_key="scratch-no-credential",
        http_client=httpx.Client(transport=httpx.MockTransport(_transport)),
        max_retries=0,
    )
    handler.clients["openai"] = scratch_client

    result = asyncio.run(handler.generate_structured_response(
        prompt="update the valid-until date",
        system_instruction="You return only the requested JSON object.",
        response_model=CanvasEditPlan,
        task_type="planning",
        provider_model=("openai", "gpt-4o"),
        allow_moa=False,
        max_tokens=1000))

    assert result is None
    assert len(physical_requests) == 1, (
        "the re-issue must be refused before the second wire call: "
        f"{len(physical_requests)} physical calls")
    rows = _attempt_rows(host)
    assert len(rows) == 1, (
        "only the admitted first call exists; the refused retry rolls back: "
        f"{[(r.attempt_id, r.reservation_status) for r in rows]}")
    assert rows[0].reservation_status == "settled"
    assert rows[0].cost_usd == pytest.approx(0.4)


def _scratch_completion(marker):
    """A valid CanvasEditPlan tool-call payload for the scratch transport."""
    return {
        "id": f"chatcmpl-{marker}",
        "object": "chat.completion",
        "created": 1,
        "model": "gpt-4o",
        "choices": [{
            "index": 0,
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": f"call_{marker}",
                    "type": "function",
                    "function": {
                        "name": "CanvasEditPlan",
                        "arguments": json.dumps({
                            "wants_edit": True,
                            "updated_content_json": '"ok"',
                        }),
                    },
                }],
            },
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }


def _structured_call(handler):
    return asyncio.run(handler.generate_structured_response(
        prompt="update the valid-until date",
        system_instruction="You return only the requested JSON object.",
        response_model=CanvasEditPlan,
        task_type="planning",
        provider_model=("openai", "gpt-4o"),
        allow_moa=False,
        max_tokens=1000))


def test_structured_client_clone_failure_refuses_before_admission(
        host, monkeypatch, tmp_path, denied_os_network):
    """An uncloneable client must not dispatch on the ORIGINAL client.

    Failing open returned the original client, so Instructor's internal
    retry could issue several wire requests under the single call-scoped
    reservation. The dispatch must now be refused BEFORE that admission is
    made: zero provider requests and no orphan reservation row.
    """
    import httpx
    import openai

    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    handler = _handler(monkeypatch, tmp_path)

    physical_requests = []

    def _transport(request):
        physical_requests.append(request)
        return httpx.Response(200, json=_scratch_completion("clone"))

    class _UncloneableOpenAI(openai.OpenAI):
        def with_options(self, **kwargs):
            raise RuntimeError("clone unsupported for this control")

    handler.clients["openai"] = _UncloneableOpenAI(
        base_url="http://127.0.0.1:1/v1",
        api_key="scratch-no-credential",
        http_client=httpx.Client(transport=httpx.MockTransport(_transport)),
        max_retries=0,
    )

    result = _structured_call(handler)

    assert result is None, (
        "a client that cannot be wrapped must fail closed, never dispatch "
        "unwrapped")
    assert physical_requests == [], (
        "no provider request may be issued when per-physical admission "
        f"cannot be installed: {len(physical_requests)} physical calls")
    assert _attempt_rows(host) == [], (
        "the refusal precedes admission, so no reservation may be orphaned")


def test_structured_client_bind_failure_refuses_before_admission(
        host, monkeypatch, tmp_path, denied_os_network):
    """A client whose transport create cannot be bound must not dispatch.

    The clone succeeds, but binding the admitting wrapper fails. Returning
    the original client would put an unadmitted transport under the single
    call-scoped reservation, so the refusal must happen before admission.
    """
    import httpx
    import openai

    _seed(host, spend=0.0)
    _reservation_pricing(monkeypatch, bound_at=0.25, actual=0.25)
    handler = _handler(monkeypatch, tmp_path)

    physical_requests = []

    def _transport(request):
        physical_requests.append(request)
        return httpx.Response(200, json=_scratch_completion("bind"))

    class _BindRefusingCompletions:
        """Expose ``create`` but reject rebinding it to the wrapper."""

        def __init__(self):
            object.__setattr__(self, "_create", lambda **kwargs: None)

        def __getattr__(self, name):
            if name == "create":
                return object.__getattribute__(self, "_create")
            raise AttributeError(name)

        def __setattr__(self, name, value):
            if name == "create":
                raise RuntimeError("transport create cannot be rebound")
            object.__setattr__(self, name, value)

    class _BindRefusingOpenAI(openai.OpenAI):
        def with_options(self, **kwargs):
            return NS(chat=NS(completions=_BindRefusingCompletions()))

    handler.clients["openai"] = _BindRefusingOpenAI(
        base_url="http://127.0.0.1:1/v1",
        api_key="scratch-no-credential",
        http_client=httpx.Client(transport=httpx.MockTransport(_transport)),
        max_retries=0,
    )

    result = _structured_call(handler)

    assert result is None, (
        "a transport create that cannot be wrapped must fail closed, never "
        "dispatch under the call-scoped reservation")
    assert physical_requests == [], (
        "no provider request may be issued when per-physical admission "
        f"cannot be installed: {len(physical_requests)} physical calls")
    assert _attempt_rows(host) == [], (
        "the refusal precedes admission, so no reservation may be orphaned")
