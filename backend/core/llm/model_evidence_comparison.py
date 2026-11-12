"""Task-scoped model evidence comparison for repeat-task graduation.

Compact typed core: one narrow entry point (:func:`compare_model_evidence`)
for the normal routing path, plus the durable assessment qualification
loader. It never routes, authorizes an effect, calls a provider, or reads
a global model leaderboard.

Evidence rules (acceptance contract)
------------------------------------
* **Freshness**: a positive window and a trustworthy timestamp are
  required. Zero, negative, malformed or missing window inputs fall back
  to the default and never bypass freshness; a future timestamp is
  untrusted. A frozen dataset date bounds freshness only for a scored run
  verifiably bound to that frozen set (matching ``dataset_id``).
* **Positive evidence**: a registry-only entry, a declared route, or an
  unscored artifact can never establish positive benchmark evidence.
  Negative verdicts and revocations are preserved.
* **Baseline**: a named graduation baseline route must be met on the same
  dataset hash, rubric and scope, including abstention where scored; a
  fresh but weaker model is rejected.
* **Identity**: only the exact served ``(provider, model)`` pair is
  evidence; an available build identity (``resolved_model``) is checked
  and conflicting builds are ambiguous.

Research basis: RouteLLM (arXiv:2406.18665) and LLMRouterBench
(arXiv:2601.07206) — routing learns from per-task outcome data, not
model branding or global leaderboards.
"""
from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.llm.model_provenance import provenance_from_metadata

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "atom-model-evidence-comparison-1"

COMPARED = "compared"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"

#: Top-level insufficient-evidence classes; candidate reasons are narrower
#: codes (e.g. ``evidence_expired``).
REASON_MISSING = "missing_evidence"
REASON_STALE = "stale_evidence"
REASON_AMBIGUOUS = "ambiguous_evidence"
REASON_MISMATCHED = "mismatched_evidence"
REASON_NO_PASSING = "no_passing_evidence"

_REASON_ORDER = (
    REASON_MISSING, REASON_STALE, REASON_AMBIGUOUS,
    REASON_MISMATCHED, REASON_NO_PASSING,
)

#: Default freshness window. Callers can override with an explicit positive
#: number or reuse an existing workload policy
#: (``CapabilityProfile.evidence_window_days``) by naming the profile.
DEFAULT_EVIDENCE_WINDOW_DAYS = 30

_SCOPE_FIELDS = ("task_policy", "decision_options", "subject_field")

_UNKNOWN_IDENTITIES = frozenset({
    "", "auto", "default", "unknown", "none", "null", "n/a",
})

_GLOBAL_EVIDENCE_TOKENS = (
    "leaderboard", "leader-board", "global_rank", "global-rank",
    "model_ranking", "model-ranking", "arena", "benchmark_rank",
)

_PASSED_STATUSES = frozenset({
    "qualified", "passed", "pass", "success", "succeeded", "ok",
})
_FAILED_STATUSES = frozenset({
    "failed", "fail", "rejected", "not_qualified", "unqualified",
})
_UNRESOLVED_STATUSES = frozenset({
    "unresolved", "unknown", "pending", "incomplete", "indeterminate", "error",
})

#: Reason -> class. The class is what the caller gates on; the reason
#: explains why. Reasons without a class (e.g. ``evidence_not_passed``,
#: ``baseline_not_met``) are routing exclusions, not evidence defects.
_REASON_CLASS = {
    "identity_missing": REASON_MISSING,
    "identity_partial": REASON_MISSING,
    "no_task_scoped_evidence": REASON_MISSING,
    "evidence_path_missing": REASON_MISSING,
    "unscored_artifact": REASON_MISSING,
    "baseline_evidence_missing": REASON_MISSING,
    "observed_at_missing": REASON_STALE,
    "observed_at_untrusted": REASON_STALE,
    "evidence_expired": REASON_STALE,
    "mixed_serving_identity": REASON_AMBIGUOUS,
    "unattributed_calls": REASON_AMBIGUOUS,
    "serving_identity_conflict": REASON_AMBIGUOUS,
    "status_conflict": REASON_AMBIGUOUS,
    "result_status_unresolved": REASON_AMBIGUOUS,
    "registry_result_disagreement": REASON_AMBIGUOUS,
    "conflicting_newest_evidence": REASON_AMBIGUOUS,
    "model_build_conflict": REASON_AMBIGUOUS,
    "task_scope_missing": REASON_MISMATCHED,
    "task_scope_mismatch": REASON_MISMATCHED,
    "rubric_version_missing": REASON_MISMATCHED,
    "rubric_version_mismatch": REASON_MISMATCHED,
    "contract_version_missing": REASON_MISMATCHED,
    "contract_version_mismatch": REASON_MISMATCHED,
    "global_leaderboard_not_task_evidence": REASON_MISMATCHED,
    "declared_served_identity_mismatch": REASON_MISMATCHED,
    "evidence_revoked": REASON_MISMATCHED,
    "superseded_result_set": REASON_MISMATCHED,
}


# --- Small normalization helpers ---


def _identity(value: Any) -> Optional[str]:
    """Return a concrete identity string, or ``None`` for aliases/unknowns."""
    if value is None:
        return None
    text = str(value).strip()
    return None if not text or text.casefold() in _UNKNOWN_IDENTITIES else text


def _route_pair(value: Any) -> Tuple[Optional[str], Optional[str]]:
    if not isinstance(value, Mapping):
        return None, None
    return _identity(value.get("provider")), _identity(value.get("model"))


def _first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def normalize_task_scope(
    scope: Any = None,
    *,
    task_policy: Any = None,
    decision_options: Any = None,
    subject_field: Any = None,
) -> Dict[str, Any]:
    """Canonical task scope used for exact matching.

    Mirrors the assessment qualification registry scope: the taught policy
    text, the ordered decision vocabulary and the subject field. Extra keys
    are ignored: they cannot broaden or narrow what the qualification
    contract itself names.
    """
    raw = dict(scope) if isinstance(scope, Mapping) else {}
    policy = task_policy if task_policy is not None else raw.get("task_policy")
    options = (
        decision_options if decision_options is not None
        else raw.get("decision_options"))
    subject = (
        subject_field if subject_field is not None
        else raw.get("subject_field"))
    option_list = (
        [options] if isinstance(options, str)
        else [str(item) for item in options]
        if isinstance(options, Iterable) else [])
    return {
        "task_policy": "" if policy is None else str(policy),
        "decision_options": option_list,
        "subject_field": "" if subject is None else str(subject),
    }


def task_scope_digest(scope: Any) -> str:
    """Stable digest of the canonical task scope."""
    canonical = normalize_task_scope(scope)
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        .encode("utf-8")).hexdigest()


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse a durable timestamp without inventing one."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        # Date-only frozen dates are a conservative lower bound (midnight UTC).
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d").replace(
                tzinfo=timezone.utc)
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _observed_at(record: Mapping[str, Any]) -> Tuple[Optional[datetime], str]:
    """Find an evidence timestamp and say where it came from."""
    for key in (
            "observed_at", "evaluated_at", "verified_at", "recorded_at",
            "created_at", "completed_at", "finished_at", "started_at"):
        parsed = _parse_datetime(record.get(key))
        if parsed is not None:
            return parsed, key
    return None, "missing"


def _as_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _serving_pairs(value: Any) -> List[Dict[str, str]]:
    pairs: List[Dict[str, str]] = []
    for entry in value if isinstance(value, (list, tuple)) else ():
        provider, model = _route_pair(entry)
        pair = {"provider": provider or "", "model": model or ""}
        pair = {key: text for key, text in pair.items() if text}
        if pair and pair not in pairs:
            pairs.append(pair)
    return pairs


def _is_global_evidence(record: Mapping[str, Any]) -> bool:
    """True for a global ranking/leaderboard, never a task-scoped result."""
    if record.get("global") is True or record.get("task_equivalent") is False:
        return True
    label = " ".join(
        str(record.get(key) or "").casefold()
        for key in ("source", "kind", "evidence_type", "evidence_kind"))
    return any(token in label for token in _GLOBAL_EVIDENCE_TOKENS)


# --- Evidence record (typed) ---


@dataclass
class _Record:
    evidence_id: str
    source: str
    provider: Optional[str]
    model: Optional[str]
    task_scope: Optional[Dict[str, Any]]
    task_scope_digest: Optional[str]
    rubric_version: str
    contract_version: str
    passed: Optional[bool]
    accuracy: Optional[float]
    abstention: Optional[bool]
    abstention_scored: bool
    observed_at: Optional[str]
    observed_at_source: str
    observed_dt: Optional[datetime]
    dataset_id: str
    dataset_sha256: str
    scoring_version: str
    registry_status: str
    revoked: bool
    is_global: bool
    phase: str
    build: Optional[str]
    issues: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    reason_classes: List[str] = field(default_factory=list)


def _served_identity(
    record: Mapping[str, Any],
) -> Tuple[Optional[str], Optional[str], List[str], str]:
    """Extract the ONE served provider/model pair, plus identity issues.

    Requested/attempted routes are never accepted: only the identity that
    produced the result is evidence. A record naming several serving routes
    (or an unattributed call) is reported as ambiguous.
    """
    issues: List[str] = []
    provider: Optional[str] = None
    model: Optional[str] = None
    source = ""

    nested = record.get("model_provenance")
    # A non-empty structured provenance object is authoritative even when it
    # says "unknown": falling back to a top-level pair would relabel an
    # explicitly unattributed record. An empty object is not a claim, so the
    # legacy top-level fields remain usable.
    nested_authoritative = isinstance(nested, Mapping) and bool(nested)
    if nested_authoritative:
        provenance = provenance_from_metadata({"model_provenance": nested})
        provider = _identity(provenance.get("provider"))
        model = _identity(provenance.get("model"))
        source = "model_provenance"

    # Source selection is atomic: the first source that names either member
    # is authoritative, and the missing member is never completed from a
    # different source (a mixed "new-provider/old-model" identity is not
    # evidence for either route).
    if not nested_authoritative:
        for label, extract in (
                ("served_route",
                 lambda r: _route_pair(r.get("served_route"))),
                ("route", lambda r: _route_pair(r.get("route"))),
                ("model_route", lambda r: _route_pair(r.get("model_route"))),
                ("served_provider_model",
                 lambda r: (
                     _identity(_first_present(
                         r, "served_provider", "route_provider")),
                     _identity(_first_present(
                         r, "served_model", "route_model")))),
                ("provider_model",
                 lambda r: (
                     _identity(r.get("provider")),
                     _identity(r.get("model")))),
        ):
            cand_provider, cand_model = extract(record)
            if cand_provider or cand_model:
                provider, model, source = cand_provider, cand_model, label
                break

    serving_pairs = _serving_pairs(
        record.get("serving_models")
        or (nested.get("serving_models")
            if isinstance(nested, Mapping) else None))
    if serving_pairs:
        if len(serving_pairs) > 1:
            issues.append("mixed_serving_identity")
        if provider and model:
            if {"provider": provider, "model": model} not in serving_pairs:
                issues.append("serving_identity_conflict")
        elif (not nested_authoritative and not provider and not model
              and len(serving_pairs) == 1):
            provider = serving_pairs[0].get("provider")
            model = serving_pairs[0].get("model")
            source = "serving_models"

    unattributed = _first_present(record, "unattributed_calls")
    if unattributed is None and isinstance(nested, Mapping):
        unattributed = _first_present(nested, "unattributed_calls")
    try:
        if int(unattributed or 0) > 0:
            issues.append("unattributed_calls")
    except (TypeError, ValueError):
        pass

    if not provider and not model:
        issues.append("identity_missing")
    elif not provider or not model:
        issues.append("identity_partial")
    return provider, model, issues, source


def _empty_scope(scope: Mapping[str, Any]) -> bool:
    return not (
        str(scope.get("task_policy") or "").strip()
        or scope.get("decision_options")
        or str(scope.get("subject_field") or "").strip()
    )


def _record_scope(record: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    scope = record.get("task_scope")
    if not isinstance(scope, Mapping):
        scope = record.get("scope")
    source = (
        scope if isinstance(scope, Mapping)
        else record if any(key in record for key in _SCOPE_FIELDS)
        else None)
    if source is None:
        return None
    canonical = normalize_task_scope(source)
    return None if _empty_scope(canonical) else canonical


def _status_values(
    record: Mapping[str, Any],
) -> Tuple[Optional[bool], List[str], Optional[bool], bool]:
    """Resolve a result's pass/fail tri-state plus its abstention verdict."""
    values: List[Tuple[str, bool]] = []
    for key in ("passed", "ok"):
        value = record.get(key)
        if isinstance(value, bool):
            values.append((key, value))
    status = str(record.get("status") or "").strip().casefold()
    for key, text in (
            ("status", status),
            ("judgment",
             str(record.get("judgment") or "").strip().casefold())):
        if text in _PASSED_STATUSES:
            values.append((key, True))
        elif text in _FAILED_STATUSES:
            values.append((key, False))
    abstention: Optional[bool] = None
    abstention_scored = False
    safe = record.get("safe_abstention")
    if isinstance(safe, Mapping) and isinstance(safe.get("passed"), bool):
        abstention = safe["passed"]
        abstention_scored = True
        values.append(("safe_abstention", safe["passed"]))
    if not values:
        return None, (
            ["result_status_unresolved"]
            if status in _UNRESOLVED_STATUSES else []), \
            abstention, abstention_scored
    distinct = {value for _key, value in values}
    if len(distinct) > 1:
        return None, ["status_conflict"], abstention, abstention_scored
    return values[0][1], [], abstention, abstention_scored


def _registry_passed(value: Any) -> Optional[bool]:
    text = str(value or "").strip().casefold()
    if text in _PASSED_STATUSES:
        return True
    return False if text in _FAILED_STATUSES else None


def _model_build(record: Mapping[str, Any], nested: Any) -> Optional[str]:
    """The model build identity, when the record carries one.

    ``resolved_model`` is the provider-echoed checkpoint id from
    ``core.llm.model_provenance``; build/version fields are equivalents.
    A missing build is not a defect; a conflicting one is ambiguous.
    """
    build = _identity(_first_present(
        record, "resolved_model", "model_build", "build_id", "model_version"))
    if build is None and isinstance(nested, Mapping):
        build = _identity(nested.get("resolved_model"))
    return build


def _normalize_record(raw: Mapping[str, Any], index: int) -> _Record:
    record = dict(raw) if isinstance(raw, Mapping) else {}
    nested = record.get("model_provenance")
    provider, model, identity_issues, _identity_source = _served_identity(
        record)
    issues: List[str] = [
        str(item) for item in (record.get("issues") or [])
        if str(item).strip()
    ]
    issues.extend(identity_issues)
    scope = _record_scope(record)
    observed, observed_source = _observed_at(record)
    passed, status_issues, abstention, abstention_scored = _status_values(
        record)
    issues.extend(status_issues)

    registry_status = str(
        record.get("registry_status") or "").strip().casefold()
    registry_passed = _registry_passed(registry_status)
    if registry_passed is not None and passed is not None and (
            registry_passed != passed):
        issues.append("registry_result_disagreement")

    declared_provider = _identity(
        _first_present(record, "declared_provider", "registry_provider"))
    declared_model = _identity(
        _first_present(record, "declared_model", "registry_model"))
    if (declared_provider and provider and declared_provider != provider) or (
            declared_model and model and declared_model != model):
        issues.append("declared_served_identity_mismatch")

    if bool(record.get("revoked")):
        issues.append("evidence_revoked")

    scoring = record.get("scoring")
    scoring_version = (
        str(scoring.get("version") or "").strip()
        if isinstance(scoring, Mapping) else "")
    if not scoring_version:
        scoring_version = str(record.get("scoring_version") or "").strip()

    return _Record(
        evidence_id=(
            str(record.get("evidence_id") or "").strip() or f"evidence:{index}"),
        source=str(record.get("source") or record.get("kind") or ""),
        provider=provider, model=model,
        task_scope=scope,
        task_scope_digest=(
            task_scope_digest(scope) if scope is not None else None),
        rubric_version=str(record.get("rubric_version") or "").strip(),
        contract_version=str(record.get("contract_version") or "").strip(),
        passed=passed,
        accuracy=_as_float(
            record.get("accuracy")
            if record.get("accuracy") is not None else record.get("score")),
        abstention=abstention, abstention_scored=abstention_scored,
        observed_at=_iso(observed), observed_at_source=observed_source,
        observed_dt=observed,
        dataset_id=str(record.get("dataset_id") or "").strip(),
        dataset_sha256=str(record.get("dataset_sha256") or "").strip(),
        scoring_version=scoring_version,
        registry_status=registry_status,
        revoked=bool(record.get("revoked")),
        is_global=_is_global_evidence(record),
        phase=str(record.get("phase") or "").strip(),
        build=_model_build(record, nested),
        issues=issues,
    )


# --- Freshness policy ---


@dataclass(frozen=True)
class _Freshness:
    policy: str
    window_days: int


def _positive_days(raw: Any) -> Optional[int]:
    if isinstance(raw, bool):
        return None
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return None
    return days if days > 0 else None


def _freshness_policy(
    *,
    freshness_days: Optional[int],
    freshness_policy: Any,
    profile_name: Optional[str],
) -> _Freshness:
    """Resolve the freshness window; always a positive number of days.

    Precedence: explicit ``freshness_days`` > injected policy object >
    named ``CapabilityProfile`` > module default. Zero, negative, malformed
    or missing inputs fall back to the default and never bypass freshness.
    """
    days = DEFAULT_EVIDENCE_WINDOW_DAYS
    label = "default"

    def adopt(raw: Any, source: str) -> None:
        nonlocal days, label
        resolved = _positive_days(raw)
        if resolved is None:
            logger.warning(
                "model evidence freshness: ignoring bad window %r from %s; "
                "using the default window", raw, source)
            return
        days = resolved
        label = source

    if freshness_policy is not None:
        if isinstance(freshness_policy, Mapping):
            name = str(freshness_policy.get("name") or "").strip()
            version = str(freshness_policy.get("version") or "").strip()
            adopt(
                _first_present(
                    freshness_policy, "evidence_window_days",
                    "freshness_days", "window_days"),
                f"capability_profile:{name}@{version}" if name
                else "injected_policy")
        else:
            # Duck-typed CapabilityProfile (avoids a hard runtime import).
            name = str(getattr(freshness_policy, "name", "") or "").strip()
            version = str(getattr(freshness_policy, "version", "") or "").strip()
            adopt(
                getattr(freshness_policy, "evidence_window_days", None),
                f"capability_profile:{name}@{version}" if name
                else "injected_policy")

    if profile_name:
        from core.llm.capability_profiles import get_profile

        profile = get_profile(profile_name)
        adopt(
            profile.evidence_window_days,
            f"capability_profile:{profile.name}@{profile.version}")

    if freshness_days is not None:
        adopt(freshness_days, "explicit")

    return _Freshness(policy=label, window_days=days)


# --- Comparison ---


def _normalize_candidate(raw: Any) -> Dict[str, str]:
    provider, model = (
        _route_pair(raw) if isinstance(raw, Mapping) else (None, None))
    if isinstance(raw, Mapping) and not (provider and model):
        provider = provider or _identity(raw.get("provider"))
        model = model or _identity(raw.get("model"))
    return {
        "provider": provider or "", "model": model or "",
        "route": f"{provider}/{model}" if provider and model else "",
    }


#: Stable order for the known qualification phases. A phase name is an
#: explicit sequence signal when several judged results share one timestamp;
#: unknown phases sort before known ones rather than being guessed as newest.
_PHASE_ORDER = {
    "preflight": 0, "create": 1, "correct": 2,
    "after-restart": 3, "restart": 3,
}


def _record_order(record: _Record) -> Tuple[float, str, int, str, str]:
    observed = record.observed_dt
    return (
        observed.timestamp() if observed is not None else float("-inf"),
        record.scoring_version,
        _PHASE_ORDER.get(record.phase, 0),
        record.dataset_id,
        record.dataset_sha256,
    )


def _timestamp_or_neg_inf(value: Any) -> float:
    parsed = _parse_datetime(value)
    return parsed.timestamp() if parsed is not None else float("-inf")


def _cohort_key(record: _Record) -> Tuple[str, str, str]:
    return record.dataset_id, record.dataset_sha256, record.scoring_version


def _add_reasons(record: _Record, reasons: Iterable[str]) -> None:
    for reason in reasons:
        if reason and reason not in record.reasons:
            record.reasons.append(reason)
    record.reason_classes = [
        _REASON_CLASS[reason]
        for reason in dict.fromkeys(record.reasons)
        if reason in _REASON_CLASS]


def _not_task_entry(record: _Record) -> Dict[str, Any]:
    return {
        "evidence_id": record.evidence_id,
        "provider": record.provider, "model": record.model,
        "reasons": list(record.reasons),
        "classes": list(record.reason_classes),
    }


def _evidence_summary(record: _Record) -> Dict[str, Any]:
    return {
        "evidence_id": record.evidence_id, "source": record.source,
        "phase": record.phase or None,
        "observed_at": record.observed_at,
        "observed_at_source": record.observed_at_source,
        "dataset_id": record.dataset_id or None,
        "dataset_sha256": record.dataset_sha256 or None,
        "scoring_version": record.scoring_version or None,
        "accuracy": record.accuracy, "passed": record.passed,
        "abstention": record.abstention, "model_build": record.build,
        "registry_status": record.registry_status or None,
    }


def _blocked_candidate(
    route: str,
    provider: Optional[str],
    model: Optional[str],
    classes: List[str],
    reasons: List[str],
    observed_at: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "route": route, "provider": provider, "model": model,
        "evidence_state": "insufficient", "passed": None, "score": None,
        "observed_at": observed_at, "reason_classes": classes,
        "reasons": reasons, "evidence": None,
    }


def _baseline_summary(
    route: Optional[str],
    state: str,
    chosen: Optional[_Record],
) -> Dict[str, Any]:
    """The baseline block: its newest passing result is the floor."""
    if chosen is None:
        return {
            "route": route, "state": state, "score": None,
            "observed_at": None, "dataset_sha256": None,
            "abstention_scored": False,
        }
    return {
        "route": route, "state": state, "score": chosen.accuracy,
        "observed_at": chosen.observed_at,
        "dataset_id": chosen.dataset_id or None,
        "dataset_sha256": chosen.dataset_sha256 or None,
        "abstention_scored": chosen.abstention_scored,
        "abstention_passed": chosen.abstention,
    }


def _evaluate_candidate(
    candidate: Mapping[str, str],
    normalized: Sequence[_Record],
    comparable: Sequence[_Record],
    *,
    min_accuracy: Optional[float],
    baseline_block: Optional[Mapping[str, Any]],
    baseline_score: Optional[float],
    baseline_abstention_scored: bool,
) -> Dict[str, Any]:
    """Evaluate one exact route against the comparable evidence."""
    provider = candidate["provider"]
    model = candidate["model"]
    route = candidate["route"]
    if not provider or not model:
        return _blocked_candidate(
            route or "unknown", provider, model,
            [REASON_MISSING], ["identity_missing"])

    records = [
        record for record in normalized
        if record.provider == provider and record.model == model]
    if not records:
        return _blocked_candidate(
            route, provider, model,
            [REASON_MISSING], ["no_task_scoped_evidence"])

    relevant = [
        record for record in comparable
        if record.provider == provider and record.model == model]
    if not relevant:
        reasons = list(dict.fromkeys(
            reason for record in records for reason in record.reasons))
        classes = list(dict.fromkeys(
            category for record in records
            for category in record.reason_classes))
        if not reasons:
            reasons, classes = ["superseded_result_set"], [REASON_MISMATCHED]
        return _blocked_candidate(route, provider, model, classes, reasons)

    latest_order = max(_record_order(record) for record in relevant)
    latest = [r for r in relevant if _record_order(r) == latest_order]

    # Conflicting outcomes or builds among the newest results are ambiguous.
    reasons = []
    if len({(r.passed, r.accuracy) for r in latest}) > 1:
        reasons.append("conflicting_newest_evidence")
    if len({r.build for r in latest if r.build}) > 1:
        reasons.append("model_build_conflict")
    if reasons:
        return _blocked_candidate(
            route, provider, model, [REASON_AMBIGUOUS], reasons,
            _iso(latest[0].observed_dt))

    chosen = sorted(latest, key=lambda record: record.evidence_id)[0]
    reasons = []
    classes: List[str] = []
    if chosen.passed is False:
        # Valid negative evidence: the route ran the task and failed it.
        reasons.append("evidence_not_passed")
    elif chosen.passed is None:
        reasons.append("result_status_unresolved")
        classes.append(REASON_AMBIGUOUS)
    else:
        if (min_accuracy is not None
                and chosen.accuracy is not None
                and chosen.accuracy < float(min_accuracy)):
            reasons.append("below_accuracy_floor")
        if baseline_block is not None and (
                baseline_block["state"] == "established"):
            if (baseline_score is not None
                    and (chosen.accuracy is None
                         or chosen.accuracy < baseline_score)):
                reasons.append("baseline_not_met")
            if baseline_abstention_scored and chosen.abstention is not True:
                reasons.append("abstention_not_met")

    if chosen.passed is False:
        state = "failed"
    elif chosen.passed is None:
        state = "insufficient"
    elif reasons:
        # Below the accuracy floor or the graduation baseline: a valid
        # negative routing result, not missing evidence.
        state = "failed"
    else:
        state = "sufficient"
    return {
        "route": route, "provider": provider, "model": model,
        "evidence_state": state, "passed": chosen.passed,
        "score": chosen.accuracy, "observed_at": chosen.observed_at,
        "reason_classes": classes, "reasons": reasons,
        "evidence": _evidence_summary(chosen),
    }


def compare_model_evidence(
    *,
    task_scope: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
    candidates: Optional[Sequence[Mapping[str, Any]]] = None,
    rubric_version: Optional[str] = None,
    contract_version: Optional[str] = None,
    freshness_days: Optional[int] = None,
    freshness_policy: Any = None,
    profile_name: Optional[str] = None,
    now: Optional[datetime] = None,
    min_accuracy: Optional[float] = None,
    baseline: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Compare exact model routes on one repeated task scope.

    ``task_scope`` carries the canonical ``task_policy``,
    ``decision_options`` and ``subject_field``; ``evidence`` records must
    name the served ``provider``/``model`` (or ``served_provider``/
    ``served_model`` / structured ``model_provenance``) and the same task
    scope. ``rubric_version``/``contract_version`` are required when given.
    ``freshness_days``/``freshness_policy``/``profile_name`` resolve the
    freshness window through an existing policy when possible; non-positive
    or malformed windows fall back to the default. ``min_accuracy`` is an
    optional accuracy floor. ``baseline`` names the graduation baseline
    route: the candidate must meet its newest passing result on the same
    dataset hash, rubric and scope (including abstention where scored), and
    a baseline that cannot be established blocks selection.

    Returns a JSON-serializable comparison. ``outcome`` is ``"compared"``
    only when at least one candidate has sufficient passing evidence
    meeting every floor; otherwise ``"insufficient_evidence"`` with
    explicit reason classes.
    """
    request_scope = normalize_task_scope(task_scope)
    request_digest = task_scope_digest(request_scope)
    request_rubric = str(rubric_version or "").strip()
    request_contract = str(contract_version or "").strip()

    freshness = _freshness_policy(
        freshness_days=freshness_days,
        freshness_policy=freshness_policy,
        profile_name=profile_name,
    )
    evaluated_at = now or datetime.now(timezone.utc)
    if evaluated_at.tzinfo is None:
        evaluated_at = evaluated_at.replace(tzinfo=timezone.utc)
    cutoff = evaluated_at - timedelta(days=freshness.window_days)

    normalized = [
        _normalize_record(raw, index)
        for index, raw in enumerate(evidence or [])
    ]

    not_task_evidence: List[Dict[str, Any]] = []
    for record in normalized:
        reasons: List[str] = list(record.issues)
        if record.is_global:
            reasons.append("global_leaderboard_not_task_evidence")
        if record.task_scope is None:
            reasons.append("task_scope_missing")
        elif record.task_scope_digest != request_digest:
            reasons.append("task_scope_mismatch")
        for required, present, field_name in (
                (request_rubric, record.rubric_version, "rubric_version"),
                (request_contract, record.contract_version,
                 "contract_version")):
            if not required:
                continue
            if not present:
                reasons.append(f"{field_name}_missing")
            elif present != required:
                reasons.append(f"{field_name}_mismatch")
        if record.observed_dt is None:
            reasons.append("observed_at_missing")
        elif record.observed_dt > evaluated_at:
            # A timestamp in the future is not a trustworthy result time.
            reasons.append("observed_at_untrusted")
        elif record.observed_dt < cutoff:
            reasons.append("evidence_expired")
        if record.passed is None and not reasons:
            # An unattributable pass/fail is unknown, not a negative result.
            reasons.append("result_status_unresolved")
        _add_reasons(record, reasons)
        if record.reason_classes:
            not_task_evidence.append(_not_task_entry(record))

    # Usable = exact identity, scope/rubric/contract, unrevoked, no
    # ambiguity/staleness. A failed result is still usable negative evidence.
    usable = [
        record for record in normalized
        if not record.reason_classes and record.provider and record.model]

    requested: List[Dict[str, str]] = []
    seen: set[Tuple[str, str]] = set()
    for raw_candidate in (candidates or []):
        candidate = _normalize_candidate(raw_candidate)
        key = (candidate["provider"], candidate["model"])
        if key not in seen:
            seen.add(key)
            requested.append(candidate)
    if not requested:
        keys = sorted({
            (record.provider, record.model)
            for record in normalized if record.provider and record.model})
        requested = [
            {"provider": p, "model": m, "route": f"{p}/{m}"}
            for p, m in keys]

    # The baseline route joins the compared set so its cohort can anchor the
    # score floor on the same dataset hash/scoring generation.
    candidate_keys = {
        (item["provider"], item["model"]) for item in requested
        if item["provider"] and item["model"]
    }
    baseline_provider: Optional[str] = None
    baseline_model: Optional[str] = None
    if baseline is not None:
        baseline_provider, baseline_model = (
            _route_pair(baseline) if isinstance(baseline, Mapping)
            else (None, None))
        if baseline_provider and baseline_model:
            candidate_keys.add((baseline_provider, baseline_model))
    baseline_route: Optional[Tuple[str, str]] = (
        (baseline_provider, baseline_model)
        if baseline_provider and baseline_model else None)

    # Comparability is over the requested routes: another route's newer run
    # must not supersede the cohort for the routes being compared.
    comparable_source = [
        record for record in usable
        if not candidate_keys
        or (record.provider, record.model) in candidate_keys
    ]

    # "Newest valid comparable results": one cohort (dataset/scoring) wins;
    # older cohorts are superseded, not mixed into the comparison.
    newest_cohort: Optional[Tuple[str, str, str]] = None
    if comparable_source:
        cohort_orders: Dict[
            Tuple[str, str, str], Tuple[float, str, int, str, str]] = {}
        for record in comparable_source:
            key = _cohort_key(record)
            order = _record_order(record)
            if key not in cohort_orders or order > cohort_orders[key]:
                cohort_orders[key] = order
        newest_cohort = max(cohort_orders.items(), key=lambda i: i[1])[0]

    comparable: List[_Record] = []
    for record in comparable_source:
        if newest_cohort is not None and _cohort_key(record) != newest_cohort:
            _add_reasons(record, ["superseded_result_set"])
            not_task_evidence.append(_not_task_entry(record))
            continue
        comparable.append(record)

    # The graduation baseline's newest passing comparable result defines the
    # score (and abstention) floor for every candidate.
    baseline_block: Optional[Dict[str, Any]] = None
    baseline_score: Optional[float] = None
    baseline_abstention_scored = False
    if baseline is not None:
        baseline_block = _baseline_summary(
            "/".join(baseline_route) if baseline_route else None,
            "invalid_identity" if baseline_route is None
            else "not_established",
            None)
        if baseline_route is not None:
            qualifying = sorted(
                (record for record in comparable
                 if (record.provider, record.model) == baseline_route
                 and record.passed is True),
                key=lambda r: (_record_order(r), r.evidence_id))
            if qualifying:
                chosen_baseline = qualifying[-1]
                baseline_score = chosen_baseline.accuracy
                baseline_abstention_scored = chosen_baseline.abstention_scored
                baseline_block = _baseline_summary(
                    "/".join(baseline_route), "established", chosen_baseline)

    candidate_results = [
        _evaluate_candidate(
            candidate, normalized, comparable,
            min_accuracy=min_accuracy,
            baseline_block=baseline_block,
            baseline_score=baseline_score,
            baseline_abstention_scored=baseline_abstention_scored,
        )
        for candidate in requested
    ]

    ranked = sorted(
        (
            candidate for candidate in candidate_results
            if candidate["evidence_state"] == "sufficient"
        ),
        key=lambda candidate: (
            0 if candidate["score"] is not None else 1,
            -(candidate["score"] or 0.0),
            -_timestamp_or_neg_inf(candidate["observed_at"]),
            candidate["provider"],
            candidate["model"],
        ),
    )

    top_reasons: List[str] = [
        category
        for candidate in candidate_results
        if candidate["evidence_state"] == "insufficient"
        for category in candidate["reason_classes"]
    ]
    # A record with no attributable route cannot appear in candidate_reasons;
    # surface its class so "model only" / "auto" evidence is never omitted.
    top_reasons.extend(
        category
        for record in normalized
        if not (record.provider and record.model)
        for category in record.reason_classes)
    if not normalized:
        top_reasons.append(REASON_MISSING)
    if baseline_block is not None and baseline_block["state"] != "established":
        # No baseline on the same dataset/rubric/scope: nothing is confirmable.
        top_reasons.append(REASON_MISSING)
        ranked = []
    if not ranked and any(
            candidate["evidence_state"] == "failed"
            for candidate in candidate_results):
        top_reasons.append(REASON_NO_PASSING)
    if not ranked and not top_reasons:
        # Nothing passed, and nothing was missing/mismatched either.
        top_reasons.append(REASON_NO_PASSING)
    top_reasons = sorted(
        set(top_reasons),
        key=lambda reason: (
            _REASON_ORDER.index(reason)
            if reason in _REASON_ORDER else len(_REASON_ORDER),
            reason,
        ),
    )

    if ranked and not top_reasons:
        evidence_state = "sufficient"
        insufficient = None
    else:
        evidence_state = "partial" if ranked else "insufficient"
        insufficient = {
            "state": INSUFFICIENT_EVIDENCE,
            "reasons": top_reasons,
            "candidate_reasons": {
                candidate["route"]: list(candidate["reasons"])
                for candidate in candidate_results
                if ranked and candidate["evidence_state"] != "sufficient"
                or not ranked
            },
            "detail": (
                "At least one exact route has sufficient task-scoped "
                "evidence; routes listed in candidate_reasons do not."
                if ranked else
                "No exact route has sufficient task-scoped, current, "
                "comparable passing evidence. Do not substitute a global "
                "leaderboard or another task's results."),
        }

    comparison_set = (
        None if newest_cohort is None else {
            "dataset_id": newest_cohort[0] or None,
            "dataset_sha256": newest_cohort[1] or None,
            "scoring_version": newest_cohort[2] or None,
        })

    return {
        "schema": SCHEMA_VERSION,
        "task_scope": {**request_scope, "digest": request_digest},
        "rubric_version": request_rubric or None,
        "contract_version": request_contract or None,
        "freshness": {
            "policy": freshness.policy,
            "window_days": freshness.window_days,
            "evaluated_at": _iso(evaluated_at), "cutoff": _iso(cutoff),
        },
        "comparison_set": comparison_set,
        "baseline": baseline_block,
        "outcome": COMPARED if ranked else INSUFFICIENT_EVIDENCE,
        "evidence_state": evidence_state,
        "insufficient_evidence": insufficient,
        "candidates": candidate_results,
        "ranked": ranked,
        "selected": ranked[0] if ranked else None,
        "not_task_evidence": not_task_evidence,
        "evidence_count": len(normalized),
    }


# --- Assessment qualification registry loader ---


def _repo_root() -> Path:
    # backend/core/llm/model_evidence_comparison.py -> repository root
    return Path(__file__).resolve().parents[3]


def _resolve_evidence_path(raw: Any, *, repo_root: Path) -> Optional[Path]:
    """Resolve a registry-referenced path, refusing escapes from the root.

    A path outside the root is not authoritative model evidence; the caller
    gets an explicit missing-evidence record instead.
    """
    text = str(raw or "").strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = repo_root / path
    try:
        resolved = path.resolve()
        resolved.relative_to(repo_root.resolve())
    except (OSError, ValueError):
        return None
    return resolved


def _locate_evidence_path(
    raw: Any,
    *,
    registry_path: Optional[str],
    repo_root: Path,
) -> Optional[Path]:
    """Resolve an evidence path against the registry directory or root.

    A temporary/test registry may keep evidence beside its own file; the
    first existing, in-root candidate wins. Escapes are refused.
    """
    bases: List[Path] = []
    if registry_path:
        bases.append(Path(registry_path).resolve().parent)
    bases.append(repo_root)
    for base in dict.fromkeys(bases):
        candidate = _resolve_evidence_path(raw, repo_root=base)
        if candidate is not None and candidate.exists():
            return candidate
    return None


def _frozen_dataset(
    evidence_path: Optional[Path],
) -> Optional[Tuple[str, str]]:
    """The frozen set's ``(ISO date, id)`` — a conservative freshness bound.

    The date may bound freshness only for scored runs verifiably bound to
    this frozen set: the caller matches the run's ``dataset_id`` first.
    """
    if evidence_path is None:
        return None
    base = evidence_path if evidence_path.is_dir() else evidence_path.parent
    for directory in (base, *list(base.parents)[:3]):
        candidate = directory / "qualification-set.json"
        if not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text())
        except Exception:  # noqa: BLE001 — optional metadata
            continue
        frozen = _parse_datetime(
            payload.get("frozen") if isinstance(payload, Mapping) else None)
        frozen_id = str(
            payload.get("id") or "").strip() if isinstance(
            payload, Mapping) else ""
        if frozen is not None and frozen_id:
            return _iso(frozen), frozen_id
    return None


def _iter_result_payloads(
    evidence_path: Optional[Path],
) -> Iterable[Tuple[Path, Dict[str, Any]]]:
    """Yield frozen workload results referenced by a registry entry.

    Only JSON objects that identify a served route are results; manifests,
    state files and READMEs are ignored. The size cap keeps a stray large
    artifact from being parsed as evidence.
    """
    if evidence_path is None or not evidence_path.exists():
        return
    files = (
        [evidence_path] if evidence_path.is_file()
        else sorted(evidence_path.rglob("*.json")))
    for path in files:
        try:
            if path.stat().st_size > 2_000_000:
                continue
            payload = json.loads(path.read_text())
        except Exception:  # noqa: BLE001 — a corrupt artifact is not evidence
            continue
        if not isinstance(payload, Mapping):
            continue
        schema = str(payload.get("schema") or "")
        # A frozen workload *judgment* is the result artifact; raw provider
        # payloads and canvas state also carry a route but are not judged
        # results and must not become comparison evidence.
        is_judgment = schema.startswith(
            "atom-substantive-assessment-judgment")
        has_served_pair = bool(
            payload.get("served_provider") and payload.get("served_model"))
        if is_judgment or has_served_pair:
            yield path, payload


def _registry_base_record(
    entry: Mapping[str, Any],
    *,
    registry_path: Optional[str],
    evidence_missing: bool = False,
) -> Dict[str, Any]:
    status = str(entry.get("status") or "").strip()
    registry_passed = _registry_passed(status)
    return {
        "source": "assessment_qualification",
        "issues": ["evidence_path_missing"] if evidence_missing else [],
        "evidence_id": f"registry:{entry.get('id') or 'configuration'}",
        "provider": entry.get("provider"), "model": entry.get("model"),
        "task_scope": entry.get("scope"),
        "contract_version": entry.get("contract_version"),
        "rubric_version": entry.get("rubric_version") or "",
        "registry_status": status,
        "registry_path": registry_path,
        "revoked": bool(entry.get("revoked")),
        # A registry row alone is not a scored result: a positive status
        # stays unresolved and is never positive benchmark evidence. A
        # failure stays negative evidence; revocation stays mismatched.
        "passed": False if registry_passed is False else None,
        "observed_at": _first_present(
            entry, "observed_at", "verified_at", "qualified_at",
            "evaluated_at"),
    }


def _result_record(
    entry: Mapping[str, Any],
    path: Path,
    payload: Mapping[str, Any],
    *,
    frozen: Optional[Tuple[str, str]],
    observed_at: Optional[Any],
    registry_path: Optional[str],
) -> Dict[str, Any]:
    scoring = payload.get("scoring")
    scoring_version = (
        str(scoring.get("version") or "").strip()
        if isinstance(scoring, Mapping) else "")
    provider, model, _issues, _source = _served_identity(payload)
    schema = str(payload.get("schema") or "")
    # Only a scored artifact can carry a verdict: a raw "success"-labeled
    # dump is never positive benchmark evidence.
    scored = (
        isinstance(payload.get("ok"), bool)
        or payload.get("accuracy") is not None
        or schema.startswith("atom-substantive-assessment-judgment"))
    record = {
        "source": "assessment_qualification",
        "issues": [] if scored else ["unscored_artifact"],
        "evidence_id": (
            f"{entry.get('id') or 'configuration'}:{path.parent.name}/"
            f"{path.name}:{payload.get('phase') or ''}"),
        "provider": provider, "model": model,
        "declared_provider": entry.get("provider"),
        "declared_model": entry.get("model"),
        "task_scope": entry.get("scope"),
        "contract_version": entry.get("contract_version"),
        "rubric_version": (
            payload.get("rubric_version")
            or entry.get("rubric_version") or ""),
        "registry_status": entry.get("status"),
        "registry_path": registry_path,
        "revoked": bool(entry.get("revoked")),
        "passed": payload.get("ok") if scored else None,
        "status": (
            (payload.get("judgment") or payload.get("status"))
            if scored else None),
        "judgment": payload.get("judgment") if scored else None,
        "safe_abstention": payload.get("safe_abstention"),
        "accuracy": payload.get("accuracy"),
        "dataset_id": payload.get("dataset_id"),
        "dataset_sha256": payload.get("dataset_sha256"),
        "scoring_version": scoring_version,
        "phase": payload.get("phase"),
        "serving": entry.get("serving"),
        "observed_at": observed_at,
        "observed_at_source": "explicit" if observed_at else None,
    }
    if not record["observed_at"]:
        for key in ("observed_at", "evaluated_at", "verified_at",
                    "recorded_at", "created_at", "finished_at", "started_at"):
            if payload.get(key):
                record["observed_at"] = payload.get(key)
                record["observed_at_source"] = f"result.{key}"
                break
    if not record["observed_at"]:
        for key in ("observed_at", "verified_at", "qualified_at",
                    "evaluated_at"):
            if entry.get(key):
                record["observed_at"] = entry.get(key)
                record["observed_at_source"] = f"registry.{key}"
                break
    if (not record["observed_at"] and frozen is not None
            and str(payload.get("dataset_id") or "").strip() == frozen[1]):
        # Verified binding: the run names this frozen set's id, so the
        # frozen declaration date is a conservative freshness bound.
        record["observed_at"] = frozen[0]
        record["observed_at_source"] = "frozen_dataset_date"
    return record


def load_assessment_qualification_evidence(
    registry: Optional[Mapping[str, Any]] = None,
    *,
    capability: str = "canvas_assessment.model_judgment",
    repo_root: Optional[Path] = None,
    observed_at: Optional[Any] = None,
    include_registry_only: bool = True,
) -> List[Dict[str, Any]]:
    """Load frozen assessment workload results as comparison evidence.

    The registry itself is the server-controlled qualification source; the
    ``judgment-*.json`` files it references are the frozen workload results
    carrying ``served_provider`` / ``served_model``. A registry entry with
    no readable workload result can still contribute its own qualification
    status when ``include_registry_only`` is true. ``registry`` is the
    parsed registry (loaded from the existing assessment qualification
    registry when omitted); ``capability`` filters entries; ``repo_root``
    anchors relative evidence paths; ``observed_at`` timestamps results.
    Returns records ready for :func:`compare_model_evidence`.
    """
    if registry is None:
        from core.canvas_capability_service import (
            load_assessment_qualification_registry,
        )

        registry = load_assessment_qualification_registry()
    root = Path(repo_root) if repo_root is not None else _repo_root()
    registry_path = (
        str(registry.get("path")) if isinstance(registry, Mapping)
        and registry.get("path") else None)

    records: List[Dict[str, Any]] = []
    for entry in (registry.get("configurations") or []):
        if not isinstance(entry, Mapping):
            continue
        if capability and str(entry.get("capability") or "") != capability:
            continue
        evidence_path = _locate_evidence_path(
            entry.get("evidence"),
            registry_path=registry_path,
            repo_root=root,
        )
        frozen = _frozen_dataset(evidence_path)
        results = list(_iter_result_payloads(evidence_path))
        for path, payload in results:
            records.append(_result_record(
                entry, path, payload,
                frozen=frozen, observed_at=observed_at,
                registry_path=registry_path))
        if not results and include_registry_only:
            records.append(_registry_base_record(
                entry,
                registry_path=registry_path,
                evidence_missing=bool(
                    str(entry.get("evidence") or "").strip())))
    return records
