"""Task-defined, structured review-result contract.

Certification comes from a STRUCTURED assessment block, never from prose.
The existing generation call emits one fenced ``review_result`` block next to
its explanation; ordinary prose is explanatory and cannot create or override
a decision.

The task's teaching supplies the allowed decisions. The accepted read supplies
subject-bound evidence IDs and the retrieval identity. The platform validates:

* execution scope;
* exact requested-subject coverage;
* allowed decision vocabulary;
* evidence IDs that resolve to the SAME subject, accepted source identity and
  accepted retrieval operation;
* policy IDs that resolve to teaching entries carrying the task's decision
  schema;
* unresolved requirements (a missing input can justify an Escalate / Ask /
  Request-More-Info decision without making the review incomplete).
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence

_IDENTITY_KEYS = ("file_name", "resource_id", "content_hash")
REVIEW_BLOCK_LANGUAGE = "review_result"
_REVIEW_BLOCK_RE = re.compile(
    r"```(?:review_result|review-result|json:review_result)\s*"
    r"(\{.*?\})\s*```",
    re.DOTALL | re.IGNORECASE,
)


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
        if not text or _record_key(text) in seen:
            continue
        seen.add(_record_key(text))
        out.append(text)
    return out


def decision_options_from_lessons(lessons: Sequence[Any]) -> List[str]:
    """The task policy's decision choices, from the first schema lesson."""
    for lesson in lessons or []:
        if not isinstance(lesson, dict):
            continue
        options = _unique([
            option for option in (lesson.get("decision_options") or [])
            if _clean(option)
        ])
        if options:
            return options[:20]
    return []


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


def _source_identity(structured: Dict[str, Any]) -> Dict[str, Any]:
    source = structured.get("source_identity") or {}
    if not isinstance(source, dict):
        source = {}
    return {
        key: source.get(key) for key in _IDENTITY_KEYS if source.get(key)
    }


def _retrieval_operation(structured: Dict[str, Any]) -> str:
    for key in ("attempt_id", "evidence_revision", "retrieval_operation"):
        value = _clean(structured.get(key))
        if value:
            return value
    return ""


def build_evidence_index(structured: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Subject-bound evidence entries from the accepted workbook read.

    A file/hash proves the workbook identity. The row reference here proves
    which subject that row belongs to; a file-level reference alone is not a
    record-level assessment.
    """
    if not isinstance(structured, dict):
        return []
    source = _source_identity(structured)
    operation = _retrieval_operation(structured)
    subjects = requested_subjects(structured)
    targets = [
        target for target in (structured.get("targets") or [])
        if isinstance(target, dict)
    ]
    by_subject: Dict[str, Dict[str, Any]] = {}
    for target in targets:
        item = _clean(target.get("item"))
        if item:
            by_subject[_record_key(item)] = target
    entries: List[Dict[str, Any]] = []
    for subject in subjects:
        target = by_subject.get(_record_key(subject)) or {}
        identity = target.get("identity") if isinstance(
            target.get("identity"), dict) else {}
        candidates = identity.get("candidates") or []
        if not candidates:
            entries.append({
                "evidence_id": f"ev:{subject}:no-row",
                "subject_id": subject,
                "source_identity": dict(source),
                "retrieval_operation": operation,
                "row_ref": None,
                "target_status": _clean(target.get("status")),
                "values": [],
            })
            continue
        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                continue
            row_ref = _clean(candidate.get("ref"))
            entries.append({
                "evidence_id": (
                    f"ev:{subject}:{row_ref or index}"),
                "subject_id": subject,
                "source_identity": dict(source),
                "retrieval_operation": operation,
                "row_ref": row_ref or None,
                "target_status": _clean(target.get("status")),
                "values": list(candidate.get("values") or []),
            })
    return entries[:24]


def build_policy_index(
    lessons: Sequence[Any],
    allowed_decisions: Sequence[Any],
) -> List[Dict[str, Any]]:
    """Teaching entries that carry THIS task's decision schema.

    Attaching every retrieved lesson would not show which policy supports the
    judgment. Only lessons whose declared decision options match the contract
    are selectable policy refs.
    """
    allowed_keys = {_decision_key(item) for item in allowed_decisions or []}
    if not allowed_keys:
        return []
    entries: List[Dict[str, Any]] = []
    seen = set()
    for lesson in lessons or []:
        if not isinstance(lesson, dict):
            continue
        options = {
            _decision_key(option)
            for option in (lesson.get("decision_options") or [])
            if _clean(option)
        }
        if options != allowed_keys:
            continue
        policy_id = _clean(lesson.get("id") or lesson.get("lesson_id"))
        if not policy_id or policy_id in seen:
            continue
        seen.add(policy_id)
        entries.append({
            "policy_id": policy_id,
            "topic": _clean(lesson.get("topic")),
            "lesson": _clean(
                lesson.get("lesson") or lesson.get("summary"))[:600],
        })
    return entries[:12]


def review_output_instruction(
    contract: Dict[str, Any],
    evidence_index: Sequence[Dict[str, Any]],
    policy_index: Sequence[Dict[str, Any]],
) -> str:
    """The one-call output contract: explanation plus structured decisions."""
    subjects = [_clean(item) for item in contract.get("subjects") or [] if _clean(item)]
    decisions = [
        _clean(item) for item in contract.get("allowed_decisions") or []
        if _clean(item)
    ]
    evidence_lines = [
        f"- {entry.get('evidence_id')} | subject={entry.get('subject_id')} "
        f"| row={entry.get('row_ref') or 'no-row'}"
        for entry in evidence_index or []
    ]
    policy_lines = [
        f"- {entry.get('policy_id')} | {entry.get('topic') or 'policy'}"
        for entry in policy_index or []
    ]
    return (
        "REVIEW OUTPUT CONTRACT. After your normal explanation, include "
        "exactly one fenced block:\n"
        "```review_result\n"
        '{"assessments":[{"subject_id":"<subject>","decision":"<allowed '
        'decision>","evidence_ids":["<evidence id>"],"policy_ids":["<policy '
        'id>"],"unresolved_requirements":[]}]}\n'
        "```\n"
        "Only the structured block is certified; the prose is explanatory. "
        "Use one assessment for every requested subject, use only the IDs "
        "listed here, and do not add subjects.\n"
        f"Allowed decisions: {', '.join(decisions)}\n"
        f"Subjects: {', '.join(subjects)}\n"
        "Evidence IDs:\n" + ("\n".join(evidence_lines) or "- none") + "\n"
        "Policy IDs:\n" + ("\n".join(policy_lines) or "- none")
    )


def parse_review_payload(answer: str) -> Optional[Dict[str, Any]]:
    """Parse the ONE structured review block; prose is never consulted."""
    matches = list(_REVIEW_BLOCK_RE.finditer(str(answer or "")))
    if len(matches) != 1:
        return None
    try:
        payload = json.loads(matches[0].group(1))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def strip_review_block(answer: str) -> str:
    """Remove the machine block from the user-facing explanation."""
    return _REVIEW_BLOCK_RE.sub("", str(answer or "")).strip()


def build_review_result(
    *,
    execution_id: Optional[str],
    requested_records: Sequence[Any],
    answer: str,
    allowed_decisions: Sequence[Any],
    evidence_index: Sequence[Dict[str, Any]],
    policy_index: Sequence[Dict[str, Any]],
    expected_execution_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate the structured assessments against the accepted contract."""
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
    evidence_by_id = {
        _clean(entry.get("evidence_id")): entry
        for entry in evidence_index or []
        if isinstance(entry, dict) and _clean(entry.get("evidence_id"))
    }
    policy_by_id = {
        _clean(entry.get("policy_id")): entry
        for entry in policy_index or []
        if isinstance(entry, dict) and _clean(entry.get("policy_id"))
    }
    if not evidence_by_id:
        errors.append({"code": "missing_evidence_index"})
    if not policy_by_id:
        errors.append({"code": "missing_policy_index"})
    # The accepted index must have one source identity and one retrieval
    # operation. Mixed/recovered sources cannot silently certify each other.
    accepted_sources = {
        tuple(sorted((entry.get("source_identity") or {}).items()))
        for entry in evidence_by_id.values()
    }
    accepted_operations = {
        _clean(entry.get("retrieval_operation"))
        for entry in evidence_by_id.values()
    }
    if len(accepted_sources) > 1:
        errors.append({"code": "mixed_evidence_sources"})
    if len(accepted_operations) > 1 or "" in accepted_operations:
        errors.append({"code": "invalid_retrieval_operation"})
    payload = parse_review_payload(answer)
    assessments_in = (
        payload.get("assessments") if isinstance(payload, dict) else None)
    if not isinstance(assessments_in, list):
        errors.append({"code": "missing_structured_review"})
        assessments_in = []
    allowed_keys = {_decision_key(item) for item in allowed}
    requested_keys = {_record_key(item) for item in requested}
    assessments: List[Dict[str, Any]] = []
    seen_subjects = set()
    for raw in assessments_in:
        if not isinstance(raw, dict):
            errors.append({"code": "invalid_assessment"})
            continue
        subject = _clean(raw.get("subject_id"))
        subject_key = _record_key(subject)
        if not subject or subject_key not in requested_keys:
            errors.append({
                "code": "unrequested_subject",
                "subject_id": subject,
            })
            continue
        if subject_key in seen_subjects:
            errors.append({
                "code": "duplicate_subject",
                "subject_id": subject,
            })
            continue
        seen_subjects.add(subject_key)
        decision = _clean(raw.get("decision"))
        if _decision_key(decision) not in allowed_keys:
            errors.append({
                "code": "invalid_decision",
                "subject_id": subject,
                "decision": decision,
            })
            continue
        evidence_ids = [
            _clean(item) for item in (raw.get("evidence_ids") or [])
            if _clean(item)
        ]
        if not evidence_ids:
            errors.append({
                "code": "missing_evidence_ids",
                "subject_id": subject,
            })
        resolved_evidence: List[Dict[str, Any]] = []
        for evidence_id in evidence_ids:
            entry = evidence_by_id.get(evidence_id)
            if entry is None:
                errors.append({
                    "code": "unknown_evidence_id",
                    "subject_id": subject,
                    "evidence_id": evidence_id,
                })
                continue
            if _record_key(entry.get("subject_id")) != subject_key:
                errors.append({
                    "code": "evidence_subject_mismatch",
                    "subject_id": subject,
                    "evidence_id": evidence_id,
                    "evidence_subject": entry.get("subject_id"),
                })
                continue
            if not entry.get("source_identity"):
                errors.append({
                    "code": "missing_source_identity",
                    "subject_id": subject,
                    "evidence_id": evidence_id,
                })
                continue
            if not _clean(entry.get("retrieval_operation")):
                errors.append({
                    "code": "missing_retrieval_operation",
                    "subject_id": subject,
                    "evidence_id": evidence_id,
                })
                continue
            resolved_evidence.append({
                "evidence_id": evidence_id,
                "subject_id": subject,
                "row_ref": entry.get("row_ref"),
                "source_identity": dict(entry.get("source_identity") or {}),
                "retrieval_operation": entry.get("retrieval_operation"),
                "values": list(entry.get("values") or []),
            })
        policy_ids = [
            _clean(item) for item in (raw.get("policy_ids") or [])
            if _clean(item)
        ]
        if not policy_ids:
            errors.append({
                "code": "missing_policy_ids",
                "subject_id": subject,
            })
        resolved_policy: List[Dict[str, Any]] = []
        for policy_id in policy_ids:
            entry = policy_by_id.get(policy_id)
            if entry is None:
                errors.append({
                    "code": "unknown_policy_id",
                    "subject_id": subject,
                    "policy_id": policy_id,
                })
                continue
            resolved_policy.append({
                "policy_id": policy_id,
                "topic": entry.get("topic"),
                "lesson": entry.get("lesson"),
            })
        assessments.append({
            "subject_id": subject,
            "decision": decision,
            "evidence_refs": resolved_evidence,
            "policy_refs": resolved_policy,
            "unresolved_requirements": _unique(
                raw.get("unresolved_requirements") or []),
        })
    missing = [
        subject for subject in requested
        if _record_key(subject) not in seen_subjects
    ]
    for subject in missing:
        errors.append({"code": "missing_decision", "subject_id": subject})
    if len(assessments) != len(requested) and not missing:
        errors.append({"code": "incomplete_subject_coverage"})
    return {
        "schema_version": "review-result-2",
        "execution_id": _clean(execution_id) or None,
        "requested_subjects": requested,
        "allowed_decisions": allowed,
        "assessments": assessments,
        "errors": errors,
        "ok": not errors and len(assessments) == len(requested),
    }


def render_review_result(review: Dict[str, Any]) -> str:
    """Render the validated decision block from the structured result."""
    if not isinstance(review, dict) or review.get("ok") is not True:
        return ""
    lines = ["VALIDATED REVIEW (request-bound):"]
    for assessment in review.get("assessments") or []:
        subject = assessment.get("subject_id")
        value = _clean(assessment.get("decision")).title()
        lines.append(f"- {subject}: Decision: {value}")
        evidence = assessment.get("evidence_refs") or []
        if evidence:
            parts = []
            for ref in evidence[:2]:
                identity = ref.get("source_identity") or {}
                bits = [
                    str(identity.get(key)) for key in _IDENTITY_KEYS
                    if identity.get(key)
                ]
                if ref.get("row_ref"):
                    bits.append(str(ref["row_ref"]))
                if bits:
                    parts.append(" ".join(bits))
            if parts:
                lines.append("  Evidence: " + "; ".join(parts))
        policy = assessment.get("policy_refs") or []
        if policy:
            topics = [
                str(ref.get("topic") or ref.get("policy_id"))
                for ref in policy[:2]
                if ref.get("topic") or ref.get("policy_id")
            ]
            if topics:
                lines.append("  Policy: " + "; ".join(topics))
        gaps = assessment.get("unresolved_requirements") or []
        if gaps:
            lines.append("  Open requirements: " + "; ".join(gaps))
    return "\n".join(lines)
