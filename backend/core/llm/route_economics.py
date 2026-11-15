"""Trusted current route economics for repeat-task selection.

The graduation comparator answers a capability/identity question: which
routes have fresh, same-benchmark evidence that meets the receipt baseline?
It deliberately does not rank by price.

This module supplies the separate, advisory economics half used by the
existing capability profile (``employee_evidence_selection`` is
``preference="economy"``). It never decides eligibility: the caller passes
only the comparator's sufficient ranked cohort, and the profile's evidence
quarantine/quality floor still applies.

Cost contract
-------------
* Only an explicit configured per-token estimate is ``known``. It is computed
  from the EXISTING pricing authority with explicit input/output token
  quantities (``DynamicPricingFetcher.estimate_cost``); this is not a 1:1
  token blend and it is not a settlement/liability claim.
* Missing, subscription/flat-rate, negative, NaN/infinite, boolean or
  malformed cost is ``unknown``. Unknown is never treated as free. A true
  explicit zero rate is a known free route.
* The pricing catalog's OpenCode Zen entries are subscription list prices, not
  actual subscription charges; they stay ``unknown`` for selection. If the
  authority/production caller cannot establish a per-token price, the route
  keeps the comparator's safe evidence order with an explicit unknown reason.

The final budget/physical-attempt admission remains the BYOK hard-stop
authority. This module only orders already evidence-eligible candidates; it
never raises a cap, reserves spend, calls a provider or infers quality from
price.
"""
from __future__ import annotations

import json
import logging
import math
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

KNOWN = "known"
UNKNOWN = "unknown"

#: Same output reservation the employee work-proposal call already uses.
#: Callers may override; the quantity is explicit in the decision trace.
DEFAULT_ECONOMIC_OUTPUT_TOKENS = 1800

#: Existing pricing-catalog source that denotes an OpenCode subscription
#: list price, not a per-token charge. It is a pricing-source classification,
#: never a model allow/deny list.
_SUBSCRIPTION_PRICING_SOURCES = frozenset({"opencode-zen"})
_SUBSCRIPTION_PRICING_PROVIDERS = frozenset({"opencode-go"})


def route_key(provider: Any, model: Any) -> Tuple[str, str]:
    return str(provider or "").strip(), str(model or "").strip()


def _provider_identity(value: Any) -> str:
    """Existing registry provider normalization, or "" when unavailable."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        from core.llm.registry.transformers import normalize_provider

        return str(normalize_provider(text) or "").strip().lower()
    except Exception:  # noqa: BLE001 — no provider identity, no quote
        return text.casefold()


def _model_identity(value: Any) -> str:
    return str(value or "").strip().casefold()


def _valid_cost(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        cost = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(cost) or cost < 0:
        return None
    return cost


def _positive_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def unknown_economics(
    provider: Any,
    model: Any,
    *,
    reason: str = "cost_unknown",
    basis: str = "unknown",
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "schema": "atom-route-economics-1",
        "provider": str(provider or "").strip(),
        "model": str(model or "").strip(),
        "state": UNKNOWN,
        "cost": None,
        "currency": "USD",
        "basis": basis,
        "reason": reason,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "advisory": True,
    }


def normalize_economics(
    raw: Any,
    provider: Any = None,
    model: Any = None,
) -> Dict[str, Any]:
    """Validate one caller-supplied economics record.

    A malformed or contradictory record is unknown, never free. An explicit
    ``state="unknown"`` stays unknown even if a numeric cost was also supplied.
    """
    route_provider = str(provider or "").strip()
    route_model = str(model or "").strip()
    if not isinstance(raw, Mapping):
        return unknown_economics(route_provider, route_model,
                                 reason="cost_unknown")
    raw_provider = str(raw.get("provider") or "").strip()
    raw_model = str(raw.get("model") or "").strip()
    # Cost identity is atomic. When the caller asks about a specific route,
    # a body naming a different provider/model is not that route's cost, even
    # if the mapping key matched. Missing body members may use the exact
    # requested key (the trusted internal mapping contract).
    if route_provider and raw_provider and (
            _provider_identity(raw_provider)
            != _provider_identity(route_provider)):
        return unknown_economics(
            route_provider, route_model,
            reason="route_identity_mismatch", basis="identity_mismatch")
    if route_model and raw_model and (
            _model_identity(raw_model) != _model_identity(route_model)):
        return unknown_economics(
            route_provider, route_model,
            reason="route_identity_mismatch", basis="identity_mismatch")
    route_provider = route_provider or raw_provider
    route_model = route_model or raw_model
    state = str(raw.get("state") or "").strip().lower()
    reason = str(raw.get("reason") or "").strip() or None
    basis = str(raw.get("basis") or "").strip() or "unknown"
    input_tokens = _positive_int(raw.get("input_tokens"))
    output_tokens = _positive_int(raw.get("output_tokens"))
    cost = _valid_cost(raw.get("cost"))
    if state == UNKNOWN:
        return unknown_economics(
            route_provider, route_model,
            reason=reason or "cost_unknown", basis=basis,
            input_tokens=input_tokens, output_tokens=output_tokens)
    if cost is None:
        reason = (
            "invalid_cost"
            if raw.get("cost") is not None
            else (reason or "cost_unknown"))
        return unknown_economics(
            route_provider, route_model, reason=reason, basis=basis,
            input_tokens=input_tokens, output_tokens=output_tokens)
    return {
        "schema": "atom-route-economics-1",
        "provider": route_provider,
        "model": route_model,
        "state": KNOWN,
        "cost": cost,
        "currency": str(raw.get("currency") or "USD"),
        "basis": basis,
        "reason": None,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "advisory": True,
    }


def _pricing_is_subscription(
    pricing: Mapping[str, Any], route_provider: str = "",
) -> bool:
    source = str(pricing.get("source") or "").strip().lower()
    pricing_provider = str(
        pricing.get("litellm_provider") or "").strip().lower()
    route_provider = str(route_provider or "").strip().lower()
    return (
        source in _SUBSCRIPTION_PRICING_SOURCES
        or pricing_provider in _SUBSCRIPTION_PRICING_PROVIDERS
        or route_provider in _SUBSCRIPTION_PRICING_PROVIDERS
    )


def resolve_configured_economics(
    routes: Sequence[Mapping[str, Any]],
    *,
    task_text: str,
    output_tokens: int = DEFAULT_ECONOMIC_OUTPUT_TOKENS,
    pricing_fetcher: Any = None,
    input_tokens: Optional[int] = None,
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Resolve configured per-token estimates for already eligible routes.

    Token quantities are explicit and common to every route, so the relative
    ordering is a like-for-like estimate. Missing token basis or pricing is
    unknown, never zero. Never raises.
    """
    from core.llm.prompt_budget import count_tokens

    estimated_tokens = False
    if input_tokens is None:
        try:
            input_tokens, estimated_tokens = count_tokens(task_text)
        except Exception:  # noqa: BLE001 — measurement, not a gate
            input_tokens = 0
    input_tokens = _positive_int(input_tokens)
    output_tokens = _positive_int(output_tokens)
    resolved: Dict[Tuple[str, str], Dict[str, Any]] = {}
    if not input_tokens or not output_tokens:
        reason = "workload_tokens_unavailable"
        for route in routes or []:
            key = route_key(route.get("provider"), route.get("model"))
            resolved[key] = unknown_economics(
                key[0], key[1], reason=reason,
                basis="workload_tokens_unavailable",
                input_tokens=input_tokens, output_tokens=output_tokens)
        return resolved
    if pricing_fetcher is None:
        try:
            from core.dynamic_pricing_fetcher import get_pricing_fetcher

            pricing_fetcher = get_pricing_fetcher()
        except Exception as exc:  # noqa: BLE001 — unknown, not free
            logger.debug("route economics pricing authority unavailable: %s", exc)
            pricing_fetcher = None
    for route in routes or []:
        provider, model = route_key(
            route.get("provider"), route.get("model"))
        if not provider or not model:
            resolved[(provider, model)] = unknown_economics(
                provider, model, reason="provider_or_model_missing",
                basis="identity_unavailable",
                input_tokens=input_tokens, output_tokens=output_tokens)
            continue
        if pricing_fetcher is None:
            resolved[(provider, model)] = unknown_economics(
                provider, model, reason="pricing_authority_unavailable",
                basis="pricing_authority_unavailable",
                input_tokens=input_tokens, output_tokens=output_tokens)
            continue
        try:
            pricing = pricing_fetcher.get_model_price(model)
        except Exception as exc:  # noqa: BLE001 — unknown, not free
            logger.debug("route economics price lookup failed for %s: %s",
                         model, exc)
            pricing = None
        if not isinstance(pricing, Mapping):
            resolved[(provider, model)] = unknown_economics(
                provider, model, reason="pricing_unavailable",
                basis="configured_per_token_estimate",
                input_tokens=input_tokens, output_tokens=output_tokens)
            continue
        if _pricing_is_subscription(pricing, provider):
            resolved[(provider, model)] = unknown_economics(
                provider, model,
                reason="subscription_cost_unknown",
                basis="subscription_list_price_not_charge",
                input_tokens=input_tokens, output_tokens=output_tokens)
            continue
        pricing_provider = str(
            pricing.get("litellm_provider") or "").strip()
        if not pricing_provider:
            resolved[(provider, model)] = unknown_economics(
                provider, model,
                reason="provider_price_unbound",
                basis="configured_per_token_estimate",
                input_tokens=input_tokens, output_tokens=output_tokens)
            continue
        if (_provider_identity(pricing_provider)
                != _provider_identity(provider)):
            resolved[(provider, model)] = unknown_economics(
                provider, model,
                reason="provider_price_mismatch",
                basis="configured_per_token_estimate",
                input_tokens=input_tokens, output_tokens=output_tokens)
            continue
        try:
            cost = pricing_fetcher.estimate_cost(
                model, input_tokens, output_tokens)
        except Exception as exc:  # noqa: BLE001 — unknown, not free
            logger.debug("route economics cost estimate failed for %s: %s",
                         model, exc)
            cost = None
        if cost is None:
            resolved[(provider, model)] = unknown_economics(
                provider, model, reason="pricing_unavailable",
                basis="configured_per_token_estimate",
                input_tokens=input_tokens, output_tokens=output_tokens)
            continue
        normalized = normalize_economics({
            "provider": provider,
            "model": model,
            "state": KNOWN,
            "cost": cost,
            "currency": "USD",
            "basis": "configured_per_token_estimate",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        })
        if normalized["state"] != KNOWN:
            normalized["reason"] = "invalid_cost"
            normalized["basis"] = "configured_per_token_estimate"
        resolved[(provider, model)] = normalized
    if estimated_tokens:
        for economics in resolved.values():
            economics["tokens_estimated"] = True
    return resolved


def workload_text(assignment: Any) -> str:
    """A bounded, server-owned task text used only for token accounting.

    The same text is used for every candidate, so it cannot advantage one
    route. It is not an evidence claim and never becomes a benchmark input.
    """
    if not isinstance(assignment, Mapping):
        return ""
    scope = assignment.get("workload_scope")
    fields = {
        "objective": assignment.get("objective"),
        "workload_scope": scope,
    }
    try:
        return json.dumps(fields, sort_keys=True, default=str)[:12000]
    except Exception:  # noqa: BLE001 — accounting must not gate routing
        return str(assignment.get("objective") or "")[:12000]


def provider_for_assignment(
    assignment: Any,
    *,
    output_tokens: int = DEFAULT_ECONOMIC_OUTPUT_TOKENS,
    pricing_fetcher: Any = None,
):
    """Return an economics provider for one durable assignment.

    The provider accepts the comparator's ranked route items and returns the
    route-keyed economics mapping consumed by
    :func:`core.llm.graduation_route.resolve_repeat_task_route`.
    """
    task_text = workload_text(assignment)

    def _provider(routes: Sequence[Mapping[str, Any]]):
        return resolve_configured_economics(
            routes,
            task_text=task_text,
            output_tokens=output_tokens,
            pricing_fetcher=pricing_fetcher,
        )

    return _provider


def economics_for_route(
    economics: Mapping[Any, Mapping[str, Any]],
    provider: Any,
    model: Any,
) -> Dict[str, Any]:
    """Look one route up in an economics mapping, normalizing the result."""
    key = route_key(provider, model)
    if key in economics:
        return normalize_economics(economics[key], key[0], key[1])
    text_key = f"{key[0]}/{key[1]}"
    if text_key in economics:
        return normalize_economics(economics[text_key], key[0], key[1])
    return unknown_economics(key[0], key[1], reason="cost_unknown")


def rank_with_profile(
    profile: Any,
    candidates: Sequence[Mapping[str, Any]],
    *,
    evidence: Optional[Mapping[str, Mapping[str, Any]]] = None,
    preference: Optional[str] = None,
) -> Dict[str, Any]:
    """Filter through the existing profile, then expose the economic trace.

    The shared preference implementation lives in
    :func:`core.llm.capability_profiles.select_profile_candidates`; this
    module only supplies explicit known/unknown cost state and the audit
    summary. The profile remains the eligibility/quarantine/quality authority.
    """
    from core.llm.capability_profiles import select_profile_candidates

    prepared: List[Dict[str, Any]] = []
    for index, raw in enumerate(candidates or []):
        candidate = dict(raw)
        candidate["evidence_order"] = index
        if "cost_state" not in candidate:
            explicit_cost = _valid_cost(candidate.get("cost"))
            candidate["cost_state"] = (
                KNOWN if explicit_cost is not None else UNKNOWN)
            candidate["cost_reason"] = (
                None if explicit_cost is not None else "cost_unknown")
            candidate["cost_basis"] = (
                candidate.get("cost_basis") or "unknown")
        else:
            candidate.setdefault("cost_reason", None)
            candidate.setdefault("cost_basis", "unknown")
        prepared.append(candidate)
    mode = str(preference or getattr(profile, "preference", "economy"))
    selection = select_profile_candidates(
        profile, prepared, evidence=evidence or {}, preference=mode)
    ranked = list(selection.get("ranked") or [])
    known = [c for c in ranked if c.get("cost_state") == KNOWN]
    unknown = [c for c in ranked if c.get("cost_state") != KNOWN]
    if selection.get("outcome") != "selected":
        basis = "no_profile_eligible_candidate"
        reason = selection.get("selection_reason")
    elif mode == "quality":
        basis = "quality_preference_known_cost_tiebreak"
        reason = "explicit quality preference among eligible routes"
    elif known and unknown:
        basis = "known_cost_then_unknown_evidence_order"
        reason = (
            "lowest known expected cost among eligible routes; unknown-cost "
            "routes follow in evidence order")
    elif known:
        basis = "lowest_known_expected_cost"
        reason = "lowest known expected cost among eligible routes"
    else:
        basis = "evidence_order_unknown_cost"
        reason = (
            "current route cost is unknown for every eligible route; the "
            "comparator's evidence order is preserved")
    selection["selection_reason"] = reason
    selection["economics"] = {
        "preference": mode,
        "known_routes": [
            {
                "provider": c.get("provider"), "model": c.get("model"),
                "cost": c.get("effective_cost"),
                "basis": c.get("cost_basis"),
            }
            for c in known
        ],
        "unknown_routes": [
            {
                "provider": c.get("provider"), "model": c.get("model"),
                "reason": c.get("cost_reason"),
                "basis": c.get("cost_basis"),
            }
            for c in unknown
        ],
        "selection_basis": basis,
    }
    return selection
