"""Deterministic business readiness for assignment steps.

This is a pure evaluation over the durable assignment view: it does not own
state, call tools or authorize effects. The executor re-evaluates before
scheduling; an effect's own lifecycle still owns dispatch authorization.
"""
from __future__ import annotations

import datetime as _dt
import math
from typing import Any, Dict, Iterable, List, Optional

EVIDENCE_STATES = (
    "established", "missing", "incomplete", "stale", "conflicting",
    "unavailable",
)
PREDICATE_KINDS = ("fact", "receipt", "authority", "time", "all", "any", "not")
RECEIPT_REQUIREMENTS = ("applied", "verified")
_VERIFIED_STATUSES = ("verified", "material_verified", "confirmed", "complete")
_REFUTED_STATUSES = ("conflict", "conflicting", "mismatch", "mismatched",
                     "refuted", "failed", "invalid")
_MAX_DEPTH = 8
_MAX_PREDICATES = 40


def _text(value: Any, limit: int = 200) -> str:
    return str(value or "").strip()[:limit]


def _truth(value: Any) -> str:
    return "true" if value is True else "false" if value is False else "unknown"


def _combine_and(values: Iterable[str]) -> str:
    values = list(values)
    if any(value == "false" for value in values):
        return "false"
    if any(value == "unknown" for value in values):
        return "unknown"
    return "true"


def _combine_or(values: Iterable[str]) -> str:
    values = list(values)
    if any(value == "true" for value in values):
        return "true"
    if any(value == "unknown" for value in values):
        return "unknown"
    return "false"


def _parse_time(value: Any) -> Optional[_dt.datetime]:
    try:
        parsed = _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_dt.timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None


def normalize_requirements(value: Any, *, depth: int = 0) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("step requirements must be a list")
    if len(value) > _MAX_PREDICATES:
        raise ValueError("too many step requirements")
    if depth > _MAX_DEPTH:
        raise ValueError("step requirement nesting is too deep")
    out: List[Dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError("each requirement must be an object")
        kind = _text(raw.get("kind"), 20).lower()
        if kind not in PREDICATE_KINDS:
            raise ValueError(f"unsupported requirement kind {kind!r}")
        item = {"kind": kind}
        if kind == "fact":
            fact_id = _text(raw.get("fact_id"), 120)
            if not fact_id:
                raise ValueError("fact requirement needs fact_id")
            item["fact_id"] = fact_id
            if "equals" in raw:
                item["equals"] = raw.get("equals")
        elif kind == "receipt":
            step_id = _text(raw.get("step_id"), 80)
            if not step_id:
                raise ValueError("receipt requirement needs step_id")
            item["step_id"] = step_id
            require = _text(raw.get("require"), 40).lower() or "applied"
            if require not in RECEIPT_REQUIREMENTS:
                raise ValueError(
                    "receipt require must be one of "
                    + ", ".join(RECEIPT_REQUIREMENTS))
            item["require"] = require
        elif kind == "authority":
            allow = raw.get("allow")
            if allow is not None:
                if not isinstance(allow, list) or not all(
                        isinstance(entry, str) for entry in allow):
                    raise ValueError("authority allow must be a string list")
                item["allow"] = [_text(entry, 40) for entry in allow]
            else:
                item["allow"] = ["authorized", "read_only"]
        elif kind == "time":
            if not raw.get("not_after"):
                raise ValueError("time requirement needs not_after")
            item["not_after"] = str(raw["not_after"])
        elif kind in ("all", "any"):
            item["of"] = normalize_requirements(
                raw.get("of") or [], depth=depth + 1)
        elif kind == "not":
            child = normalize_requirements(
                [raw.get("of")] if isinstance(raw.get("of"), dict)
                else raw.get("of") or [], depth=depth + 1)
            if len(child) != 1:
                raise ValueError("not requires exactly one child requirement")
            item["of"] = child[0]
        out.append(item)
    return out


def normalize_facts(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("assignment facts must be a list")
    out: List[Dict[str, Any]] = []
    seen = set()
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError("each fact must be an object")
        fact_id = _text(raw.get("fact_id"), 120)
        if not fact_id or fact_id in seen:
            raise ValueError(f"invalid or duplicate fact_id {fact_id!r}")
        seen.add(fact_id)
        state = _text(raw.get("evidence_state"), 20) or "unknown"
        if state not in EVIDENCE_STATES:
            raise ValueError(f"unknown evidence_state {state!r}")
        fact = {
            "fact_id": fact_id,
            "subject": dict(raw.get("subject") or {}),
            "field_id": _text(raw.get("field_id"), 120) or None,
            "value": raw.get("value"),
            "value_type": _text(raw.get("value_type"), 40) or None,
            "evidence_state": state,
            "source_refs": [
                dict(item) for item in (raw.get("source_refs") or [])
                if isinstance(item, dict)][:20],
            "authority_ref": _text(raw.get("authority_ref"), 200) or None,
            "validity": dict(raw.get("validity") or {}),
        }
        out.append(fact)
    return out


def _fact_truth(fact: Optional[Dict[str, Any]], requirement: Dict[str, Any],
                now: _dt.datetime, *,
                assignment: Optional[Dict[str, Any]] = None) -> str:
    if fact is None:
        return "unknown"
    if fact.get("evidence_state") != "established":
        return "unknown"
    # An established fact must bind a stable source/evidence identity or an
    # explicit authored authority. A free-form note or a bare boolean is not
    # sufficient proof.
    stable_keys = ("resource_id", "source_id", "id", "uri", "sha256")
    stable_refs = [
        str(next(
            (ref.get(key) for key in stable_keys
             if ref.get(key) not in (None, "", [], {})), ""))
        for ref in (fact.get("source_refs") or [])
        if isinstance(ref, dict)
    ]
    stable_refs = [item for item in stable_refs if item]
    authored = bool(str(fact.get("authority_ref") or "").strip())
    if not stable_refs and not authored:
        return "unknown"
    if not authored and assignment is not None:
        # A source reference must resolve against the accepted source scope;
        # a model-supplied identifier is not authority by itself.
        accepted = {
            str(source.get("resource_id") or source.get("source_id")
                or source.get("id") or "")
            for source in (assignment.get("sources") or [])
            if isinstance(source, dict)
        }
        accepted.discard("")
        if not accepted or not any(ref in accepted for ref in stable_refs):
            return "unknown"
    validity = fact.get("validity") or {}
    expires = validity.get("expires_at") if isinstance(validity, dict) else None
    if expires:
        parsed = _parse_time(expires)
        if parsed is None or now >= parsed:
            return "unknown"
    if "equals" not in requirement:
        return "true"
    expected = requirement.get("equals")
    actual = fact.get("value")
    if isinstance(expected, bool) or isinstance(actual, bool):
        return _truth(actual is expected)
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if not (math.isfinite(float(expected)) and math.isfinite(float(actual))):
            return "unknown"
        return _truth(float(actual) == float(expected))
    return _truth(actual == expected)


_SOURCE_ADAPTERS = frozenset({
    "workbook.read", "document.read", "external.research",
})
_ARTIFACT_ADAPTERS = frozenset({
    "artifact.document", "artifact.spreadsheet", "artifact.presentation",
    "email.draft",
})
_EXTERNAL_ADAPTERS = frozenset({
    "email.send_outlook", "outbound.send",
    "assignment.controlled_outbox",
})


def _first_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _bool_or_none(value: Any) -> Optional[bool]:
    return value if isinstance(value, bool) else None


def _proof_profile(step: Dict[str, Any]) -> str:
    """Classify the material proof a receipt is expected to carry."""
    operation_type = _text(step.get("operation_type"), 40).lower()
    effect = _text(step.get("effect"), 20).lower()
    adapter = _text(step.get("adapter"), 120).lower()
    if effect == "external" or (
            adapter in _EXTERNAL_ADAPTERS and effect != "local"):
        return "external"
    if operation_type == "present" or adapter.startswith("artifact.") or (
            adapter in _ARTIFACT_ADAPTERS):
        return "artifact"
    if operation_type == "retrieve" or effect == "read_only" or (
            adapter.endswith(".read") or adapter in _SOURCE_ADAPTERS):
        return "source"
    return "local"


def _binding_actual(
    result: Dict[str, Any], step: Dict[str, Any], field: str,
) -> Any:
    receipt = result.get("receipt") if isinstance(
        result.get("receipt"), dict) else {}
    outbound = receipt.get("outbound") if isinstance(
        receipt.get("outbound"), dict) else {}
    remote = receipt.get("remote_identity") if isinstance(
        receipt.get("remote_identity"), dict) else {}
    source = result.get("source") if isinstance(
        result.get("source"), dict) else {}
    receipt_source = receipt.get("source") if isinstance(
        receipt.get("source"), dict) else {}
    artifact = result.get("artifact") if isinstance(
        result.get("artifact"), dict) else {}
    binding = result.get("binding") if isinstance(
        result.get("binding"), dict) else {}
    return {
        "operation_id": _first_value(
            result.get("operation_id"), step.get("operation_id"),
            receipt.get("operation_id"), remote.get("operation_id")),
        "request_id": _first_value(
            result.get("request_id"), receipt.get("request_id"),
            remote.get("request_id")),
        "resource_id": _first_value(
            result.get("resource_id"), source.get("resource_id"),
            source.get("id"), binding.get("resource_id"),
            receipt_source.get("resource_id"), remote.get("resource_id")),
        "subject": _first_value(
            result.get("subject"), result.get("subject_id"),
            binding.get("subject"), outbound.get("subject")),
        "version": _first_value(
            result.get("version"), result.get("source_version"),
            source.get("version"), source.get("source_version"),
            receipt_source.get("source_version"),
            receipt_source.get("version"), receipt_source.get("revision"),
            artifact.get("revision"), remote.get("version")),
        "sha256": _first_value(
            result.get("sha256"), source.get("sha256"),
            receipt_source.get("sha256"), artifact.get("sha256"),
            remote.get("sha256")),
        "provider_ref": _first_value(
            result.get("provider_ref"), outbound.get("provider_ref"),
            outbound.get("remote_id"), remote.get("provider_ref"),
            remote.get("remote_id")),
        "message_id": _first_value(
            result.get("message_id"), outbound.get("message_id"),
            receipt.get("message_id"), remote.get("message_id")),
        "account": _first_value(
            result.get("account"), result.get("mailbox"),
            outbound.get("account"), outbound.get("mailbox"),
            remote.get("account")),
    }.get(field)


def _requested_source_binding(step: Dict[str, Any]) -> Dict[str, Any]:
    """Identity the accepting plan asked the source read to establish."""
    inputs = step.get("inputs") if isinstance(
        step.get("inputs"), dict) else {}
    requested: Dict[str, Any] = {}
    for key in ("resource_binding", "source_binding", "binding", "source"):
        value = inputs.get(key)
        if isinstance(value, dict):
            for field, item in value.items():
                if item not in (None, "", [], {}):
                    requested.setdefault(str(field), item)
    for key in ("resource_id", "source_id", "file_id", "uri",
                "version", "source_version", "sha256"):
        value = inputs.get(key)
        if value not in (None, "", [], {}):
            requested.setdefault(key, value)
    return requested


def _observed_source_binding(
    verification: Dict[str, Any],
    result: Dict[str, Any],
    step: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "resource_id": _binding_actual(result, step, "resource_id"),
        "version": _binding_actual(result, step, "version"),
        "sha256": _binding_actual(result, step, "sha256"),
    }


def _coverage_count(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or not number.is_integer():
        return None
    return int(number)


def _source_coverage_state(
    result: Dict[str, Any], verification: Dict[str, Any],
) -> str:
    receipt = result.get("receipt") if isinstance(
        result.get("receipt"), dict) else {}
    receipt_source = receipt.get("source") if isinstance(
        receipt.get("source"), dict) else {}
    coverage = result.get("coverage")
    if not isinstance(coverage, dict):
        coverage = verification.get("coverage")
    if not isinstance(coverage, dict):
        coverage = receipt_source.get("coverage")
    if not isinstance(coverage, dict) or not coverage:
        return "missing"
    complete = _bool_or_none(coverage.get("complete"))
    known = _bool_or_none(coverage.get("known"))
    truncated = _bool_or_none(coverage.get("truncated"))
    if truncated is True:
        return "truncated"
    if complete is False:
        return "incomplete"
    if known is False:
        return "unknown"
    raw_expected = coverage.get(
        "expected_count", coverage.get(
            "requested_count", coverage.get(
                "source_row_count", coverage.get("source_count"))))
    raw_observed = coverage.get(
        "observed_count", coverage.get(
            "matched_count", coverage.get(
                "selected_count", coverage.get(
                    "accepted_count", coverage.get("returned_count")))))
    if raw_expected is not None or raw_observed is not None:
        expected_count = _coverage_count(raw_expected)
        observed_count = _coverage_count(raw_observed)
        if expected_count is None or observed_count is None:
            return "unknown"
        if observed_count < expected_count:
            return "incomplete"
    if complete is True:
        return "complete"
    if known is True and truncated is not True:
        return "complete"
    return "unknown"


def _verification_binding(
    verification: Dict[str, Any],
    result: Dict[str, Any],
    step: Dict[str, Any],
) -> tuple:
    """Every identity the proof declares must match the receipt it verifies."""
    for field in ("operation_id", "request_id", "resource_id", "subject",
                  "version", "sha256", "provider_ref", "message_id",
                  "account"):
        if field not in verification:
            continue
        declared = verification.get(field)
        if declared in (None, "", [], {}):
            continue
        actual = _binding_actual(result, step, field)
        if actual in (None, "", [], {}):
            return "unknown", f"verified_binding_{field}_missing"
        if isinstance(declared, (dict, list)) or isinstance(
                actual, (dict, list)):
            if declared != actual:
                return "false", f"verified_binding_{field}_mismatch"
        elif str(declared) != str(actual):
            return "false", f"verified_binding_{field}_mismatch"
    return "true", ""


def _profile_binding(
    profile: str,
    verification: Dict[str, Any],
    result: Dict[str, Any],
    step: Dict[str, Any],
) -> tuple:
    declared = _verification_binding(verification, result, step)
    if declared[0] != "true":
        return declared

    if profile == "source":
        requested = _requested_source_binding(step)
        observed = _observed_source_binding(verification, result, step)
        if not (observed["resource_id"] or observed["sha256"]):
            return "unknown", "verified_identity_missing"
        if not (observed["version"] or observed["sha256"]):
            return "unknown", "verified_version_missing"
        for field in ("resource_id", "version", "sha256"):
            wanted = requested.get(field)
            if field == "version" and wanted in (None, ""):
                wanted = requested.get("source_version")
            if wanted in (None, "", [], {}):
                continue
            actual = observed.get(field)
            if actual in (None, "", [], {}):
                return "unknown", f"verified_binding_{field}_missing"
            if str(wanted) != str(actual):
                return "false", f"verified_binding_{field}_mismatch"
        if result.get("truncated") is True or (
                verification.get("truncated") is True):
            return "unknown", "verified_coverage_truncated"
        coverage = _source_coverage_state(result, verification)
        if coverage == "truncated":
            return "unknown", "verified_coverage_truncated"
        if coverage == "incomplete":
            return "unknown", "verified_coverage_incomplete"
        if coverage == "unknown":
            return "unknown", "verified_coverage_unknown"
        if coverage == "missing":
            return "unknown", "verified_coverage_missing"
        return "true", ""

    if profile == "external":
        receipt = result.get("receipt") if isinstance(
            result.get("receipt"), dict) else {}
        outbound = receipt.get("outbound") if isinstance(
            receipt.get("outbound"), dict) else {}
        remote = receipt.get("remote_identity") if isinstance(
            receipt.get("remote_identity"), dict) else {}
        observed_operation = _first_value(
            result.get("operation_id"), receipt.get("operation_id"),
            remote.get("operation_id"))
        if not observed_operation:
            return "unknown", "verified_operation_identity_missing"
        expected_operation = _first_value(
            step.get("operation_id"), step.get("inputs", {}).get(
                "operation_id") if isinstance(step.get("inputs"), dict) else None)
        if expected_operation and str(observed_operation) != str(
                expected_operation):
            return "false", "verified_binding_operation_id_mismatch"
        observed_remote = _first_value(
            result.get("provider_ref"), result.get("message_id"),
            result.get("remote_id"), outbound.get("provider_ref"),
            outbound.get("message_id"), outbound.get("remote_id"),
            remote.get("provider_ref"), remote.get("message_id"),
            remote.get("remote_id"))
        if not observed_remote:
            return "unknown", "verified_remote_identity_missing"
        inputs = step.get("inputs") if isinstance(
            step.get("inputs"), dict) else {}
        target = inputs.get("target") if isinstance(
            inputs.get("target"), dict) else {}
        for field in ("provider_ref", "message_id", "account", "mailbox"):
            wanted = inputs.get(field)
            if wanted in (None, "", [], {}):
                wanted = target.get(field)
            if wanted in (None, "", [], {}):
                continue
            actual = _binding_actual(result, step, field)
            if actual in (None, "", [], {}):
                return "unknown", f"verified_binding_{field}_missing"
            if str(actual) != str(wanted):
                return "false", f"verified_binding_{field}_mismatch"
        return "true", ""

    if profile == "artifact":
        artifact = result.get("artifact") if isinstance(
            result.get("artifact"), dict) else {}
        if not artifact.get("revision") or not artifact.get("sha256"):
            return "unknown", "verified_artifact_receipt_missing"
        return "true", ""

    if result.get("value") is None and not isinstance(
            result.get("calculation_receipt"), dict):
        return "unknown", "verified_material_result_missing"
    return "true", ""


def _verified_receipt_proof(
    result: Dict[str, Any], step: Optional[Dict[str, Any]] = None,
) -> tuple:
    """Return (truth, reason) for a receipt that requires verified proof.

    A step status of ``applied`` is not material verification. The proof must
    say verified/confirmed, carry no missing/mismatched/conflicting fields,
    bind the applicable profile identity and coverage, and match the requested
    resource/version where the accepting plan names one.
    """
    step = step or {}
    verification = result.get("verification")
    receipt = result.get("receipt") if isinstance(
        result.get("receipt"), dict) else {}
    if not isinstance(verification, dict) or not verification:
        # Durable operation receipts carry the same proof under
        # ``remote_identity.verification``. Older/restarted results may only
        # have this form; it is still explicit structured verification, not a
        # free-form status.
        remote = receipt.get("remote_identity") if isinstance(
            receipt.get("remote_identity"), dict) else {}
        verification = remote.get("verification")
        if not isinstance(verification, dict) or not verification:
            verification = receipt.get("verification")
    if not isinstance(verification, dict) or not verification:
        return "unknown", "verified_proof_missing"
    status = str(verification.get("status") or "").lower()
    if status in _REFUTED_STATUSES:
        return "false", "verified_proof_refuted"
    if status not in _VERIFIED_STATUSES:
        return "unknown", "verified_proof_incomplete"
    for key in ("missing_fields", "mismatches", "conflicts", "refuted_fields"):
        value = verification.get(key)
        if value:
            return "false", f"verified_proof_{key}"
    return _profile_binding(
        _proof_profile(step), verification, result, step)


def _predicate(
    predicate: Dict[str, Any],
    assignment: Dict[str, Any],
    *,
    task_authorization: str,
    now: _dt.datetime,
) -> Dict[str, Any]:
    kind = predicate.get("kind")
    blockers: List[Dict[str, Any]] = []
    supporting: List[str] = []
    if kind == "fact":
        fact_id = predicate.get("fact_id")
        fact = next((item for item in assignment.get("facts") or []
                     if item.get("fact_id") == fact_id), None)
        truth = _fact_truth(fact, predicate, now, assignment=assignment)
        if truth != "true":
            blockers.append({
                "kind": "qualification",
                "fact_id": fact_id,
                "reason": (
                    "missing" if fact is None else
                    "unknown" if truth == "unknown" else "false"),
            })
        else:
            supporting.extend(
                str(ref.get("resource_id") or "")
                for ref in (fact.get("source_refs") or [])
                if ref.get("resource_id"))
        return {"truth": truth, "blockers": blockers,
                "supporting_refs": supporting}

    if kind == "receipt":
        dependency = next((step for step in assignment.get("steps") or []
                           if step.get("step_id") == predicate.get("step_id")),
                          None)
        if dependency is None or dependency.get("status") != "applied":
            return {"truth": "unknown",
                    "blockers": [{
                        "kind": "predecessor",
                        "step_id": predicate.get("step_id"),
                        "reason": "not_applied",
                    }], "supporting_refs": []}
        result = dependency.get("result")
        if not isinstance(result, dict) or not result:
            return {"truth": "unknown",
                    "blockers": [{
                        "kind": "predecessor",
                        "step_id": predicate.get("step_id"),
                        "reason": "applied_without_result",
                    }], "supporting_refs": []}
        require = str(predicate.get("require") or "applied").lower()
        if require == "verified":
            proof, reason = _verified_receipt_proof(result, dependency)
            if proof != "true":
                return {"truth": proof,
                        "blockers": [{
                            "kind": "predecessor",
                            "step_id": predicate.get("step_id"),
                            "reason": reason,
                        }], "supporting_refs": []}
        else:
            verification = result.get("verification")
            if isinstance(verification, dict) and str(
                    verification.get("status") or "").lower() in (
                        "incomplete", "unknown", "unverified"):
                return {"truth": "unknown",
                        "blockers": [{
                            "kind": "predecessor",
                            "step_id": predicate.get("step_id"),
                            "reason": "material_verification_incomplete",
                        }], "supporting_refs": []}
        return {"truth": "true", "blockers": [],
                "supporting_refs": [str(predicate.get("step_id"))]}

    if kind == "authority":
        allow = [str(item).lower() for item in predicate.get("allow") or []]
        current = str(task_authorization or "read_only").lower()
        truth = _truth(current in allow)
        if truth != "true":
            blockers.append({
                "kind": "authority", "reason": "current_authority_insufficient",
                "current": current, "required": allow,
            })
        else:
            supporting.append(f"authority:{current}")
        return {"truth": truth, "blockers": blockers,
                "supporting_refs": supporting}

    if kind == "time":
        deadline = _parse_time(predicate.get("not_after"))
        truth = "unknown" if deadline is None else _truth(now < deadline)
        if truth != "true":
            blockers.append({"kind": "time", "reason": "deadline_passed"})
        return {"truth": truth, "blockers": blockers,
                "supporting_refs": []}

    if kind in ("all", "any"):
        child_results = [
            _predicate(item, assignment,
                       task_authorization=task_authorization, now=now)
            for item in predicate.get("of") or []
        ]
        truth = (_combine_and(item["truth"] for item in child_results)
                 if kind == "all"
                 else _combine_or(item["truth"] for item in child_results))
        # An eligible OR/NOT branch must not surface a demand that did not
        # block the chosen outcome. Only unresolved/false children are
        # material when the predicate itself is not true.
        blockers = [] if truth == "true" else [
            blocker for item in child_results
            for blocker in item["blockers"]]
        supporting = [ref for item in child_results
                      for ref in item["supporting_refs"]]
        return {"truth": truth, "blockers": blockers,
                "supporting_refs": supporting}

    if kind == "not":
        child = _predicate(
            predicate.get("of") or {}, assignment,
            task_authorization=task_authorization, now=now)
        if child["truth"] == "true":
            return {"truth": "false",
                    "blockers": [{"kind": "condition_false",
                                  "reason": "negated_condition_true"}],
                    "supporting_refs": child["supporting_refs"]}
        if child["truth"] == "false":
            return {"truth": "true", "blockers": [],
                    "supporting_refs": child["supporting_refs"]}
        return {"truth": "unknown", "blockers": child["blockers"],
                "supporting_refs": child["supporting_refs"]}
    return {"truth": "unknown", "blockers": [{
        "kind": "requirement", "reason": "unsupported_predicate"}],
        "supporting_refs": []}


def evaluate_step_readiness(
    step: Dict[str, Any],
    assignment: Dict[str, Any],
    *,
    task_authorization: str = "read_only",
    now: Optional[_dt.datetime] = None,
) -> Dict[str, Any]:
    """Return a typed three-valued readiness decision for one step."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    predicates = normalize_requirements(step.get("requires") or [])
    if not predicates:
        return {
            "step_id": step.get("step_id"), "truth": "true",
            "eligible": True, "blockers": [], "supporting_refs": [],
        }
    results = [
        _predicate(item, assignment,
                   task_authorization=task_authorization, now=now)
        for item in predicates
    ]
    truth = _combine_and(item["truth"] for item in results)
    blockers = ([] if truth == "true" else [
        blocker for item in results for blocker in item["blockers"]])
    supporting = [ref for item in results for ref in item["supporting_refs"]]
    return {
        "step_id": step.get("step_id"),
        "truth": truth,
        "eligible": truth == "true",
        "blockers": blockers[:40],
        "supporting_refs": supporting[:40],
        "checked_task_version": None,
        "checked_plan_revision": assignment.get("plan_revision"),
    }
