"""Source-authority derivation for research turns.

The accepted request/task owns its source requirements. Teaching can add a
source obligation only when an applicable, own lesson explicitly instructs the
agent to consult that source. A service merely being mentioned in a retrieved
lesson is not authority to require it.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

_DATASET_WORD = re.compile(
    r"\b(?:workbook|price\s+lists?|spreadsheet|xlsx?|xlsm|csv|workdrive)\b",
    re.IGNORECASE,
)
_OUTLOOK_WORD = re.compile(
    r"\b(?:e-?mails?|outlook|inbox|attachments?|threads?|correspondence)\b",
    re.IGNORECASE,
)
_DOCUMENT_WORD = re.compile(
    r"\b(?:documents?|docs?|pdfs?|docx?|word\s+files?)\b",
    re.IGNORECASE,
)
_AFFIRMATIVE_VERB = re.compile(
    r"\b(?:check|search|read|review|verify|consult|include|use|rely\s+on|"
    r"look\s+(?:at|through|for)|scan|pull|fetch|compare|cross[- ]?check|"
    r"find|locate|gather|reconcile|match)\b",
    re.IGNORECASE,
)
_NEGATED_OR_OUTBOUND = re.compile(
    r"\b(?:do\s+not|don't|never|without|avoid|no|send|draft|reply|forward)\b"
    r"[^.!?;\n]{0,60}$",
    re.IGNORECASE,
)
# Explicit exclusion of a source ("check the email; do not use the workbook").
_SOURCE_EXCLUDED = re.compile(
    r"\b(?:do\s+not|don't|never|without|avoid|no|not)\s+"
    r"(?:use|check|read|include|consult|look\s+at|rely\s+on)\b"
    r"[^.!?;\n]{0,50}$",
    re.IGNORECASE,
)
_SOURCE_NAMES = {
    "email": "outlook",
    "e-mail": "outlook",
    "mail": "outlook",
    "outlook": "outlook",
    "inbox": "outlook",
    "attachment": "outlook",
    "attachments": "outlook",
    "thread": "outlook",
    "threads": "outlook",
    "correspondence": "outlook",
    "workbook": "datasets",
    "spreadsheet": "datasets",
    "xlsx": "datasets",
    "xls": "datasets",
    "xlsm": "datasets",
    "csv": "datasets",
    "datasets": "datasets",
    "documents": "documents",
}


def _normal_service(value: Any) -> str:
    text = str(value or "").strip().lower()
    return _SOURCE_NAMES.get(text, text)


def _explicit_mention(text: str, pattern: re.Pattern) -> bool:
    """A source word with an affirmative research verb, not negation/outbound."""
    for match in pattern.finditer(text or ""):
        prefix = (text or "")[max(0, match.start() - 100):match.start()]
        if _NEGATED_OR_OUTBOUND.search(prefix):
            continue
        if _AFFIRMATIVE_VERB.search(prefix):
            return True
    return False


def _excluded_mention(text: str, pattern: re.Pattern) -> bool:
    """Whether the source word is explicitly excluded by the request."""
    for match in pattern.finditer(text or ""):
        prefix = (text or "")[max(0, match.start() - 100):match.start()]
        if _SOURCE_EXCLUDED.search(prefix):
            return True
    return False


def _task_source_values(task: Optional[Dict[str, Any]]) -> List[Any]:
    if not isinstance(task, dict):
        return []
    out: List[Any] = []
    for key in ("source_requirements", "required_sources"):
        value = task.get(key)
        if isinstance(value, dict):
            out.extend(k for k, v in value.items() if v)
        elif isinstance(value, (list, tuple, set)):
            out.extend(value)
        elif isinstance(value, str) and value.strip():
            out.append(value)
    program = task.get("turn_program")
    if isinstance(program, dict):
        value = program.get("source_requirements")
        if isinstance(value, dict):
            out.extend(k for k, v in value.items() if v)
        elif isinstance(value, (list, tuple, set)):
            out.extend(value)
        elif isinstance(value, str) and value.strip():
            out.append(value)
    return out


def attach_source_requirements(
    task: Optional[Dict[str, Any]],
    diagnostic: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Persist the accepted source obligation on the task that owns it.

    Later confirmation/recovery turns read this instead of re-deriving an
    obligation from whatever text happens to be in front of them.
    """
    if not isinstance(task, dict):
        return task
    sources = [
        str(service) for service in ((diagnostic or {}).get("sources") or [])
        if str(service).strip()
    ]
    # A transient derivation failure must not erase an obligation the accepted
    # task already owns. Only a successful derivation may replace the set.
    if not sources and task.get("source_requirements"):
        return task
    task["source_requirements"] = sources
    task["source_requirement_evidence"] = [
        {
            "kind": item.get("kind"),
            "source": item.get("source"),
            "lesson_id": item.get("lesson_id"),
            "topic": item.get("topic"),
            "scope": item.get("scope"),
            "goal_id": item.get("goal_id"),
            "reason": item.get("reason"),
        }
        for item in ((diagnostic or {}).get("evidence") or [])
        if isinstance(item, dict)
    ]
    return task


def derive_required_research_sources(
    *,
    message: str,
    lessons: Optional[Iterable[Dict[str, Any]]] = None,
    accepted_task: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return required sources plus attributable evidence.

    ``sources`` is ordered deterministically (datasets, documents, outlook).
    ``lesson_candidates`` records every own/global lesson that mentions a
    source word; only explicit affirmative instructions are accepted.
    """
    required = set()
    evidence: List[Dict[str, Any]] = []
    message_sources: List[str] = []

    if (
        _DATASET_WORD.search(message or "")
        and not _excluded_mention(message or "", _DATASET_WORD)
    ):
        required.add("datasets")
        message_sources.append("datasets")
        evidence.append({
            "kind": "message",
            "source": "datasets",
            "reason": "request names a workbook/spreadsheet source",
        })
    if (
        _DOCUMENT_WORD.search(message or "")
        and not _excluded_mention(message or "", _DOCUMENT_WORD)
    ):
        required.add("documents")
        message_sources.append("documents")
        evidence.append({
            "kind": "message",
            "source": "documents",
            "reason": "request names a document source",
        })
    if _explicit_mention(message or "", _OUTLOOK_WORD):
        required.add("outlook")
        message_sources.append("outlook")
        evidence.append({
            "kind": "message",
            "source": "outlook",
            "reason": "request explicitly asks to consult correspondence",
        })

    task_sources: List[str] = []
    for raw in _task_source_values(accepted_task):
        service = _normal_service(raw)
        if service in ("datasets", "documents", "outlook"):
            task_sources.append(service)
            required.add(service)
            evidence.append({
                "kind": "accepted_task",
                "source": service,
                "reason": "accepted task declares this source requirement",
            })

    lesson_candidates: List[Dict[str, Any]] = []
    for lesson in (lessons or []):
        if not isinstance(lesson, dict):
            continue
        text = " ".join(str(
            lesson.get("lesson") or lesson.get("summary") or "").split())
        if not text:
            continue
        identity = {
            "lesson_id": lesson.get("id"),
            "topic": lesson.get("topic"),
            "scope": lesson.get("scope") or "global",
            "goal_id": lesson.get("goal_id"),
            "source_agent_id": lesson.get("_source_agent_id"),
        }
        # Sibling lessons are knowledge, not authority over THIS task's
        # source obligations. They are still RECORDED so the diagnostic can
        # name exactly which lesson's mention was considered and rejected.
        sibling = bool(lesson.get("_source_agent_id"))
        for service, pattern in (
            ("datasets", _DATASET_WORD),
            ("documents", _DOCUMENT_WORD),
            ("outlook", _OUTLOOK_WORD),
        ):
            if not pattern.search(text):
                continue
            if sibling:
                accepted = False
                reason = (
                    "sibling lesson is not source authority for this task")
            else:
                accepted = _explicit_mention(text, pattern)
                reason = (
                    "explicit affirmative source instruction"
                    if accepted else
                    "source mention without an affirmative research instruction")
            lesson_candidates.append({
                **identity,
                "source": service,
                "accepted": accepted,
                "reason": reason,
            })
            if accepted:
                required.add(service)
                evidence.append({
                    "kind": "lesson",
                    "source": service,
                    **identity,
                    "reason": "applicable own lesson explicitly requires the source",
                })

    ordered = [
        service for service in ("datasets", "documents", "outlook")
        if service in required
    ]
    return {
        "sources": ordered,
        "evidence": evidence,
        "message_sources": message_sources,
        "task_sources": task_sources,
        "lesson_candidates": lesson_candidates,
    }
