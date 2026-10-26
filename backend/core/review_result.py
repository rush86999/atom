"""Task-defined review-result contract.

The platform validates IDENTITY, COVERAGE, EVIDENCE and DELIVERY. It does not
know what "process", "escalate", "approve" or "deny" mean: the task's own
policy/teaching supplies ``allowed_decisions``. That keeps the completion
mechanism domain-independent while the judgment rules stay with the business.

A review is complete only when its assessments bind to the accepted request:

* the exact requested subjects (no missing, duplicate, or unrequested subject);
* the execution that produced the result;
* source evidence matching the accepted evidence requirements;
* policy/lesson refs used for the judgment;
* optional unresolved requirements (a missing input can justify an Escalate /
  Request-More-Info decision without making the review incomplete).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

_IDENTITY_KEYS = ("file_name", "resource_id", "content_hash")
_RECORD_ID_RE = re.compile(r"\b[A-Za-z]{1,8}-\d{1,8}\b")
_LABEL_RE = re.compile(
    r"(?:recommendation|decision|verdict|assessment|outcome)"
    r"\s*[:\-]?\s*\**\s*",
    re.IGNORECASE,
)


def requested_subjects(structured: Dict[str, Any]) -> List[str]:
    """The subjects the accepted read actually requested."""
    if not isinstance(structured, dict):
        return []
    records = list(structured.get("requested_items") or [])
    if not records:
        records = [
            str(target.get("item") or "")
            for target in (structured.get("targets") or [])
            if isinstance(target, dict) and target.get("item")
        ]
    return _unique(records)[:12]


def evidence_refs_from_structured(
    structured: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Source identity + row refs from a structured workbook read."""
    if not isinstance(structured, dict):
        return []
    source = structured.get("source_identity") or {}
    identity = {
        key: source.get(key) for key in _IDENTITY_KEYS if source.get(key)
    }
    if not identity:
        return []
    refs: List[Dict[str, Any]] = [{
        "kind": "file",
        **identity,
        "addresses_requested": True,
    }]
    for target in structured.get("targets") or []:
        if not isinstance(target, dict):
            continue
        candidates = (
            ((target.get("identity") or {}).get("candidates") or [])
            if isinstance(target.get("identity"), dict) else []
        )
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            ref = str(candidate.get("ref") or "").strip()
            if not ref:
                continue
            refs.append({
                "kind": "file",
                **identity,
                "ref": ref,
                "addresses_requested": True,
            })
    out: List[Dict[str, Any]] = []
    seen = set()
    for ref in refs:
        key = (
            ref.get("file_name"), ref.get("resource_id"),
            ref.get("content_hash"), ref.get("ref"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(ref)
    return out[:12]


def decision_options_from_lessons(lessons: Sequence[Any]) -> List[str]:
    """The task-defined decision choices taught for this agent/task.

    Teaching supplies the judgment vocabulary; the platform only validates
    that a delivered decision is one of these choices.
    """
    # The lessons arrive relevance-ordered. The first lesson that declares a
    # decision schema owns this task's choices; unioning every lesson could
    # mix unrelated task vocabularies on a multi-job agent.
    for lesson in lessons or []:
        if not isinstance(lesson, dict):
            continue
        options: List[str] = []
        seen = set()
        for option in lesson.get("decision_options") or []:
            text = _clean(option)
            key = _decision_key(text)
            if text and key not in seen:
                seen.add(key)
                options.append(text)
        if options:
            return options[:20]
    return []


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _record_key(value: Any) -> str:
    return _clean(value).casefold()


def _decision_key(value: Any) -> str:
    return re.sub(r"[\s_-]+", " ", _clean(value)).casefold()


def _unique(values: Sequence[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values or []:
        text = _clean(value)
        if not text or _decision_key(text) in seen:
            continue
        seen.add(_decision_key(text))
        out.append(text)
    return out


def _decision_alternatives(allowed_decisions: Sequence[str]) -> str:
    alternatives = []
    for decision in allowed_decisions or []:
        parts = [
            re.escape(part)
            for part in re.split(r"[\s_-]+", _clean(decision))
            if part
        ]
        if parts:
            alternatives.append(r"[\s_-]+".join(parts))
    return "|".join(alternatives)


def _decision_map(
    answer: str,
    requested: Sequence[str],
    allowed_decisions: Sequence[str],
) -> Dict[str, set]:
    """Decisions explicitly labelled inside a requested subject's segment.

    The allowed decisions come from the task contract, never from a platform
    vocabulary. Bare phrases ("recommend processing") and unlabelled prose do
    not bind to a subject.
    """
    text = str(answer or "")
    lower = text.casefold()
    alternatives = _decision_alternatives(allowed_decisions)
    if not alternatives:
        return {}
    pattern = re.compile(
        _LABEL_RE.pattern + r"(" + alternatives + r")(?![A-Za-z0-9])",
        re.IGNORECASE,
    )
    positions: List[tuple[int, str]] = []
    for record in requested:
        record_re = re.compile(
            rf"(?<![A-Za-z0-9]){re.escape(record.casefold())}(?![A-Za-z0-9])")
        for match in record_re.finditer(lower):
            positions.append((match.start(), record))
    positions.sort(key=lambda item: item[0])
    decisions: Dict[str, set] = {}
    for index, (start, record) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(
            text)
        segment = text[start:end]
        for match in pattern.finditer(segment):
            decisions.setdefault(record, set()).add(
                _decision_key(match.group(1)))
        # Table row shape: | V-200 | Deny |
        row_re = re.compile(
            rf"\|\s*{re.escape(record)}\s*\|\s*"
            rf"({alternatives})\s*\|",
            re.IGNORECASE,
        )
        for match in row_re.finditer(segment):
            decisions.setdefault(record, set()).add(
                _decision_key(match.group(1)))
    requested_keys = {_record_key(record) for record in requested}
    for match in _RECORD_ID_RE.finditer(text):
        record_id = match.group(0)
        if _record_key(record_id) in requested_keys:
            continue
        tail = text[match.end():match.end() + 500]
        found = pattern.search(tail)
        if found:
            decisions.setdefault(record_id, set()).add(
                _decision_key(found.group(1)))
    return decisions


def _basis_refs(
    subject_id: str, evidence_refs: Sequence[Any],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for ref in evidence_refs or []:
        if not isinstance(ref, dict):
            continue
        if ref.get("addresses_requested") is False:
            continue
        identity = {key: ref.get(key) for key in _IDENTITY_KEYS if ref.get(key)}
        if not identity:
            continue
        out.append({
            "kind": str(ref.get("kind") or "file"),
            "subject_id": subject_id,
            **identity,
            "ref": ref.get("ref") or ref.get("cell"),
        })
    return out[:8]


def _required_evidence_met(
    basis_refs: Sequence[Dict[str, Any]],
    required_evidence: Sequence[Any],
) -> bool:
    if not required_evidence:
        return True
    for required in required_evidence:
        if isinstance(required, dict):
            wanted = {
                key: required.get(key) for key in _IDENTITY_KEYS
                if required.get(key)
            }
            if not wanted:
                continue
            if not any(
                all(
                    str(ref.get(key) or "") == str(value)
                    for key, value in wanted.items()
                )
                for ref in basis_refs
            ):
                return False
        else:
            needle = _clean(required).casefold()
            if not needle:
                continue
            if not any(
                needle in str(ref.get(key) or "").casefold()
                for ref in basis_refs for key in _IDENTITY_KEYS
            ):
                return False
    return True


def _policy_refs(refs: Sequence[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for ref in refs or []:
        if not isinstance(ref, dict):
            continue
        lesson_id = _clean(ref.get("id") or ref.get("lesson_id"))
        topic = _clean(ref.get("topic"))
        lesson = _clean(ref.get("lesson") or ref.get("summary"))
        key = (lesson_id, topic, lesson[:160])
        if not (lesson_id or topic or lesson) or key in seen:
            continue
        seen.add(key)
        out.append({
            "id": lesson_id,
            "topic": topic,
            "lesson": lesson[:600],
        })
    return out[:8]


def build_review_result(
    *,
    execution_id: Optional[str],
    requested_records: Sequence[Any],
    answer: str,
    allowed_decisions: Sequence[Any],
    evidence_refs: Sequence[Any],
    required_evidence: Sequence[Any] = (),
    policy_refs: Sequence[Any] = (),
    unresolved_requirements: Sequence[Any] = (),
    expected_execution_id: Optional[str] = None,
    require_policy_refs: bool = True,
) -> Dict[str, Any]:
    """Build and validate a request-bound review result.

    ``ok`` is the only certification signal. ``errors`` names every rejected
    condition. Decision labels are matched against ``allowed_decisions`` from
    the task contract; the platform never hardcodes a business vocabulary.
    """
    requested = _unique(requested_records)
    allowed = _unique(allowed_decisions)
    errors: List[Dict[str, Any]] = []
    if not _clean(execution_id):
        errors.append({"code": "missing_execution_id"})
    elif (expected_execution_id is not None
          and _clean(execution_id) != _clean(expected_execution_id)):
        errors.append({
            "code": "execution_mismatch",
            "execution_id": _clean(execution_id),
            "expected_execution_id": _clean(expected_execution_id),
        })
    if not requested:
        errors.append({"code": "missing_requested_subjects"})
    if not allowed:
        errors.append({"code": "missing_allowed_decisions"})
    decisions_raw = _decision_map(answer, requested, allowed)
    assessments: List[Dict[str, Any]] = []
    required = list(required_evidence or [])
    for subject in requested:
        found = decisions_raw.get(subject) or set()
        if not found:
            errors.append({
                "code": "missing_decision",
                "subject_id": subject,
            })
            continue
        if len(found) > 1:
            errors.append({
                "code": "ambiguous_decision",
                "subject_id": subject,
                "decisions": sorted(found),
            })
            continue
        decision = next(iter(found))
        allowed_keys = {_decision_key(item) for item in allowed}
        if decision not in allowed_keys:
            errors.append({
                "code": "invalid_decision",
                "subject_id": subject,
                "decision": decision,
            })
            continue
        basis = _basis_refs(subject, evidence_refs)
        if not basis:
            errors.append({
                "code": "missing_evidence_refs",
                "subject_id": subject,
            })
        if not _required_evidence_met(basis, required):
            errors.append({
                "code": "missing_required_evidence",
                "subject_id": subject,
            })
        policies = _policy_refs(policy_refs)
        if require_policy_refs and not policies:
            errors.append({
                "code": "missing_policy_refs",
                "subject_id": subject,
            })
        assessments.append({
            "subject_id": subject,
            "decision": decision,
            "evidence_refs": basis,
            "policy_refs": policies,
            "unresolved_requirements": _unique(unresolved_requirements),
        })
    requested_keys = {_record_key(subject) for subject in requested}
    for subject, found in decisions_raw.items():
        if _record_key(subject) in requested_keys:
            continue
        errors.append({
            "code": "unrequested_subject",
            "subject_id": subject,
            "decisions": sorted(found),
        })
    if len(assessments) != len(requested) and not any(
            error.get("code") in ("missing_decision", "ambiguous_decision")
            for error in errors):
        errors.append({"code": "incomplete_subject_coverage"})
    return {
        "schema_version": "review-result-1",
        "execution_id": _clean(execution_id) or None,
        "requested_subjects": requested,
        "allowed_decisions": allowed,
        "assessments": assessments,
        "errors": errors,
        "ok": not errors,
    }


def render_review_result(review: Dict[str, Any]) -> str:
    """Render a compact, validated decision block for the delivered answer."""
    if not isinstance(review, dict) or review.get("ok") is not True:
        return ""
    lines = ["VALIDATED REVIEW (request-bound):"]
    for assessment in review.get("assessments") or []:
        subject = assessment.get("subject_id")
        value = _clean(assessment.get("decision")).title()
        lines.append(f"- {subject}: Decision: {value}")
        basis = assessment.get("evidence_refs") or []
        if basis:
            parts = []
            for ref in basis[:2]:
                bits = [
                    str(ref.get(key)) for key in
                    ("file_name", "resource_id", "content_hash", "ref")
                    if ref.get(key)
                ]
                if bits:
                    parts.append(" ".join(bits))
            if parts:
                lines.append("  Evidence: " + "; ".join(parts))
        policy = assessment.get("policy_refs") or []
        if policy:
            topics = [
                str(ref.get("topic") or ref.get("id"))
                for ref in policy[:2] if ref.get("topic") or ref.get("id")
            ]
            if topics:
                lines.append("  Policy: " + "; ".join(topics))
        gaps = assessment.get("unresolved_requirements") or []
        if gaps:
            lines.append("  Open requirements: " + "; ".join(gaps))
    return "\n".join(lines)
