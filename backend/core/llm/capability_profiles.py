"""Workload capability profiles and quality-before-cost candidate selection.

This is a thin policy layer over the existing BYOK/BPC ranking. It does not
call providers, hold credentials or replace the learning router. It answers
one question for a declared workload: which already-eligible configured routes
have measured evidence that they can carry this contract, and among those,
which is cheapest/fastest?

Owner clarification (2026-11-04): Flash / low-price / low-latency models are
first-class when they meet the task. A profile's quality floor is a prior, not
a branding rule. Task-specific evidence can exclude a route; it can also keep
an efficient route eligible when its success evidence is good. Higher price or
a larger model is never a quality proof.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

PROFILE_SCHEMA_VERSION = "capability-profile-1"


@dataclass(frozen=True)
class CapabilityProfile:
    """Server-selected, versioned workload contract.

    ``min_quality`` is the static prior floor used only after provider,
    credential, protocol, context and policy eligibility. ``preference``
    controls ordering WITHIN the eligible set: ``economy`` (default) prefers
    expected cost then latency, ``quality`` explicitly prefers measured
    quality. A profile never authorizes a provider or an effect.
    """

    name: str
    version: str
    min_quality: int
    policy: str = "best_effort"  # quality_critical | best_effort
    preference: str = "economy"  # economy | balanced | quality
    required_capabilities: Tuple[str, ...] = ("structured",)
    min_context_tokens: int = 8000
    min_output_tokens: int = 512
    allow_escalation: bool = False
    max_escalations: int = 1
    evidence_min_samples: int = 3
    evidence_window_days: int = 30
    max_failure_rate: float = 0.25
    disqualifying_failure_kinds: Tuple[str, ...] = (
        "unsafe_action", "invented_fact", "semantic_failure",
        "invalid_plan_reference", "wrong_field_mapping",
    )
    allow_cost_relaxation: bool = False

    def metadata(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "min_quality": self.min_quality,
            "policy": self.policy,
            "preference": self.preference,
            "required_capabilities": list(self.required_capabilities),
            "min_context_tokens": self.min_context_tokens,
            "allow_escalation": self.allow_escalation,
            "max_escalations": self.max_escalations,
        }


# Floors are deliberately modest: they are priors, not capability
# qualifications. A measured Flash route with a 90 prior remains eligible and
# is preferred on cost when its evidence is adequate. The local 8B failures do
# not justify a higher brand-wide floor.
_PROFILES: Dict[str, CapabilityProfile] = {
    "employee_evidence_selection": CapabilityProfile(
        name="employee_evidence_selection", version="2026-11-04.1",
        min_quality=80, policy="quality_critical", preference="economy",
        allow_escalation=True),
    "employee_semantic_mapping": CapabilityProfile(
        name="employee_semantic_mapping", version="2026-11-04.1",
        min_quality=80, policy="quality_critical", preference="economy",
        allow_escalation=True),
    "employee_adaptive_planning": CapabilityProfile(
        name="employee_adaptive_planning", version="2026-11-04.1",
        min_quality=82, policy="quality_critical", preference="economy",
        allow_escalation=True),
    "employee_wait_choice": CapabilityProfile(
        name="employee_wait_choice", version="2026-11-04.1",
        min_quality=82, policy="quality_critical", preference="economy",
        allow_escalation=True),
    "goal_replanning": CapabilityProfile(
        name="goal_replanning", version="2026-11-04.1",
        min_quality=82, policy="quality_critical", preference="economy",
        allow_escalation=True),
    "alignment_judging": CapabilityProfile(
        name="alignment_judging", version="2026-11-04.1",
        min_quality=85, policy="quality_critical", preference="economy",
        allow_escalation=False),
    "extraction": CapabilityProfile(
        name="extraction", version="2026-11-04.1",
        min_quality=80, policy="best_effort", preference="economy",
        allow_escalation=False),
    "document_drafting": CapabilityProfile(
        name="document_drafting", version="2026-11-04.1",
        min_quality=80, policy="best_effort", preference="balanced",
        allow_escalation=False),
    # Compatibility profile for ordinary planning calls that do not identify
    # themselves as employee decisions. It keeps the existing cost-priority
    # relaxation but is explicitly best-effort.
    "planning_legacy": CapabilityProfile(
        name="planning_legacy", version="2026-11-04.1",
        min_quality=85, policy="best_effort", preference="economy",
        allow_cost_relaxation=True),
}

_LOG_LABEL_PROFILES = {
    "employee work proposal": "employee_evidence_selection",
    "employee adaptation": "employee_adaptive_planning",
    "employee wait": "employee_wait_choice",
    "goal replanning": "goal_replanning",
    "goal planning": "goal_replanning",
    "alignment judge": "alignment_judging",
    "alignment judging": "alignment_judging",
    "knowledge extraction": "extraction",
    "extraction": "extraction",
    "document drafting": "document_drafting",
}


def resolve_capability_profile(
    explicit: Optional[str] = None,
    task_type: Optional[str] = None,
    log_label: Optional[str] = None,
) -> Optional[CapabilityProfile]:
    """Resolve a server-coded profile. Unknown names are an error only when
    they were explicitly requested; free-form task types remain compatible."""
    if explicit:
        profile = _PROFILES.get(str(explicit).strip())
        if profile is None:
            raise ValueError(
                f"unknown capability profile {explicit!r}; known profiles: "
                f"{sorted(_PROFILES)}")
        return profile
    label = str(log_label or "").strip().lower()
    for needle, name in _LOG_LABEL_PROFILES.items():
        if needle in label:
            return _PROFILES[name]
    normalized = str(task_type or "").strip().lower()
    if normalized in _PROFILES:
        return _PROFILES[normalized]
    return None


def profile_names() -> List[str]:
    return sorted(_PROFILES)


def get_profile(name: str) -> CapabilityProfile:
    profile = _PROFILES.get(str(name or "").strip())
    if profile is None:
        raise KeyError(name)
    return profile


def parse_evidence_rows(
    rows: Iterable[Mapping[str, Any]],
    profile: CapabilityProfile,
    *,
    workspace_id: str = "",
    tenant_id: str = "",
) -> Dict[str, Dict[str, Any]]:
    """Aggregate existing LLMRoutingFeedback-shaped rows for one profile.

    Scope and version are part of the key: a row from another workspace,
    another tenant, an older profile version or an unrelated task never
    poisons this profile. Rows without capability metadata are ignored for
    task-specific selection (they remain useful to the existing learning
    router).
    """
    evidence: Dict[str, Dict[str, Any]] = {}
    cutoff = time.time() - profile.evidence_window_days * 86400
    for row in rows:
        features = row.get("prompt_features")
        if not isinstance(features, Mapping):
            continue
        if str(features.get("capability_profile") or "") != profile.name:
            continue
        if str(features.get("profile_version") or "") != profile.version:
            continue
        row_workspace = str(features.get("workspace_id") or "").strip()
        # Exact scope only. Missing scope is unknown evidence, never inferred
        # from the current reader (verifier boundary 4).
        if workspace_id and row_workspace != str(workspace_id):
            continue
        row_tenant = str(
            row.get("tenant_id") or features.get("tenant_id") or "").strip()
        if tenant_id and row_tenant != str(tenant_id):
            continue
        created = row.get("created_at")
        if created is not None:
            try:
                stamp = (
                    created.timestamp() if hasattr(created, "timestamp")
                    else float(created))
                if stamp < cutoff:
                    continue
            except (TypeError, ValueError):
                pass
        model = str(row.get("model_id") or "").strip()
        provider = str(features.get("route_provider")
                       or features.get("provider_id") or "").strip()
        # A model name alone is not a provider configuration identity: it
        # must not transfer evidence across providers (verifier boundary 4).
        if not model or not provider:
            continue
        key = f"{provider}/{model}"
        bucket = evidence.setdefault(key, {
            "samples": 0, "successes": 0, "quality_successes": 0,
            "semantic_failures": 0, "unsafe_failures": 0,
            "retries": 0, "latency_ms": None, "last_failure_kind": "",
            "failure_kinds": set(),
            "profile": profile.name, "profile_version": profile.version,
            "workspace_id": row_workspace or workspace_id,
            "tenant_id": row_tenant or tenant_id,
        })
        bucket["samples"] += 1
        failure_kind = str(features.get("failure_kind") or "").strip()
        semantic_failure_kinds = {
            "semantic_failure", "invented_fact",
            "invalid_plan_reference", "wrong_field_mapping",
        }
        unsafe = failure_kind == "unsafe_action"
        semantic = failure_kind in semantic_failure_kinds
        # A transport-successful response is not a satisfactory business
        # outcome. Require explicit quality satisfaction AND no known
        # semantic/unsafe failure (verifier boundary 2).
        satisfactory = (
            bool(row.get("success"))
            and bool(row.get("quality_satisfied"))
            and not semantic and not unsafe)
        if satisfactory:
            bucket["successes"] += 1
            bucket["quality_successes"] += 1
        if failure_kind:
            bucket["last_failure_kind"] = failure_kind
            bucket["failure_kinds"].add(failure_kind)
            if unsafe:
                bucket["unsafe_failures"] += 1
            elif semantic:
                bucket["semantic_failures"] += 1
        if bool(features.get("retry")):
            bucket["retries"] += 1
        latency = row.get("actual_latency_ms")
        if latency is not None:
            try:
                bucket["latency_ms"] = float(latency)
            except (TypeError, ValueError):
                pass
    return evidence


def _evidence_for(
    evidence: Mapping[str, Mapping[str, Any]],
    provider: str,
    model: str,
) -> Optional[Mapping[str, Any]]:
    return evidence.get(f"{provider}/{model}") or evidence.get(model)


def _quality(candidate: Mapping[str, Any]) -> float:
    quality = float(candidate.get("quality") or 0.0)
    return quality * 100.0 if quality <= 1.0 else quality


def _cost(candidate: Mapping[str, Any]) -> float:
    try:
        return float(candidate.get("cost") or 0.0)
    except (TypeError, ValueError):
        return float("inf")


def _latency(candidate: Mapping[str, Any]) -> float:
    try:
        return float(candidate.get("latency_ms") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def select_profile_candidates(
    profile: CapabilityProfile,
    candidates: Sequence[Mapping[str, Any]],
    *,
    evidence: Optional[Mapping[str, Mapping[str, Any]]] = None,
    preference: Optional[str] = None,
) -> Dict[str, Any]:
    """Filter and order already-eligible candidates for one workload.

    No authority, provider, credential or effect decision is made here. The
    caller must have applied scoped provider policy, local-only, credential,
    protocol, context and budget gates before calling. This function adds the
    workload-specific quality/evidence layer and returns an explicit
    ``no_suitable`` outcome instead of silently relaxing a required floor.
    """
    evidence = evidence or {}
    mode = str(preference or profile.preference or "economy")
    eligible: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []
    for raw in candidates:
        if not isinstance(raw, Mapping):
            continue
        candidate = dict(raw)
        provider = str(candidate.get("provider") or "")
        model = str(candidate.get("model") or "")
        route = f"{provider}/{model}"
        reasons: List[str] = []
        quality = _quality(candidate)
        if quality < profile.min_quality:
            reasons.append("below_quality_prior")
        capabilities = {
            str(item).strip().lower()
            for item in (candidate.get("capabilities") or [])
            if str(item).strip()
        }
        for required in profile.required_capabilities:
            if required in ("structured", "tools"):
                flag = candidate.get(
                    "supports_structured" if required == "structured"
                    else "supports_tools")
                if flag is False:
                    reasons.append(f"missing_{required}")
            elif capabilities and required not in capabilities:
                reasons.append(f"missing_{required}")
        context = candidate.get("context_window")
        if context is not None:
            try:
                if int(context) < profile.min_context_tokens:
                    reasons.append("context_too_small")
            except (TypeError, ValueError):
                pass
        measured = _evidence_for(evidence, provider, model)
        evidence_state = "prior"
        if measured and int(measured.get("unsafe_failures") or 0) > 0:
            # A verified unsafe outcome is a quarantine signal at the first
            # observation, not behind the ordinary sample floor.
            reasons.append("measured_unsafe_action")
            evidence_state = "measured"
        if measured and int(measured.get("samples") or 0) >= (
                profile.evidence_min_samples):
            samples = max(1, int(measured.get("samples") or 1))
            success_rate = float(measured.get("successes") or 0) / samples
            retry_rate = float(measured.get("retries") or 0) / samples
            failure_rate = 1.0 - success_rate
            if "measured_unsafe_action" in reasons:
                pass
            elif failure_rate > profile.max_failure_rate:
                reasons.append("measured_failure_rate")
            elif str(measured.get("last_failure_kind") or "") in (
                    profile.disqualifying_failure_kinds):
                reasons.append("measured_disqualifying_failure")
            evidence_state = "measured"
            candidate["expected_success"] = round(success_rate, 4)
            candidate["retry_rate"] = round(retry_rate, 4)
        else:
            candidate["expected_success"] = None
            candidate["retry_rate"] = None
        if reasons:
            excluded.append({"route": route, "reasons": reasons})
            continue
        cost = _cost(candidate)
        expected_success = candidate.get("expected_success")
        retry_rate = candidate.get("retry_rate") or 0.0
        # Expected cost of a satisfactory result: retries and measured
        # failure risk increase the effective cost. Unknown evidence uses
        # the static prior and no invented success rate.
        if expected_success is None:
            risk_factor = 1.0
        else:
            risk_factor = 1.0 + max(0.0, float(retry_rate)) * 2.0
            risk_factor += max(0.0, 1.0 - float(expected_success))
        candidate["effective_cost"] = cost * risk_factor
        candidate["evidence_state"] = evidence_state
        candidate["profile"] = profile.name
        candidate["profile_version"] = profile.version
        eligible.append(candidate)

    if mode == "quality":
        eligible.sort(key=lambda c: (
            -_quality(c), c["effective_cost"], _latency(c)))
    elif mode == "balanced":
        eligible.sort(key=lambda c: (
            c["effective_cost"] + _latency(c) * 1e-6,
            -_quality(c)))
    else:  # economy: cheapest expected satisfactory result first
        eligible.sort(key=lambda c: (
            c["effective_cost"], _latency(c), -_quality(c)))

    outcome = "selected" if eligible else "no_suitable"
    return {
        "outcome": outcome,
        "profile": profile.metadata(),
        "preference": mode,
        "ranked": eligible,
        "excluded": excluded,
        "selection_reason": (
            "lowest expected cost among routes meeting the workload floor"
            if mode == "economy" and eligible else
            "explicit quality preference among eligible routes"
            if mode == "quality" and eligible else
            "no configured route meets the workload capability floor"
            if not eligible else "balanced eligible ordering"),
    }


def escalation_candidate(
    profile: CapabilityProfile,
    ranked: Sequence[Mapping[str, Any]],
    failed_route: Tuple[str, str],
) -> Optional[Dict[str, Any]]:
    """One bounded, policy-eligible escalation after a specific failure.

    The caller must revalidate the result through its normal compiler/proof
    path. This never repeats the failed pair and never selects a route outside
    the already-ranked eligible set.
    """
    if not profile.allow_escalation or not ranked:
        return None
    failed = (str(failed_route[0]), str(failed_route[1]))
    failed_index = next(
        (index for index, candidate in enumerate(ranked)
         if (str(candidate.get("provider")), str(candidate.get("model")))
         == failed),
        None)
    if failed_index is None:
        # The failed pair was not eligible; do not invent an escalation.
        return None
    failed_quality = _quality(ranked[failed_index])
    for candidate in ranked[failed_index + 1:]:
        if _quality(candidate) > failed_quality or (
                candidate.get("expected_success") is not None
                and ranked[failed_index].get("expected_success") is not None
                and float(candidate["expected_success"])
                > float(ranked[failed_index]["expected_success"])):
            return dict(candidate)
    return None


def pin_decision(
    profile: CapabilityProfile,
    provider: str,
    model: str,
    *,
    quality: float,
    context_window: Optional[int] = None,
    supports_structured: bool = True,
    supports_tools: bool = True,
    evidence: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Strict qualification-pin decision: exact route or failed attempt.

    A pin never silently escapes to another model. The caller records this
    decision and fails the qualification attempt; production auto-routing
    (without a pin) may still choose another eligible route.
    """
    candidate = {
        "provider": provider, "model": model, "quality": quality,
        "cost": 0.0, "context_window": context_window,
        "supports_structured": supports_structured,
        "supports_tools": supports_tools,
    }
    selected = select_profile_candidates(
        profile, [candidate], evidence=evidence,
        preference="quality")
    if selected["outcome"] == "selected":
        return {
            "eligible": True,
            "route": (provider, model),
            "profile": profile.metadata(),
            "reasons": [],
            "evidence_state": selected["ranked"][0]["evidence_state"],
        }
    return {
        "eligible": False,
        "route": (provider, model),
        "profile": profile.metadata(),
        "reasons": (selected["excluded"][0]["reasons"]
                    if selected["excluded"] else ["not_eligible"]),
        "evidence_state": "measured"
        if evidence and _evidence_for(evidence, provider, model) else "prior",
    }


# ---------------------------------------------------------------------------
# Audit journal (not a routing source)
# ---------------------------------------------------------------------------
_JOURNAL_LOCK = threading.Lock()
_MEMORY_DECISIONS: List[Dict[str, Any]] = []
_JOURNAL_MAX = 100


def _journal_path() -> Path:
    override = os.getenv("ATOM_CAPABILITY_ROUTING_JOURNAL")
    if override:
        return Path(override)
    # World-owned storage, never a repository-shared runtime history. Prefer
    # the isolated world data root, then the SQLite database directory, then
    # the office data root. The temp fallback is diagnostic-only for callers
    # with no configured world.
    data_root = os.getenv("ATOM_DATA_DIR")
    if data_root:
        return Path(data_root) / "llm_capability_routing.json"
    database_url = str(os.getenv("DATABASE_URL") or "")
    if database_url.startswith("sqlite:///"):
        return Path(database_url[len("sqlite:///"):]).resolve().parent / (
            "llm_capability_routing.json")
    office_root = os.getenv("ATOM_OFFICE_DIR")
    if office_root:
        return Path(office_root) / "llm_capability_routing.json"
    return Path(tempfile.gettempdir()) / "atom-llm-capability-routing.json"


def record_capability_decision(entry: Mapping[str, Any]) -> Dict[str, Any]:
    """Persist one bounded, server-controlled routing decision for audit.

    This journal is observational only: reloading it cannot grant authority or
    make a model eligible. It exists so "why was this route chosen/excluded"
    survives restart and can be inspected beside the existing feedback rows.
    """
    payload = dict(entry)
    payload.setdefault("schema", "capability-routing-decision-1")
    payload.setdefault("at", datetime_now())
    payload["digest"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]
    global _MEMORY_DECISIONS
    with _JOURNAL_LOCK:
        _MEMORY_DECISIONS = [*_MEMORY_DECISIONS, payload][-_JOURNAL_MAX:]
        if os.getenv("TESTING") and not os.getenv(
                "ATOM_CAPABILITY_ROUTING_JOURNAL"):
            # Tests that do not own a world journal stay in memory; never
            # create a repository-shared runtime history.
            return payload
        path = _journal_path()
        try:
            existing: List[Dict[str, Any]] = []
            if path.is_file():
                raw = json.loads(path.read_text())
                if isinstance(raw, list):
                    existing = [item for item in raw if isinstance(item, dict)]
            entries = [*existing, payload][-_JOURNAL_MAX:]
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
            tmp.write_text(json.dumps(entries, indent=1, default=str) + "\n")
            tmp.replace(path)
        except Exception as exc:  # noqa: BLE001 — audit must not block routing
            logger.debug("capability routing journal write skipped: %s", exc)
    return payload


def _decision_in_scope(
    item: Mapping[str, Any], workspace_id: str, tenant_id: str,
) -> bool:
    if workspace_id and str(item.get("workspace_id") or "") != str(
            workspace_id):
        return False
    if tenant_id and str(item.get("tenant_id") or "") != str(tenant_id):
        return False
    return True


def capability_decisions(
    limit: int = 20,
    *,
    workspace_id: str = "",
    tenant_id: str = "",
) -> List[Dict[str, Any]]:
    """Recent decisions, optionally scoped to an authenticated owner.

    A scoped read requires exact workspace AND tenant identity on the stored
    record. Missing scope is never inferred from the reader; an unscoped
    diagnostic call is internal-only and must not be exposed by a route.
    """
    def _read(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        scoped = [
            item for item in entries
            if _decision_in_scope(item, workspace_id, tenant_id)]
        return scoped[-max(1, int(limit)):]

    with _JOURNAL_LOCK:
        if _MEMORY_DECISIONS:
            return _read(list(_MEMORY_DECISIONS))
    try:
        path = _journal_path()
        if path.is_file():
            raw = json.loads(path.read_text())
            if isinstance(raw, list):
                return _read([item for item in raw if isinstance(item, dict)])
    except Exception:
        pass
    return []


def reset_capability_journal_memory() -> None:
    """Test helper: clear only the in-process mirror, not the audit file."""
    global _MEMORY_DECISIONS
    with _JOURNAL_LOCK:
        _MEMORY_DECISIONS = []


def datetime_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


# Short-lived evidence cache. The source of truth remains LLMRoutingFeedback;
# this only avoids a query per ranking call. The key includes profile version,
# scope and policy revision so a policy/qualification change cannot reuse a
# stale decision.
_EVIDENCE_CACHE_LOCK = threading.Lock()
_EVIDENCE_CACHE: Dict[Tuple[Any, ...], Tuple[float, Dict[str, Dict[str, Any]]]] = {}
_EVIDENCE_TTL_SECONDS = 30.0


def reset_capability_evidence_cache() -> None:
    with _EVIDENCE_CACHE_LOCK:
        _EVIDENCE_CACHE.clear()


def load_feedback_evidence(
    profile: CapabilityProfile,
    *,
    workspace_id: str = "",
    tenant_id: str = "",
    policy_revision: str = "",
) -> Dict[str, Dict[str, Any]]:
    """Read profile-scoped outcome evidence from the existing feedback table.

    Only rows explicitly stamped with this profile name and version are
    considered. An empty result means "no task-specific evidence", not "the
    model is bad"; the static prior remains the floor.
    """
    from datetime import datetime, timedelta

    cache_key = (
        profile.name, profile.version, str(workspace_id or ""),
        str(tenant_id or ""), str(policy_revision or ""))
    now = time.monotonic()
    with _EVIDENCE_CACHE_LOCK:
        cached = _EVIDENCE_CACHE.get(cache_key)
        if cached and now - cached[0] < _EVIDENCE_TTL_SECONDS:
            return dict(cached[1])
    rows: List[Dict[str, Any]] = []
    try:
        from core.database import get_db_session
        from core.models import LLMRoutingFeedback

        cutoff = datetime.utcnow() - timedelta(
            days=profile.evidence_window_days)
        with get_db_session() as db:
            query = db.query(LLMRoutingFeedback).filter(
                LLMRoutingFeedback.created_at >= cutoff)
            if tenant_id and tenant_id != "default":
                query = query.filter(
                    LLMRoutingFeedback.tenant_id == tenant_id)
            for row in query.order_by(
                    LLMRoutingFeedback.created_at.desc()).limit(500).all():
                rows.append({
                    "tenant_id": row.tenant_id,
                    "model_id": row.model_id,
                    "success": row.success,
                    "quality_satisfied": row.quality_satisfied,
                    "actual_latency_ms": row.actual_latency_ms,
                    "created_at": row.created_at,
                    "prompt_features": row.prompt_features,
                })
    except Exception as exc:  # noqa: BLE001 — evidence lookup must not break routing
        logger.debug("capability evidence lookup skipped: %s", exc)
        rows = []
    evidence = parse_evidence_rows(
        rows, profile, workspace_id=workspace_id, tenant_id=tenant_id)
    evidence = apply_capability_recoveries(
        profile, evidence, workspace_id=workspace_id, tenant_id=tenant_id)
    with _EVIDENCE_CACHE_LOCK:
        _EVIDENCE_CACHE[cache_key] = (now, evidence)
    return evidence


def profile_descriptions() -> List[Dict[str, Any]]:
    """Public, route-free descriptions for the settings surface."""
    return [
        {**profile.metadata(),
         "description": (
             "Workload capability profile; cheapest eligible route is "
             "preferred within the static floor and measured evidence.")}
        for profile in sorted(_PROFILES.values(), key=lambda item: item.name)
    ]


def recover_capability_quarantine(
    profile: CapabilityProfile,
    provider: str,
    model: str,
    *,
    reviewed_by: str,
    reason: str = "",
    workspace_id: str = "",
    tenant_id: str = "",
) -> Dict[str, Any]:
    """Explicit reviewed recovery for one profile/route quarantine.

    This records the review, not an automatic clearing. Historical feedback
    rows remain intact; subsequent evidence reads apply this recovery only to
    the exact profile/version/route/scope. No route outside the quarantine is
    affected.
    """
    if not str(reviewed_by or "").strip():
        raise ValueError("reviewed_by is required for quarantine recovery")
    return record_capability_decision({
        "event": "recovery",
        "profile": profile.metadata(),
        "route": [str(provider), str(model)],
        "reviewed_by": str(reviewed_by)[:200],
        "reason": str(reason or "")[:800],
        "workspace_id": str(workspace_id or ""),
        "tenant_id": str(tenant_id or ""),
    })


def apply_capability_recoveries(
    profile: CapabilityProfile,
    evidence: Dict[str, Dict[str, Any]],
    *,
    workspace_id: str = "",
    tenant_id: str = "",
) -> Dict[str, Dict[str, Any]]:
    """Apply exact-scope reviewed recoveries to parsed profile evidence."""
    recoveries = [
        entry for entry in capability_decisions(
            200, workspace_id=workspace_id, tenant_id=tenant_id)
        if entry.get("event") == "recovery"
        and str((entry.get("profile") or {}).get("name") or "")
        == profile.name
        and str((entry.get("profile") or {}).get("version") or "")
        == profile.version
    ]
    for entry in recoveries:
        route = entry.get("route") or []
        if not isinstance(route, list) or len(route) != 2:
            continue
        key = f"{route[0]}/{route[1]}"
        bucket = evidence.get(key)
        if not bucket:
            continue
        cleared = int(bucket.get("unsafe_failures") or 0) + int(
            bucket.get("semantic_failures") or 0)
        bucket["samples"] = max(
            0, int(bucket.get("samples") or 0) - cleared)
        bucket["unsafe_failures"] = 0
        bucket["semantic_failures"] = 0
        bucket["last_failure_kind"] = ""
        bucket["failure_kinds"] = set()
        bucket["recovered_by"] = entry.get("reviewed_by")
        bucket["recovery_reason"] = entry.get("reason")
    return evidence
