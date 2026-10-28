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
* decision basis (why the decision was made) separated from unresolved
  accepted review work;
* completion classification shared by first delivery and repeat reuse. A
  business restriction or required action by another person is basis, not an
  unfinished review; only accepted task work (or genuinely unclassified
  uncertainty) makes the review partial, and an unperformed action the user
  assigned to Atom makes it incomplete.

``execution_id`` identifies the DECISION/DELIVERY turn. The read's own
provenance rides each assessment as ``source_execution_ids`` and
``resumed_read``; a saved/recovered read may be reviewed, but the distinction
between "read now" and "reviewed a persisted read" is explicit rather than
silently rewritten.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

try:  # The repository already carries Pydantic; keep this module importable
    # in a minimal extraction that does not.
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover - only for stripped environments
    BaseModel = None  # type: ignore[assignment]
    Field = None  # type: ignore[assignment]

_IDENTITY_KEYS = ("file_name", "resource_id", "content_hash")
REVIEW_BLOCK_LANGUAGE = "review_result"
_REVIEW_BLOCK_RE = re.compile(
    r"```(?:review_result|review-result|json:review_result|json)\s*"
    r"(\{.*\})\s*```",
    re.DOTALL | re.IGNORECASE,
)

if BaseModel is not None:
    class ReviewAssessmentModel(BaseModel):  # type: ignore[misc,valid-type]
        """Transport-level shape for ONE assessment.

        Fields are REQUIRED and arrays that identify evidence/policy are
        non-empty. This constrains generation where the provider supports a
        schema; ``build_review_result`` still validates every reference
        against the authoritative evidence/policy indexes afterwards.
        """

        subject_id: str = Field(..., min_length=1)
        decision: str = Field(..., min_length=1)
        evidence_ids: List[str] = Field(..., min_length=1)
        policy_ids: List[str] = Field(..., min_length=1)
        basis: List[str] = Field(..., min_length=1)
        unresolved_requirements: List[str] = Field(...)

    class ReviewPayloadModel(BaseModel):  # type: ignore[misc,valid-type]
        """The structured review call's complete output.

        ``explanation`` is the user-facing prose; ``assessments`` is the
        machine block that the validator certifies.
        """

        explanation: str = ""
        assessments: List[ReviewAssessmentModel] = Field(..., min_length=1)
else:  # pragma: no cover - stripped environments only
    ReviewAssessmentModel = None  # type: ignore[assignment]
    ReviewPayloadModel = None  # type: ignore[assignment]


def review_output_schema() -> Dict[str, Any]:
    """JSON schema for the existing structured-output facility.

    Callers that can constrain transport output pass this schema/model to the
    SAME generation call. It is additive: content validation never trusts the
    transport and still runs through ``build_review_result``.
    """
    if ReviewPayloadModel is None:
        return {}
    if hasattr(ReviewPayloadModel, "model_json_schema"):
        return ReviewPayloadModel.model_json_schema()
    return ReviewPayloadModel.schema()  # type: ignore[no-any-return]


def serialize_review_payload(payload: Any) -> str:
    """Turn a structured review payload into the fenced contract answer.

    The model's explanation stays user-facing prose; only ``assessments`` is
    placed in the machine block. ``build_review_result`` still validates every
    subject/evidence/policy reference, so a transport-valid object is never
    automatically certified.
    """
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    elif hasattr(payload, "dict"):
        payload = payload.dict()
    if not isinstance(payload, dict):
        return ""
    assessments = payload.get("assessments")
    if not isinstance(assessments, list) or not assessments:
        return ""
    explanation = str(payload.get("explanation") or "").strip()
    block = json.dumps(
        {"assessments": assessments}, ensure_ascii=False, default=str)
    return (f"{explanation}\n\n" if explanation else "") + (
        f"```review_result\n{block}\n```")


#: Diagnostic state for the LAST structured-review attempt. It deliberately
#: carries no prompt/response body — only the request identity, the resolved
#: route, the transport mode and the failure stage. Callers/logs can
#: distinguish "not dispatched" from "empty payload" and "schema rejection".
LAST_STRUCTURED_REVIEW: Dict[str, Any] = {}


def _review_request_sha(messages: Sequence[Dict[str, Any]]) -> str:
    payload = json.dumps(
        list(messages or []), sort_keys=True, separators=(",", ":"),
        default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _structured_review_failure(
    kind: str, stage: str, detail: str = "", **extra: Any,
) -> None:
    LAST_STRUCTURED_REVIEW.update(
        ok=False, failure_kind=kind, failure_stage=stage,
        failure_detail=str(detail or "")[:500], **extra)
    logger.warning(
        "[review-structured] failed kind=%s stage=%s detail=%s",
        kind, stage, str(detail or "")[:300])


async def generate_structured_review(
    llm_service: Any,
    *,
    messages: Sequence[Dict[str, Any]],
    model: Any = "auto",
    llm_scope: Optional[Dict[str, Any]] = None,
    max_tokens: Optional[int] = None,
) -> Optional[str]:
    """Use the existing structured-output facility for ONE review call.

    The caller's COMPLETE ordered message list is passed through to the
    handler. The model/provider pin is resolved with the existing scoped pin
    helper, and the handler records the route it actually served.

    Returns the same fenced answer shape the validator already accepts, or
    ``None`` with a typed reason in ``LAST_STRUCTURED_REVIEW``. The caller may
    fall back to the ordinary completion path; a payload that was produced but
    fails reference validation is NEVER re-rolled here.
    """
    ordered = [dict(msg) for msg in (messages or []) if isinstance(msg, dict)]
    request_sha = _review_request_sha(ordered)
    LAST_STRUCTURED_REVIEW.clear()
    LAST_STRUCTURED_REVIEW.update(
        ok=False, request_sha256=request_sha, message_count=len(ordered),
        failure_kind=None, failure_stage=None, dispatched=None,
        provider=None, model=None, output_mode="json")
    if ReviewPayloadModel is None:
        _structured_review_failure(
            "unsupported_structured_transport", "import",
            "ReviewPayloadModel unavailable")
        return None
    system_parts = [
        str(msg.get("content") or "")
        for msg in ordered
        if msg.get("role") == "system"
        and str(msg.get("content") or "").strip()
    ]
    user_prompt = ""
    for msg in reversed(ordered):
        if msg.get("role") == "user":
            user_prompt = str(msg.get("content") or "")
            break
    if not system_parts or not user_prompt:
        _structured_review_failure(
            "invalid_request", "message_shape",
            f"system_parts={len(system_parts)} user_prompt={bool(user_prompt)}")
        return None

    scope = dict(llm_scope or {})
    resolved_model = str(model or "").strip()
    if resolved_model.lower() in ("", "auto"):
        resolved_model = str(
            os.getenv("ATOM_REVIEW_MODEL", "") or "").strip() or "auto"
    provider = str(os.getenv("ATOM_REVIEW_PROVIDER", "") or "").strip()
    if not provider and resolved_model.startswith("deepseek"):
        provider = "deepseek"
    pin_kwargs: Dict[str, Any] = {}
    if provider and resolved_model not in ("", "auto"):
        try:
            from core.llm.pinned_planning import build_provider_model_pin

            pin_kwargs = build_provider_model_pin(
                llm_service, provider, resolved_model,
                workspace_id=scope.get("workspace_id"),
                tenant_id=scope.get("tenant_id"))
        except Exception as exc:  # noqa: BLE001 — pinning is best effort
            logger.debug("structured review pin skipped: %r", exc)
    LAST_STRUCTURED_REVIEW.update(
        provider=provider or None, model=resolved_model,
        pin=dict(pin_kwargs), output_mode="json")
    kwargs: Dict[str, Any] = {
        "prompt": user_prompt,
        "response_model": ReviewPayloadModel,
        "system_instruction": "\n\n".join(system_parts),
        "messages": ordered,
        "model": resolved_model,
        "task_type": "review",
        "allow_moa": False,
        "cascade": False,
        "output_mode": "json",
        "claim_wait_seconds": 45.0,
        **pin_kwargs,
    }
    for key in ("workspace_id", "tenant_id", "agent_id", "temperature"):
        if scope.get(key) is not None:
            kwargs[key] = scope[key]
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    try:
        payload = await llm_service.generate_structured_response(**kwargs)
    except Exception as exc:  # noqa: BLE001 — transport capability, not judgment
        text = str(exc).lower()
        kind = (
            "unsupported_structured_transport"
            if any(term in text for term in (
                "instructor", "protocol", "not supported", "unsupported"))
            else "provider_exception")
        _structured_review_failure(
            kind, "dispatch", f"{type(exc).__name__}: {exc}")
        return None
    if payload is None:
        _structured_review_failure(
            "empty_payload", "dispatch",
            "structured service returned no payload")
        return None
    LAST_STRUCTURED_REVIEW.update(
        ok=True, failure_kind=None, failure_stage=None,
        payload_type=type(payload).__name__)
    try:
        serialized = serialize_review_payload(payload)
    except Exception as exc:  # noqa: BLE001 — validation boundary
        _structured_review_failure(
            "payload_validation_failure", "serialize",
            f"{type(exc).__name__}: {exc}")
        return None
    if not serialized:
        _structured_review_failure(
            "payload_validation_failure", "serialize",
            "payload had no assessments")
        return None
    return serialized


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


_WORK_STOPWORDS = frozenset({
    "the", "and", "or", "for", "from", "with", "that", "this", "those",
    "these", "into", "onto", "per", "via", "was", "were", "are", "is",
    "has", "have", "had", "not", "but", "its", "their", "your", "our",
    "a", "an", "of", "to", "in", "on", "at", "by", "as", "be", "been",
    "required", "requirement", "requirements", "missing", "needed",
    "review", "reviewed", "task", "work", "still", "open", "unfinished",
    "complete", "completed", "status", "value", "values", "field",
})


def _as_text_list(value: Any) -> List[str]:
    if isinstance(value, str):
        return _unique([value])
    if isinstance(value, (list, tuple, set)):
        return _unique([str(item) for item in value if str(item or "").strip()])
    return []


def _meaning_tokens(value: Any) -> set:
    return {
        token for token in re.findall(
            r"[a-z0-9][a-z0-9_\-]+", _clean(value).casefold())
        if len(token) >= 3
        and token not in _WORK_STOPWORDS
        and not token.isdigit()
    }


def _mentions_requirement(
    text: Any,
    requirements: Sequence[Any],
) -> bool:
    item_tokens = _meaning_tokens(text)
    if not item_tokens:
        return False
    for requirement in requirements or []:
        if item_tokens & _meaning_tokens(requirement):
            return True
    return False


def accepted_requirement_texts(
    contract: Optional[Dict[str, Any]],
) -> List[str]:
    """The accepted task's own subjects/fields/actions — not model prose."""
    if not isinstance(contract, dict):
        return []
    out: List[str] = []
    out.extend(_as_text_list(contract.get("subjects")))
    out.extend(_as_text_list(contract.get("requested_fields")))
    for action in contract.get("required_actions") or []:
        if isinstance(action, dict):
            text = action.get("text") or action.get("label") or action.get("kind")
        else:
            text = action
        out.extend(_as_text_list(text))
    return _unique(out)[:40]


def required_action_texts(
    contract: Optional[Dict[str, Any]],
) -> List[str]:
    if not isinstance(contract, dict):
        return []
    out: List[str] = []
    for action in contract.get("required_actions") or []:
        if isinstance(action, dict):
            text = action.get("text") or action.get("label") or action.get("kind")
        else:
            text = action
        out.extend(_as_text_list(text))
    return _unique(out)[:12]


def classify_assessment_work(
    assessment: Dict[str, Any],
    accepted_contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, List[str]]:
    """Divide reported unresolved text into task work vs decision basis.

    Precedence matters: a requested field/subject/action wins over a policy
    phrase, so a genuinely missing requested value stays a gap. Unmatched
    free text is preserved as uncertainty; it is never silently promoted to
    a platform obligation or silently dropped.
    """
    basis = _as_text_list(assessment.get("basis"))
    unresolved = _as_text_list(assessment.get("unresolved_requirements"))
    requirements = accepted_requirement_texts(accepted_contract)
    basis_sources: List[str] = list(basis)
    for ref in assessment.get("policy_refs") or []:
        if not isinstance(ref, dict):
            continue
        basis_sources.extend(_as_text_list(ref.get("topic")))
        basis_sources.extend(_as_text_list(ref.get("lesson")))
    accepted: List[str] = []
    supported: List[str] = []
    uncertain: List[str] = []
    for item in unresolved:
        if _mentions_requirement(item, requirements):
            accepted.append(item)
        elif _mentions_requirement(item, basis_sources):
            supported.append(item)
        else:
            uncertain.append(item)
    return {
        "accepted": accepted,
        "supported": supported,
        "uncertain": uncertain,
    }


def _assessment_work(
    assessment: Dict[str, Any],
    accepted_contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, List[str]]:
    if not isinstance(assessment, dict):
        return {"accepted": [], "supported": [], "uncertain": []}
    if (
        "accepted_unresolved_requirements" in assessment
        or "unclassified_requirements" in assessment
        or "basis_supported_requirements" in assessment
    ):
        return {
            "accepted": _as_text_list(assessment.get(
                "accepted_unresolved_requirements")),
            "supported": _as_text_list(assessment.get(
                "basis_supported_requirements")),
            "uncertain": _as_text_list(assessment.get(
                "unclassified_requirements")),
        }
    return classify_assessment_work(assessment, accepted_contract)


def _action_receipt_texts(receipts: Sequence[Any]) -> List[str]:
    out: List[str] = []
    for receipt in receipts or []:
        if isinstance(receipt, dict):
            status = _clean(
                receipt.get("status") or receipt.get("outcome") or "")
            if status.casefold() in ("failed", "error", "rejected", "blocked"):
                continue
            out.extend(_as_text_list(
                receipt.get("text") or receipt.get("action")
                or receipt.get("kind") or receipt.get("label")))
        else:
            out.extend(_as_text_list(receipt))
    return _unique(out)


def review_completion(
    review_result: Optional[Dict[str, Any]],
    accepted_contract: Optional[Dict[str, Any]] = None,
) -> str:
    """One shared completion classification for delivery and repeat reuse.

    ``completed`` = the accepted review was delivered and no accepted task
    work remains. ``partial`` = a validated review was delivered but accepted
    work/uncertainty remains. ``incomplete`` = no certified review.
    """
    if not isinstance(review_result, dict) or review_result.get("ok") is not True:
        return "incomplete"
    contract = (
        accepted_contract if isinstance(accepted_contract, dict)
        else review_result.get("accepted_contract")
        if isinstance(review_result.get("accepted_contract"), dict)
        else None)
    assessments = [
        item for item in (review_result.get("assessments") or [])
        if isinstance(item, dict)
    ]
    if not assessments:
        return "incomplete"
    # An accepted action that Atom did not perform is a hard incomplete
    # outcome, even when the model also reported it as unresolved work.
    # Check it before the softer accepted-gap/uncertainty classification.
    required_actions = required_action_texts(contract)
    if not required_actions:
        required_actions = _as_text_list(review_result.get("required_actions"))
    receipts = _action_receipt_texts(
        review_result.get("action_receipts") or [])
    for action in required_actions:
        if not _mentions_requirement(action, receipts):
            return "incomplete"
    for assessment in assessments:
        work = _assessment_work(assessment, contract)
        if work.get("accepted") or work.get("uncertain"):
            return "partial"
    return "completed"


_DECISION_LABEL_PATTERNS = (
    re.compile(
        r"(?:use\s+exactly\s+these\s+)?decision\s+labels?\s*:\s*"
        r"([A-Za-z][A-Za-z0-9 _-]*(?:\s*[,/;|]\s*[A-Za-z][A-Za-z0-9 _-]*)+)",
        re.IGNORECASE),
    re.compile(
        r"(?:allowed|permitted)\s+decisions?\s*:\s*"
        r"([A-Za-z][A-Za-z0-9 _-]*(?:\s*[,/;|]\s*[A-Za-z][A-Za-z0-9 _-]*)+)",
        re.IGNORECASE),
)


def decision_options_from_text(text: str) -> List[str]:
    """The decision labels a teacher explicitly names in a lesson.

    The canvas/chat teaching surfaces do not expose a separate decision-option
    form; the lesson itself is the contract. Parse ONLY an explicit
    ``decision labels:`` / ``allowed decisions:`` list so ordinary prose
    cannot manufacture a review schema. Returns [] when no list is declared.
    """
    source = str(text or "")
    if not source:
        return []
    for pattern in _DECISION_LABEL_PATTERNS:
        match = pattern.search(source)
        if not match:
            continue
        raw = match.group(1)
        options: List[str] = []
        for part in re.split(r"\s*[,/;|]\s*", raw):
            label = _clean(part)
            if not label:
                continue
            label = re.sub(
                r"\s+(?:and|or)$", "", label, flags=re.IGNORECASE).strip()
            if not label or len(label) > 40:
                continue
            if re.fullmatch(
                    r"(?:please|use|exactly|these|labels?|decisions?|the|and|or)",
                    label, re.IGNORECASE):
                continue
            options.append(label)
        options = _unique(options)
        if len(options) >= 2:
            return options[:20]
    return []


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
        # Teaching surfaces (canvas Training tab, /teach chat command) have
        # no separate decision-option control: the lesson text IS the schema.
        # Parse an explicit label list so those lessons can participate in
        # the review path without an API-only argument.
        options = decision_options_from_text(
            str(lesson.get("lesson") or lesson.get("text") or ""))
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


def build_evidence_index(
    structured: Dict[str, Any],
    subjects: Optional[Sequence[Any]] = None,
) -> List[Dict[str, Any]]:
    """Subject-bound evidence entries from the accepted workbook read.

    A file/hash proves the workbook identity. The row reference here proves
    which subject that row belongs to; a file-level reference alone is not a
    record-level assessment. When ``subjects`` is supplied it is the ACCEPTED
    contract and the read block cannot add or replace subjects.
    """
    if not isinstance(structured, dict):
        return []
    source = _source_identity(structured)
    operation = _retrieval_operation(structured)
    retrieval_execution_id = _clean(
        structured.get("source_execution_id")
        or structured.get("retrieval_execution_id")
        or structured.get("execution_id"))
    subjects = (
        _unique([str(value) for value in subjects or []])
        if subjects is not None else requested_subjects(structured)
    )
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
                "retrieval_execution_id": retrieval_execution_id,
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
                "retrieval_execution_id": retrieval_execution_id,
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
        if not options:
            options = {
                _decision_key(option)
                for option in decision_options_from_text(
                    str(lesson.get("lesson") or lesson.get("text") or ""))
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
    policy_lines = []
    for entry in policy_index or []:
        policy_id = _clean(entry.get("policy_id"))
        topic = _clean(entry.get("topic") or "policy")
        lesson = _clean(entry.get("lesson"))
        policy_lines.append(
            f"- {policy_id} | {topic}" + (f"\n  {lesson}" if lesson else ""))
    required_actions = _as_text_list(contract.get("required_actions"))
    return (
        "REVIEW OUTPUT CONTRACT. Return ONLY one fenced block with valid "
        "JSON; no prose before or after it. The outer JSON object MUST have "
        "its closing brace.\n"
        "```review_result\n"
        '{"assessments":[{"subject_id":"<subject>","decision":"<allowed '
        'decision>","basis":["<why this decision was made>"],'
        '"evidence_ids":["<evidence id>"],"policy_ids":["<policy id>"],'
        '"unresolved_requirements":[]}]}\n'
        "```\n"
        "Only the structured block is certified; the prose is explanatory. "
        "Use exactly one assessment object for every requested subject and "
        "no other object; every object MUST include subject_id. Use only the "
        "IDs listed here, and do not add subjects. Every assessment MUST set "
        "`decision` to exactly one allowed label below — not null, not an "
        "empty string, and not a request to confirm; produce the final "
        "decisions now. Every assessment MUST also include `evidence_ids`, "
        "`basis`, `unresolved_requirements`, and a NON-EMPTY `policy_ids` "
        "array. Copy at least one policy ID from the Policy IDs list below; "
        "never omit policy_ids, guess an ID, or attach a policy whose text "
        "does not support the decision. An assessment with a missing or "
        "empty policy_ids array is rejected.\n"
        "`decision` must be the label ONLY (for example HOLD), with no "
        "amount, parentheses or explanation; put the reasoning in `basis`. "
        "`basis` is WHY you made the decision: the policy, a business "
        "restriction, a negative finding, or an action required of another "
        "person. `unresolved_requirements` is ONLY accepted review work "
        "still unfinished (requested subjects/fields not assessed, or an "
        "action/send the user asked Atom to perform that was not performed). "
        "A negative recommendation, escalation recommendation, business "
        "restriction or required action by another person is not "
        "automatically an unfinished review. Report what remains necessary "
        "to fulfil the user's assigned task separately from the reasons "
        "supporting your decision.\n"
        f"Allowed decisions: {', '.join(decisions)}\n"
        f"Subjects: {', '.join(subjects)}\n"
        + (
            "Required actions assigned to Atom: "
            + ", ".join(required_actions) + "\n"
            if required_actions else ""
        )
        + "Policy entries are INDEPENDENT standing instructions, not an "
          "ordered revision log. Do not infer that an entry supersedes "
          "another from its position. A correction is authoritative only "
          "when it rewrites the same policy ID in place; use that entry's "
          "current text. A newer unrelated lesson never invalidates an "
          "older applicable rule. Apply every entry that is applicable, "
          "and keep genuinely conflicting applicable rules explicit in "
          "`basis` and/or `unresolved_requirements` instead of silently "
          "choosing one.\n"
          "Only the entries listed under Policy IDs are authorized to "
          "govern this assessment. Other workspace/memory lessons — "
          "including ones taught to a different agent — are background "
          "context only; they must not change the allowed decisions, "
          "subjects, evidence IDs, or policy IDs for this task.\n"
          "Use the applicable instruction text below, not just its topic. "
          "For every assessment, `basis` must explain the decision using "
          "the cited row values and the applicable policy text.\n"
        + "Evidence IDs:\n" + ("\n".join(evidence_lines) or "- none") + "\n"
        "Policy IDs:\n" + ("\n".join(policy_lines) or "- none")
    )


def parse_review_payload(answer: str) -> Optional[Dict[str, Any]]:
    """Parse the ONE structured review block; prose is never consulted.

    A `json` fence is accepted when its object carries the review schema
    (`assessments`); unrelated JSON blocks are ignored. Content validation
    stays in build_review_result.
    """
    text = str(answer or "")
    candidates: List[Dict[str, Any]] = []
    for match in _REVIEW_BLOCK_RE.finditer(text):
        try:
            payload = json.loads(match.group(1))
        except Exception:
            continue
        if isinstance(payload, dict) and isinstance(
                payload.get("assessments"), list):
            candidates.append(payload)
    if not candidates:
        # Structured-output transports may return the object itself rather
        # than a fenced block. Accept it only when it carries the review
        # schema; arbitrary JSON prose is still ignored.
        bare = text.strip()
        if bare.startswith("{") and bare.endswith("}"):
            try:
                payload = json.loads(bare)
            except Exception:
                payload = None
            if isinstance(payload, dict) and isinstance(
                    payload.get("assessments"), list):
                candidates.append(payload)
    return candidates[0] if len(candidates) == 1 else None


# Errors produced when the reply carried NO parseable review block at all.
# A reply WITH a block that fails subject/evidence/policy validation emits
# different codes — that is a judgment/validation failure and is never retried.
_MISSING_BLOCK_CODES = frozenset({
    "missing_structured_review", "missing_decision"})


def missing_block_only(errors: Sequence[Any]) -> bool:
    """True when validation failed ONLY because no block was parseable.

    A streaming fallback can ship a reply that lost the fenced block while
    still carrying the contract. That is a FORMAT collapse, not a rejected
    judgment: one contract-only retry with the same evidence/policy IDs is
    legitimate. Any other rejection code (wrong subject, swapped evidence,
    unknown policy, bad decision label, execution mismatch) means a block
    was produced and refused — retrying it would shop for acceptance, so
    this returns False and the evidence-only failure stands.
    """
    if not errors:
        return False
    codes = {
        str(error.get("code") or "")
        for error in errors
        if isinstance(error, dict)
    }
    if not codes or not codes.issubset(_MISSING_BLOCK_CODES):
        return False
    return "missing_structured_review" in codes


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
    accepted_contract: Optional[Dict[str, Any]] = None,
    action_receipts: Optional[Sequence[Any]] = None,
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
            if not _clean(entry.get("retrieval_execution_id")):
                errors.append({
                    "code": "missing_retrieval_execution_id",
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
                "retrieval_execution_id": entry.get(
                    "retrieval_execution_id"),
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
        _source_execs = sorted({
            str(ref.get("retrieval_execution_id") or "")
            for ref in resolved_evidence
            if ref.get("retrieval_execution_id")
        })
        raw_basis = _as_text_list(
            raw.get("basis") or raw.get("decision_basis"))
        raw_unresolved = _as_text_list(
            raw.get("unresolved_requirements"))
        work = classify_assessment_work(
            {
                "basis": raw_basis,
                "unresolved_requirements": raw_unresolved,
                "policy_refs": resolved_policy,
            },
            accepted_contract,
        )
        # With an accepted contract, `unresolved_requirements` means
        # ACCEPTED review work (plus explicit uncertainty). A model-reported
        # restriction that the contract did not assign to Atom moves to
        # `basis` and/or `reported_unresolved_requirements`; it is preserved,
        # never silently dropped, and never promoted to an obligation.
        if accepted_contract is None:
            visible_unresolved = raw_unresolved
        else:
            visible_unresolved = _unique(
                work["accepted"] + work["uncertain"])
        assessments.append({
            "subject_id": subject,
            "decision": decision,
            "basis": _unique(raw_basis + work["supported"]),
            "evidence_refs": resolved_evidence,
            "policy_refs": resolved_policy,
            "unresolved_requirements": visible_unresolved,
            "reported_unresolved_requirements": raw_unresolved,
            "accepted_unresolved_requirements": work["accepted"],
            "basis_supported_requirements": work["supported"],
            "unclassified_requirements": work["uncertain"],
            "source_execution_ids": _source_execs,
            "resumed_read": any(
                source_execution_id != _clean(execution_id)
                for source_execution_id in _source_execs),
        })
    missing = [
        subject for subject in requested
        if _record_key(subject) not in seen_subjects
    ]
    for subject in missing:
        errors.append({"code": "missing_decision", "subject_id": subject})
    if len(assessments) != len(requested) and not missing:
        errors.append({"code": "incomplete_subject_coverage"})
    _ok = not errors and len(assessments) == len(requested)
    result = {
        "schema_version": "review-result-2",
        "execution_id": _clean(execution_id) or None,
        "requested_subjects": requested,
        "allowed_decisions": allowed,
        "source_execution_ids": sorted({
            str(ref.get("retrieval_execution_id") or "")
            for assessment in assessments
            for ref in (assessment.get("evidence_refs") or [])
            if ref.get("retrieval_execution_id")
        }),
        # An uncertified result is NOT an assessment a consumer may act on.
        # Keep the candidates under a separate diagnostic key (F7).
        "assessments": assessments if _ok else [],
        "candidate_assessments": [] if _ok else assessments,
        "errors": errors,
        "ok": _ok,
        "required_actions": required_action_texts(accepted_contract),
        "action_receipts": [
            dict(item) if isinstance(item, dict) else str(item)
            for item in (action_receipts or [])
        ],
    }
    result["completion"] = review_completion(result, accepted_contract)
    return result


def review_matches_delivered_text(
    review_summary: Any, delivered_text: Any,
) -> bool:
    """A validated review may certify only the text that carries its block."""
    summary = _clean(review_summary)
    delivered = _clean(delivered_text)
    return bool(summary) and summary in delivered


def deterministic_read_fallback_allowed(
    *,
    review_required: bool,
    deterministic_answer: Any,
) -> bool:
    """Whether narration failure may fall back to a raw structured read.

    A lookup can degrade to the verified scan when the model is unavailable.
    A REVIEW cannot: the read is only evidence, and serving it would claim a
    judgment the platform never made. The review obligation stays unresolved
    for recovery instead.
    """
    if review_required:
        return False
    return bool(deterministic_answer)


def align_review_failure(
    response: Optional[Dict[str, Any]],
    task_outcome: Optional[Dict[str, Any]],
) -> bool:
    """Force a failed review envelope to agree with the task outcome.

    The read may have resolved ``completed`` before the review contract was
    evaluated. When a required review was not certified, the envelope must
    not ship success/completed (independent-review F1).
    """
    if not isinstance(task_outcome, dict):
        return False
    if (task_outcome.get("delivery") or {}).get(
            "review_required") is not True:
        return False
    if task_outcome.get("objective_met") is not False:
        return False
    if isinstance(response, dict):
        response["success"] = False
        response["outcome"] = "failed"
        response["error_code"] = (
            response.get("error_code") or "turn_objective_not_met")
        response["_recorded_outcome"] = {
            "state": "failed",
            "work_turn": True,
            "noop": False,
            "delivered": False,
        }
    return True


def render_assessment_table(
    review: Dict[str, Any], structured: Dict[str, Any],
) -> str:
    """Render validated decisions joined to authoritative source rows.

    Every selected subject must have both an assessment and a bound target
    row; otherwise the table is withheld (the model cannot add/remove
    membership). Values come from the structured read targets, never from
    model prose.
    """
    if (not isinstance(review, dict) or review.get("ok") is not True
            or not isinstance(structured, dict)):
        return ""
    subject_column = str(structured.get("subject_column") or "Subject")
    fields = [str(f) for f in (structured.get("requested_fields") or [])]
    subjects = [str(s) for s in (structured.get("requested_items") or [])]
    targets = {
        _record_key(t.get("item")): t
        for t in (structured.get("targets") or [])
        if isinstance(t, dict) and _clean(t.get("item"))
    }
    assessments = {
        _record_key(a.get("subject_id")): a
        for a in (review.get("assessments") or [])
        if isinstance(a, dict) and _clean(a.get("subject_id"))
    }
    rows = []
    for subject in subjects:
        key = _record_key(subject)
        target = targets.get(key)
        assessment = assessments.get(key)
        if not target or not assessment:
            return ""
        candidates = ((target.get("identity") or {}).get("candidates") or [])
        if not candidates or not isinstance(candidates[0], dict):
            return ""
        values = {
            str(v.get("field")): v.get("value")
            for v in (candidates[0].get("values") or [])
            if isinstance(v, dict) and v.get("field")
        }
        rows.append((subject, values, _clean(assessment.get("decision"))))
    if not rows:
        return ""
    header = [subject_column] + fields + ["Decision"]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(
            "---" if i in (0, len(header) - 1) else "---:"
            for i in range(len(header))
        ) + " |",
    ]
    for subject, values, decision in rows:
        cells = [subject] + [
            "" if values.get(f) is None else str(values.get(f))
            for f in fields
        ] + [decision]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append(
        "Source: " + str(
            ((structured.get("source_identity") or {}).get("file_name"))
            or "") + " · rows from the bound selection")
    return "\n".join(lines)


def render_review_result(review: Dict[str, Any]) -> str:
    """Render the validated decision block from the structured result."""
    if not isinstance(review, dict) or review.get("ok") is not True:
        return ""
    lines = ["VALIDATED REVIEW (request-bound):"]
    for assessment in review.get("assessments") or []:
        subject = assessment.get("subject_id")
        value = _clean(assessment.get("decision"))
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
        basis = _as_text_list(assessment.get("basis"))
        if basis:
            lines.append("  Basis: " + "; ".join(basis[:4]))
        if (
            "accepted_unresolved_requirements" in assessment
            or "unclassified_requirements" in assessment
        ):
            gaps = _unique(
                _as_text_list(assessment.get(
                    "accepted_unresolved_requirements"))
                + _as_text_list(assessment.get(
                    "unclassified_requirements")))
        else:
            gaps = _as_text_list(
                assessment.get("unresolved_requirements"))
        if gaps:
            lines.append("  Open requirements: " + "; ".join(gaps[:6]))
    return "\n".join(lines)
