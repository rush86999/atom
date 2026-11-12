"""Runtime repeat-task route resolution from durable graduation evidence.

This is the dispatch-side bridge that was missing between the verified
comparator (:mod:`core.llm.model_evidence_comparison`) and the durable
qualification receipt (:mod:`core.agent_graduation_service`). It answers one
question at runtime: is there a receipt-anchored, evidence-eligible route for
this repeated task, and if not, what supervises instead?

Contract (acceptance handoff ``GRADUATION_RUNTIME_HANDOFF.md``):

* The receipt and its benchmark/serving-route binding are read from durable
  state and revalidated fail-closed; caller-supplied scope, benchmark claims
  and route eligibility are never trusted. The baseline is the committed
  promotion transition into the agent's current tier plus the durable
  receipt it binds (:func:`resolve_runtime_qualification_baseline`), so a
  promoted agent keeps its verified tier baseline without relaxing the
  pre-transition promotion gate.
* Route evidence is only the validated reserved ``benchmark_evidence``
  records the server-side campaign producer wrote
  (:func:`load_repeat_task_evidence`); generic execution metadata is never
  benchmark authority and a caller-injected or altered record is discarded,
  never scored.
* The current assignment's server-derived workload identity must match the
  receipt binding's workload scope before any route is selected
  (:func:`assignment_workload_identity`); an unrelated or unknown workload
  never inherits the receipt baseline.
* A baseline (the original serving model from the receipt binding) must be
  established, and the actual candidate needs fresh passing evidence on the
  SAME benchmark (dataset hash, rubric, task scope) that meets it.
* The structured qualification pin (:func:`build_provider_model_pin`) and the
  existing capability profile (:func:`select_profile_candidates`) filter every
  provider attempt; a pinned graduation call is strict (exact route or
  failure) so an unqualified fallback can never be dispatched.
* A missing or conflicting provider response identity makes the result
  ineligible for autonomous use; the normal supervised path applies.
* Before an irreversible effect the fresh evidence and the owner's existing
  autonomy gate (:func:`gate_for_topic`, called by the executor) are
  revalidated.

This module never calls a provider itself and never authorizes an effect; it
produces decisions and lets the existing executor/approval machinery act.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.llm.model_evidence_comparison import (
    COMPARED,
    compare_model_evidence,
    task_scope_digest,
)
from core.llm.model_provenance import normalize_model_family

logger = logging.getLogger(__name__)

#: Capability profile whose workload floor filters a graduation route before
#: an attempt. The employee work-proposal stage resolves to this profile via
#: its call label, so the filter uses the SAME workload contract as dispatch.
ROUTE_PROFILE = "employee_evidence_selection"

#: Decision-log kind for durable repeat-task route decisions. The assignment
#: executor's effect gate looks for this kind when revalidating.
ROUTE_DECISION_KIND = "repeat_task_route"

STATE_PINNED = "pinned"
STATE_SUPERVISED = "supervised"
STATE_UNROUTED = "unrouted"

IDENTITY_VERIFIED = "verified"
IDENTITY_MISSING = "missing"
IDENTITY_CONFLICT = "conflict"

_UNKNOWN_BUILD_TOKENS = frozenset(
    {
        "",
        "auto",
        "default",
        "unknown",
        "none",
        "null",
        "n/a",
    }
)

#: Alias tags that name the same callable route rather than a concrete build.
#: Mirrors the benchmark producer's build/route distinction; kept local so the
#: runtime consumer does not depend on a private producer helper.
_ALIAS_BUILD_TAGS = frozenset({"free", "preview", "latest"})


def _identity_text(value: Any) -> Optional[str]:
    """A concrete identity string, or ``None`` for an alias/unknown value."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.casefold() in _UNKNOWN_BUILD_TOKENS:
        return None
    return text


def _model_key(value: Any) -> str:
    """Provider-prefix/case-insensitive key for exact build comparison."""
    text = str(value or "").strip().casefold()
    return text.split("/", 1)[-1] if text else ""


def _is_concrete_build(value: Any) -> bool:
    """True when ``value`` names a dated/snapshot build, not a route alias.

    ``gpt-5.4-2026-03`` is a build; ``gpt-5.4`` and ``gpt-5.4-latest`` are
    callable route labels for that family. Variant tiers stay distinct because
    the normalized family keeps them.
    """
    text = _identity_text(value)
    if text is None:
        return False
    name = text.casefold().split("/", 1)[-1]
    tokens = [token for token in re.split(r"[-_:\s]+", name) if token]
    without_alias_tags = "-".join(
        token for token in tokens if token not in _ALIAS_BUILD_TAGS)
    return normalize_model_family(text) != without_alias_tags


# --- Durable evidence loader ---


def load_repeat_task_evidence(db: Any, agent: Any) -> List[Dict[str, Any]]:
    """Validated campaign-writer benchmark records for one agent.

    Benchmark evidence is the reserved ``benchmark_evidence`` block of
    ``AgentExecution.metadata_json`` that the server-side campaign producer
    (:mod:`core.employee_benchmark_evidence`) wrote and digest-sealed: the
    frozen workload identity, the authoritative execution completion time,
    the accepted callable ``(provider, model)`` route and the provider build
    echo it was served by. The canonical reader
    (:func:`inspect_employee_benchmark_evidence`) revalidates every record —
    producer authority, record/core digests, canonical scope digest and the
    server-controlled registry pin — before anything is returned.

    Generic execution metadata is never authority: a row's free
    ``passed``/``accuracy``/``verdict``, its ``benchmark_identity`` or a
    caller-injected ``benchmark_evidence`` value fails the record
    digest/authority checks and is discarded, never scored. The served
    identity comes from the record's own provider-echoed ``served_identity``;
    the callable route stays the comparison identity and the provider build
    rides separately as ``resolved_model``. Requested or attempted routes are
    never read.

    Scope checks are preserved: rows outside the agent's tenant/workspace
    are skipped, and a record whose embedded execution material does not
    match the durable row it was read from is not evidence. The comparator
    still enforces scope/rubric/freshness matching on everything that is
    returned.
    """
    from core.employee_benchmark_evidence import (
        evidence_comparison_record,
        inspect_employee_benchmark_evidence,
    )
    from core.models import AgentExecution
    from core.personal_scope import resolve_tenant_id, resolve_workspace_id

    tenant_id = resolve_tenant_id(agent)
    workspace_id = resolve_workspace_id(agent)
    rows: List[Dict[str, Any]] = []
    records = (
        db.query(AgentExecution)
        .filter(AgentExecution.agent_id == str(agent.id))
        .order_by(AgentExecution.completed_at.desc(), AgentExecution.started_at.desc())
        .limit(200)
        .all()
    )
    for record in records:
        record_tenant = str(getattr(record, "tenant_id", None) or "")
        record_workspace = str(getattr(record, "workspace_id", None) or "")
        if tenant_id and record_tenant and record_tenant != str(tenant_id):
            continue
        if (
            workspace_id
            and record_workspace
            and (record_workspace != str(workspace_id))
        ):
            continue
        metadata = getattr(record, "metadata_json", None)
        if not isinstance(metadata, Mapping):
            continue
        inspection = inspect_employee_benchmark_evidence(metadata)
        for rejected in inspection["rejected"]:
            logger.info(
                "repeat-task route: discarded invalid benchmark record "
                "%s from execution %s (%s)",
                rejected.get("evidence_id"),
                getattr(record, "id", None),
                rejected.get("reasons"),
            )
        row_agent = str(getattr(record, "agent_id", None) or "")
        record_id = str(getattr(record, "id", None) or "")
        for validated in inspection["records"]:
            execution = validated.get("execution")
            execution = execution if isinstance(execution, Mapping) else {}
            # The record must be bound to exactly this durable row, in the
            # agent's scope; anything else is not this row's evidence.
            if str(execution.get("id") or "") != record_id:
                continue
            if str(execution.get("agent_id") or "") != row_agent:
                continue
            if tenant_id and str(
                    execution.get("tenant_id") or "") != str(tenant_id):
                continue
            if workspace_id and str(
                    execution.get("workspace_id") or "") != str(workspace_id):
                continue
            rows.append(evidence_comparison_record(validated))
    return rows


# --- Receipt/binding resolution ---


def assignment_workload_identity(assignment: Any) -> Any:
    """The current assignment's server-derived workload identity, or None.

    Only the durable assignment plan the server itself composed and
    persisted (the task lifecycle record) is consulted, through its
    server-owned ``workload_scope`` field. Nothing from the dispatch-time
    request is read here: a caller cannot hand a scope to the resolver, and
    an assignment recorded without a workload scope stays unknown. No
    identity is invented from free text or from the receipt — an unknown
    workload must not inherit the receipt baseline, so unknown stays
    unknown and the caller supervises.
    """
    if not isinstance(assignment, Mapping):
        return None
    raw = assignment.get("workload_scope")
    if raw is None:
        return None
    from core.agent_graduation_service import (
        _binding_scope as canonical_scope,
        _binding_text as binding_text,
    )

    if isinstance(raw, Mapping):
        # Canonical reduction, identical to the receipt binding's scope
        # reducer: unknown keys cannot broaden the recorded contract.
        return canonical_scope(dict(raw))
    return binding_text(raw)


def _workload_scopes_match(binding_scope: Any, assignment_scope: Any) -> bool:
    """Exact canonical match between the receipt binding and the assignment.

    A mapping scope matches by the shared canonical task-scope digest; a
    string scope matches only another identical string. Cross-type shapes
    are a mismatch, never an equivalence.
    """
    if isinstance(binding_scope, str) or isinstance(assignment_scope, str):
        return (
            isinstance(binding_scope, str)
            and isinstance(assignment_scope, str)
            and binding_scope.strip() == assignment_scope.strip()
        )
    if not (
        isinstance(binding_scope, Mapping)
        and isinstance(assignment_scope, Mapping)
    ):
        return False
    try:
        return task_scope_digest(
            dict(binding_scope)) == task_scope_digest(dict(assignment_scope))
    except Exception:  # noqa: BLE001 — incomparable shapes are a mismatch
        return False


def _binding_routes(binding: Mapping[str, Any]) -> List[Dict[str, str]]:
    routes = []
    for route in binding.get("serving_routes") or []:
        if not isinstance(route, Mapping):
            continue
        provider = str(route.get("provider") or "").strip()
        model = str(route.get("model") or "").strip()
        if provider and model:
            routes.append({"provider": provider, "model": model})
    return routes


def _resolve_baseline(
    binding_routes: Sequence[Mapping[str, Any]],
    evidence_rows: Sequence[Mapping[str, Any]],
) -> Optional[Dict[str, str]]:
    """Nominate the graduation baseline route from validated writer records.

    The receipt binding may name several actually-served routes; the baseline
    is the one with the strongest newest passing observation (accuracy, then
    recency, then stable order). The comparator still re-establishes the
    baseline on the same dataset/rubric/scope; a nomination without such a
    passing observation blocks selection rather than being trusted.
    """
    best: Optional[Tuple[float, str, str, str]] = None
    for route in binding_routes:
        provider = str(route.get("provider") or "")
        model = str(route.get("model") or "")
        passing = [
            row
            for row in evidence_rows
            if str(row.get("provider") or "") == provider
            and str(row.get("model") or "") == model
            and row.get("passed") is True
        ]
        if not passing:
            continue
        newest = max(
            passing,
            key=lambda row: (
                str(row.get("observed_at") or ""),
                str(row.get("evidence_id") or ""),
            ),
        )
        accuracy = newest.get("accuracy")
        key = (
            accuracy if isinstance(accuracy, (int, float)) else -1.0,
            str(newest.get("observed_at") or ""),
            provider,
            model,
        )
        if best is None or key > best:
            best = key
    if best is None:
        return None
    return {"provider": best[2], "model": best[3]}


def discover_route_candidates(
    evidence_rows: Sequence[Mapping[str, Any]],
    *,
    profile_name: Optional[str] = None,
    measured_evidence: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    """The discovery cohort for an ordinary assignment (no operator pin).

    Candidates are populated from the scoped current evidence — the validated
    campaign-writer benchmark records that already carry the receipt benchmark's workload
    identity — and filtered through the EXISTING capability profile policy
    (the same workload quality floor and measured feedback evidence the
    attempt filter enforces), so a quarantined or below-floor route cannot
    win selection and then demote the whole resolution while an eligible
    route (typically the receipt's own serving route) was available. Provider
    availability at the dispatch scope stays an attempt-time check
    (:func:`filter_route_for_attempt` refuses the pin for a scope whose
    handler does not carry the provider). A route whose newest passing
    observation carries no recorded accuracy cannot demonstrate the workload
    floor and is not admitted by discovery.

    This is normal discovery only: an explicit operator route constraint is
    never substituted by this cohort (the caller passes ``candidates`` for
    that, and eligibility is still decided from durable evidence alone).
    """
    quality_by_route: Dict[Tuple[str, str], Optional[float]] = {}
    newest_passing: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for row in evidence_rows or []:
        provider = str(row.get("provider") or "").strip()
        model = str(row.get("model") or "").strip()
        if not provider or not model:
            continue
        key = (provider, model)
        if row.get("passed") is not True:
            continue
        observed = str(row.get("observed_at") or "")
        order = (observed, str(row.get("evidence_id") or ""))
        if key not in newest_passing or order > newest_passing[key]:
            newest_passing[key] = order
            accuracy = row.get("accuracy")
            quality_by_route[key] = (
                float(accuracy)
                if isinstance(accuracy, (int, float)) else None)
    info: Dict[str, Any] = {
        "profile": profile_name or ROUTE_PROFILE,
        "evidenced_routes": sorted(quality_by_route),
        "excluded": [],
    }
    if not quality_by_route:
        info["reason"] = "no_scored_evidence_routes"
        return [], info
    from core.llm.capability_profiles import (
        resolve_capability_profile,
        select_profile_candidates,
    )

    try:
        profile = resolve_capability_profile(
            profile_name or ROUTE_PROFILE, None, "")
    except Exception as exc:  # noqa: BLE001 — fail closed
        info["reason"] = f"profile_unavailable:{exc}"
        return [], info
    proposals = [
        {
            "provider": provider,
            "model": model,
            **({"quality": quality} if quality is not None else {}),
        }
        for (provider, model), quality in sorted(quality_by_route.items())
    ]
    try:
        selection = select_profile_candidates(
            profile, proposals, evidence=measured_evidence or {})
    except Exception as exc:  # noqa: BLE001 — fail closed
        info["reason"] = f"capability_filter_error:{exc}"
        return [], info
    info["excluded"] = [
        {"route": item.get("route"), "reasons": list(item.get("reasons") or [])}
        for item in selection.get("excluded") or []
    ]
    candidates = [
        {"provider": str(item.get("provider") or ""),
         "model": str(item.get("model") or "")}
        for item in selection.get("ranked") or []
    ]
    info["reason"] = (
        "selected" if candidates else "no_profile_eligible_candidate")
    return candidates, info


def _normalize_candidates(
    candidates: Optional[Sequence[Any]],
) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    seen: set = set()
    for candidate in candidates or []:
        if isinstance(candidate, Mapping):
            provider = str(candidate.get("provider") or "").strip()
            model = str(candidate.get("model") or "").strip()
        elif isinstance(candidate, (tuple, list)) and len(candidate) == 2:
            provider = str(candidate[0] or "").strip()
            model = str(candidate[1] or "").strip()
        else:
            continue
        if not provider or not model:
            continue
        pair = {"provider": provider, "model": model}
        key = (provider, model)
        if key not in seen:
            seen.add(key)
            normalized.append(pair)
    return normalized


def resolve_repeat_task_route(
    db: Any,
    agent: Any,
    *,
    assignment: Optional[Any] = None,
    candidates: Optional[Sequence[Any]] = None,
    evidence_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    now: Optional[datetime] = None,
    profile_name: Optional[str] = None,
    measured_evidence: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Resolve the evidence-eligible repeat-task route for one agent.

    Fails closed: without a current, validated qualification baseline whose
    benchmark binding is comparable, the current assignment's server-derived
    workload identity matching that binding, an established baseline, and
    fresh passing candidate evidence on the same benchmark, the outcome is
    ``supervised`` (the normal supervised path applies — unrelated routing is
    untouched). ``candidates`` are PROPOSALS only: eligibility always comes
    from durable evidence, never from the caller's claim.

    Explicit ``candidates`` are an operator route constraint: the compared
    set is exactly the proposed routes, never silently substituted by
    another route. With no constraint, the candidate set is discovered from
    the scoped current evidence plus the existing capability profile policy
    (:func:`discover_route_candidates`), so ordinary assignments can select
    a fresh eligible replacement from the trusted benchmark cohort without
    an operator pin.

    The baseline comes from ``resolve_runtime_qualification_baseline``: the
    newest committed promotion transition into the agent's current tier plus
    the durable receipt it binds. The receipt that authorized STUDENT ->
    INTERN stops being a pre-transition authorization once the agent is
    INTERN, but it remains the verified baseline for repeat work on the tier
    it established; a stale or superseded transition resolves to nothing.

    ``assignment`` is the durable assignment plan the server persisted for
    the current run. Its server-derived workload identity
    (:func:`assignment_workload_identity`) must match the receipt binding's
    workload scope before any route is selected: an unrelated or unknown
    workload never inherits the receipt baseline. No caller-supplied scope
    is ever consulted.
    """
    from core.agent_graduation_service import (
        _complete_benchmark_identity as complete_benchmark_identity,
        resolve_runtime_qualification_baseline,
    )

    decision: Dict[str, Any] = {
        "kind": ROUTE_DECISION_KIND,
        "route_state": STATE_SUPERVISED,
        "agent_id": str(getattr(agent, "id", "") or ""),
        "receipt_id": None,
        "target_level": None,
        "promotion_id": None,
        "source_level": None,
        "benchmark": None,
        "workload_scope": None,
        "baseline_route": None,
        "candidate_routes": [],
        "candidate_source": None,
        "discovery": None,
        "selected_route": None,
        "selected_build": None,
        "ranked_routes": [],
        "reasons": [],
        "identity_state": None,
        "autonomous_eligible": False,
        "comparison": None,
    }

    def supervise(*reasons: str, state: str = STATE_SUPERVISED) -> Dict[str, Any]:
        decision["route_state"] = state
        decision["reasons"] = [
            reason[:200] for reason in reasons if reason]
        decision["autonomous_eligible"] = False
        return decision

    baseline_resolution = resolve_runtime_qualification_baseline(db, agent)
    if not baseline_resolution.get("ok"):
        state = str(baseline_resolution.get("state") or "unresolved_missing")
        return supervise(
            f"baseline_{state}",
            str(baseline_resolution.get("message") or ""))
    if baseline_resolution.get("repeat_task_comparable") is not True:
        return supervise(
            "receipt_binding_not_comparable",
            str(baseline_resolution.get("binding_state") or ""),
        )
    binding = baseline_resolution.get("binding") or {}
    benchmark = binding.get("benchmark_identity") or {}
    if not complete_benchmark_identity(benchmark):
        return supervise("binding_identity_incomplete")
    workload_scope = benchmark.get("workload_scope")
    rubric_version = str(benchmark.get("rubric_version") or "")
    binding_routes = _binding_routes(binding)
    if not binding_routes:
        return supervise("binding_routes_missing")

    decision["receipt_id"] = baseline_resolution.get("receipt_id")
    decision["target_level"] = baseline_resolution.get("target_level")
    decision["promotion_id"] = baseline_resolution.get("promotion_id")
    decision["source_level"] = baseline_resolution.get("source_level")
    decision["benchmark"] = {
        "dataset_sha256": benchmark.get("dataset_sha256"),
        "rubric_version": rubric_version,
    }
    decision["workload_scope"] = workload_scope

    # The current assignment's server-derived workload identity gates route
    # selection: a receipt baseline is only comparable for the workload the
    # receipt itself was earned on. Unknown or unrelated assignments are
    # supervised before any evidence is read, so nothing about this
    # assignment inherits the baseline.
    assignment_scope = assignment_workload_identity(assignment)
    if assignment_scope is None:
        return supervise("workload_scope_unknown")
    if not _workload_scopes_match(workload_scope, assignment_scope):
        return supervise("workload_scope_mismatch")

    rows: List[Dict[str, Any]] = list(
        evidence_rows
        if evidence_rows is not None
        else load_repeat_task_evidence(db, agent)
    )
    baseline = _resolve_baseline(binding_routes, rows)
    if baseline is None:
        return supervise("baseline_not_established")
    decision["baseline_route"] = baseline

    # Explicit caller candidates are an operator route constraint: the
    # compared set is exactly the proposed routes, never silently
    # substituted by another route. Without a constraint, candidates are
    # discovered from the scoped current evidence plus the existing
    # capability profile policy, so an ordinary assignment can select a
    # fresh eligible replacement without an operator pin.
    explicit = _normalize_candidates(list(candidates or []))
    if explicit:
        compared = explicit
        decision["candidate_source"] = "operator"
    else:
        discovered, discovery = discover_route_candidates(
            rows,
            profile_name=profile_name or ROUTE_PROFILE,
            measured_evidence=measured_evidence,
        )
        decision["candidate_source"] = "discovered"
        decision["discovery"] = discovery
        compared = discovered
        if not discovered:
            return supervise(
                str(discovery.get("reason") or "no_eligible_candidate"),
                *[
                    f"{item.get('route')}:{reason}"
                    for item in discovery.get("excluded") or []
                    for reason in item.get("reasons") or []
                ],
            )

    comparison = compare_model_evidence(
        task_scope=workload_scope if isinstance(workload_scope, Mapping) else {},
        evidence=rows,
        candidates=compared,
        rubric_version=rubric_version,
        baseline=baseline,
        profile_name=profile_name or ROUTE_PROFILE,
        now=now,
    )
    decision["candidate_routes"] = [
        {
            "provider": str(item.get("provider") or ""),
            "model": str(item.get("model") or ""),
        }
        for item in compared
    ]
    decision["comparison"] = comparison
    selected = comparison.get("selected")
    ranked = comparison.get("ranked") or []
    decision["ranked_routes"] = [
        {
            "provider": item.get("provider"),
            "model": item.get("model"),
            "score": item.get("score"),
            "observed_at": item.get("observed_at"),
            "build": (
                (item.get("evidence") or {}).get("model_build")
                if isinstance(item.get("evidence"), Mapping) else None),
        }
        for item in ranked
    ]
    insufficient = comparison.get("insufficient_evidence") or {}
    if comparison.get("outcome") != COMPARED or not selected:
        return supervise(
            *list(insufficient.get("reasons") or []) or ["no_eligible_candidate"]
        )
    decision["route_state"] = STATE_PINNED
    decision["selected_route"] = {
        "provider": str(selected.get("provider") or ""),
        "model": str(selected.get("model") or ""),
    }
    # Bind the benchmark's actual provider build next to the callable route.
    # The route stays the alias that is dispatched; the build is the concrete
    # provider identity the benchmark observed answering that alias. It is
    # carried into the durable decision so dispatch and the effect gate can
    # reject a missing or changed response echo.
    evidence = selected.get("evidence")
    build = (
        (evidence or {}).get("model_build")
        if isinstance(evidence, Mapping) else None)
    decision["selected_build"] = _identity_text(build)
    decision["autonomous_eligible"] = True
    return decision


# --- Capability filter before each provider attempt ---


def filter_route_for_attempt(
    route: Mapping[str, Any],
    *,
    quality: Optional[float] = None,
    profile_name: Optional[str] = None,
    workspace_id: str = "",
    tenant_id: str = "",
    llm_service: Any = None,
    evidence: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Filter one evidence-eligible route through the capability profile.

    Applied BEFORE each provider attempt (there is only ever one, because a
    graduation-pinned call is strict): the profile's measured transport
    evidence may quarantine or disqualify the route, and the structured
    qualification pin (:func:`build_provider_model_pin`) must actually
    resolve for the dispatch scope. A benchmark observation without a
    recorded accuracy cannot demonstrate the workload quality floor and is
    excluded rather than assumed.
    """
    from core.llm.capability_profiles import (
        load_feedback_evidence,
        resolve_capability_profile,
        select_profile_candidates,
    )
    from core.llm.pinned_planning import build_provider_model_pin

    result: Dict[str, Any] = {
        "allowed": False,
        "reasons": [],
        "pin": None,
        "selection": None,
    }
    profile_name = profile_name or ROUTE_PROFILE
    try:
        profile = resolve_capability_profile(profile_name, None, "")
    except Exception as exc:  # noqa: BLE001 — fail closed
        result["reasons"] = [f"profile_unavailable:{exc}"]
        return result
    try:
        measured = (
            evidence
            if evidence is not None
            else load_feedback_evidence(
                profile, workspace_id=workspace_id, tenant_id=tenant_id
            )
        )
    except Exception as exc:  # noqa: BLE001 — unknown evidence is the prior
        logger.debug("graduation route evidence lookup skipped: %s", exc)
        measured = {}
    provider = str(route.get("provider") or "")
    model = str(route.get("model") or "")
    candidate: Dict[str, Any] = {"provider": provider, "model": model}
    if quality is not None:
        candidate["quality"] = float(quality)
    try:
        selection = select_profile_candidates(profile, [candidate], evidence=measured)
    except Exception as exc:  # noqa: BLE001 — fail closed
        result["reasons"] = [f"capability_filter_error:{exc}"]
        return result
    result["selection"] = {
        "outcome": selection.get("outcome"),
        "excluded": selection.get("excluded") or [],
    }
    if selection.get("outcome") != "selected":
        result["reasons"] = [
            reason
            for item in (selection.get("excluded") or [])
            for reason in (item.get("reasons") or [])
        ] or ["capability_filter_no_suitable"]
        return result
    if llm_service is not None:
        pin = build_provider_model_pin(
            llm_service,
            provider,
            model,
            workspace_id=workspace_id or None,
            tenant_id=tenant_id or None,
        )
        if not pin.get("provider_model"):
            result["reasons"] = ["pin_refused"]
            return result
        result["pin"] = tuple(pin["provider_model"])
    result["allowed"] = True
    return result


# --- Provider response identity ---


def _accepted_response_identity(
    attribution: Any,
) -> Tuple[Optional[str], Optional[str]]:
    """The accepted transport call's provider echo as ``(provider, model)``.

    Only an accepted transport response is identity. When the transport's
    accepted call carries an echo, that echo is authoritative; the separate
    ``resolved_model`` capture is the equivalent legacy location when the
    transport block is absent. A rejected call never contributes an identity,
    and a missing echo is reported as missing rather than substituted from
    the served/requested route.
    """
    if not isinstance(attribution, Mapping):
        return None, None
    transport = attribution.get("transport")
    transport = transport if isinstance(transport, Mapping) else None
    if transport is not None:
        if "accepted" in transport and transport.get("accepted") is not True:
            return None, None
        identity = transport.get("response_identity")
        if isinstance(identity, Mapping):
            provider = _identity_text(identity.get("provider"))
            model = _identity_text(identity.get("model"))
            # An accepted call with no usable echo is missing, never the
            # served/requested route relabelled as a build.
            return provider, model
        if identity is not None:
            return None, None
    model = _identity_text(attribution.get("resolved_model"))
    if model is None and transport is not None:
        model = _identity_text(transport.get("resolved_model"))
    return None, model


def response_build_identity(attribution: Any) -> Optional[str]:
    """The concrete build (provider echo) of the accepted response, if any."""
    _provider, model = _accepted_response_identity(attribution)
    return model


def _served_route_pair(attribution: Mapping[str, Any]) -> Tuple[str, str]:
    served = attribution.get("served_route")
    if not isinstance(served, Mapping):
        transport = attribution.get("transport")
        served = (
            transport.get("served_route")
            if isinstance(transport, Mapping) else None)
    if not isinstance(served, Mapping):
        return "", ""
    return (
        str(served.get("provider") or "").strip(),
        str(served.get("model") or "").strip(),
    )


def validate_served_identity(
    expected_route: Any,
    attribution: Any,
    *,
    expected_build: Optional[str] = None,
) -> str:
    """Classify the provider's response identity against the pinned route.

    A missing or conflicting served identity makes the result ineligible for
    autonomous use. The served route must be the exact pinned pair. The
    accepted response's actual provider echo is required: when a benchmark
    build was bound (:func:`resolve_repeat_task_route` carries it in
    ``selected_build``), the echo must be that exact concrete build — a
    same-family build is a conflict, and a shorter/unversioned echo is not
    proof for an exact versioned build. Without a concrete build binding the
    echo must at least belong to the pinned model family; the callable alias
    remains dispatchable, and the provider build is a separate identity.
    """
    if not (
        isinstance(expected_route, (tuple, list, Mapping))
        and (
            len(expected_route) == 2
            if isinstance(expected_route, (tuple, list))
            else True
        )
    ):
        return IDENTITY_CONFLICT
    if isinstance(expected_route, Mapping):
        expected_provider = str(expected_route.get("provider") or "")
        expected_model = str(expected_route.get("model") or "")
    else:
        expected_provider = str(expected_route[0] or "")
        expected_model = str(expected_route[1] or "")
    if not expected_provider or not expected_model:
        return IDENTITY_CONFLICT
    if not isinstance(attribution, Mapping):
        return IDENTITY_MISSING
    served_provider, served_model = _served_route_pair(attribution)
    if not served_provider or not served_model:
        return IDENTITY_MISSING
    if (served_provider.casefold() != expected_provider.casefold()
            or served_model != expected_model):
        return IDENTITY_CONFLICT
    echo_provider, echo_model = _accepted_response_identity(attribution)
    if not echo_model:
        # The provider's own echo is the build witness; an accepted call with
        # no echo cannot prove which build answered the pinned route.
        return IDENTITY_MISSING
    if echo_provider and (
            echo_provider.casefold() != expected_provider.casefold()):
        return IDENTITY_CONFLICT
    bound_build = _identity_text(expected_build)
    if bound_build is not None:
        if (normalize_model_family(bound_build)
                != normalize_model_family(expected_model)):
            # A build of a different model family is not this route's build.
            return IDENTITY_CONFLICT
        if _is_concrete_build(bound_build):
            if _model_key(echo_model) != _model_key(bound_build):
                return IDENTITY_CONFLICT
            return IDENTITY_VERIFIED
    if normalize_model_family(echo_model) != normalize_model_family(
            expected_model):
        return IDENTITY_CONFLICT
    return IDENTITY_VERIFIED


# --- Effect-gate revalidation ---


def latest_repeat_task_route_decision(
    decisions: Sequence[Any],
    *,
    agent_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """The newest durable repeat-task route decision for the run, if any."""
    found: Optional[Dict[str, Any]] = None
    for entry in decisions or []:
        if not isinstance(entry, Mapping):
            continue
        if str(entry.get("kind") or "") != ROUTE_DECISION_KIND:
            continue
        if agent_id and str(entry.get("agent_id") or "") not in ("", str(agent_id)):
            continue
        found = dict(entry)
    return found


def _route_identity(route: Any) -> Tuple[str, str]:
    if isinstance(route, Mapping):
        return (
            str(route.get("provider") or "").strip(),
            str(route.get("model") or "").strip(),
        )
    return "", ""


def _build_matches_bound(
    bound_build: str,
    actual_build: Optional[str],
    route_model: Optional[str],
) -> bool:
    """The dispatch echo must match the benchmark build it was bound to.

    A concrete benchmark build requires the exact concrete echo. An alias-only
    benchmark binding requires an echo of the same normalized family; a
    versioned echo of that alias is the build that answered it, not a
    different route.
    """
    actual = _identity_text(actual_build)
    if not actual:
        return False
    if _is_concrete_build(bound_build):
        return _is_concrete_build(actual) and (
            _model_key(actual) == _model_key(bound_build))
    family = normalize_model_family(route_model or bound_build)
    return normalize_model_family(actual) == family


def _effect_build_denial(
    prior: Mapping[str, Any],
    *,
    kind: str,
    detail: str,
) -> Dict[str, Any]:
    return {
        "outcome": "propose",
        "reason": (
            f"Repeat-task route evidence no longer establishes the benchmark "
            f"build that authorized this effect ({kind}: {detail}); human "
            f"approval is required."
        ),
        "route_state": prior.get("route_state"),
        "build_state": kind,
    }


def revalidate_repeat_task_effect(
    db: Any,
    *,
    agent_id: str,
    decisions: Sequence[Any],
    assignment: Optional[Any] = None,
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Revalidate current evidence before an irreversible effect.

    Returns ``None`` when the run carries no repeat-task route context
    (unrelated routing is untouched). Otherwise the owner's autonomy gate has
    already returned ``execute``; this adds the evidence half:

    * a durable missing/conflicting response identity on this run's route
      decision keeps the result ineligible for autonomous use;
    * the benchmark build bound at resolution must still be the build the
      accepted response echoed, and the fresh durable resolution must still
      select the same callable route and a compatible build — a changed build
      for the same alias (including a new benchmark), a missing build witness,
      or a disappeared binding demotes the effect to supervision;
    * a fresh durable resolution (new session, no caches) must still pin a
      route for the CURRENT assignment's server-derived workload — stale
      evidence, a changed binding, a revoked receipt or an unrelated/unknown
      workload demote the effect to the normal supervised path.
    """
    prior = latest_repeat_task_route_decision(decisions, agent_id=agent_id)
    if prior is None:
        return None
    if str(prior.get("agent_id") or "") not in ("", str(agent_id or "")):
        return {
            "outcome": "propose",
            "reason": (
                "The run's repeat-task route decision belongs to a different "
                "agent; human approval is required."
            ),
            "route_state": prior.get("route_state"),
        }
    identity_state = prior.get("identity_state")
    if identity_state not in (None, IDENTITY_VERIFIED):
        label = "missing" if identity_state == IDENTITY_MISSING else "conflicting"
        return {
            "outcome": "propose",
            "reason": (
                f"The provider response identity for this run's repeat-task "
                f"route is {label}; the result is ineligible for autonomous "
                f"use. Human approval is required."
            ),
            "route_state": prior.get("route_state"),
            "identity_state": identity_state,
        }

    prior_provider, prior_model = _route_identity(prior.get("selected_route"))
    prior_build = _identity_text(prior.get("selected_build"))
    prior_identity_build = _identity_text(prior.get("identity_build"))
    if prior_build:
        if not prior_identity_build:
            return _effect_build_denial(
                prior, kind="missing",
                detail="the accepted response did not record a provider build")
        if not _build_matches_bound(
                prior_build, prior_identity_build, prior_model):
            return _effect_build_denial(
                prior, kind="conflict",
                detail=(
                    "the accepted response build did not match the bound "
                    "benchmark build"))
    from core.models import AgentRegistry

    agent = db.get(AgentRegistry, str(agent_id or ""))
    if agent is None:
        return {
            "outcome": "propose",
            "reason": (
                "The repeat-task route agent no longer resolves; human "
                "approval is required."
            ),
            "route_state": prior.get("route_state"),
        }
    fresh = resolve_repeat_task_route(
        db, agent, assignment=assignment, now=now)
    if fresh.get("route_state") == STATE_PINNED and fresh.get("selected_route"):
        fresh_provider, fresh_model = _route_identity(fresh.get("selected_route"))
        if prior_provider and prior_model and (
                prior_provider.casefold() != fresh_provider.casefold()
                or prior_model != fresh_model):
            return _effect_build_denial(
                prior, kind="route_changed",
                detail=(
                    "the current evidence selects a different callable "
                    "route"))
        fresh_build = _identity_text(fresh.get("selected_build"))
        if prior_build:
            if not fresh_build:
                return _effect_build_denial(
                    prior, kind="missing",
                    detail="the current benchmark evidence carries no build")
            if normalize_model_family(fresh_build) != normalize_model_family(
                    prior_model or prior_build):
                return _effect_build_denial(
                    prior, kind="conflict",
                    detail="the current benchmark build is a different model")
            previous_concrete = (
                _model_key(prior_build)
                if _is_concrete_build(prior_build)
                else _model_key(prior_identity_build)
                if prior_identity_build
                and _is_concrete_build(prior_identity_build) else "")
            if (previous_concrete and _is_concrete_build(fresh_build)
                    and _model_key(fresh_build) != previous_concrete):
                return _effect_build_denial(
                    prior, kind="changed",
                    detail=(
                        "a new benchmark observation of the same alias was "
                        "served by a different provider build"))
        elif fresh_build and _is_concrete_build(fresh_build) and (
                _model_key(fresh_build) != _model_key(fresh_model)):
            # A durable decision written before build binding existed cannot
            # prove it was authorized for a separate concrete build under an
            # alias. The callable route itself being the build is still fine.
            return _effect_build_denial(
                prior, kind="missing",
                detail=(
                    "the durable decision did not bind the benchmark build"))
        return {
            "outcome": "execute",
            "route": fresh.get("selected_route"),
            "route_state": STATE_PINNED,
            "build": fresh_build,
        }
    reasons = list(fresh.get("reasons") or [])
    detail = "; ".join(reasons) if reasons else "route eligibility is unknown"
    return {
        "outcome": "propose",
        "reason": (
            "Repeat-task route evidence no longer establishes an eligible "
            f"route ({detail}); the normal supervised path applies."
        ),
        "route_state": fresh.get("route_state"),
        "reasons": reasons,
    }
