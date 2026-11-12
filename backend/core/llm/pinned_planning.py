"""Pinned structured-planning calls with an unpinned fallback.

WHY THIS EXISTS
---------------
Several planning/classification call sites deliberately PIN one cheap
(provider, model) — the tool planner, the canvas editor, knowledge extraction,
the spreadsheet SQL planner — so BPC's value ranking doesn't send planning work
to frontier-priced models, and so a turn doesn't burn its budget on
connection-retry cascades against an unreachable client.

The pin is applied with ``provider_model=(provider, model)``, which
``BYOKHandler.generate_structured_response`` implements by collapsing the
candidate list to that single tuple::

    if provider_model is not None:
        options = [provider_model]      # byok_handler.py

That is deliberate recursion control (MoA samples pin their own pair) — but for
a TOP-LEVEL caller it also removes every provider fallback. A pin is only a
preference; the moment the pinned model is rate-limited, gated, revoked, or
otherwise briefly unreachable, the whole planning leg dies.

Observed live 2026-09-10: OpenRouter answered **429 Too Many Requests**
("qwen/qwen3.7-flash is temporarily rate-limited upstream"). Both the structured
call and the raw-JSON rescue re-issued on that same rate-limited model,
``plan_canvas_edit`` raised ``CanvasPlanUnavailable``, and the agent told the
user "I couldn't reach the model I use to plan canvas edits, so nothing was
changed" — for the entire rate-limit window, even though the workspace had other
configured providers. The user's instruction ("add vipul and chandrakant to cc
and fix table styling") was simply not executed.

THE CONTRACT
------------
Try the pin once. If it yields nothing (``None``) or raises, retry ONCE with no
pin, which re-ranks across the workspace's OWN configured providers
(OAuth → BYOK → env). Both attempts failing returns ``None`` so each caller
keeps its own failure contract (raise ``CanvasPlanUnavailable``, degrade to the
live path, return empty knowledge, fall back to the deterministic router).

Callers that need per-call extras (``image_payload``, ``cascade``, an explicit
``max_tokens``) pass them in ``extra_kwargs``; they are forwarded to BOTH
attempts so the retry is not a weaker request than the first.
"""
from __future__ import annotations

import asyncio
import time as _time
import logging
from typing import Any, Dict, Mapping, Optional

logger = logging.getLogger(__name__)

_FAILURE_FIELDS = {"kind": None, "detail": "", "label": ""}


def _new_failure_record(label: str = "") -> Dict[str, Any]:
    """A fresh diagnostic record owned by ONE call."""
    record = dict(_FAILURE_FIELDS)
    record["label"] = label or ""
    return record


def _copy_failure(record: Mapping[str, Any],
                  capture: Optional[Dict[str, Any]]) -> None:
    """Mirror a call-local record into the caller-owned capture."""
    if capture is None:
        return
    capture.clear()
    capture.update(dict(record))


# Boundary-diagnostic seam (owner assignment 3): the KIND of a failure must
# reach the caller even though every provider error is converted to ``None``.
# There is deliberately NO process-wide "last failure" record. A caller that
# needs the diagnosis owns a mapping and passes it as ``failure_capture``;
# the wrapper writes only that mapping. This keeps overlapping and sequential
# calls from lending each other a failure kind.
def _publish_failure(label: str, err: BaseException,
                     record: Dict[str, Any]) -> None:
    name = type(err).__name__
    text = f"{name} {err}".lower()
    if "nosuitableconfiguredmodelerror" in name.lower() or (
            "no_suitable_configured_model" in text):
        kind = "no_suitable_configured_model"
    elif "timeout" in name.lower() or "timeout" in text or "cancel" in name.lower():
        kind = "deadline_cancelled"
    elif any(k in text for k in ("json", "parse", "schema", "malformed",
                                 "truncat", "validation")):
        kind = "malformed_structured_output"
    else:
        kind = "provider_failure"
    record.update(kind=kind, detail=f"{name}: {str(err)[:160]}",
                  label=label)


def _mark_success(record: Dict[str, Any]) -> None:
    """The call produced a result: its TERMINAL diagnosis is empty.

    A rejected pinned attempt publishes its own error before the unpinned
    retry runs. When that retry succeeds the CALL did not fail, so the
    caller-owned capture must not keep reporting the discarded attempt as
    the outcome. Per-attempt observer events were emitted with their own
    copy of the error before this point, so the attempt stays visible in the
    attempt journal without mislabelling the finished call.
    """
    record.update(kind=None, detail="", label=record.get("label") or "")


def _mark_cancelled(record: Dict[str, Any], label: str,
                    err: BaseException) -> None:
    """A caller deadline/cancellation is a distinct boundary, not an empty
    result. ``CancelledError`` must still propagate unchanged."""
    record.update(kind="deadline_cancelled",
                  detail=f"{type(err).__name__}: {str(err)[:160]}",
                  label=label)


def build_provider_model_pin(
    llm_service: Any,
    provider: str,
    model: str,
    *,
    workspace_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return the kwargs dict carrying a pin, or ``{}`` when unavailable.

    Mirrors the long-standing planner convention: the pin is only meaningful if
    that provider actually has a client in the handler (otherwise the pin names
    a provider this workspace cannot call at all and the first attempt is
    guaranteed to fail, paying a full round trip for nothing).

    SCOPE (owner-approved repair 2026-10-18): the membership check must
    resolve the SAME handler scope the structured dispatch will use.
    BYOK providers are loaded per (workspace, tenant); checking the
    service's unscoped constructor handler silently dropped the pin for
    workspace-registered providers (live attempt 7: the declared pin
    never dispatched, and the unpinned fallback sent a different model to
    a different gateway). Callers without request scope keep the previous
    no-argument behavior byte-identically; a NAMED-but-unresolved scope
    refuses the pin rather than borrowing another scope's handler. The
    service's constructor scope is never mutated.

    LOCAL-ONLY (owner directive 2026-10-15): a cloud pin is refused outright
    when the documented local-only policy is enabled — no cloud dispatch may
    happen under ATOM_LOCAL_ONLY=true, pins included. The caller's fallback
    then routes through the handler's local-only candidate pool (the same
    pool the handler's own pin consumption re-enters).
    """
    try:
        from core.llm.byok_handler import _local_only_blocks_provider

        if _local_only_blocks_provider(provider):
            logger.warning(
                "LOCAL-ONLY: pin %s/%s refused — cloud dispatch is "
                "blocked; the call routes locally instead",
                provider, model)
            return {}
    except Exception:  # noqa: BLE001 — the gate must not break pinning
        pass
    try:
        if workspace_id is None and tenant_id is None:
            handler = llm_service._get_handler()
        else:
            handler = llm_service._get_handler(
                workspace_id=workspace_id, tenant_id=tenant_id)
        if handler is not None and provider in handler.clients:
            policy = getattr(handler, "provider_policy", None)
            if policy is not None and not policy.allows(provider, model):
                logger.warning(
                    "PROVIDER-POLICY: pin %s/%s refused — outside the "
                    "allowed set (revision %s); the caller may fall back "
                    "only within the same policy",
                    provider, model, getattr(policy, "revision", "?"))
                return {}
            return {"provider_model": (provider, model)}
    except Exception:  # noqa: BLE001 — pinning is best-effort by design
        pass
    return {}


def resolve_pinned_provider_model(
    llm_service: Any,
    env_var: str,
    default: str,
    *,
    provider: Optional[str] = None,
    workspace_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve a pin from ``env_var`` as ``"provider:model"``.

    Returns ``{}`` when the env var is unset/malformed, and strips the pin when
    the named provider has no client. ``provider`` (when given) is the fallback
    provider used for a bare model id. ``workspace_id``/``tenant_id`` (when the
    call site has request scope) gate the pin against the SAME handler scope
    the dispatch will use — see :func:`build_provider_model_pin`. Callers
    without request scope keep the previous no-scope behavior.

    Used by pin sites whose model is operator-tunable; the fallback behavior in
    :func:`pinned_structured_call` applies identically whether or not a pin
    resolved.
    """
    import os

    raw = (os.getenv(env_var) or "").strip()
    if not raw:
        if provider and default:
            return build_provider_model_pin(
                llm_service, provider, default,
                workspace_id=workspace_id, tenant_id=tenant_id)
        return {}
    if ":" in raw:
        prov, model = raw.split(":", 1)
        prov, model = prov.strip(), model.strip()
        if prov and model:
            return build_provider_model_pin(
                llm_service, prov, model,
                workspace_id=workspace_id, tenant_id=tenant_id)
        return {}
    if provider:
        return build_provider_model_pin(
            llm_service, provider, raw,
            workspace_id=workspace_id, tenant_id=tenant_id)
    return {}


async def _record_if_cancelled(coro, log_label, task_type, t0,
                               failure=None, failure_capture=None):
    """Await ``coro``; if the CALLER's budget cancelled us, record a
    timeout outcome for the model this call resolved to — cancelled
    planning calls otherwise leave no routing feedback and a
    budget-burning model keeps winning the route (live 2026-09-15/16).

    The cancellation is also published to THIS call's explicit diagnostic
    record (``failure``/``failure_capture``) so a consumer can distinguish a
    deadline from an empty answer without reading any shared state."""
    import time as _time

    try:
        return await coro
    except asyncio.CancelledError as err:
        if failure is not None:
            _mark_cancelled(failure, log_label, err)
            _copy_failure(failure, failure_capture)
        try:
            from core.llm.learning_router_registry import record_timeout_outcome

            model = None
            try:
                from core.llm.model_provenance import get_resolved_model

                model = get_resolved_model()
            except Exception:  # noqa: BLE001 — provenance optional
                model = None
            if model:
                asyncio.get_event_loop().create_task(
                    record_timeout_outcome(
                        str(model), task_type=task_type,
                        elapsed_s=_time.monotonic() - t0))
        except Exception:  # noqa: BLE001 — never block cancellation
            pass
        raise


def _observer_notify(observer: Optional[Any], event: str, **fields: Any) -> None:
    """Best-effort boundary event; diagnostics never break the call."""
    if observer is None:
        return
    try:
        observer(event, **fields)
    except Exception:  # noqa: BLE001 — observation is passive
        pass


def _schema_json(response_model: Any) -> Dict[str, Any]:
    try:
        return response_model.model_json_schema()
    except Exception:  # noqa: BLE001 — observation is passive
        return {}


def _raw_payload(result: Any) -> Any:
    raw = getattr(result, "_raw_response", None)
    if raw is None:
        return None
    try:
        return str(raw)[:24000]
    except Exception:  # noqa: BLE001 — diagnostics only
        return None


def _parsed_payload(result: Any) -> Any:
    try:
        if hasattr(result, "model_dump"):
            return result.model_dump()
        if isinstance(result, dict):
            return result
        return str(result)[:12000]
    except Exception:  # noqa: BLE001
        return None


def _route_snapshot() -> Any:
    """The call-local requested/selected/served route, for the raw journal."""
    try:
        from core.llm.model_provenance import get_route_attribution

        return get_route_attribution()
    except Exception:  # noqa: BLE001 — diagnostics only
        return None


def _capture_provenance(capture: Optional[Dict[str, Any]]) -> None:
    """Write the current call's provenance into a request-owned capture.

    ContextVars are task-local: a caller that awaits this wrapper through
    ``asyncio.wait_for`` (which schedules a child task) cannot read values the
    child set. The capture object is created by the caller and shared across
    the task boundary, so the generation receipt and served route survive
    without a singleton or a handler "last id" fallback.
    """
    if capture is None:
        return
    try:
        from core.llm.model_provenance import get_route_attribution

        attribution = get_route_attribution()
    except Exception:  # noqa: BLE001 — attribution is optional
        attribution = {}
    capture.clear()
    capture.update(dict(attribution or {}))


def routing_snapshot(
    capture: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Business-safe routing view for a consumer's result.

    Ambient ContextVars describe the CURRENT task. When the call ran in a child
    task, ``capture`` (written by :func:`_capture_provenance` in that child)
    is the authoritative attempt provenance. Missing keys stay missing; this
    never substitutes a handler-wide "last id" or another scope.
    """
    try:
        from core.llm.model_provenance import get_route_attribution

        attribution = get_route_attribution()
    except Exception:  # noqa: BLE001 — diagnostics are optional
        attribution = {}
    if not attribution.get("mode"):
        attribution["mode"] = "deterministic"
    if capture:
        for key in (
                "mode", "requested_route", "served_route", "resolved_model",
                "profile", "error", "routing_result_id", "transport"):
            if key in capture:
                attribution[key] = capture[key]
    return attribution


def _usage_payload(result: Any) -> Any:
    """Token usage when the provider exposed it; never inferred."""
    raw = getattr(result, "_raw_response", None)
    usage = getattr(raw, "usage", None)
    if usage is None:
        return None
    values = {}
    for name in (
            "prompt_tokens", "completion_tokens", "total_tokens",
            "input_tokens", "output_tokens"):
        value = getattr(usage, name, None)
        if value is None and isinstance(usage, dict):
            value = usage.get(name)
        if value is not None:
            values[name] = value
    return values or None


def _raw_payload(result: Any) -> Any:
    """Best-effort raw provider completion for the attempt journal."""
    raw = getattr(result, "_raw_response", None)
    if raw is None:
        return None
    try:
        return str(raw)[:12000]
    except Exception:  # noqa: BLE001
        return None


async def pinned_structured_call(
    llm_service: Any,
    *,
    prompt: str,
    response_model: Any,
    system_instruction: str,
    temperature: float = 0.0,
    disable_reasoning: bool = True,
    call_kwargs: Optional[Dict[str, Any]] = None,
    extra_kwargs: Optional[Dict[str, Any]] = None,
    log_label: str = "planning",
    task_type: Optional[str] = None,
    workspace_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    stage: Optional[str] = None,
    attempt_observer: Optional[Any] = None,
    capability_profile: Optional[str] = None,
    provenance: Optional[Dict[str, Any]] = None,
    failure_capture: Optional[Dict[str, Any]] = None,
    strict_pin: Optional[bool] = None,
) -> Any:
    """Structured call that honours a pin, then falls back to unpinned routing.

    Args:
        llm_service: Service exposing ``generate_structured_response``.
        prompt: Structured-output prompt.
        response_model: Pydantic model describing the output.
        system_instruction: System instruction for the call.
        temperature: Sampling temperature (default 0.0 — planning is
            deterministic).
        disable_reasoning: Skip hidden thinking on these small calls.
        call_kwargs: The pin kwargs, typically from
            :func:`build_provider_model_pin`. An empty dict means "no pin" and
            the call is issued once with normal ranked routing.
        extra_kwargs: Additional per-call kwargs forwarded to every attempt.
        log_label: Human-readable label used in log lines.
        task_type: Declares the workload so BPC can rank it appropriately.
            Small-verdict workloads (``"planning"``, ``"extraction"``,
            ``"nl2sql"``, ``"classification"``, ``"routing"``) switch BPC into
            cost-priority mode — rank by price over a quality floor — because
            the answer is a few hundred tokens of JSON where the flash-class
            quality spread is a couple of points while the price spread is
            >2x. Without a task_type these calls use the default
            quality-weighted score and drift onto 2-6x pricier models.

    Returns:
        The parsed ``response_model`` instance, or ``None`` when every attempt
        failed. Never raises — provider errors are logged and converted to
        ``None`` so the caller's own failure contract stays in charge.

        ``provenance`` is a caller-owned mutable mapping. On every return it
        receives the LAST attempt's mode/requested/served route, resolved
        model, profile, error and generation id. The caller reads it after
        awaiting this wrapper, even when the await crossed a child-task
        boundary. It is cleared at entry so a failed call can never reuse an
        older receipt.

        ``failure_capture`` is a caller-owned mutable mapping carrying THIS
        call's failure kind/detail/label. It is cleared at entry and updated
        at exit (including the empty record when the call produced no
        exception), so a caller can read its own diagnostic even when another
        call finished in between.

        A FAILED attempt is not a failed CALL: when the pinned attempt raises
        (or returns nothing) and the unpinned retry then yields a result, the
        terminal record is empty — the rejected pin's error lives in the
        attempt's own observer event. When the retry also produces nothing,
        the last attempt's failure kind is retained, so "fallback empty"
        still reads as a failure.
    """
    # A call's diagnostics are its own: open a fresh record before any
    # provider work, so a previous or overlapping call can neither lend this
    # call its failure nor be erased by it. Only the caller-owned mapping is
    # written; there is no process-wide record.
    failure = _new_failure_record(log_label)
    _copy_failure(failure, failure_capture)

    def _finish_failure() -> None:
        _copy_failure(failure, failure_capture)

    if provenance is not None:
        # Preserve caller-seeded REQUEST facts (mode/requested route/profile):
        # a cancelled child may never reach _capture_provenance, and those
        # facts remain truthful. Clear only RESULT facts so a failed attempt
        # cannot lend an older receipt.
        for _result_key in (
                "served_route", "resolved_model", "routing_result_id",
                "error"):
            provenance.pop(_result_key, None)
    base: Dict[str, Any] = dict(
        prompt=prompt,
        response_model=response_model,
        system_instruction=system_instruction,
        temperature=temperature,
    )
    if disable_reasoning:
        base["disable_reasoning"] = True
    if task_type:
        base["task_type"] = task_type
    # WORKLOAD PROFILE (owner clarification 2026-11-04): the server-coded
    # call label selects a versioned capability contract. Route-only
    # metadata stays out of provider generation kwargs; LLMService consumes
    # and forwards it to BYOK ranking. An explicit profile wins.
    try:
        from core.llm.capability_profiles import resolve_capability_profile

        _profile = resolve_capability_profile(
            capability_profile, task_type, log_label)
        if _profile is not None:
            base["capability_profile"] = _profile.name
    except Exception:  # noqa: BLE001 — legacy callers remain compatible
        pass
    # THE CALLER'S SCOPE (J6 draft finding): a structured call without it
    # resolves the service's frozen constructor scope and never sees the
    # workspace-registered local providers. Both are optional — callers
    # that have no scope keep today's behaviour byte-identically.
    if workspace_id:
        base["workspace_id"] = workspace_id
    if tenant_id:
        base["tenant_id"] = tenant_id
    # PLAN-ATTEMPT ATTRIBUTION (verifier work order, steps 1-2): the
    # dispatch traces carry THIS execution and stage, so per-attempt
    # lines are attributable to one turn's one planning stage — model
    # calls are distinguishable from fresh-data and narration calls.
    if execution_id:
        base["route_trace_id"] = f"{stage or log_label}:{execution_id}"
    if extra_kwargs:
        base.update(extra_kwargs)

    try:
        from core.llm.model_provenance import (
            clear_route_attribution, clear_routing_error,
            get_route_attribution, set_requested_route, set_route_mode,
            set_routing_error, set_routing_profile,
        )

        clear_route_attribution()
        if base.get("capability_profile"):
            try:
                from core.llm.capability_profiles import (
                    resolve_capability_profile,
                )

                _attribute_profile = resolve_capability_profile(
                    base.get("capability_profile"), task_type, log_label)
                if _attribute_profile is not None:
                    set_routing_profile(
                        _attribute_profile.name, _attribute_profile.version)
            except Exception:
                pass
    except Exception:  # noqa: BLE001 — attribution is observational
        get_route_attribution = None  # type: ignore[assignment]
        set_requested_route = set_route_mode = None  # type: ignore[assignment]
        set_routing_error = set_routing_profile = None  # type: ignore[assignment]
        clear_routing_error = None  # type: ignore[assignment]
    pin_kwargs = dict(call_kwargs or {})
    pinned = bool(pin_kwargs.get("provider_model"))
    if set_route_mode is not None:
        set_route_mode("pinned" if pinned else "unpinned")
    if pinned and set_requested_route is not None:
        _pin_route = tuple(pin_kwargs.get("provider_model") or ())
        if len(_pin_route) == 2:
            set_requested_route(_pin_route[0], _pin_route[1])
    # EXPLICIT PROFILE + PIN = STRICT QUALIFICATION PIN (verifier boundary 1).
    # The auto-derived profile used by ordinary employee calls keeps its
    # historical unpinned fallback; an explicit server qualification profile
    # is exact-route-or-failure. It never escapes on exception, None,
    # timeout or malformed output. A caller may also force strictness
    # directly (``strict_pin=True``) for an evidence-pinned graduation route
    # whose profile is resolved by the call label; ``None`` keeps the
    # historical behavior byte-identically.
    strict_pin = bool(pinned) and (
        bool(capability_profile) if strict_pin is None else bool(strict_pin))

    _t0 = _time.monotonic()
    _pinned_attempt = 0
    _pinned_started = _time.monotonic()
    if pinned:
        _pinned_attempt = 1
        _observer_notify(
            attempt_observer, "dispatch", label=log_label, attempt=1,
            route="pinned", prompt=prompt, prompt_chars=len(prompt),
            system_instruction=system_instruction,
            response_model=getattr(response_model, "__name__", str(response_model)),
            response_schema=_schema_json(response_model),
            temperature=temperature, extra=dict(extra_kwargs or {}))
        try:
            result = await _record_if_cancelled(
                llm_service.generate_structured_response(
                    **base, **pin_kwargs),
                log_label, task_type, _t0, failure, failure_capture)
        except Exception as pinned_err:  # noqa: BLE001
            _observer_notify(
                attempt_observer, "failure", label=log_label, attempt=1,
                route="pinned", seconds=_time.monotonic() - _pinned_started,
                exception=pinned_err)
            _publish_failure(log_label, pinned_err, failure)
            if strict_pin:
                if set_routing_error is not None:
                    _kind = "no_suitable_configured_model" if (
                        "nosuitableconfiguredmodelerror"
                        in type(pinned_err).__name__.lower()
                    ) else "provider_failure"
                    set_routing_error(_kind, str(pinned_err))
                logger.warning(
                    "%s strict qualification pin (%s) raised (%s): %s — "
                    "no unpinned fallback",
                    log_label, pin_kwargs.get("provider_model"),
                    type(pinned_err).__name__, pinned_err)
                _capture_provenance(provenance)
                _finish_failure()
                return None
            logger.warning(
                "%s pinned call raised (%s): %s — retrying unpinned",
                log_label,
                pin_kwargs.get("provider_model"),
                pinned_err,
            )
            if clear_routing_error is not None:
                clear_routing_error()
            result = None
        if result is not None:
            _observer_notify(
                attempt_observer, "parsed", label=log_label, attempt=1,
                route="pinned",
                seconds=_time.monotonic() - _pinned_started,
                usage=_usage_payload(result),
                routing=_route_snapshot(),
                parsed=_parsed_payload(result), raw=_raw_payload(result))
            _mark_success(failure)
            _capture_provenance(provenance)
            _finish_failure()
            return result
        _observer_notify(
            attempt_observer, "no_result", label=log_label, attempt=1,
            route="pinned", seconds=_time.monotonic() - _pinned_started,
            failure=dict(failure))
        if strict_pin:
            if set_routing_error is not None:
                set_routing_error(
                    "provider_failure",
                    "the qualification pin produced no usable result")
            logger.warning(
                "%s strict qualification pin (%s) returned no result — "
                "failed qualification attempt, no unpinned fallback",
                log_label, pin_kwargs.get("provider_model"))
            _capture_provenance(provenance)
            _finish_failure()
            return None
        logger.info(
            "%s pinned call (%s) returned no result — retrying unpinned "
            "across the workspace's configured providers",
            log_label,
            pin_kwargs.get("provider_model"),
        )
        # EXCLUDE THE FAILED PIN (2026-09-29 live, fork 91fedfd1): the
        # pinned route had just failed deterministically (output truncated
        # at max_tokens — a per-route, per-cap failure that repeats), and
        # the unpinned fallback re-ranked the SAME route to the top and
        # repeated the failure until the plan budget died. A failed pin is
        # evidence about that ROUTE, not about the pool: exclude it from
        # the fallback so the cascade lands on a different model.
        if set_route_mode is not None:
            set_route_mode("unpinned_fallback")
        fallback_kwargs = dict(base)
        _failed_pin = pin_kwargs.get("provider_model")
        if _failed_pin:
            fallback_kwargs["exclude_provider_model"] = _failed_pin
        _observer_notify(
            attempt_observer, "dispatch", label=log_label, attempt=2,
            route="unpinned_fallback", prompt=prompt, prompt_chars=len(prompt),
            system_instruction=system_instruction,
            response_model=getattr(response_model, "__name__", str(response_model)),
            response_schema=_schema_json(response_model),
            temperature=temperature, extra=dict(extra_kwargs or {}))
        _fallback_started = _time.monotonic()
        try:
            fallback_result = await _record_if_cancelled(
                llm_service.generate_structured_response(**fallback_kwargs),
                log_label, task_type, _t0, failure, failure_capture)
            if fallback_result is not None:
                # The pin's failure was per-ATTEMPT, not the call's outcome:
                # a successful retry must not leave the caller's capture
                # reporting the discarded route as a terminal failure.
                _mark_success(failure)
                if clear_routing_error is not None:
                    clear_routing_error()
                _observer_notify(
                    attempt_observer, "parsed", label=log_label, attempt=2,
                    route="unpinned_fallback",
                    seconds=_time.monotonic() - _fallback_started,
                    usage=_usage_payload(fallback_result),
                    routing=_route_snapshot(),
                    parsed=_parsed_payload(fallback_result),
                    raw=_raw_payload(fallback_result))
            elif set_routing_error is not None:
                set_routing_error(
                    "provider_failure",
                    "the configured routes produced no usable result")
            if fallback_result is None:
                _observer_notify(
                    attempt_observer, "no_result", label=log_label,
                    attempt=2, route="unpinned_fallback",
                    seconds=_time.monotonic() - _fallback_started,
                    failure=dict(failure))
            _capture_provenance(provenance)
            _finish_failure()
            return fallback_result
        except Exception as unpinned_err:  # noqa: BLE001
            _observer_notify(
                attempt_observer, "failure", label=log_label, attempt=2,
                route="unpinned_fallback",
                seconds=_time.monotonic() - _fallback_started,
                exception=unpinned_err)
            _publish_failure(log_label, unpinned_err, failure)
            if set_routing_error is not None:
                _kind = "no_suitable_configured_model" if (
                    "nosuitableconfiguredmodelerror"
                    in type(unpinned_err).__name__.lower()
                ) else "provider_failure"
                set_routing_error(_kind, str(unpinned_err))
            logger.warning("%s unpinned retry raised: %s", log_label, unpinned_err)
            _capture_provenance(provenance)
            _finish_failure()
            return None

    _observer_notify(
        attempt_observer, "dispatch", label=log_label, attempt=1,
        route="unpinned", prompt=prompt, prompt_chars=len(prompt),
        system_instruction=system_instruction,
        response_model=getattr(response_model, "__name__", str(response_model)),
        response_schema=_schema_json(response_model),
        temperature=temperature, extra=dict(extra_kwargs or {}))
    _direct_started = _time.monotonic()
    try:
        direct_result = await _record_if_cancelled(
            llm_service.generate_structured_response(**base),
            log_label, task_type, _t0, failure, failure_capture)
        if direct_result is not None:
            _observer_notify(
                attempt_observer, "parsed", label=log_label, attempt=1,
                route="unpinned",
                seconds=_time.monotonic() - _direct_started,
                usage=_usage_payload(direct_result),
                routing=_route_snapshot(),
                parsed=_parsed_payload(direct_result),
                raw=_raw_payload(direct_result))
            _mark_success(failure)
        else:
            _observer_notify(
                attempt_observer, "no_result", label=log_label, attempt=1,
                route="unpinned",
                seconds=_time.monotonic() - _direct_started,
                failure=dict(failure))
        _capture_provenance(provenance)
        _finish_failure()
        return direct_result
    except Exception as err:  # noqa: BLE001
        _observer_notify(
            attempt_observer, "failure", label=log_label, attempt=1,
            route="unpinned", seconds=_time.monotonic() - _direct_started,
            exception=err)
        _publish_failure(log_label, err, failure)
        if set_routing_error is not None:
            name = type(err).__name__.lower()
            text = str(err).lower()
            if "scop" in name or "workspace resolution" in text:
                code = "scope_unresolved"
            elif "nosuitableconfiguredmodel" in name:
                code = "no_suitable_configured_model"
            elif "timeout" in name or "cancel" in name:
                code = "deadline_cancelled"
            else:
                code = "provider_failure"
            set_routing_error(code, str(err))
        logger.warning("%s call raised: %s", log_label, err)
        _capture_provenance(provenance)
        _finish_failure()
        return None
