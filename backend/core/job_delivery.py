"""Deterministic staged delivery for job results (guide steps 3-4).

Renders the AUTHORITATIVE structured record (findings + remaining
obligations) — never prose memory, never a second model call. Delivered
through the ChatMessage store the UI reads, keyed by a stable job-event
identity, not by text.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional


def job_event_id(job_id: str, result_revision: int,
                 event_type: str) -> str:
    """Stable identity for one delivery event: job + revision + type.
    Identical text from distinct events is NOT the same event."""
    return "evt:" + hashlib.sha256(
        f"{job_id}|{result_revision}|{event_type}".encode()
    ).hexdigest()[:24]


def render_findings(findings: List[Dict[str, Any]],
                    item: str = "") -> str:
    """Deterministic rendering of typed findings from the structured
    record. Source identity attached (file!sheet!row is a LOCATION; the
    content hash is the version identity — both shown)."""
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
    """Remaining obligations from the structured open-work record."""
    if not remaining:
        return ""
    lines = []
    for r in remaining:
        what = str(r.get("next_action") or r.get("question") or "?")
        lines.append(f"- {what}")
    return "Still needed:\n" + "\n".join(lines)


def render_job_result(task_record: Optional[Dict[str, Any]],
                       job_id: str) -> str:
    """The terminal rendering: findings from the authoritative
    operation's execution facts + remaining obligations from open work.
    A failed read stays failed; partial findings are delivered with
    their actual scope visible."""
    if task_record is None:
        return f"Job {job_id[:12]}: no record found."
    findings: List[Dict[str, Any]] = []
    item = ""
    for op in task_record.get("operations") or []:
        facts = op.get("execution") or {}
        for f in facts.get("findings") or []:
            findings.append(f)
        if not item and facts.get("items"):
            item = str(list(facts["items"].keys())[0])
    from core.task_lifecycle import next_unfinished_work
    work = next_unfinished_work(task_record)
    remaining = [
        {"next_action": a.get("next_action"),
         "question": a.get("question")}
        for a in (work or {}).get("actions") or []]
    parts = []
    if findings:
        parts.append(render_findings(findings, item))
    if remaining:
        parts.append(render_remaining(remaining))
    if not parts:
        parts.append(
            f"Job {job_id[:12]}: no findings recorded and no remaining "
            "work listed — the job may have ended without evidence.")
    status = str(task_record.get("status") or "")
    if status in ("completed", "achieved"):
        parts.append("Status: completed.")
    elif status in ("cancelled", "failed"):
        parts.append(f"Status: {status}.")
    elif remaining or findings:
        parts.append("Status: partial — findings above are what was "
                     "established; the remaining items are listed."
                     if remaining else
                     "Status: partial — findings above are what was "
                     "established so far.")
    return "\n\n".join(parts)


def render_acknowledgement(job_id: str, item: str,
                           pending_actions: int) -> str:
    """The staged acknowledgement: describes the ACTUAL durable job."""
    what = (f"investigating '{item}'" if item else "the requested work")
    return (
        f"Started {what}. The work is saved on the job "
        f"({job_id[:12]}) — I'll report the findings here when they're "
        f"ready. {pending_actions} step(s) queued."
        if pending_actions else
        f"Started {what}. The work is saved on the job "
        f"({job_id[:12]}) — findings will follow.")
