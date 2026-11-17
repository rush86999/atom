# -*- coding: utf-8 -*-
"""Per-call failure diagnostics for the pinned planning wrapper.

``pinned_structured_call`` converts provider errors to ``None`` by contract,
so the failure KIND must travel beside the result. That diagnosis is now
strictly call-local: the caller owns a mapping and passes it as
``failure_capture``; the wrapper clears and fills only that mapping. There is
no process-wide "last failure" record, so a later call that produces no
result (no exception to publish) can never inherit a previous call's error,
and overlapping calls cannot read or erase each other's record.

These controls use a fake service: no provider, network, credentials or
live data.

The final section adds the ACTUAL dispatch boundary for the strict-pin
contract: real ``LLMService`` -> real ``BYOKHandler`` -> real OpenAI SDK
client whose HTTP is an in-process ``httpx.MockTransport``, plus the real
proposal consumer. No socket, provider, credential or live data is used;
every answer is a synthetic local transport-double payload.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Tuple

import pytest

from core.llm import pinned_planning as pp


class _TenantGoneThenRefusal:
    """First tenant unresolved; the control tenant returns no output.

    ``LLMScopeUnresolvedError`` is the real boundary error the live proposal
    raised. The control tenant's refusal is a bare ``None`` — the shape that
    carries no exception, so nothing would overwrite a stale record.
    """

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def generate_structured_response(self, **kwargs: Any) -> Any:
        self.calls.append(dict(kwargs))
        if kwargs.get("tenant_id") == "tenant-gone":
            from core.llm_service import LLMScopeUnresolvedError

            raise LLMScopeUnresolvedError("tenant-gone", "unknown_tenant")
        return None


async def _call(service: Any, *, tenant_id: str, label: str,
                capture: Dict[str, Any],
                observer: Any = None) -> Any:
    return await pp.pinned_structured_call(
        service,
        prompt="p",
        response_model=dict,
        system_instruction="Return JSON.",
        log_label=label,
        workspace_id="ws-ctrl",
        tenant_id=tenant_id,
        failure_capture=capture,
        attempt_observer=observer,
    )


@pytest.mark.asyncio
async def test_unresolved_scope_failure_does_not_leak_into_the_next_call():
    service = _TenantGoneThenRefusal()

    proposal_failure: Dict[str, Any] = {}
    proposal = await _call(
        service, tenant_id="tenant-gone", label="employee work proposal",
        capture=proposal_failure)
    assert proposal is None
    assert proposal_failure["kind"] == "provider_failure"
    assert "tenant-gone" in proposal_failure["detail"]

    # The control tenant produced no output (a refusal, not an exception).
    # Its diagnostic must be ITS OWN empty record, never the proposal's.
    refusal_failure: Dict[str, Any] = {}
    refusal = await _call(
        service, tenant_id="tenant-ctrl", label="canvas edit planning",
        capture=refusal_failure)
    assert refusal is None
    assert refusal_failure == {
        "kind": None, "detail": "", "label": "canvas edit planning"}
    assert "tenant-gone" not in refusal_failure["detail"]


def test_no_process_wide_failure_record_exists():
    """The diagnostic seam must not expose a shared "last failure" dict."""
    assert not hasattr(pp, "LAST_FAILURE")


@pytest.mark.asyncio
async def test_overlapping_call_cannot_supply_another_calls_diagnostic():
    service_entered = asyncio.Event()
    release_refusal = asyncio.Event()

    class _OverlapService:
        async def generate_structured_response(self, **kwargs: Any) -> Any:
            if kwargs.get("tenant_id") == "tenant-gone":
                from core.llm_service import LLMScopeUnresolvedError

                raise LLMScopeUnresolvedError("tenant-gone", "unknown_tenant")
            service_entered.set()
            await release_refusal.wait()
            return None

    events: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {
        "gone": [], "ctrl": []}

    def _observer(sink: List[Tuple[str, Dict[str, Any]]]):
        def observe(event: str, **fields: Any) -> None:
            if event == "no_result":
                sink.append((event, dict(fields.get("failure") or {})))
        return observe

    service = _OverlapService()
    ctrl_capture: Dict[str, Any] = {}
    ctrl_task = asyncio.create_task(_call(
        service, tenant_id="tenant-ctrl", label="canvas edit planning",
        capture=ctrl_capture, observer=_observer(events["ctrl"])))
    await service_entered.wait()

    gone_capture: Dict[str, Any] = {}
    gone_task = asyncio.create_task(_call(
        service, tenant_id="tenant-gone", label="employee work proposal",
        capture=gone_capture, observer=_observer(events["gone"])))
    await gone_task
    assert gone_capture["kind"] == "provider_failure"
    assert "tenant-gone" in gone_capture["detail"]

    # The control call was already in flight. Let it finish AFTER the other
    # call published; its own capture and no-result event must still be empty.
    release_refusal.set()
    await ctrl_task

    assert events["ctrl"] == [(
        "no_result", {"kind": None, "detail": "",
                      "label": "canvas edit planning"})]
    assert ctrl_capture == {
        "kind": None, "detail": "", "label": "canvas edit planning"}


@pytest.mark.asyncio
async def test_cancelled_call_publishes_deadline_cancelled_to_its_capture():
    entered = asyncio.Event()

    class _HangingService:
        async def generate_structured_response(self, **kwargs: Any) -> Any:
            entered.set()
            await asyncio.sleep(30)

    capture: Dict[str, Any] = {}
    task = asyncio.create_task(_call(
        _HangingService(), tenant_id="tenant-ctrl",
        label="canvas edit planning", capture=capture))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Cancellation is its own boundary, published to THIS call's capture.
    # It is never left looking like an empty answer and never becomes a
    # provider failure.
    assert capture["kind"] == "deadline_cancelled"
    assert capture["label"] == "canvas edit planning"
    assert capture["detail"].startswith("CancelledError")


@pytest.mark.asyncio
async def test_canvas_consumer_reads_only_its_own_calls_capture(monkeypatch):
    """The canvas outcome must cite this call's kind, not a prior failure."""
    from core.chat_canvas_editor import (
        CanvasPlanOutcome, CanvasPlanUnavailable, plan_canvas_edit,
    )

    monkeypatch.delenv("ATOM_ASYNC_EDIT_PLAN_MODEL", raising=False)

    class _RaisingService:
        async def generate_structured_response(self, **kwargs: Any) -> Any:
            from core.llm_service import LLMScopeUnresolvedError

            raise LLMScopeUnresolvedError("tenant-gone", "unknown_tenant")

    class _EmptyService:
        async def generate_structured_response(self, **kwargs: Any) -> Any:
            return None

    canvas = {
        "canvas_id": "cv-failure-isolation", "canvas_type": "document",
        "title": "Q", "content": "Unit price: $1.00\n",
    }
    with pytest.raises(CanvasPlanUnavailable) as first:
        await plan_canvas_edit("update the price", [], canvas, _RaisingService())
    assert first.value.kind == CanvasPlanOutcome.PROVIDER_FAILURE

    with pytest.raises(CanvasPlanUnavailable) as second:
        await plan_canvas_edit("update the price", [], canvas, _EmptyService())
    assert second.value.kind == CanvasPlanOutcome.EMPTY, (
        "an empty answer after a prior provider failure must not inherit "
        "the prior call's diagnosis")


@pytest.mark.asyncio
async def test_interpretation_consumer_reads_only_its_own_calls_capture():
    """The interpretation reason must come from this call's capture."""
    from core import turn_decision as td

    class _RaisingService:
        async def generate_structured_response(self, **kwargs: Any) -> Any:
            from core.llm_service import LLMScopeUnresolvedError

            raise LLMScopeUnresolvedError("tenant-gone", "unknown_tenant")

    class _EmptyService:
        async def generate_structured_response(self, **kwargs: Any) -> Any:
            return None

    td.reset_interpretation_for_tests()
    try:
        failed = await td.interpret_turn_request(
            "check the approved record", {}, [], {},
            request_id="req-shared", llm_service=_RaisingService())
        assert failed["origin"] == "unresolved"
        assert failed["unresolved_reason"] == "error"

        empty = await td.interpret_turn_request(
            "check the approved record", {}, [], {},
            request_id="req-shared", llm_service=_EmptyService())
        assert empty["origin"] == "unresolved"
        # The earlier provider failure must not be re-read as this call's
        # diagnosis (which would surface as "error").
        assert empty["unresolved_reason"] != "error"
        assert empty["unresolved_reason"] == "missing_scope"
    finally:
        td.reset_interpretation_for_tests()


@pytest.mark.asyncio
async def test_canvas_reader_uses_the_current_calls_capture():
    """Direct contract of the canvas seam reader."""
    from core.chat_canvas_editor import (
        CanvasPlanOutcome, _plan_failure_kind_from_seam,
    )

    assert _plan_failure_kind_from_seam({}) == CanvasPlanOutcome.EMPTY
    assert _plan_failure_kind_from_seam(None) == CanvasPlanOutcome.EMPTY
    assert _plan_failure_kind_from_seam(
        {"kind": "provider_failure"}) == CanvasPlanOutcome.PROVIDER_FAILURE
    assert _plan_failure_kind_from_seam(
        {"kind": "malformed_structured_output"}
    ) == CanvasPlanOutcome.MALFORMED
    assert _plan_failure_kind_from_seam(
        {"kind": "deadline_cancelled"}
    ) == CanvasPlanOutcome.DEADLINE_CANCELLED


@pytest.mark.asyncio
async def test_successful_call_clears_the_previous_calls_failure():
    class _Service:
        def __init__(self) -> None:
            self.calls = 0

        async def generate_structured_response(self, **kwargs: Any) -> Any:
            self.calls += 1
            if self.calls == 1:
                from core.llm_service import LLMScopeUnresolvedError

                raise LLMScopeUnresolvedError("tenant-gone", "unknown_tenant")
            return {"ok": True}

    service = _Service()
    await _call(service, tenant_id="tenant-gone",
                label="employee work proposal", capture={})

    capture: Dict[str, Any] = {"kind": "stale", "detail": "old", "label": "old"}
    result = await _call(service, tenant_id="tenant-ctrl",
                         label="employee work proposal", capture=capture)
    assert result == {"ok": True}
    assert capture == {
        "kind": None, "detail": "", "label": "employee work proposal"}


# --- pinned attempt vs. terminal outcome ------------------------------------
#
# A failed PIN is a failed ATTEMPT, not a failed CALL. These controls pin the
# three contracts the canvas/interpretation consumers depend on.

_PIN = ("fake-provider", "fake-model")


async def _pinned_call(service: Any, *, capture: Dict[str, Any],
                       label: str = "employee work proposal",
                       observer: Any = None,
                       strict_pin: Any = None) -> Any:
    return await pp.pinned_structured_call(
        service,
        prompt="p",
        response_model=dict,
        system_instruction="Return JSON.",
        log_label=label,
        workspace_id="ws-ctrl",
        tenant_id="tenant-ctrl",
        call_kwargs={"provider_model": _PIN},
        failure_capture=capture,
        attempt_observer=observer,
        strict_pin=strict_pin,
    )


class _PinRaisesFallbackAnswers:
    """The preferred (pinned) route raises; the unpinned retry succeeds."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def generate_structured_response(self, **kwargs: Any) -> Any:
        self.calls.append(dict(kwargs))
        if kwargs.get("provider_model"):
            raise RuntimeError("pinned route unavailable")
        return {"ok": True}


class _PinRaisesFallbackEmpty:
    """The pinned route raises; the unpinned retry produces no output."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def generate_structured_response(self, **kwargs: Any) -> Any:
        self.calls.append(dict(kwargs))
        if kwargs.get("provider_model"):
            raise RuntimeError("pinned route unavailable")
        return None


@pytest.mark.asyncio
async def test_successful_unpinned_fallback_clears_the_rejected_pins_failure():
    """Regression: a good fallback result is a SUCCESSFUL call.

    Verified fake-service reproduction of the live shape: the preferred
    non-strict pin raises RuntimeError, the unpinned fallback returns valid
    output, and the capture still said ``provider_failure`` — every consumer
    reads that as "nothing was planned" and discards a good answer.
    """
    service = _PinRaisesFallbackAnswers()
    events: List[Tuple[str, Dict[str, Any]]] = []

    def observe(event: str, **fields: Any) -> None:
        events.append((event, dict(fields)))

    capture: Dict[str, Any] = {"kind": "stale", "detail": "old", "label": "old"}
    result = await _pinned_call(service, capture=capture, observer=observe)

    assert result == {"ok": True}
    # Terminal record: the call succeeded, so no provider failure is reported.
    assert capture == {
        "kind": None, "detail": "", "label": "employee work proposal"}

    # Both attempts really ran, in order, and the retry was unpinned with the
    # failed pin excluded (the retry is not a repeat of the failing route).
    assert len(service.calls) == 2
    assert service.calls[0].get("provider_model") == _PIN
    assert "provider_model" not in service.calls[1]
    assert service.calls[1].get("exclude_provider_model") == _PIN

    # Clearing the TERMINAL record must not erase the per-attempt diagnosis:
    # the pinned attempt's own observer event still carries its error.
    pinned_failures = [
        fields for event, fields in events
        if event == "failure" and fields.get("route") == "pinned"]
    assert len(pinned_failures) == 1
    observed = pinned_failures[0].get("exception")
    assert isinstance(observed, RuntimeError)
    assert str(observed) == "pinned route unavailable"


@pytest.mark.asyncio
async def test_empty_unpinned_fallback_still_reports_the_failure():
    """Unchanged contract: pin raises AND retry is empty => failure retained."""
    service = _PinRaisesFallbackEmpty()
    capture: Dict[str, Any] = {}

    result = await _pinned_call(service, capture=capture)

    assert result is None
    assert len(service.calls) == 2
    assert capture == {
        "kind": "provider_failure",
        "detail": "RuntimeError: pinned route unavailable",
        "label": "employee work proposal",
    }


@pytest.mark.asyncio
async def test_strict_pin_failure_is_terminal_and_never_falls_back():
    """Unchanged contract: a strict pin is exact-route-or-failure."""
    service = _PinRaisesFallbackAnswers()
    capture: Dict[str, Any] = {}

    result = await _pinned_call(service, capture=capture, strict_pin=True)

    assert result is None
    assert len(service.calls) == 1, (
        "a strict pin must not dispatch the unpinned retry")
    assert capture == {
        "kind": "provider_failure",
        "detail": "RuntimeError: pinned route unavailable",
        "label": "employee work proposal",
    }


@pytest.mark.asyncio
async def test_explicit_strict_without_a_route_pin_fails_before_dispatch():
    """A strict request that never built a pin must not run unpinned.

    ``build_provider_model_pin`` can refuse a pin (local-only/policy/no
    client). Passing that empty kwargs with an explicit ``strict_pin=True``
    used to become an ordinary unpinned dispatch — a silent contract
    weakening. The call now fails before any provider work.
    """
    service = _PinRaisesFallbackAnswers()
    capture: Dict[str, Any] = {}

    result = await pp.pinned_structured_call(
        service,
        prompt="p",
        response_model=dict,
        system_instruction="Return JSON.",
        log_label="employee work proposal",
        call_kwargs={},
        strict_pin=True,
        failure_capture=capture,
    )

    assert result is None
    assert service.calls == [], "no unpinned dispatch for a strict request"
    assert capture["kind"] == "provider_failure"
    assert "without a dispatchable route" in capture["detail"]


# ---------------------------------------------------------------------------
# ACTUAL DISPATCH BOUNDARY: a strict qualification pin is exact-route-or-
# failure inside the REAL service -> handler -> SDK boundary too.
#
# The wrapper above already refuses its own unpinned RETRY. The gap this
# closes is one layer down: the handler's own pin block could silently DROP
# the pin (cooldown, provider-unavailable, local-only, provider policy,
# context) and re-rank the caller's already-eligible pool. A weaker route
# then produced a normal ``source="model"`` proposal before the later
# identity/effect gate demoted the effect — the answer had already been
# consumed. ``strict_pin`` now travels through LLMService into the handler;
# every one of those branches is an explicit pre-dispatch refusal for a
# strict call, and the ordinary (non-strict) pin keeps its designed fallback.
# ---------------------------------------------------------------------------

_STRICT_WS = "strict-pin-ws"
_STRICT_TENANT = "strict-pin-tenant"
_STRICT_PROFILE = "employee_evidence_selection"
_PIN = ("local_probe", "qualrouter-70b")
_WEAK = ("local_fallback", "qualrouter-mini")
_ALT = ("local_alt", "qualrouter-alt")
_CLOUD = ("cloud_probe", "qualrouter-cloud")
_PIN_ECHO = "qualrouter-70b-2026-01"
_WEAK_ECHO = "qualrouter-mini-2026-01"
_ALT_ECHO = "qualrouter-alt-2026-01"

#: A valid EmployeeWorkProposal body. Every routed answer is this synthetic
#: local double's payload — no model quality claim is made anywhere here.
_PROPOSAL_JSON = {
    "proposal_kind": "evidence_read",
    "reason": "read the authorized note",
    "evidence_reads": [{
        "step_id": "evidence-1",
        "title": "Read note",
        "source_id": "doc-1",
    }],
}


class _TransportPlan:
    """Per-model scripted HTTP responses for the in-process SDK transport."""

    def __init__(self) -> None:
        self.routes: Dict[str, Dict[str, Any]] = {}
        self.calls: List[Dict[str, Any]] = []

    def serve(self, model: str, *, echo: str) -> None:
        self.routes[model] = {"content": _PROPOSAL_JSON, "echo": echo}

    def fail(self, model: str, status: int, message: str) -> None:
        self.routes[model] = {"status": status, "error": message}

    def reset(self) -> None:
        self.calls.clear()


def _transport_handler(provider_id: str, plan: _TransportPlan):
    def _handle(request):
        import httpx

        try:
            body = json.loads(request.content.decode("utf-8"))
        except Exception:  # noqa: BLE001 — the request itself is still one call
            body = {}
        model = str(body.get("model") or "")
        route = plan.routes.get(model) or {}
        plan.calls.append({
            "provider": provider_id,
            "model": model,
            "path": request.url.path,
        })
        if route.get("status"):
            return httpx.Response(route["status"], json={"error": {
                "message": route.get("error") or "controlled failure",
                "type": "invalid_request_error",
            }})
        return httpx.Response(200, json={
            "id": "chatcmpl-strict-pin-local",
            "object": "chat.completion",
            "created": 0,
            "model": route.get("echo") or model,
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(route.get("content") or _PROPOSAL_JSON),
                },
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 40,
                "total_tokens": 140,
            },
        })

    return _handle


@pytest.fixture()
def dispatch_world(monkeypatch):
    """REAL LLMService -> REAL BYOKHandler -> real OpenAI SDK client.

    HTTP is an in-process ``httpx.MockTransport``; no socket is opened and no
    provider is contacted. Only the ranked candidate list is a declared local
    fixture (the ranking itself was runtime-proven by the dispatch-floor
    probe); every route decision AFTER it, the pin gate, availability gates,
    the wire request and the consumer are the real code.
    """
    import httpx
    import openai

    import core.llm.byok_handler as bh
    from core.dynamic_pricing_fetcher import get_pricing_fetcher
    from core.employee_proposal import (
        build_employee_context,
        propose_employee_work,
    )
    from core.llm.byok_handler import BYOKHandler
    from core.llm_service import LLMService

    # Provider/model cooldowns and auth memos are process-wide: every arm
    # starts and ends with a clean registry, so one arm's 401/cooldown cannot
    # leak into the next (or into another file's test).
    BYOKHandler.invalidate_provider_failures()

    plan = _TransportPlan()
    plan.serve(_PIN[1], echo=_PIN_ECHO)
    plan.serve(_WEAK[1], echo=_WEAK_ECHO)
    plan.serve(_ALT[1], echo=_ALT_ECHO)

    fetcher = get_pricing_fetcher()
    monkeypatch.setattr(fetcher, "pricing_cache", {
        model: {"litellm_provider": "ollama", "max_input_tokens": 131072}
        for model in (_PIN[1], _WEAK[1], _ALT[1], _CLOUD[1])
    })
    monkeypatch.setattr(bh, "get_pricing_fetcher", lambda: fetcher)
    # The declared routes below ARE the workspace's local providers for this
    # world; never probe the host environment or a live runtime.
    monkeypatch.setattr(
        BYOKHandler, "_load_local_providers", lambda self: None)

    # The durable reservation ledger is the real scratch test store. Its
    # strict billing reader needs the honest scope rows; a missing non-default
    # tenant refuses admission before dispatch. Rows are scoped to this test
    # and removed below.
    from core.database import SessionLocal
    from core.models import Tenant, TokenUsage, Workspace

    service = LLMService(
        workspace_id=_STRICT_WS, tenant_id=_STRICT_TENANT)
    handler = service.handler
    assert isinstance(handler, BYOKHandler)
    handler.workspace_id = _STRICT_WS
    handler.tenant_id = _STRICT_TENANT
    handler._is_trial_restricted = lambda: False

    for provider_id in (_PIN[0], _WEAK[0], _ALT[0], _CLOUD[0]):
        handler.clients[provider_id] = openai.OpenAI(
            api_key="sk-strict-pin-local",
            base_url="http://127.0.0.1:9/v1",
            http_client=httpx.Client(transport=httpx.MockTransport(
                _transport_handler(provider_id, plan))),
        )
    handler.async_clients = {}

    routes = {
        _PIN[1]: (_PIN[0], 0.88),
        _WEAK[1]: (_WEAK[0], 0.80),
        _ALT[1]: (_ALT[0], 0.82),
    }
    handler._local_routes = {}
    for model, (provider_key, quality) in routes.items():
        handler._local_routes[model] = {
            "provider_key": provider_key,
            "workspace_id": _STRICT_WS,
            "provider_id": f"prov-{provider_key}",
            "provider_type": "ollama",
            "supports_tools": True,
            "supports_structured": True,
            "supports_vision": False,
            "supports_reasoning": False,
            "quality_score": quality,
            "context_window": 131072,
        }

    ranked: List[Tuple[str, str]] = [_PIN, _WEAK, _ALT]

    from core.llm.byok_handler import AwaitableResult

    handler.get_ranked_providers = (
        lambda *_args, **_kwargs: AwaitableResult(list(ranked)))

    def _context(*, extra_sources: int = 0):
        sources = [{
            "kind": "document",
            "representation": "document_text",
            "resource_id": "doc-1",
            "file_name": "note.txt",
        }]
        for index in range(extra_sources):
            sources.append({
                "kind": "document",
                "representation": "document_text",
                "resource_id": f"doc-{index + 2}",
                "file_name": (
                    f"authorized-note-{index + 2}-" + "x" * 320 + ".txt"),
            })
        return build_employee_context(
            objective="Read the authorized evidence",
            workspace_id=_STRICT_WS,
            tenant_id=_STRICT_TENANT,
            sources=sources,
            stage="discovery",
        )

    async def _propose(*, strict: bool, pin=_PIN, context=None):
        return await propose_employee_work(
            context if context is not None else _context(),
            llm_service=service,
            provider_model=tuple(pin) if pin else None,
            strict_pin=True if (strict and pin) else None,
        )

    world = {
        "service": service,
        "handler": handler,
        "plan": plan,
        "context": _context,
        "propose": _propose,
        "set_ranked": lambda routes_: ranked.__setitem__(slice(None), routes_),
    }
    with SessionLocal() as db:
        db.merge(Tenant(
            id=_STRICT_TENANT, name="Strict pin tenant",
            subdomain="strict-pin-tenant", edition="personal",
            is_active=True))
        db.merge(Workspace(
            id=_STRICT_WS, name="Strict pin workspace",
            tenant_id=_STRICT_TENANT))
        db.commit()

    yield world
    with SessionLocal() as db:
        db.query(TokenUsage).filter(
            TokenUsage.workspace_id == _STRICT_WS).delete()
        db.query(Workspace).filter(Workspace.id == _STRICT_WS).delete()
        db.query(Tenant).filter(Tenant.id == _STRICT_TENANT).delete()
        db.commit()
    for client in handler.clients.values():
        try:
            client.close()
        except Exception:  # noqa: BLE001 — test teardown is best-effort
            pass
    BYOKHandler.invalidate_provider_failures()


@pytest.mark.asyncio
async def test_llm_service_forwards_strict_pin_only_for_an_explicit_call():
    """The strict marker crosses the service only when the caller asked.

    Every other structured call keeps the exact handler kwargs it had before
    the parameter existed (legacy handler doubles must not see a new key).
    """
    from unittest.mock import AsyncMock, MagicMock

    from core.llm_service import LLMService

    handler = MagicMock()
    handler.generate_structured_response = AsyncMock(return_value="OK")
    service = LLMService.__new__(LLMService)
    service._get_handler = MagicMock(return_value=handler)
    service.continuous_learning = None

    await service.generate_structured_response(
        prompt="p", response_model=object, task_type="planning",
        strict_pin=True)
    strict_kwargs = handler.generate_structured_response.await_args.kwargs
    assert strict_kwargs["strict_pin"] is True

    handler.generate_structured_response.reset_mock()
    await service.generate_structured_response(
        prompt="p", response_model=object, task_type="planning")
    ordinary_kwargs = handler.generate_structured_response.await_args.kwargs
    assert "strict_pin" not in ordinary_kwargs


def _served(result: Dict[str, Any]) -> Any:
    return (result.get("routing") or {}).get("served_route")


@pytest.mark.asyncio
async def test_strict_pin_serves_the_exact_route_positive(dispatch_world):
    """Control: a healthy strict pin really dispatches its own exact route."""
    plan = dispatch_world["plan"]
    plan.reset()

    result = await dispatch_world["propose"](strict=True)

    assert result["source"] == "model", result
    assert result["technical_fallback"] is False
    assert _served(result) == {"provider": _PIN[0], "model": _PIN[1]}
    assert (result["routing"] or {}).get("resolved_model") == _PIN_ECHO
    assert plan.calls == [{
        "provider": _PIN[0],
        "model": _PIN[1],
        "path": "/v1/chat/completions",
    }]


@pytest.mark.asyncio
async def test_strict_pin_cooldown_is_explicit_failure_with_zero_dispatch(
        dispatch_world):
    """Baseline failure: cooldown unpinned and a weaker route answered.

    The pinned attempt is never weakened: the route is benched, so the strict
    call fails before dispatch. No request reaches ANY provider — the weaker
    replacement gets zero physical fake requests, not merely a rejected
    answer after it ran.
    """
    plan = dispatch_world["plan"]
    handler = dispatch_world["handler"]
    plan.reset()
    handler._bench_model(_PIN[0], _PIN[1], seconds=120)

    result = await dispatch_world["propose"](strict=True)

    assert result["source"] == "deterministic", result
    assert _served(result) is None
    assert plan.calls == [], (
        "a strict pin must fail closed before a weaker route is dispatched")
    assert (result["routing"] or {}).get("error", {}).get("code")


@pytest.mark.asyncio
async def test_strict_pin_after_transport_401_never_unpins_on_next_call(
        dispatch_world):
    """Baseline failure: the NEXT call after a real 401 served the weak route.

    The first call fails closed (already the strict contract). The repaired
    contract is the second call: the provider the 401 benched is still the
    only route this qualification allows, so it refuses before dispatch
    instead of serving the unmeasured replacement.
    """
    plan = dispatch_world["plan"]
    handler = dispatch_world["handler"]
    plan.reset()
    plan.fail(_PIN[1], 401, "invalid api key")

    first = await dispatch_world["propose"](strict=True)
    assert first["source"] == "deterministic", first
    assert handler._provider_cooldown_active(_PIN[0]) is True
    assert plan.calls == [{
        "provider": _PIN[0],
        "model": _PIN[1],
        "path": "/v1/chat/completions",
    }]

    plan.reset()
    plan.serve(_PIN[1], echo=_PIN_ECHO)
    second = await dispatch_world["propose"](strict=True)

    assert second["source"] == "deterministic", second
    assert _served(second) is None
    assert plan.calls == [], (
        "the next strict call must not unpin onto an unqualified route")
    assert (second["routing"] or {}).get("error", {}).get("code")


@pytest.mark.asyncio
async def test_non_strict_pin_twins_keep_the_designed_fallback(dispatch_world):
    """Ordinary pins are unchanged: cooldown and failure still fall back.

    These are the explicit non-strict twins of the two arms above. They must
    keep answering from the ranked pool (and the fallback's served route is
    honestly reported), proving the strictness is opt-in.
    """
    plan = dispatch_world["plan"]
    handler = dispatch_world["handler"]

    # Twin 1: benched pin -> re-rank across the healthy pool.
    plan.reset()
    handler._bench_model(_PIN[0], _PIN[1], seconds=120)
    cooled = await dispatch_world["propose"](strict=False)

    assert cooled["source"] == "model", cooled
    assert _served(cooled) == {"provider": _WEAK[0], "model": _WEAK[1]}
    assert plan.calls == [{
        "provider": _WEAK[0],
        "model": _WEAK[1],
        "path": "/v1/chat/completions",
    }]
    handler.invalidate_provider_failures()

    # Twin 2: the pinned attempt itself fails (401) -> the wrapper's one
    # unpinned retry excludes the failed pin and serves the ranked route.
    plan.reset()
    plan.fail(_PIN[1], 401, "invalid api key")
    failed = await dispatch_world["propose"](strict=False)

    assert failed["source"] == "model", failed
    assert _served(failed) == {"provider": _WEAK[0], "model": _WEAK[1]}
    assert [call["provider"] for call in plan.calls] == [
        _PIN[0], _WEAK[0]]


@pytest.mark.asyncio
async def test_strict_pin_policy_refusal_does_not_rerank_within_policy(
        dispatch_world):
    """A strict pin never overrides a policy refusal by choosing another route."""
    from core.llm.provider_policy import ProviderPolicy

    plan = dispatch_world["plan"]
    handler = dispatch_world["handler"]
    dispatch_world["set_ranked"]([_PIN, _ALT])
    # The pin's provider is outside the allowed set; the alternative is in it.
    handler.provider_policy = ProviderPolicy(
        mode="selected", allowed_providers=frozenset({_ALT[0]}))
    plan.reset()

    result = await dispatch_world["propose"](strict=True)

    assert result["source"] == "deterministic", result
    assert plan.calls == [], (
        "the policy refusal is final for a strict pin; no alternate route")
    assert (result["routing"] or {}).get("error", {}).get("code")


@pytest.mark.asyncio
async def test_strict_pin_local_only_refusal_does_not_rerank_locally(
        dispatch_world, monkeypatch):
    """Local-only blocks a cloud pin; a strict call refuses, no local rerank."""
    import core.llm.byok_handler as bh
    from core.privsec.local_only_guard import LocalOnlyGuard
    from core.llm.provider_policy import ProviderPolicy

    plan = dispatch_world["plan"]
    handler = dispatch_world["handler"]
    handler.provider_policy = ProviderPolicy(mode="unset")
    real_quality = bh.get_quality_score
    monkeypatch.setattr(
        bh, "get_quality_score",
        lambda model: 90 if model == _CLOUD[1] else real_quality(model))
    dispatch_world["set_ranked"]([_CLOUD, _ALT])
    plan.serve(_CLOUD[1], echo="qualrouter-cloud-2026-01")
    plan.reset()

    monkeypatch.setenv("ATOM_LOCAL_ONLY", "true")
    LocalOnlyGuard.reset_cache()
    try:
        assert bh._local_only_blocks_provider(_CLOUD[0]) is True
        assert bh._local_only_blocks_provider(_ALT[0]) is False
        result = await dispatch_world["propose"](strict=True, pin=_CLOUD)
    finally:
        monkeypatch.delenv("ATOM_LOCAL_ONLY", raising=False)
        LocalOnlyGuard.reset_cache()

    assert result["source"] == "deterministic", result
    assert plan.calls == [], (
        "a strict cloud pin under local-only makes no cloud or local call")
    assert (result["routing"] or {}).get("error", {}).get("code")


@pytest.mark.asyncio
async def test_strict_pin_context_shortfall_refuses_before_dispatch(
        dispatch_world):
    """A pin that fits the profile floor but not THIS request fails closed.

    The profile's 8000-token floor still admits the pin (so the pin gate is
    not what refuses); the request's own size does not fit it. The stricter
    branch is the pre-dispatch ``_pinned_model_fits`` unpin — it must refuse,
    not silently re-rank onto the weaker route that used to answer.
    """
    plan = dispatch_world["plan"]
    handler = dispatch_world["handler"]
    handler._local_routes[_PIN[1]]["context_window"] = 8000
    from core.dynamic_pricing_fetcher import get_pricing_fetcher

    get_pricing_fetcher().pricing_cache[_PIN[1]]["max_input_tokens"] = 8000
    dispatch_world["set_ranked"]([_WEAK, _ALT])
    plan.reset()
    # Enough context text that input + 6000-token headroom exceeds 8000.
    context = dispatch_world["context"](extra_sources=40)
    from core.employee_proposal import _proposal_prompt

    assert len(_proposal_prompt(context)) > 8000

    result = await dispatch_world["propose"](strict=True, context=context)

    assert result["source"] == "deterministic", result
    assert plan.calls == [], (
        "the context gate must refuse the strict pin, not unpin it")
    assert (result["routing"] or {}).get("error", {}).get("code")


@pytest.mark.asyncio
async def test_strict_pin_exclusion_refuses_before_dispatch(dispatch_world):
    """A pin a caller also excluded is an explicit failure, never a swap."""
    from core.employee_proposal import EmployeeWorkProposal

    plan = dispatch_world["plan"]
    handler = dispatch_world["handler"]
    plan.reset()

    result = await handler.generate_structured_response(
        prompt="Read the authorized evidence",
        system_instruction="Return JSON only.",
        response_model=EmployeeWorkProposal,
        provider_model=_PIN,
        exclude_provider_model=_PIN,
        capability_profile=_STRICT_PROFILE,
        strict_pin=True,
        output_mode="json",
        cascade=False,
        allow_moa=False,
    )

    assert result is None
    assert plan.calls == [], (
        "an excluded strict pin must not re-rank onto another provider")
