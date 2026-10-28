"""Accepted review contract — one subject authority for a review turn.

The user's accepted objective names the review subjects. The read reports what
it found. The review reports what was assessed. These are three different
facts and must never be reconstructed from each other:

    accepted_contract.subjects   -> from the accepted objective
    read_result.subjects_found   -> from the structured read
    review_result.assessments    -> from the certified output

Catalogued filenames and requested field labels are not subjects. Filenames are
stripped by their exact catalogued identity (full name, stem, extensionless
stem), and requested fields are kept in their own field list.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

from core.review_result import decision_options_from_lessons
from core.target_set_resolution import extract_items_from_text
from core.workbook_read_artifact import extract_field_labels


def _unique(values: Iterable[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def strip_catalogued_names(
    text: str,
    catalogued_names: Optional[Sequence[str]] = None,
) -> str:
    """Remove complete catalogued file identities before subject extraction.

    This is identity-based, not a filename regex: every supplied catalogued
    name, its path-stem, and its extensionless stem are removed verbatim.
    """
    cleaned = str(text or "")
    variants: List[str] = []
    for raw in catalogued_names or []:
        name = str(raw or "").strip()
        if not name:
            continue
        base = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        variants.extend([name, base])
        stem = base.rsplit(".", 1)[0] if "." in base else base
        variants.extend([stem, stem.replace("_", " "), stem.replace("-", " ")])
    for variant in sorted(set(variants), key=len, reverse=True):
        if len(variant) < 3:
            continue
        cleaned = re.sub(
            re.escape(variant), " ", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split())


def accepted_subjects(
    objective: str,
    *,
    catalogued_names: Optional[Sequence[str]] = None,
) -> List[str]:
    """The identifiers the accepted objective actually names."""
    cleaned = strip_catalogued_names(objective, catalogued_names)
    return _unique(extract_items_from_text(cleaned))[:12]


def requested_fields(objective: str) -> List[str]:
    """Field labels the objective itself names; never review subjects.

    The accepted contract records the user's own wording ("Ask Amount",
    "Unit Price"), not the read layer's canonical alias ("price"). The
    canonical form is useful for column matching, but using it here made an
    Ask Amount task claim the user requested a price field.
    """
    return _unique(extract_field_labels([str(objective or "")]))[:20]


def required_actions(objective: str) -> List[str]:
    """Actions the accepted objective asks Atom itself to perform.

    A review recommendation is not an action. This uses the request's own
    assignment/obligation table; an action that cannot be grounded there is
    not manufactured here.
    """
    try:
        from core.turn_decision import extract_request_assignments

        obligations = extract_request_assignments(str(objective or ""))
    except Exception:  # noqa: BLE001 — contract remains usable
        return []
    text = str(objective or "")

    def _prohibited(action_text: str) -> bool:
        # The assignment table is shape-based; an explicit prohibition
        # ("do not update anything") is not an action assigned to Atom.
        return bool(re.search(
            r"\b(?:do\s+not|don't|must\s+not|should\s+not|never|without)\b"
            r"[^.\n]{0,80}" + re.escape(action_text),
            text, re.IGNORECASE))

    return _unique([
        str(action.get("text") or "").strip()
        for action in (obligations.get("additional_actions") or [])
        if isinstance(action, dict)
        and str(action.get("text") or "").strip()
        and not _prohibited(str(action.get("text") or "").strip())
    ])[:8]


def teaching_fingerprint(lessons: Optional[Sequence[Dict[str, Any]]]) -> str:
    """A stable revision for the applicable teaching/decision schema."""
    payload = []
    for lesson in lessons or []:
        if not isinstance(lesson, dict):
            continue
        payload.append({
            "id": lesson.get("id"),
            "topic": lesson.get("topic"),
            "scope": lesson.get("scope"),
            "lesson": lesson.get("lesson") or lesson.get("summary"),
            "decision_options": list(lesson.get("decision_options") or []),
        })
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:24]


def build_accepted_contract(
    objective: str,
    *,
    catalogued_names: Optional[Sequence[str]] = None,
    source_version: Optional[str] = None,
    lessons: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """The accepted review inputs, preserved independently of the read."""
    return {
        "subjects": accepted_subjects(
            objective, catalogued_names=catalogued_names),
        "requested_fields": requested_fields(objective),
        "source_version": str(source_version or ""),
        "teaching_revision": teaching_fingerprint(lessons),
        "decision_schema": list(decision_options_from_lessons(lessons or [])),
        "required_actions": required_actions(objective),
    }


def same_contract_inputs(
    stored: Optional[Dict[str, Any]],
    current: Optional[Dict[str, Any]],
) -> bool:
    """Whether a repeat can reuse a validated assessment."""
    if not isinstance(stored, dict) or not isinstance(current, dict):
        return False
    for key in (
        "subjects",
        "requested_fields",
        "source_version",
        "teaching_revision",
        "decision_schema",
        "required_actions",
    ):
        if list(stored.get(key) or []) != list(current.get(key) or []):
            return False
    return True


# READ-RECEIPT HANDOFF (kept beside the contract so callers have one import
# for "what this review accepted" and "which read may supply it").  The
# implementation lives in core.review_handoff to keep receipt extraction and
# carrier adoption out of the pure contract helpers above.
def extract_receipt_identity(receipt: Any) -> Dict[str, Any]:
    from core.review_handoff import extract_receipt_identity as _extract

    return _extract(receipt)


def extract_record_identity(record: Any) -> Dict[str, Any]:
    from core.review_handoff import extract_record_identity as _extract

    return _extract(record)


def identity_conflicts(
    receipt_identity: Optional[Dict[str, Any]],
    record_identity: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    from core.review_handoff import identity_conflicts as _conflicts

    return _conflicts(receipt_identity, record_identity)


def reject_conflicting_identity_fields(
    receipt_identity: Optional[Dict[str, Any]],
    record_identity: Optional[Dict[str, Any]],
) -> None:
    from core.review_handoff import (
        reject_conflicting_identity_fields as _reject,
    )

    return _reject(receipt_identity, record_identity)


def validate_against_bound_source(
    receipt_identity: Optional[Dict[str, Any]],
    record_identity: Optional[Dict[str, Any]],
    bound_source: Optional[Dict[str, Any]],
    **kwargs: Any,
) -> str:
    from core.review_handoff import (
        validate_against_bound_source as _validate,
    )

    return _validate(
        receipt_identity, record_identity, bound_source, **kwargs)


def validate_read_receipt(
    planner_result: Any,
    accepted_contract: Optional[Dict[str, Any]],
    bound_source: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    from core.review_handoff import validate_read_receipt as _validate

    return _validate(
        planner_result, accepted_contract, bound_source, **kwargs)


def validate_structured_read(
    structured: Any,
    accepted_contract: Optional[Dict[str, Any]],
    bound_source: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    from core.review_handoff import validate_structured_read as _validate

    return _validate(
        structured, accepted_contract, bound_source, **kwargs)


def select_review_read(
    candidates: Sequence[Any],
    accepted_contract: Optional[Dict[str, Any]],
    bound_source: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    from core.review_handoff import select_review_read as _select

    return _select(candidates, accepted_contract, bound_source, **kwargs)


def adopt_read_result(
    selected_read: Dict[str, Any],
    **kwargs: Any,
) -> Dict[str, Any]:
    from core.review_handoff import adopt_read_result as _adopt

    return _adopt(selected_read, **kwargs)


def build_review_input(
    accepted_contract: Optional[Dict[str, Any]],
    turn_read: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    from core.review_handoff import build_review_input as _build

    return _build(accepted_contract, turn_read)
