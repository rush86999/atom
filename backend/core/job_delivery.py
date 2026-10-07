"""Deterministic staged delivery for job results (guide steps 3-4).

Production delivery: renders from the AUTHORITATIVE structured record,
persists through the ChatMessage store keyed by a STABLE event ID whose
uniqueness is DATABASE-ENFORCED (the delivery_events table's primary
key — two concurrent writers: exactly one insert succeeds).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional


def job_event_id(job_id: str, result_revision: str,
                 event_type: str) -> str:
    """Stable identity for one delivery event."""
    return "evt:" + hashlib.sha256(
        f"{job_id}|{result_revision}|{event_type}".encode()
    ).hexdigest()[:24]


def derive_result_revision(task_record: Optional[Dict[str, Any]]) -> str:
    """A RESULT-ONLY revision: changes when findings, dispositions,
    remaining obligations, or terminal status change. Claim renewals,
    attempt-counter bumps and worker bookkeeping do NOT change it —
    pin: those produce no new event."""
    if task_record is None:
        return "0"
    h = hashlib.sha256()
    # FINDINGS ONLY (owner correction 2026-10-07): read-attempt
    # bookkeeping (more operations with read_returned_no_receipt) does
    # NOT change the result revision — only actual findings, question
    # dispositions, and terminal status do. Hashing every operation's
    # outcome made attempt-only cycles produce identical-text events.
    for op in sorted(task_record.get("operations") or [],
                     key=lambda o: str(o.get("operation_id") or "")):
        facts = op.get("execution") or {}
        for f in facts.get("findings") or []:
            h.update(json.dumps(
                {"f": f.get("field"), "v": (f.get("parsed") or {})
                 .get("value"), "s": f.get("source")},
                sort_keys=True, default=str).encode())
    # dispositions + remaining obligations (status changes matter)
    for q in sorted(
            (task_record.get("task_revision") or {}).get("unresolved")
            or [],
            key=lambda q: str(q.get("question_id") or "")):
        h.update(json.dumps({
            "q": str(q.get("question_id") or "")[:40],
            "st": q.get("status"),
            "kind": q.get("kind"),
        }, sort_keys=True).encode())
    # terminal status
    h.update(str(task_record.get("status") or "").encode())
    return h.hexdigest()[:16]


def render_findings(findings: List[Dict[str, Any]],
                    item: str = "") -> str:
    if not findings:
        return ""
    lines = []
    for f in findings:
        field = str(f.get("field") or "?")
        col = str(f.get("column") or "?")
        parsed = f.get("parsed") or {}
        val = parsed.get("value")
        cur = parsed.get("currency")
        unit = parsed.get("unit")
        shown = f"{val}"
        if cur:
            shown += f" {cur}"
        if unit:
            shown += f" {unit}"
        src = str(f.get("source") or "")
        ver = str(f.get("content_hash") or "")
        loc = f" ({src})" if src else ""
        ver_note = f" [content {ver[:12]}]" if ver else ""
        lines.append(f"- {field}: {shown} — column {col}{loc}{ver_note}")
    header = f"Findings for {item}:" if item else "Findings:"
    return header + "\n" + "\n".join(lines)


def render_remaining(remaining: List[Dict[str, Any]]) -> str:
    if not remaining:
        return ""
    return ("Still needed:\n"
            + "\n".join(
                f"- {r.get('next_action') or r.get('question') or '?'}"
                for r in remaining))


def render_job_result(task_record: Optional[Dict[str, Any]],
                      job_id: str) -> str:
    """Terminal rendering from the authoritative record. INVARIANT:
    open obligations prevent a 'completed' label even if the stored
    status is inconsistent; a failed read remains visible when no
    selectable action remains."""
    if task_record is None:
        return f"Job {job_id[:12]}: no record found."
    findings: List[Dict[str, Any]] = []
    item = ""
    any_failed = False
    for op in task_record.get("operations") or []:
        facts = op.get("execution") or {}
        for f in facts.get("findings") or []:
            findings.append(f)
        if str(facts.get("outcome") or "").startswith("read_fail"):
            any_failed = True
        if str(facts.get("outcome") or "") == "read_returned_no_receipt":
            any_failed = True
        if not item and facts.get("items"):
            item = str(list(facts["items"].keys())[0])
    remaining: List[Dict[str, Any]] = []
    for q in (task_record.get("task_revision") or {}).get(
            "unresolved") or []:
        if q.get("status") != "open":
            continue
        kind = q.get("kind")
        if kind == "business_decision":
            remaining.append({
                "question": str(q.get("question")
                                or "owner decision needed"),
                "next_action": "owner decision"})
        elif int(q.get("attempts") or 0) >= 3:
            remaining.append({
                "question": str(q.get("question")
                                or "action exhausted"),
                "next_action": "exhausted — needs owner review"})
        elif q.get("next_action"):
            remaining.append({"next_action": q.get("next_action"),
                              "question": q.get("question")})
    parts = []
    if findings:
        parts.append(render_findings(findings, item))
    if remaining:
        parts.append(render_remaining(remaining))
    if any_failed:
        parts.append("Note: some reads could not complete — the "
                     "findings above are what was actually established.")
    if not parts:
        parts.append(f"Job {job_id[:12]}: no findings recorded and no "
                     "remaining work listed.")
    # INVARIANT: open obligations prevent the completed label
    stored_status = str(task_record.get("status") or "")
    if remaining:
        parts.append("Status: open — items above still need attention.")
    elif stored_status in ("completed", "achieved"):
        parts.append("Status: completed.")
    elif stored_status in ("cancelled", "failed"):
        parts.append(f"Status: {stored_status}.")
    else:
        parts.append("Status: no further work identified.")
    return "\n\n".join(parts)


def deliver_job_event(
        conversation_id: str, job_id: str,
        task_record: Optional[Dict[str, Any]],
        event_type: str = "research_update",
        session_mirror=None) -> Optional[str]:
    """THE production delivery function. Atomically arbitrated via the
    delivery_events table's primary key: two concurrent writers —
    exactly one succeeds. Returns the event ID if delivered, None if
    already delivered. The session mirror is gated on the SAME outcome
    (it appends only when the database delivery actually happened)."""
    revision = derive_result_revision(task_record)
    event = job_event_id(job_id, revision, event_type)
    text = render_job_result(task_record, job_id)
    from core.database import get_db_session
    from core.models import ChatMessage, DeliveryEvent

    with get_db_session() as db:
        db.add(DeliveryEvent(
            event_id=event, conversation_id=conversation_id,
            job_id=job_id, result_revision=revision))
        try:
            db.flush()
        except Exception as exc:
            # ONLY the established duplicate-event conflict (PK
            # IntegrityError) is "already delivered". Missing table,
            # disk failure, or any other error PROPAGATES so delivery
            # stays retryable — silently suppressing would lose results.
            from sqlalchemy.exc import IntegrityError

            db.rollback()
            if isinstance(exc, IntegrityError):
                return None  # another writer delivered this event
            raise  # retryable — the caller sees the failure
        db.add(ChatMessage(
            conversation_id=conversation_id, role="assistant",
            tenant_id="default", content=text[:4000],
            metadata_json=json.dumps({
                "delivery_event": event, "job_id": job_id,
                "result_revision": revision})))
        db.commit()
    if session_mirror is not None:
        try:
            session_mirror(text)
        except Exception:
            pass
    return event


def calc_pending_question_reply(
        message, user_id, workspace_id, conversation_id):
    """The precise input question for a pending calculation (re-exported
    from pricing_calculation for the delivery path)."""
    from core.pricing_calculation import calc_pending_question_reply as _f

    return _f(message, user_id, workspace_id, conversation_id)


def render_acknowledgement(job_id: str, description: str,
                           queued_steps: int,
                           clarification: Optional[str] = None) -> str:
    """The staged acknowledgement. Only issued when executable work is
    durable and eligible. Missing owner inputs are a CLARIFICATION, not
    queued work — the research worker cannot supply them."""
    if clarification:
        return clarification
    return (
        f"Started {description}. The work is saved on job "
        f"{job_id[:12]} — findings will be delivered here when the "
        f"worker completes. {queued_steps} step(s) queued."
        if queued_steps else
        f"Started {description}. The work is saved on job "
        f"{job_id[:12]} — findings will be delivered here.")
