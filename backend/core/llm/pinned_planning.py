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

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def build_provider_model_pin(
    llm_service: Any,
    provider: str,
    model: str,
) -> Dict[str, Any]:
    """Return the kwargs dict carrying a pin, or ``{}`` when unavailable.

    Mirrors the long-standing planner convention: the pin is only meaningful if
    that provider actually has a client in the handler (otherwise the pin names
    a provider this workspace cannot call at all and the first attempt is
    guaranteed to fail, paying a full round trip for nothing).
    """
    try:
        if provider in llm_service._get_handler().clients:
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
) -> Dict[str, Any]:
    """Resolve a pin from ``env_var`` as ``"provider:model"``.

    Returns ``{}`` when the env var is unset/malformed, and strips the pin when
    the named provider has no client. ``provider`` (when given) is the fallback
    provider used for a bare model id.

    Used by pin sites whose model is operator-tunable; the fallback behavior in
    :func:`pinned_structured_call` applies identically whether or not a pin
    resolved.
    """
    import os

    raw = (os.getenv(env_var) or "").strip()
    if not raw:
        if provider and default:
            return build_provider_model_pin(llm_service, provider, default)
        return {}
    if ":" in raw:
        prov, model = raw.split(":", 1)
        prov, model = prov.strip(), model.strip()
        if prov and model:
            return build_provider_model_pin(llm_service, prov, model)
        return {}
    if provider:
        return build_provider_model_pin(llm_service, provider, raw)
    return {}


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
    """
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
    if extra_kwargs:
        base.update(extra_kwargs)

    pin_kwargs = dict(call_kwargs or {})
    pinned = bool(pin_kwargs.get("provider_model"))

    if pinned:
        try:
            result = await llm_service.generate_structured_response(
                **base, **pin_kwargs
            )
        except Exception as pinned_err:  # noqa: BLE001
            logger.warning(
                "%s pinned call raised (%s): %s — retrying unpinned",
                log_label,
                pin_kwargs.get("provider_model"),
                pinned_err,
            )
            result = None
        if result is not None:
            return result
        logger.info(
            "%s pinned call (%s) returned no result — retrying unpinned "
            "across the workspace's configured providers",
            log_label,
            pin_kwargs.get("provider_model"),
        )
        try:
            return await llm_service.generate_structured_response(**base)
        except Exception as unpinned_err:  # noqa: BLE001
            logger.warning("%s unpinned retry raised: %s", log_label, unpinned_err)
            return None

    try:
        return await llm_service.generate_structured_response(**base)
    except Exception as err:  # noqa: BLE001
        logger.warning("%s call raised: %s", log_label, err)
        return None
