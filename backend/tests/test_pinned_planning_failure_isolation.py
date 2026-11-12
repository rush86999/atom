# -*- coding: utf-8 -*-
"""Per-call failure diagnostics for the pinned planning wrapper.

``pinned_structured_call`` converts provider errors to ``None`` by contract,
so the failure KIND must travel beside the result. That diagnosis is now
strictly call-local: the caller owns a mapping and passes it as
``failure_capture``; the wrapper clears and fills only that mapping. There is
no process-wide "last failure" record, so a later call that produces no
result (no exception to publish) can never inherit a previous call's error,
and overlapping calls cannot read or erase each other's record.

These controls use only a fake service: no provider, network, credentials or
live data.
"""
from __future__ import annotations

import asyncio
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
