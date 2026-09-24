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
import uuid
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
# Outbound/mutation verbs that disqualify a same-file turn from being the
# recovered READ objective — an approval of "email me the price list" must
# never execute a workbook read instead.
_OUTBOUND_ACTION_RE = re.compile(
    r"\b(?:send|email|forward|upload|attach)\b",
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
# Continuation fillers a lineage turn may carry without becoming new work
# ("find its prices and let me know"): pronouns, delivery verbs, and
# politeness that never name the work itself.
_CONTINUATION_VOCABULARY = _CONFIRMATION_VOCABULARY | {
    "let", "know", "tell", "show", "give", "still", "also", "just",
    "then", "them", "they", "there", "here", "again", "more", "all",
    "any", "get", "need", "want", "see",
}
# Verbs that ARE the retry operation itself — a confirmation/retry-classified
# turn may carry them without naming new work ("try the file search again").
# New NOUNS beyond these ("revision history", "quantities") are the turn's
# own work even when the loose retry regex classified it lineage-shaped.
_RETRY_LINEAGE_VOCABULARY = {
    "check", "try", "retry", "verify", "excel", "re", "run", "recheck",
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


# An explicit RE-RETRIEVAL request ("search the file again", "refresh",
# "check the latest version") — a different instruction from an approval:
# a completed read is RE-RUN with freshness reported, never answered from
# the cached copy.
_REFRESH_RE = re.compile(
    r"\b(?:re-?run|re-?read|re-?retrieve|re-?scan|re-?check|re-?fetch|"
    r"refresh|latest|newest|up-?to-?date|updated?|current\s+version)\b"
    r"|\b(?:check|search|read|look|pull|fetch|scan)\s+"
    r"[^\n]{0,40}\bagain\b",
    re.IGNORECASE,
)


def is_retrieval_refresh_request(message: str) -> bool:
    """An explicit request to RUN the lookup again / fetch fresh data —
    as opposed to an approval ("go ahead"), which may re-deliver an
    already completed result (2026-09-24 review: cached re-delivery and
    retrying retrieval are different operations)."""
    t = (message or "").strip()
    if not t:
        return False
    return bool(_FILE_RETRY_RE.search(t) or _REFRESH_RE.search(t))


def _canon(value: str) -> str:
    return re.sub(r"[\s_\-]+", "", (value or "").strip().lower())


def build_pending_task(
    message: str,
    mention: str,
    disambiguation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Store the ask that did not get its lookup, so a later confirmation
    can resume it verbatim. Lifecycle: ``pending`` -> ``retrieved`` ->
    ``delivered``. A lookup that ran but failed, hit a search miss, or
    returned only metadata leaves the task pending (``attempts``
    incremented, whatever file identity was resolved retained in
    ``resolved_file`` — identity and completion are tracked separately)."""
    now = time.time()
    return {
        # TASK LINEAGE (2026-09-24 review): confirmations and retries attach
        # to the SAME task id (merge preserves it); only a genuinely new
        # objective builds a new task. Recovery records which legacy origin
        # it reconstructed in ``recovered_from``.
        "task_id": uuid.uuid4().hex,
        "mention": (mention or "").strip().lower(),
        "original_message": message or "",
        "status": "pending",
        "attempts": 0,
        "resolved_file": None,
        "created_at": now,
        "updated_at": now,
        **({"disambiguation": dict(disambiguation)} if disambiguation else {}),
    }


def mark_task_retrieved(
    task: Optional[Dict[str, Any]],
    resolved_file: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Retrieval COMPLETED (structured results exist and are persisted) —
    but the answer has not necessarily REACHED the user yet (2026-09-24
    review: distinguish retrieval completion from answer delivery). A
    retrieved task is not re-read; the delivery path re-renders the
    persisted result."""
    retrieved = dict(task or build_pending_task("", ""))
    retrieved["status"] = "retrieved"
    if resolved_file:
        retrieved["resolved_file"] = resolved_file
    retrieved["retrieved_at"] = time.time()
    retrieved["updated_at"] = time.time()
    return retrieved


def mark_task_delivered(task: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The persisted result was rendered into a response that reached the
    user. Terminal state (a new substantive file ask starts a new task)."""
    delivered = dict(task or build_pending_task("", ""))
    delivered["status"] = "delivered"
    delivered["delivered_at"] = time.time()
    delivered["updated_at"] = time.time()
    return delivered


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
    existing: Optional[Dict[str, Any]],
    message: str,
    mention: str,
    disambiguation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Update the stored task for THIS turn. A confirmation refreshing the
    stored task keeps the ORIGINAL ask (a confirmation is not a new
    request) and counts the attempt; a substantive file ask replaces the
    task wholesale. A terminal task is never refreshed by a confirmation —
    its ask was answered; only a new substantive ask starts a new task.
    EXCEPTION (2026-09-24 review): an explicit re-retrieval request
    revives even a terminal task for a fresh read — the ORIGINAL ask and
    its source constraints are retained (a refresh is not a new
    objective), the attempt is counted, and the revival is stamped."""
    refresh = is_retrieval_refresh_request(message)
    was_terminal = isinstance(existing, dict) and existing.get(
        "status") in ("served", "retrieved", "delivered")
    if (isinstance(existing, dict) and existing.get("original_message")
            and (existing.get("status") not in ("served", "retrieved",
                                                "delivered") or refresh)
            and (is_filename_confirmation(message) or refresh)):
        merged = dict(existing)
        new_mention = (mention or "").strip().lower()
        if new_mention:
            merged["confirmed_mention"] = new_mention
        if disambiguation and not merged.get("disambiguation"):
            merged["disambiguation"] = dict(disambiguation)
        merged["attempts"] = int(merged.get("attempts") or 0) + 1
        merged["updated_at"] = time.time()
        if refresh:
            merged["refreshed"] = True
            merged["refreshed_at"] = time.time()
            if was_terminal:
                # Re-opening an answered ask for a FRESH read: back to
                # pending until the new retrieval completes.
                merged["status"] = "pending"
        return merged
    return build_pending_task(message, mention, disambiguation)


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


def _introduces_new_work(
    turn_text: str,
    original_message: str,
    mentions: Optional[List[str]] = None,
    extra_anchor: Optional[set] = None,
) -> bool:
    """Whether a turn requests DIFFERENT work than the stored objective
    (2026-09-24 review: "find its prices", "check its revision history",
    and "compare its quantities" can name ONE file while requesting
    different work — same file does not mean same task).

    Lineage is preserved only when the turn CONTINUES or REFINES the
    objective: confirmation wording ("... is correct"), or at most one
    content word the ask does not already carry beyond continuation
    fillers ("find its prices", "and let me know"). Two or more new
    content words are the turn's own work — a new task. Mention spans are
    stripped first: a filename that CONTAINS work words ("price list") is
    the subject, not the work. ``extra_anchor`` adds the retry-operation
    vocabulary used when judging a confirmation/retry-classified turn.
    """
    stripped = _strip_mentions(turn_text, mentions)
    if _CONFIRMATION_WORD_RE.search(stripped):
        return False
    anchor = (
        set(_content_words(original_message or ""))
        | _CONTINUATION_VOCABULARY
        | (extra_anchor or set())
    )
    new_words = set(_content_words(stripped)) - anchor
    return len(new_words) >= 2


def _same_file_identity(a: str, b: str) -> bool:
    """Whether two file mentions name the SAME file strongly enough to
    count as one task's lineage — exact/normalized/containment tiers only
    (a shared bare token is too weak: two price lists both contain
    'prices')."""
    try:
        from core.agent_file_context import (
            MATCH_TIER_CONTAINMENT,
            MATCH_TIER_EXACT,
            MATCH_TIER_NORMALIZED,
            score_file_match,
        )

        return score_file_match(a, b) in (
            MATCH_TIER_EXACT, MATCH_TIER_NORMALIZED, MATCH_TIER_CONTAINMENT,
        )
    except Exception:  # noqa: BLE001 — pure helper, belt-only
        return _canon(a) == _canon(b)


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

    History lineage (2026-09-24, task-continuity regression): turns that
    are themselves confirmation/retry-shaped — or that restate the SAME
    work on the same file — belong to this task, never supersede it (live:
    the filename confirmation "Consolidated Price List 2019.xlsx is
    correct" classifies substantive, and the text-equality check then
    broke the match even with state stored). Same file does NOT always
    mean same task: a same-file turn carrying its own work ("check its
    revision history", "compare its quantities") supersedes. Only an
    explicit re-retrieval request ("search again", "check the latest
    version") matches a terminal task — to RE-RUN the read; a bare
    approval re-delivers the persisted result instead (the delivery path).
    """
    if not isinstance(pending, dict):
        return None
    mention = str(pending.get("mention") or "").strip()
    original = str(pending.get("original_message") or "").strip()
    if not mention or not original:
        return None
    refresh = is_retrieval_refresh_request(message)
    if pending.get("status") in ("served", "retrieved", "delivered"):
        if not refresh:
            # served/delivered: answered — a later bare "yes" must not
            # resurrect it (the DELIVERY path re-renders the persisted
            # result). retrieved: same — the delivery path owns it.
            return None
        # An explicit refresh RE-RUNS the read: live intent, exempt from
        # the TTL below (bounded by the loader's newest-row window).
    else:
        try:
            created = float(pending.get("created_at") or 0)
        except (TypeError, ValueError):
            return None
        if not refresh and time.time() - created > _PENDING_FILE_TASK_TTL_SECONDS:
            return None
    if not (is_filename_confirmation(message) or refresh):
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
    if refresh:
        # An explicit re-retrieval continues THIS task (the mention
        # agreement above is the identity check) — no lineage scan: the
        # message names the operation, not a new objective.
        return pending
    if history:
        try:
            from core.plan_relevance import _is_substantive_request

            for entry in reversed(history[-12:]):
                user_text = str((entry or {}).get("message") or "").strip()
                if not user_text:
                    continue
                if _same_ask(user_text, original):
                    # The ask itself is the newest decisive turn — the
                    # confirmation confirms exactly what the history shows.
                    return pending
                entry_mentions = detect_file_task_mentions(user_text)
                if is_filename_confirmation(user_text):
                    if _introduces_new_work(
                            user_text, original, entry_mentions,
                            extra_anchor=_RETRY_LINEAGE_VOCABULARY):
                        # Retry/confirmation-SHAPED, but the turn names its
                        # own new work ("check the revision history of the
                        # file" — the loose action+file retry pattern can
                        # classify it lineage): a new task superseded this
                        # one.
                        return None
                    # The task's own lineage: a retry/confirmation never
                    # supersedes the ask it continues.
                    continue
                if entry_mentions:
                    if not any(
                        _same_file_identity(m, mention)
                        for m in entry_mentions
                    ):
                        return None  # a different file's ask supersedes
                    if _introduces_new_work(
                            user_text, original, entry_mentions):
                        # Same file, DIFFERENT work ("check its revision
                        # history", "compare its quantities") — a new task
                        # superseded this one; the approval must not reach
                        # back over it.
                        return None
                    # Same-file continuation/refinement — lineage, keep
                    # scanning.
                    continue
                if user_text and _is_substantive_request(user_text):
                    if not _introduces_new_work(user_text, original):
                        # A pronoun-led continuation ("find its prices and
                        # let me know") refines THIS objective — lineage.
                        continue
                    # An unrelated substantive exchange is newer than the
                    # stored ask — the confirmation must not reach over it.
                    return None
        except Exception as e:  # noqa: BLE001 — resume is best-effort
            logger.debug(f"pending file task: history check skipped: {e}")
    return pending


# A SEEK-shaped turn names what to locate with a verb or question word —
# deliberately NARROWER than the reply layer's read-shape regex: words that
# occur inside filenames ("price list", "is the file correct") must not
# qualify a turn as the objective (live 2026-09-24: the confirmation
# "Consolidated Price List 2019.xlsx is correct" contains "price" and would
# otherwise out-rank the real ask).
_SEEK_SHAPE_RE = re.compile(
    r"\b(?:find|search|look\s?up|lookup|check|show|list|pull|read|"
    r"fetch|locate|compare|how\s+much|what|which|where)\b",
    re.IGNORECASE,
)

# A reply that COMMITS to work that has not started ("I'll search for it
# now") — honest-status gate: a turn with an outstanding file task that
# executed no lookup must answer with the blocker, not a promise.
_PROMISE_NO_EXECUTION_RE = re.compile(
    r"\b(?:i'?ll|i\s+will|let\s+me|going\s+to|i'?m)\b[^\n]{0,60}"
    r"\b(?:search|look|read|check|pull|fetch|find|scan|query|open)\b"
    r"|\b(?:searching|looking|checking|reading|scanning)\s+(?:now|for[^\n]{0,40})\b"
    r"|^(?:searching|on\s+it|working\s+on\s+it)\b[^\n]{0,40}\bnow\b",
    re.IGNORECASE,
)

#: How far back recovery looks — the same bounded window the matcher uses.
_RECOVERY_WINDOW = 12


def _strip_mentions(
    text: str, mentions: Optional[List[str]]
) -> str:
    """The text with detected file mentions blanked out, so vocabulary that
    lives INSIDE a filename cannot classify the turn."""
    stripped = text or ""
    for m in (mentions or []):
        try:
            stripped = re.sub(re.escape(m), " ", stripped, flags=re.IGNORECASE)
        except Exception:  # noqa: BLE001 — pure helper
            continue
    return stripped


def _seek_shaped(text: str, mentions: Optional[List[str]] = None) -> bool:
    """SEEK shape judged on the text with the file mentions BLANKED OUT —
    seek vocabulary inside a filename ("price **list**", "search
    **guide**.xlsx") must not qualify the turn (live 2026-09-24: the
    confirmation 'Consolidated Price List 2019.xlsx is correct' carries
    'list' and otherwise out-ranks the real ask)."""
    return bool(_SEEK_SHAPE_RE.search(_strip_mentions(text, mentions)))


def pending_task_is_recoverable(stored: Optional[Any]) -> bool:
    """Whether history recovery may run for this conversation: only when
    nothing was ever ANSWERED. A terminal task (served/retrieved/delivered)
    stays retired — its result is re-delivered by the delivery path, never
    re-derived by recovery (the restart loader refuses the same
    resurrection)."""
    if not isinstance(stored, dict):
        return True  # no state at all — the legacy-conversation case
    return (stored.get("status") or "pending") == "pending"


def recover_pending_task_from_history(
    history: Optional[List[Dict[str, Any]]],
    message: str = "",
) -> Optional[Dict[str, Any]]:
    """Reconstruct the latest UNRESOLVED file-read objective from the
    conversation itself (2026-09-24 legacy migration, task-continuity
    regression).

    A conversation that predates the pending-task store has NO stored
    task, so a retry ("try excel file search again") or a bare approval
    ("go ahead") has nothing to resume — live, the retry then promised a
    search and executed nothing, and the next "go ahead" was answered
    from the open email canvas: the wrong task, substitution instead of
    retrieval.

    Scan newest -> oldest within the same bounded window the matcher
    uses:
    - confirmation/retry turns belong to the task's lineage; the file
      identity they confirm is harvested (the newest specific name wins);
    - the newest substantive, SEEK-shaped turn naming a compatible file
      is the objective — recovered verbatim;
    - a substantive turn with an outbound-action shape refuses recovery
      (the approval may belong to an action, not a read); a substantive
      turn naming a DIFFERENT file supersedes; a substantive turn with
      its own non-file subject ends the scan unless the current message
      is itself an explicit file retry re-pointing at the earlier ask.

    Returns the recovered task (never raises). The caller persists it on
    the session so the existing resume path executes it exactly like a
    just-stored task.
    """
    try:
        from core.agent_file_context import detect_file_task_mentions
        from core.plan_relevance import _is_substantive_request

        confirmed_mentions: List[str] = []
        for entry in reversed((history or [])[-_RECOVERY_WINDOW:]):
            text = str((entry or {}).get("message") or "").strip()
            if not text:
                continue
            mentions = detect_file_task_mentions(text)
            if is_filename_confirmation(text):
                for m in mentions:
                    if m not in confirmed_mentions:
                        confirmed_mentions.append(m)
                if not _introduces_new_work(
                        text, "", mentions,
                        extra_anchor=_RETRY_LINEAGE_VOCABULARY):
                    continue
                # Confirmation/retry-SHAPED but carrying its own work
                # ("check the revision history of the file"): this is the
                # newest objective — fall through and evaluate it as one.
            if mentions and confirmed_mentions and not any(
                _same_file_identity(m, c)
                for m in mentions for c in confirmed_mentions
            ):
                return None  # a different file's objective — superseded
            substantive = _is_substantive_request(text)
            if not substantive:
                continue
            if mentions and not confirmed_mentions:
                confirmed_mentions = list(mentions)
            if not confirmed_mentions:
                if _FILE_RETRY_RE.search(message or ""):
                    # An explicit file retry re-points at the earlier ask
                    # across an intervening unrelated objective.
                    continue
                # A bare approval belongs to THIS objective (not a file
                # read) — the normal flows own it; recovery stays out.
                return None
            _actionless = _strip_mentions(text, mentions)
            if (_CONFIRMATION_ACTION_RE.search(_actionless)
                    or _OUTBOUND_ACTION_RE.search(_actionless)):
                # Same file, but the turn asks to DO something with it
                # (send/update/replace): guessing a read underneath an
                # action is exactly the substitution this module exists
                # to prevent — the normal flows own the approval.
                return None
            if not _seek_shaped(text, mentions):
                if _OUTBOUND_ACTION_RE.search(text):
                    # No seek verb, and an outbound verb the stripping
                    # swallowed (a prose-prefixed mention span can hide
                    # it, live: "email me the <file>"): treat as the
                    # action it names. A false refusal only falls back
                    # to the normal flows; a false recovery would
                    # substitute tasks.
                    return None
                # A same-file restatement/confirmation — lineage, not a
                # new objective; keep scanning for the seek-shaped ask.
                continue
            # The objective: prefer the most specific confirmed identity
            # (a later "Consolidated Price List 2019.xlsx is correct"
            # refines the ask's own extensionless "price list 2019").
            mention = max(
                confirmed_mentions,
                key=lambda m: (len(_canon(m)), _canon(m)),
            )
            task = build_pending_task(text, mention)
            task["recovered"] = True
            task["recovered_at"] = time.time()
            task["recovered_via"] = (message or "")[:160]
            return task
    except Exception as e:  # noqa: BLE001 — recovery is best-effort
        logger.debug(f"pending file task: history recovery skipped: {e}")
    return None


def reply_promises_unrun_lookup(text: str) -> bool:
    """Whether a reply COMMITS to a search/lookup as future or just-started
    work ("I'll search for the file now"). Used as the honest-status gate on
    turns where an outstanding file task exists but no lookup executed:
    progress requires a started operation."""
    if not text:
        return False
    return bool(_PROMISE_NO_EXECUTION_RE.search(text))
