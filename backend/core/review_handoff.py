"""Read-receipt handoff for review turns.

A review read is evidence, not the answer.  The orchestrator has several
carriers for a read (``_turn_structured_record``, the rendered/presentation
text, the durable ``_pending_file_result`` row) and a review needs all of
them to describe the SAME retrieval.  Updating only one carrier is how a
newer receipt came to be paired with an older empty-item rendering.

This module validates one receipt against the accepted contract and the
bound source identity, then normalises the structured record, presentation,
evidence index and durable carrier together.  A metadata key alone is not
evidence: the record must contain a row for every accepted subject, and the
row must belong to the bound workbook/version.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence

from core.review_result import build_evidence_index

logger = logging.getLogger(__name__)

TARGET_EXTRACTION_VERSION = 3

_IDENTITY_KEYS = (
    "file_name",
    "resource_id",
    "file_id",
    "content_hash",
    "source_version",
    "version",
)
_RECEIPT_KEYS = ("storage_read", "structured_result", "file_read", "datasets_search")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _text(value: Any) -> str:
    """Presentation text keeps its line breaks; only trim the edges."""
    return str(value or "").strip()


def _key(value: Any) -> str:
    return _clean(value).casefold()


def _basename(value: Any) -> str:
    text = _clean(value)
    return text.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _unique(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values or []:
        text = _clean(value)
        if not text or _key(text) in seen:
            continue
        seen.add(_key(text))
        out.append(text)
    return out


def _planner_meta(planner_result: Any) -> Dict[str, Any]:
    """The structured receipt metadata an executor attached to a plan."""
    if planner_result is None:
        return {}
    meta = getattr(planner_result, "_result_meta", None)
    if isinstance(meta, dict):
        return dict(meta)
    if isinstance(planner_result, dict):
        nested = planner_result.get("_result_meta")
        if isinstance(nested, dict):
            return dict(nested)
        return dict(planner_result)
    return {}


def _iter_receipt_records(
    meta: Dict[str, Any],
) -> Iterable[tuple[str, Dict[str, Any], Dict[str, Any]]]:
    """Yield ``(label, structured_record, receipt_payload)`` candidates.

    The order is deliberate: the storage-read record is the production
    carrier; a bare ``datasets_search`` envelope is only a lead, never a
    substitute for a structured record.
    """
    seen = set()
    for key in _RECEIPT_KEYS:
        payload = meta.get(key)
        if not isinstance(payload, dict):
            continue
        candidates = []
        if key == "structured_result":
            candidates.append(("structured_result", payload, payload))
        else:
            candidates.append((key, payload, payload))
            nested = payload.get("structured_result")
            if isinstance(nested, dict):
                candidates.append((f"{key}.structured_result", nested, payload))
        for label, record, receipt in candidates:
            marker = id(record)
            if marker in seen:
                continue
            seen.add(marker)
            yield label, record, receipt

    # Some executors put the record at the top level of a plan dictionary.
    for key in ("structured_result", "workbook_read"):
        record = meta.get(key)
        if isinstance(record, dict) and id(record) not in seen:
            seen.add(id(record))
            yield key, record, {}


def _is_structured_record(record: Any) -> bool:
    return bool(
        isinstance(record, dict)
        and (
            isinstance(record.get("targets"), list)
            or isinstance(record.get("requested_items"), list)
        )
    )


def _record_identity(
    record: Dict[str, Any],
    receipt: Dict[str, Any],
) -> Dict[str, Any]:
    identity: Dict[str, Any] = {}
    for source in (receipt, record.get("source_identity")):
        if not isinstance(source, dict):
            continue
        nested = source.get("identity")
        if isinstance(nested, dict):
            for key in _IDENTITY_KEYS:
                if nested.get(key) and not identity.get(key):
                    identity[key] = nested.get(key)
        for key in _IDENTITY_KEYS:
            if source.get(key) and not identity.get(key):
                identity[key] = source.get(key)
    return identity


def _version_of(identity: Dict[str, Any]) -> str:
    return _clean(
        identity.get("content_hash")
        or identity.get("source_version")
        or identity.get("version")
    )


def _bound_source_mismatch(
    bound_source: Optional[Dict[str, Any]],
    identity: Dict[str, Any],
    record: Dict[str, Any],
) -> str:
    """Why the receipt cannot be the bound workbook/version, or ``""``."""
    bound = _as_dict(bound_source)
    if not bound:
        return "" if identity else "receipt has no source identity"

    if not identity:
        return "receipt has no source identity"

    for key in ("resource_id", "file_id"):
        expected = _clean(bound.get(key))
        actual = _clean(identity.get(key))
        if expected and actual and expected != actual:
            return f"{key} mismatch ({actual!r} != {expected!r})"

    expected_name = _basename(bound.get("file_name"))
    actual_name = _basename(identity.get("file_name"))
    if expected_name and actual_name and _key(expected_name) != _key(
            actual_name):
        return (
            f"file_name mismatch ({actual_name!r} != {expected_name!r})")

    expected_version = _version_of(bound)
    actual_version = _version_of(identity)
    if expected_version:
        if not actual_version:
            return "receipt has no version to bind to the accepted source"
        if _key(actual_version) != _key(expected_version):
            return (
                f"source version mismatch ({actual_version!r} != "
                f"{expected_version!r})")

    # The rendered evidence revision carries the same content hash in the
    # artifact-native record.  A receipt that names the bound hash but was
    # rendered from a different revision is still not the bound read.
    revision = _clean(record.get("evidence_revision"))
    if expected_version and revision:
        revision_hash = revision.split(":", 1)[0]
        if revision_hash and _key(revision_hash) != _key(expected_version):
            return (
                f"evidence revision mismatch ({revision_hash!r} != "
                f"{expected_version!r})")
    return ""


def _target_rows(target: Dict[str, Any]) -> int:
    """How many row-level references this target carries."""
    if not isinstance(target, dict):
        return 0
    identity = target.get("identity")
    if not isinstance(identity, dict):
        identity = {}
    candidates = identity.get("candidates")
    if isinstance(candidates, list):
        rows = [
            candidate for candidate in candidates
            if isinstance(candidate, dict)
            and (
                _clean(candidate.get("ref"))
                or candidate.get("values")
                or candidate.get("row") is not None
            )
        ]
        if rows:
            return len(rows)
    for container in (target, target.get("field")):
        if not isinstance(container, dict):
            continue
        values = container.get("values")
        if isinstance(values, list) and values:
            return len(values)
    if _clean(target.get("row_ref")) or target.get("row") is not None:
        return 1
    return 0


def _subject_rows(
    record: Dict[str, Any],
    subjects: Sequence[str],
) -> tuple[Dict[str, int], List[str]]:
    targets = [
        target for target in (record.get("targets") or [])
        if isinstance(target, dict)
    ]
    by_subject: Dict[str, Dict[str, Any]] = {}
    for target in targets:
        item = _key(target.get("item"))
        if item and item not in by_subject:
            by_subject[item] = target
    rows: Dict[str, int] = {}
    missing: List[str] = []
    for subject in subjects:
        key = _key(subject)
        target = by_subject.get(key)
        count = _target_rows(target) if target else 0
        if count <= 0:
            missing.append(subject)
        else:
            rows[subject] = count
    return rows, missing


def _presentation_for(
    record: Dict[str, Any],
    subjects: Sequence[str],
    rendered: str,
) -> str:
    """Render the record; fall back to the receipt text it came with."""
    candidate = dict(record)
    requested = _unique(candidate.get("requested_items") or [])
    if subjects and (
        not requested
        or {_key(item) for item in requested}
        != {_key(item) for item in subjects}
    ):
        # The accepted contract owns the subject set.  Rendering the
        # record's stale requested-item view is what produced the
        # empty-item sentence while a fresh row was present.
        candidate["requested_items"] = list(subjects)
    try:
        from core.answer_presentation import present_from_record

        answer = str(present_from_record(candidate).get("answer") or "").strip()
        if answer:
            return answer
    except Exception as exc:  # noqa: BLE001 — receipt text is the floor
        logger.debug("[review-handoff] presentation render failed: %r", exc)
    return _text(rendered)


def validate_structured_read(
    structured: Any,
    accepted_contract: Optional[Dict[str, Any]],
    bound_source: Optional[Dict[str, Any]] = None,
    *,
    identity: Optional[Dict[str, Any]] = None,
    rendered: str = "",
    workbook_read: Optional[Dict[str, Any]] = None,
    source_execution_id: str = "",
) -> Dict[str, Any]:
    """Validate one structured record against the accepted subject set.

    Returns a normalised selection.  ``ok`` is true only when every accepted
    subject has at least one row from the bound source.
    """
    contract = _as_dict(accepted_contract)
    subjects = _unique(contract.get("subjects") or [])
    record = _as_dict(structured)
    if source_execution_id and not (
        record.get("source_execution_id")
        or record.get("retrieval_execution_id")
        or record.get("execution_id")
    ):
        record["source_execution_id"] = _clean(source_execution_id)
    failure = {
        "ok": False,
        "reason": "",
        "structured_result": record or None,
        "presentation": "",
        "rendered": _text(rendered),
        "evidence_index": [],
        "identity": _as_dict(identity),
        "workbook_read": workbook_read,
        "source_execution_id": _clean(source_execution_id),
        "subjects_found": [],
    }
    if not subjects:
        failure["reason"] = "accepted contract has no subjects"
        return failure
    if not _is_structured_record(record):
        failure["reason"] = "receipt has no structured read record"
        return failure

    merged_identity = _record_identity(
        record, {"identity": _as_dict(identity)})
    binding = _as_dict(bound_source)
    if contract.get("source_version") and not _version_of(binding):
        binding["source_version"] = _clean(contract.get("source_version"))
    if not binding and contract.get("source_version"):
        binding["source_version"] = _clean(contract.get("source_version"))
    mismatch = _bound_source_mismatch(
        binding or {
            "content_hash": contract.get("source_version") or "",
        },
        merged_identity,
        record,
    )
    if mismatch:
        failure["reason"] = mismatch
        failure["identity"] = merged_identity
        return failure

    rows, missing = _subject_rows(record, subjects)
    if missing:
        failure["reason"] = (
            "receipt has no matching row for accepted subject(s): "
            + ", ".join(missing)
        )
        failure["identity"] = merged_identity
        failure["subjects_found"] = sorted(rows)
        return failure

    evidence_index = build_evidence_index(record, subjects=subjects)
    if not evidence_index:
        failure["reason"] = "receipt produced no subject-bound evidence"
        failure["identity"] = merged_identity
        failure["subjects_found"] = sorted(rows)
        return failure

    operation = _clean(
        record.get("attempt_id")
        or record.get("evidence_revision")
        or record.get("retrieval_operation")
    )
    if not operation:
        failure["reason"] = "receipt has no retrieval operation identity"
        failure["identity"] = merged_identity
        failure["subjects_found"] = sorted(rows)
        return failure

    execution = _clean(
        source_execution_id
        or record.get("source_execution_id")
        or record.get("retrieval_execution_id")
        or record.get("execution_id")
    )

    return {
        "ok": True,
        "reason": "",
        "structured_result": record,
        "presentation": _presentation_for(record, subjects, rendered),
        "rendered": _text(rendered),
        "evidence_index": evidence_index,
        "identity": merged_identity,
        "workbook_read": workbook_read,
        "source_execution_id": execution,
        "subjects": subjects,
        "subjects_found": sorted(rows),
    }


def validate_read_receipt(
    planner_result: Any,
    accepted_contract: Optional[Dict[str, Any]],
    bound_source: Optional[Dict[str, Any]] = None,
    *,
    execution_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Select ONE validated read from a planner/executor receipt.

    A receipt metadata key alone is not enough.  Every candidate structured
    record is checked for the accepted subjects' rows and the bound
    workbook/version; the first complete record wins.  When none qualify the
    result is ``ok=False`` with the reasons collected from the candidates.
    """
    meta = _planner_meta(planner_result)
    reasons: List[str] = []
    best: Optional[Dict[str, Any]] = None
    for label, record, receipt in _iter_receipt_records(meta):
        if not _is_structured_record(record):
            continue
        identity = _record_identity(record, receipt)
        selected = validate_structured_read(
            record,
            accepted_contract,
            bound_source,
            identity=identity,
            rendered=_text(
                receipt.get("rendered_answer")
                or receipt.get("rendered")
                or receipt.get("block")
                or meta.get("rendered_answer")
                or meta.get("block")
            ),
            workbook_read=(
                receipt.get("workbook_read")
                if isinstance(receipt.get("workbook_read"), dict)
                else meta.get("workbook_read")
            ),
            source_execution_id=_clean(
                execution_id
                or receipt.get("source_execution_id")
                or receipt.get("execution_id")
                or meta.get("source_execution_id")
                or meta.get("execution_id")
            ),
        )
        if selected.get("ok"):
            return selected
        reasons.append(f"{label}: {selected.get('reason')}")
    if best is None:
        best = {
            "ok": False,
            "reason": "; ".join(reasons) or "receipt has no structured read record",
            "structured_result": None,
            "presentation": "",
            "rendered": "",
            "evidence_index": [],
            "identity": {},
            "workbook_read": None,
            "source_execution_id": "",
            "subjects_found": [],
        }
    else:
        best["reason"] = "; ".join(reasons) or best.get("reason") or ""
    return best


def select_review_read(
    candidates: Sequence[Any],
    accepted_contract: Optional[Dict[str, Any]],
    bound_source: Optional[Dict[str, Any]] = None,
    *,
    execution_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Pick the first candidate that validates — never the first nonempty."""
    reasons: List[str] = []
    for candidate in candidates or []:
        if isinstance(candidate, dict):
            selected = validate_structured_read(
                candidate,
                accepted_contract,
                bound_source,
                identity=_as_dict(candidate.get("source_identity")),
                rendered=_text(candidate.get("rendered")),
                source_execution_id=_clean(execution_id),
            )
        else:
            selected = validate_read_receipt(
                candidate, accepted_contract, bound_source,
                execution_id=execution_id)
        if selected.get("ok"):
            return selected
        reasons.append(str(selected.get("reason") or "not a valid read"))
    return {
        "ok": False,
        "reason": "; ".join(reasons) or "no review evidence available",
        "structured_result": None,
        "presentation": "",
        "rendered": "",
        "evidence_index": [],
        "identity": {},
        "workbook_read": None,
        "source_execution_id": "",
        "subjects_found": [],
    }


def adopt_read_result(
    selected_read: Dict[str, Any],
    *,
    execution_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalise one validated read into every downstream carrier.

    The returned ``structured_result``, ``presentation`` and
    ``evidence_index`` all come from the SAME selected receipt, and the
    returned ``carrier`` is the durable session row that points at them.
    """
    selected = _as_dict(selected_read)
    if selected.get("ok") is not True:
        raise ValueError("adopt_read_result requires a validated read")
    structured = _as_dict(selected.get("structured_result"))
    evidence_index = [
        dict(entry) for entry in (selected.get("evidence_index") or [])
        if isinstance(entry, dict)
    ]
    identity = _as_dict(selected.get("identity"))
    presentation = _text(
        selected.get("presentation")
        or selected.get("rendered")
    )
    source_execution_id = _clean(
        execution_id
        or selected.get("source_execution_id")
        or structured.get("source_execution_id")
        or structured.get("retrieval_execution_id")
        or structured.get("execution_id")
    )
    attempt_id = _clean(
        structured.get("attempt_id")
        or structured.get("retrieval_operation")
    )
    evidence_revision = _clean(structured.get("evidence_revision"))
    evidence_action = _clean(structured.get("evidence_action"))
    subjects_found = _unique(
        selected.get("subjects_found")
        or [
            target.get("item")
            for target in (structured.get("targets") or [])
            if isinstance(target, dict) and target.get("item")
        ]
    )
    carrier = {
        "status": "retrieved",
        "target_extraction_version": TARGET_EXTRACTION_VERSION,
        "rendered": presentation[:24000],
        "rendered_core": presentation[:24000],
        "identity": identity,
        "workbook_read": selected.get("workbook_read"),
        "execution_id": source_execution_id,
        "source_execution_id": source_execution_id,
        "retrieved_at": time.time(),
        "structured_result": structured,
        "attempt_id": attempt_id or None,
        "evidence_revision": evidence_revision or None,
        "evidence_action": evidence_action or None,
        "evidence_index": evidence_index,
        "subjects_found": subjects_found,
    }
    return {
        **selected,
        "ok": True,
        "structured_result": structured,
        "presentation": presentation,
        "rendered": presentation,
        "evidence_index": evidence_index,
        "identity": identity,
        "source_execution_id": source_execution_id,
        "attempt_id": attempt_id,
        "evidence_revision": evidence_revision,
        "evidence_action": evidence_action,
        "subjects_found": subjects_found,
        "carrier": carrier,
    }


def build_review_input(
    accepted_contract: Optional[Dict[str, Any]],
    turn_read: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """One review input shared by the prompt and the validator."""
    contract = _as_dict(accepted_contract)
    read = _as_dict(turn_read)
    subjects = _unique(contract.get("subjects") or [])
    structured = _as_dict(read.get("structured_result"))
    evidence_index = [
        dict(entry) for entry in (read.get("evidence_index") or [])
        if isinstance(entry, dict)
    ]
    if structured and not evidence_index:
        evidence_index = build_evidence_index(structured, subjects=subjects)
    return {
        "accepted_contract": contract,
        "subjects": subjects,
        "structured_result": structured,
        "evidence_index": evidence_index,
        "presentation": _text(
            read.get("presentation") or read.get("rendered")),
        "identity": _as_dict(read.get("identity")),
        "source_execution_id": _clean(read.get("source_execution_id")),
        "attempt_id": _clean(
            read.get("attempt_id") or structured.get("attempt_id")),
        "evidence_revision": _clean(
            read.get("evidence_revision")
            or structured.get("evidence_revision")),
        "evidence_action": _clean(
            read.get("evidence_action")
            or structured.get("evidence_action")),
        "subjects_found": _unique(
            read.get("subjects_found")
            or [
                target.get("item")
                for target in (structured.get("targets") or [])
                if isinstance(target, dict) and target.get("item")
            ]
        ),
    }
