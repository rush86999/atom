"""Pending file task — a file-scoped ask whose lookup never ran, kept
across turns so the user's CONFIRMATION resumes it.

Live incident (2026-09-23): the user asked for eight machine prices in
"Consolidated Price List 2019.xlsx" (Zoho WorkDrive). The tool planner
timed out behind the canvas-edit leg, so no lookup ran; the answer came
from September-2026 email prices instead. The user then confirmed the
filename ("That filename is correct") — and the turn was planned as small
talk: the planner declined ("No live lookup needed"), because a bare
confirmation names nothing to look up. The requested read died with the
turn.

This module is the session-keyed bridge between those turns:

- turn N asks about a file and no live lookup serves it  -> the ask is
  stored on the session (``FILE_TASK_SESSION_KEY``) by the reply leg;
- turn N+1 is a filename CONFIRMATION                     -> the stored
  ask is resumed: the planner plans the ORIGINAL request, and the
  relevance gate judges the plan against it.

A confirmation is deliberately narrow: an approval phrase, or a
back-reference to the file/name plus a confirmation word. A message with
its own subject ("correct the typo in the draft") is a new request, not a
confirmation, and never resumes anything.
"""
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Session-dict key for the stored pending task (JSON-serializable value;
#: sessions persist to chat_sessions*.json, so the task survives restarts).
FILE_TASK_SESSION_KEY = "_pending_file_task"

#: How long a stored ask stays resumable (seconds; env-overridable).
_PENDING_FILE_TASK_TTL_SECONDS = float(
    os.getenv("ATOM_PENDING_FILE_TASK_TTL_SECONDS", "21600") or 21600)

# A confirmation phrase anywhere in the message, or the entire message is
# just a confirmation word ("correct.", "exactly.").
_CONFIRMATION_PHRASE_RE = re.compile(
    r"\b(?:yes|yeah|yep|yup|sure|ok|okay|go ahead|proceed|please do|"
    r"do it|confirmed|that works|sounds good)\b",
    re.IGNORECASE,
)
_BARE_CONFIRMATION_RE = re.compile(
    r"^\s*(?:correct|right|exactly|confirmed|perfect|go)\s*[.!]?\s*$",
    re.IGNORECASE,
)
# An explicit back-reference to the file the user was asked about:
# "that filename is correct", "that's the one", "the file name is right".
_FILE_BACKREF_RE = re.compile(
    r"\b(?:that|this|the)\s+(?:file\s*name|filename|file|name|workbook|"
    r"spreadsheet|sheet|document|price\s*list|list|one)\b"
    r"|\bthat'?s\s+(?:the\s+one|correct|right|it)\b"
    r"|\bfilename\s+is\s+(?:correct|right)\b"
    r"|\bfile\s+name\s+is\s+(?:correct|right)\b",
    re.IGNORECASE,
)
_FILE_RETRY_RE = re.compile(
    r"\b(?:read|open|search|look\s*up|check|retry|try)\b"
    r"[^\n]{0,80}\b(?:again|file|workbook|spreadsheet|sheet|filename)\b|"
    r"\b(?:read|open)\s+[^,.;?!]{1,80}\.(?:xlsx|xls|csv|tsv|pdf|docx?)\b",
    re.IGNORECASE,
)
_CONFIRMATION_ACTION_RE = re.compile(
    r"\b(?:send|export|share|post|publish|submit|schedule|ship|"
    r"update|replace|delete|edit)\b",
    re.IGNORECASE,
)
_CONFIRMATION_WORD_RE = re.compile(
    r"\b(?:correct|right|exact|exactly|confirmed|yes|yeah|one)\b",
    re.IGNORECASE,
)
# Vocabulary a confirmation may carry beyond its confirmation words; more
# than two OTHER content words means the message has its own subject.
_CONFIRMATION_VOCABULARY = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "go", "ahead",
    "proceed", "please", "do", "it", "did", "correct", "right", "exact",
    "exactly", "confirmed", "that", "this", "the", "is", "was", "one",
    "filename", "file", "name", "workbook", "spreadsheet", "sheet",
    "document", "list", "price", "it", "its", "and", "you", "can", "now",
    "search", "read", "open", "lookup", "look", "up", "go", "with", "to",
    "sounds", "good", "great", "works", "perfect", "thanks", "thank",
}
_WORD_RE = re.compile(r"[a-z0-9']+")


def _content_words(text: str) -> List[str]:
    return [
        re.sub(r"'s$", "", w) for w in _WORD_RE.findall((text or "").lower())
    ]


def _mention_words(message: str) -> set:
    """Tokens of any filename the message itself names — a confirmation may
    RESTATE the filename ("yes, Consolidated Price List 2019.xlsx is
    correct"), and those tokens are the confirmed subject, not a new one."""
    try:
        from core.agent_file_context import detect_file_task_mentions

        words = set()
        for m in detect_file_task_mentions(message):
            words.update(_WORD_RE.findall(m))
        return words
    except Exception:  # noqa: BLE001 — pure helper, belt-only
        return set()


def is_filename_confirmation(message: str) -> bool:
    """Is this turn a confirmation of a previously-asked file/task?

    True for approvals ("yes", "go ahead"), bare confirmation words
    ("correct."), and back-referenced confirmations ("that filename is
    correct", "yes that's the one", "yes, <filename> is correct"). False
    for anything with its own subject — questions, new requests, "correct
    the typo in the draft", "yes please search Gmail for the quotes" (an
    approval WITH its own instruction is a new request, not a resume).
    """
    t = (message or "").strip()
    if not t or "?" in t:
        return False
    if _CONFIRMATION_ACTION_RE.search(t):
        return False
    if _FILE_RETRY_RE.search(t):
        return True
    if _BARE_CONFIRMATION_RE.match(t):
        return True
    subject_words = _CONFIRMATION_VOCABULARY | _mention_words(t)

    def _others(text: str) -> List[str]:
        return [
            w for w in _content_words(text) if w not in subject_words
        ]

    if _CONFIRMATION_PHRASE_RE.search(t):
        # An approval carrying at most ONE content word of its own ("yes
        # the September one") is still an approval; two or more means the
        # turn names its own instruction.
        return len(_others(t)) <= 1
    if _FILE_BACKREF_RE.search(t) and _CONFIRMATION_WORD_RE.search(t):
        return len(_others(t)) <= 2
    return False


def _canon(value: str) -> str:
    return re.sub(r"[\s_\-]+", "", (value or "").strip().lower())


def build_pending_task(message: str, mention: str) -> Dict[str, Any]:
    """Store the ask that did not get its lookup, so a later confirmation
    can resume it verbatim. Lifecycle: ``pending`` -> ``served`` — and only
    a COMPLETED read serves it. A lookup that ran but failed, hit a search
    miss, or returned only metadata leaves the task pending (``attempts``
    incremented, whatever file identity was resolved retained in
    ``resolved_file`` — identity and completion are tracked separately)."""
    now = time.time()
    return {
        "mention": (mention or "").strip().lower(),
        "original_message": message or "",
        "status": "pending",
        "attempts": 0,
        "resolved_file": None,
        "created_at": now,
        "updated_at": now,
    }


def mark_task_served(
    task: Optional[Dict[str, Any]],
    resolved_file: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """A completed read of the file: the ask is answered. The resolved
    identity is retained on the task for the audit trail (the chat layer
    also keeps a separate ``_resolved_file_identity`` for preview reuse)."""
    served = dict(task or build_pending_task("", ""))
    served["status"] = "served"
    if resolved_file:
        served["resolved_file"] = resolved_file
    served["updated_at"] = time.time()
    return served


def merge_pending_task(
    existing: Optional[Dict[str, Any]], message: str, mention: str,
) -> Dict[str, Any]:
    """Update the stored task for THIS turn. A confirmation refreshing the
    stored task keeps the ORIGINAL ask (a confirmation is not a new
    request) and counts the attempt; a substantive file ask replaces the
    task wholesale. A SERVED task is never refreshed by a confirmation —
    its ask was answered; only a new substantive ask starts a new task."""
    if (isinstance(existing, dict) and existing.get("original_message")
            and existing.get("status") != "served"
            and is_filename_confirmation(message)):
        merged = dict(existing)
        new_mention = (mention or "").strip().lower()
        if new_mention:
            merged["confirmed_mention"] = new_mention
        merged["attempts"] = int(merged.get("attempts") or 0) + 1
        merged["updated_at"] = time.time()
        return merged
    return build_pending_task(message, mention)


def supersedes_pending_task(pending: Optional[Any], message: str) -> bool:
    """Whether a new turn should discard a resumable file task."""
    if not isinstance(pending, dict) or not (message or "").strip():
        return False
    if is_filename_confirmation(message):
        return False
    text = (message or "").strip()
    if "?" in text:
        return False
    try:
        from core.plan_relevance import _is_substantive_request

        if _is_substantive_request(text):
            return True
    except Exception:
        pass
    return bool(re.search(
        r"\b(?:search|find|read|open|fetch|send|update|replace|"
        r"create|delete|show|list|compare|research)\b",
        text,
        re.IGNORECASE,
    ))


def _same_ask(history_user_text: str, original_message: str) -> bool:
    return _canon(history_user_text) == _canon(original_message or "")


def matching_pending_task(
    pending: Optional[Any], message: str,
    history: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """The stored task this turn's message CONFIRMS and may resume, or
    None.

    Conditions (all must hold):
    - the stored task is well-formed and inside its TTL;
    - the message is a filename confirmation (``is_filename_confirmation``);
    - if the message itself names a file, it agrees with the stored one;
    - the stored ask is still the LAST substantive request in the
      conversation — a newer request supersedes it, and the confirmation
      must not reach over it.
    """
    if not isinstance(pending, dict):
        return None
    mention = str(pending.get("mention") or "").strip()
    original = str(pending.get("original_message") or "").strip()
    if not mention or not original:
        return None
    if pending.get("status") == "served":
        # The ask was already answered by a completed read; a later bare
        # "yes" must not resurrect it.
        return None
    try:
        created = float(pending.get("created_at") or 0)
    except (TypeError, ValueError):
        return None
    if time.time() - created > _PENDING_FILE_TASK_TTL_SECONDS:
        return None
    if not is_filename_confirmation(message):
        return None
    try:
        from core.agent_file_context import detect_file_task_mentions

        msg_mentions = detect_file_task_mentions(message)
    except Exception:  # noqa: BLE001 — detector is pure, this is belt-only
        msg_mentions = []
    if msg_mentions:
        pm = _canon(mention)
        if not any(
            pm in _canon(m) or _canon(m) in pm for m in msg_mentions
        ):
            return None
    if history:
        try:
            from core.plan_relevance import _is_substantive_request

            for entry in reversed(history[-12:]):
                user_text = str((entry or {}).get("message") or "").strip()
                if user_text and _is_substantive_request(user_text):
                    return pending if _same_ask(
                        user_text, original) else None
        except Exception as e:  # noqa: BLE001 — resume is best-effort
            logger.debug(f"pending file task: history check skipped: {e}")
    return pending
