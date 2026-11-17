"""Server-minted qualification authority for the dispatch quality floor.

WHY THIS EXISTS
---------------
The repeat-task resolver selects a route from *measured* held-out benchmark
evidence: the campaign producer seals the record, the canonical reader
revalidates it, the review/receipt chain binds it to the agent's qualification,
and the comparator decides freshness/baseline/build. The resolver then pins the
exact route/build for the structured qualification call.

One seam did NOT consume that measurement. The BYOK dispatch floor re-derived
its quality input from ``get_quality_score(model)`` (a static brand prior) or a
workspace-declared ``quality_score``, so a valid measured route with a low
static prior (e.g. an unknown gateway name scoring 70 against an 80 floor) was
refused *after* the resolver had already proven it. The comparator and the
attempt filter saw the measurement; the floor did not.

WHAT THIS IS
------------
A request-owned, server-built **reference** to the exact validated material
that justified one pin -- receipt/promotion/revision, evidence id + record and
core digests, benchmark/dataset/rubric/scoring, canonical workload-scope digest,
route and of observed build -- and a **revalidator** that re-reads the durable
authority through the existing canonical APIs at dispatch time.

The reference is NOT authority. It is a set of assertions to check. A bare
``qualified=true``, a float, request/plan metadata, client benchmark claims or
unbound generic feedback can never mint authority: :func:`revalidate` ignores
every claim and recomputes the pipeline (runtime baseline -> validated evidence
rows -> comparator) against durable state. Missing, stale, superseded,
tampered, foreign-scope, foreign-profile or wrong-receipt material fails
closed, and the caller keeps its honest no-suitable/supervised path.

SCOPE
-----
Only the profile's **measured quality-prior component** is substitutable, and
only after proof. Every operational gate (provider policy, credentials,
local-only, protocol, context fit, cooldown, failed-pin exclusion, unsafe
outcome quarantine, current budget, baseline comparability) stays independent
and unchanged. Generic feedback, unmeasured routes, raw operator pins and
callers without a qualification decision keep their historical prior.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Tuple

SCHEMA = "atom-qualification-authority-1"

#: Default measurement workload profile. It is the profile the repeat-task
#: resolver/discovery/comparator use (``graduation_route.ROUTE_PROFILE``).
DEFAULT_MEASUREMENT_PROFILE = "employee_evidence_selection"

_REQUIRED_TEXT = (
    "agent_id",
    "tenant_id",
    "workspace_id",
    "receipt_id",
    "promotion_id",
    "target_level",
    "source_level",
    "source_revision",
    "benchmark_id",
    "dataset_sha256",
    "rubric_version",
    "scoring_version",
    "workload_scope_digest",
    "provider",
    "model",
    "evidence_id",
    "evidence_record_sha256",
    "evidence_core_sha256",
    "observed_at",
    "measurement_profile",
    "measurement_profile_version",
)


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_utc(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def measured_quality(accuracy: Any) -> Optional[float]:
    """The same normalization the capability layer applies to a measurement.

    A 0..1 accuracy becomes a 0..100 quality; an already-normalized score is
    kept. Non-finite or negative values have no measured quality.
    """
    if accuracy is None or isinstance(accuracy, bool):
        return None
    try:
        value = float(accuracy)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value * 100.0 if value <= 1.0 else value


@dataclass(frozen=True)
class QualificationAuthority:
    """Immutable reference to ONE validated qualification measurement.

    Frozen so an in-process caller cannot mutate the object between minting and
    dispatch; the handler still revalidates every field, so a reconstructed or
    forged mapping is refused by the durable checks rather than trusted.
    """

    agent_id: str
    tenant_id: str
    workspace_id: str
    receipt_id: str
    promotion_id: str
    target_level: str
    source_level: str
    source_revision: str
    receipt_fingerprint: str
    review_fingerprint: str
    binding_state: str
    benchmark_id: str
    dataset_sha256: str
    rubric_version: str
    scoring_version: str
    workload_scope: Mapping[str, Any]
    workload_scope_digest: str
    baseline_route: Tuple[str, str]
    provider: str
    model: str
    build: Optional[str]
    evidence_id: str
    evidence_record_sha256: str
    evidence_core_sha256: str
    accuracy: float
    observed_at: str
    measurement_profile: str
    measurement_profile_version: str
    schema: str = SCHEMA

    @property
    def route(self) -> Tuple[str, str]:
        return (self.provider, self.model)

    def as_dict(self) -> Dict[str, Any]:
        """JSON-serializable reference (durable audit / dispatch kwarg)."""
        payload: Dict[str, Any] = {
            "schema": self.schema,
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "receipt_id": self.receipt_id,
            "promotion_id": self.promotion_id,
            "target_level": self.target_level,
            "source_level": self.source_level,
            "source_revision": self.source_revision,
            "receipt_fingerprint": self.receipt_fingerprint,
            "review_fingerprint": self.review_fingerprint,
            "binding_state": self.binding_state,
            "benchmark_id": self.benchmark_id,
            "dataset_sha256": self.dataset_sha256,
            "rubric_version": self.rubric_version,
            "scoring_version": self.scoring_version,
            "workload_scope": copy.deepcopy(dict(self.workload_scope)),
            "workload_scope_digest": self.workload_scope_digest,
            "baseline_route": {
                "provider": self.baseline_route[0],
                "model": self.baseline_route[1],
            },
            "provider": self.provider,
            "model": self.model,
            "build": self.build,
            "evidence_id": self.evidence_id,
            "evidence_record_sha256": self.evidence_record_sha256,
            "evidence_core_sha256": self.evidence_core_sha256,
            "accuracy": self.accuracy,
            "observed_at": self.observed_at,
            "measurement_profile": self.measurement_profile,
            "measurement_profile_version": (
                self.measurement_profile_version),
        }
        payload["digest"] = authority_digest(payload)
        return payload


def authority_digest(payload: Mapping[str, Any]) -> str:
    """Correlation digest over the reference (never a signature).

    The durable revalidation is the authority. This digest only gives the
    audit/journal a stable handle and detects accidental corruption; it is not
    secret and an attacker who can rewrite the reference can recompute it.
    """
    material = {k: v for k, v in dict(payload).items() if k != "digest"}
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:32]


def authority_from_reference(raw: Any) -> Optional[QualificationAuthority]:
    """Normalize a dataclass or mapping into the frozen reference, or None."""
    if isinstance(raw, QualificationAuthority):
        return raw
    if not isinstance(raw, Mapping):
        return None
    if str(raw.get("schema") or "") != SCHEMA:
        return None
    values = {key: _text(raw.get(key)) for key in _REQUIRED_TEXT}
    if any(value is None for value in values.values()):
        return None
    scope = raw.get("workload_scope")
    if not isinstance(scope, Mapping) or not scope:
        return None
    baseline = raw.get("baseline_route")
    if isinstance(baseline, Mapping):
        baseline_pair = (
            _text(baseline.get("provider")), _text(baseline.get("model")))
    elif isinstance(baseline, (tuple, list)) and len(baseline) == 2:
        baseline_pair = (_text(baseline[0]), _text(baseline[1]))
    else:
        return None
    if not all(baseline_pair):
        return None
    accuracy = raw.get("accuracy")
    if accuracy is None or isinstance(accuracy, bool):
        return None
    try:
        accuracy_value = float(accuracy)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(accuracy_value):
        return None
    observed = _text(raw.get("observed_at"))
    if observed is None or _parse_utc(observed) is None:
        return None
    return QualificationAuthority(
        agent_id=values["agent_id"],
        tenant_id=values["tenant_id"],
        workspace_id=values["workspace_id"],
        receipt_id=values["receipt_id"],
        promotion_id=values["promotion_id"],
        target_level=values["target_level"],
        source_level=values["source_level"],
        source_revision=values["source_revision"],
        receipt_fingerprint=_text(raw.get("receipt_fingerprint")) or "",
        review_fingerprint=_text(raw.get("review_fingerprint")) or "",
        binding_state=_text(raw.get("binding_state")) or "",
        benchmark_id=values["benchmark_id"],
        dataset_sha256=values["dataset_sha256"],
        rubric_version=values["rubric_version"],
        scoring_version=values["scoring_version"],
        workload_scope=dict(scope),
        workload_scope_digest=values["workload_scope_digest"],
        baseline_route=(baseline_pair[0], baseline_pair[1]),
        provider=values["provider"],
        model=values["model"],
        build=_text(raw.get("build")),
        evidence_id=values["evidence_id"],
        evidence_record_sha256=values["evidence_record_sha256"],
        evidence_core_sha256=values["evidence_core_sha256"],
        accuracy=accuracy_value,
        observed_at=observed,
        measurement_profile=values["measurement_profile"],
        measurement_profile_version=values[
            "measurement_profile_version"],
    )


def authority_from_route_decision(
    decision: Any,
    *,
    profile_name: str = DEFAULT_MEASUREMENT_PROFILE,
) -> Optional[QualificationAuthority]:
    """Mint the reference for a PINNED repeat-task decision, or None.

    Every value is copied from the durable decision the resolver produced from
    validated evidence. Nothing is inferred: missing material yields ``None``
    and the dispatch floor keeps its historical static prior (i.e. no
    accidental admission). This function deliberately does not re-read the DB;
    the handler does that at dispatch time.
    """
    if not isinstance(decision, Mapping):
        return None
    from core.llm.graduation_route import STATE_PINNED

    if str(decision.get("route_state") or "") != STATE_PINNED:
        return None
    selected = decision.get("selected_route")
    if not isinstance(selected, Mapping):
        return None
    provider = _text(selected.get("provider"))
    model = _text(selected.get("model"))
    if not provider or not model:
        return None
    comparison = decision.get("comparison")
    ranked = (
        (comparison or {}).get("ranked")
        if isinstance(comparison, Mapping) else None) or []
    item = next(
        (row for row in ranked
         if isinstance(row, Mapping)
         and str(row.get("provider") or "") == provider
         and str(row.get("model") or "") == model),
        None,
    )
    if item is None:
        return None
    evidence = item.get("evidence")
    if not isinstance(evidence, Mapping):
        return None

    from core.llm.model_evidence_comparison import task_scope_digest

    workload_scope = decision.get("workload_scope")
    if not isinstance(workload_scope, Mapping) or not workload_scope:
        return None
    scope_digest = task_scope_digest(workload_scope)
    benchmark = decision.get("benchmark") or {}
    dataset_sha = _text(benchmark.get("dataset_sha256"))
    rubric = _text(benchmark.get("rubric_version"))
    scoring = _text(evidence.get("scoring_version"))
    if not dataset_sha or not rubric or not scoring:
        return None
    if _text(evidence.get("dataset_sha256")) != dataset_sha:
        return None
    accuracy = evidence.get("accuracy")
    quality = measured_quality(accuracy)
    if quality is None:
        return None
    observed = _text(evidence.get("observed_at"))
    if observed is None or _parse_utc(observed) is None:
        return None
    baseline = decision.get("baseline_route")
    if not isinstance(baseline, Mapping):
        return None
    baseline_pair = (
        _text(baseline.get("provider")), _text(baseline.get("model")))
    if not all(baseline_pair):
        return None

    from core.llm.capability_profiles import resolve_capability_profile

    try:
        profile = resolve_capability_profile(profile_name, None, "")
    except Exception:  # noqa: BLE001 — unknown profile is no authority
        return None
    if profile is None:
        return None

    required = {
        "agent_id": _text(decision.get("agent_id")),
        "receipt_id": _text(decision.get("receipt_id")),
        "promotion_id": _text(decision.get("promotion_id")),
        "target_level": _text(decision.get("target_level")),
        "source_level": _text(decision.get("source_level")),
        "source_revision": _text(decision.get("receipt_revision")),
        "benchmark_id": _text(evidence.get("phase")),
        "evidence_id": _text(evidence.get("evidence_id")),
        "record_sha": _text(evidence.get("record_sha256")),
        "core_sha": _text(evidence.get("core_sha256")),
        "build": _text(evidence.get("model_build")),
    }
    missing = [
        key for key, value in required.items()
        if value is None and key != "build"]
    if missing:
        return None
    binding_state = _text(decision.get("binding_state"))
    if binding_state != "bound":
        return None

    tenant_id = _text(decision.get("tenant_id"))
    workspace_id = _text(decision.get("workspace_id"))
    if not tenant_id or not workspace_id:
        return None

    return QualificationAuthority(
        agent_id=required["agent_id"],
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        receipt_id=required["receipt_id"],
        promotion_id=required["promotion_id"],
        target_level=str(required["target_level"]).lower(),
        source_level=str(required["source_level"]).lower(),
        source_revision=required["source_revision"],
        receipt_fingerprint=_text(decision.get("receipt_fingerprint")) or "",
        review_fingerprint=_text(decision.get("review_fingerprint")) or "",
        binding_state=binding_state,
        benchmark_id=required["benchmark_id"],
        dataset_sha256=dataset_sha,
        rubric_version=rubric,
        scoring_version=scoring,
        workload_scope=dict(workload_scope),
        workload_scope_digest=scope_digest,
        baseline_route=(baseline_pair[0], baseline_pair[1]),
        provider=provider,
        model=model,
        build=required["build"],
        evidence_id=required["evidence_id"],
        evidence_record_sha256=required["record_sha"],
        evidence_core_sha256=required["core_sha"],
        accuracy=float(accuracy),
        observed_at=observed,
        measurement_profile=profile.name,
        measurement_profile_version=profile.version,
    )


def _failure(reason: str, detail: str = "", *,
             provenance: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    return {
        "ok": False,
        "reason": reason,
        "detail": detail,
        "quality": None,
        "quality_basis": "prior",
        "evidence_state": "prior",
        "provenance": dict(provenance or {}),
    }


def _provenance(
    authority: Optional[QualificationAuthority],
) -> Dict[str, Any]:
    if authority is None:
        return {"schema": SCHEMA}
    return {
        "schema": SCHEMA,
        "agent_id": authority.agent_id,
        "receipt_id": authority.receipt_id,
        "promotion_id": authority.promotion_id,
        "source_revision": authority.source_revision,
        "evidence_id": authority.evidence_id,
        "evidence_record_sha256": authority.evidence_record_sha256,
        "benchmark_id": authority.benchmark_id,
        "dataset_sha256": authority.dataset_sha256,
        "rubric_version": authority.rubric_version,
        "scoring_version": authority.scoring_version,
        "workload_scope_digest": authority.workload_scope_digest,
        "observed_at": authority.observed_at,
        "build": authority.build,
        "measurement_profile": authority.measurement_profile,
        "measurement_profile_version": (
            authority.measurement_profile_version),
        "digest": authority_digest(authority.as_dict()),
    }


def revalidate_qualification_authority(
    raw: Any,
    *,
    db: Any,
    provider: str,
    model: str,
    workspace_id: str = "",
    tenant_id: str = "",
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Recompute ONE authority from durable state; never trust the reference.

    Returns ``{"ok", "reason", "detail", "quality", "quality_basis",
    "evidence_state", "provenance"}``. On success ``quality`` is the measured
    benchmark accuracy in the capability layer's 0..100 scale and is the ONLY
    value the dispatch floor may substitute for the static prior.
    """
    authority = authority_from_reference(raw)
    if authority is None:
        return _failure(
            "authority_unreadable",
            "the qualification authority reference is incomplete or malformed")
    provenance = _provenance(authority)
    if (authority.provider, authority.model) != (
            str(provider or ""), str(model or "")):
        return _failure(
            "authority_route_mismatch",
            "the qualification authority does not name the pinned route",
            provenance=provenance)
    if workspace_id and str(workspace_id) != authority.workspace_id:
        return _failure(
            "authority_scope_mismatch",
            "the qualification authority names another workspace",
            provenance=provenance)
    if tenant_id and str(tenant_id) != authority.tenant_id:
        return _failure(
            "authority_scope_mismatch",
            "the qualification authority names another tenant",
            provenance=provenance)

    try:
        from core.agent_graduation_service import (
            resolve_runtime_qualification_baseline,
        )
        from core.llm.model_evidence_comparison import (
            COMPARED,
            compare_model_evidence,
            task_scope_digest,
        )
        from core.llm.graduation_route import (
            _binding_routes,
            _resolve_baseline,
            load_repeat_task_evidence,
        )
        from core.models import AgentRegistry
        from core.personal_scope import (
            resolve_tenant_id,
            resolve_workspace_id,
        )
    except Exception as exc:  # noqa: BLE001 — unavailable authority fails closed
        return _failure(
            "authority_unavailable", f"{type(exc).__name__}: {exc}",
            provenance=provenance)

    try:
        agent = db.get(AgentRegistry, authority.agent_id)
    except Exception as exc:  # noqa: BLE001
        return _failure(
            "authority_unavailable", f"{type(exc).__name__}: {exc}",
            provenance=provenance)
    if agent is None:
        return _failure(
            "authority_agent_missing",
            "the qualification authority names no current agent",
            provenance=provenance)
    # Re-read the agent row: a tier/pointer change since issuance must be
    # visible to this decision even on a session that already loaded it.
    try:
        db.expire(agent)
    except Exception:  # noqa: BLE001 — best-effort freshness
        pass
    if (str(resolve_workspace_id(agent) or "") != authority.workspace_id
            or str(resolve_tenant_id(agent) or "") != authority.tenant_id):
        return _failure(
            "authority_scope_mismatch",
            "the current agent is outside the authority's scope",
            provenance=provenance)

    # The measurement profile must still be the versioned server contract it
    # was minted under: a changed floor/capability definition is not silently
    # reinterpreted as authority.
    try:
        from core.llm.capability_profiles import resolve_capability_profile

        profile = resolve_capability_profile(
            authority.measurement_profile, None, "")
    except Exception:  # noqa: BLE001
        profile = None
    if (profile is None
            or profile.name != authority.measurement_profile
            or profile.version != authority.measurement_profile_version):
        return _failure(
            "authority_profile_changed",
            "the measurement workload profile is unknown or changed",
            provenance=provenance)

    try:
        baseline = resolve_runtime_qualification_baseline(db, agent)
    except Exception as exc:  # noqa: BLE001 — unresolved is fail-closed
        return _failure(
            "authority_receipt_unresolved", f"{type(exc).__name__}: {exc}",
            provenance=provenance)
    if not baseline.get("ok") or str(baseline.get("state") or "") != "valid":
        return _failure(
            "authority_receipt_unresolved",
            str(baseline.get("message") or baseline.get("state") or ""),
            provenance=provenance)
    if baseline.get("repeat_task_comparable") is not True:
        return _failure(
            "authority_receipt_binding_not_comparable",
            str(baseline.get("binding_state") or ""),
            provenance=provenance)
    drift = {
        "receipt_id": (_text(baseline.get("receipt_id")),
                       authority.receipt_id, "receipt"),
        "promotion_id": (_text(baseline.get("promotion_id")),
                         authority.promotion_id, "promotion"),
        "target_level": (str(baseline.get("target_level") or "").lower(),
                         authority.target_level, "target tier"),
        "source_level": (str(baseline.get("source_level") or "").lower(),
                         authority.source_level, "source tier"),
        "source_revision": (_text(baseline.get("source_revision")),
                            authority.source_revision, "receipt revision"),
    }
    for _field, (current, expected, label) in drift.items():
        if current != expected:
            return _failure(
                "authority_receipt_drift",
                f"the current {label} no longer matches the authority",
                provenance=provenance)
    for field, expected in (
            ("receipt_fingerprint", authority.receipt_fingerprint),
            ("review_fingerprint", authority.review_fingerprint)):
        current = _text(baseline.get(field))
        if expected and current and current != expected:
            return _failure(
                "authority_receipt_drift",
                f"the current {field} changed after the authority",
                provenance=provenance)
    if str(baseline.get("binding_state") or "") != "bound":
        return _failure(
            "authority_receipt_binding_not_comparable",
            "the qualification binding is not currently comparable",
            provenance=provenance)

    binding = baseline.get("binding") or {}
    benchmark = binding.get("benchmark_identity") or {}
    if (_text(benchmark.get("dataset_sha256")) != authority.dataset_sha256
            or _text(benchmark.get("rubric_version"))
            != authority.rubric_version):
        return _failure(
            "authority_benchmark_changed",
            "the qualification binding names another dataset/rubric",
            provenance=provenance)
    binding_scope = benchmark.get("workload_scope")
    if (not isinstance(binding_scope, Mapping)
            or task_scope_digest(binding_scope)
            != authority.workload_scope_digest):
        return _failure(
            "authority_workload_mismatch",
            "the qualification binding names another workload scope",
            provenance=provenance)
    binding_routes = _binding_routes(binding)
    if not binding_routes:
        return _failure(
            "authority_baseline_missing",
            "the qualification binding names no serving route",
            provenance=provenance)

    try:
        rows = load_repeat_task_evidence(db, agent)
    except Exception as exc:  # noqa: BLE001
        return _failure(
            "authority_unavailable", f"{type(exc).__name__}: {exc}",
            provenance=provenance)
    row = next(
        (item for item in rows
         if str(item.get("evidence_id") or "") == authority.evidence_id
         and str(item.get("provider") or "") == authority.provider
         and str(item.get("model") or "") == authority.model),
        None,
    )
    if row is None:
        return _failure(
            "authority_evidence_missing",
            "the authority's validated benchmark record is no longer current",
            provenance=provenance)
    observed_row = _parse_utc(row.get("observed_at"))
    observed_authority = _parse_utc(authority.observed_at)
    if (observed_row is None or observed_authority is None
            or observed_row != observed_authority):
        return _failure(
            "authority_evidence_tampered",
            "the validated record's observation time changed",
            provenance=provenance)
    if (_text(row.get("record_sha256"))
            != authority.evidence_record_sha256
            or _text(row.get("core_sha256"))
            != authority.evidence_core_sha256):
        return _failure(
            "authority_evidence_tampered",
            "the validated record digest changed",
            provenance=provenance)
    if (_text(row.get("dataset_sha256")) != authority.dataset_sha256
            or _text(row.get("scoring_version"))
            != authority.scoring_version
            or _text(row.get("rubric_version"))
            != authority.rubric_version
            or _text(row.get("phase")) != authority.benchmark_id):
        return _failure(
            "authority_benchmark_changed",
            "the validated record names another benchmark/dataset/rubric",
            provenance=provenance)
    row_build = _text(row.get("resolved_model"))
    if (row_build or "").casefold() != (authority.build or "").casefold():
        return _failure(
            "authority_build_mismatch",
            "the validated record's provider build changed",
            provenance=provenance)
    row_accuracy = row.get("accuracy")
    try:
        accuracy_value = float(row_accuracy)
    except (TypeError, ValueError):
        return _failure(
            "authority_quality_unmeasured",
            "the validated record carries no measured accuracy",
            provenance=provenance)
    if not math.isclose(
            accuracy_value, authority.accuracy, rel_tol=0.0, abs_tol=1e-9):
        return _failure(
            "authority_evidence_tampered",
            "the validated record's measured accuracy changed",
            provenance=provenance)

    current_baseline = _resolve_baseline(binding_routes, rows)
    if current_baseline is None:
        return _failure(
            "authority_baseline_not_established",
            "the qualification baseline is not currently established",
            provenance=provenance)
    if (str(current_baseline.get("provider") or ""),
            str(current_baseline.get("model") or "")) != authority.baseline_route:
        return _failure(
            "authority_baseline_changed",
            "the qualification baseline changed after the authority",
            provenance=provenance)

    evaluation_at = now or datetime.now(timezone.utc)
    if evaluation_at.tzinfo is None:
        evaluation_at = evaluation_at.replace(tzinfo=timezone.utc)
    try:
        comparison = compare_model_evidence(
            task_scope=dict(authority.workload_scope),
            evidence=rows,
            candidates=[{
                "provider": authority.provider,
                "model": authority.model,
            }],
            rubric_version=authority.rubric_version,
            profile_name=authority.measurement_profile,
            baseline={
                "provider": authority.baseline_route[0],
                "model": authority.baseline_route[1],
            },
            now=evaluation_at,
        )
    except Exception as exc:  # noqa: BLE001 — fail closed
        return _failure(
            "authority_unavailable", f"{type(exc).__name__}: {exc}",
            provenance=provenance)
    if comparison.get("outcome") != COMPARED or not comparison.get("selected"):
        reasons = list(
            (comparison.get("insufficient_evidence") or {}).get(
                "reasons") or [])
        stale = "stale_evidence" in reasons or any(
            "evidence_expired" in (item.get("reasons") or [])
            for item in comparison.get("not_task_evidence") or [])
        code = "authority_evidence_stale" if stale else (
            "authority_evidence_insufficient")
        detail = ", ".join(reasons[:6]) or "no sufficient current evidence"
        return _failure(code, detail, provenance=provenance)

    selected = comparison["selected"]
    selected_evidence = selected.get("evidence") or {}
    if (_text(selected_evidence.get("evidence_id"))
            != authority.evidence_id):
        return _failure(
            "authority_evidence_superseded",
            "newer validated evidence now supersedes the authority's record",
            provenance=provenance)
    selected_observed = _parse_utc(selected_evidence.get("observed_at"))
    if (selected_observed is None
            or selected_observed != observed_authority):
        return _failure(
            "authority_evidence_superseded",
            "the comparator selected a different observation",
            provenance=provenance)
    selected_build = _text(selected_evidence.get("model_build"))
    if (selected_build or "").casefold() != (authority.build or "").casefold():
        return _failure(
            "authority_build_mismatch",
            "the current evidence carries another provider build",
            provenance=provenance)
    quality = measured_quality(selected.get("score"))
    if quality is None:
        return _failure(
            "authority_quality_unmeasured",
            "the current comparison carries no measured quality",
            provenance=provenance)

    success = _provenance(authority)
    success.update({
        "accuracy": float(selected.get("score")),
        "quality": quality,
    })
    return {
        "ok": True,
        "reason": None,
        "detail": "",
        "quality": quality,
        "quality_basis": "measured_benchmark",
        "evidence_state": "measured_benchmark",
        "provenance": success,
    }
