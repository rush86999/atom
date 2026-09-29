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
from typing import Any, Dict, Iterable, List, Optional

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
    r"|\bthat\s+is\s+the\s+(?:right|correct)\s+file\b"
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
    # function words and degree adverbs never name the work
    "of", "from", "in", "for", "on", "at", "by", "about", "into", "over",
    "under", "after", "before", "between", "these", "those", "their",
    "be", "been", "are", "were", "do", "does", "has", "have", "had",
    "me", "my", "our", "us", "out", "so", "if", "or", "as", "than",
    "thoroughly", "carefully", "fully", "properly", "deeply", "harder",
    "once", "please", "maybe", "perhaps", "instead", "rather", "quite",
    # articles (2026-09-29): "search again and give me a clean response"
    # — an indefinite article never names the work either
    "a", "an",
}
# Verbs that ARE the retry operation itself — a confirmation/retry-classified
# turn may carry them without naming new work ("try the file search again").
# New NOUNS beyond these ("revision history", "quantities") are the turn's
# own work even when the loose retry regex classified it lineage-shaped.
_RETRY_LINEAGE_VOCABULARY = {
    "check", "try", "retry", "verify", "excel", "re", "run", "recheck",
}
# STRUCTURED WORK SIGNATURE (2026-09-24 review round 3): task identity is
# (action group, requested objects) — not a new-word COUNT. "check
# availability" changes the objective with one new word; "search again
# more thoroughly" adds words without changing it.
_WORK_VERB_GROUPS = {
    "seek": {
        "find", "search", "look", "lookup", "check", "get", "show",
        "list", "pull", "read", "fetch", "locate", "scan", "what",
        "which", "where", "how",
    },
    "compare": {"compare", "contrast", "differentiate", "reconcile"},
    "verify": {"verify", "validate", "audit", "confirm"},
    "summarize": {"summarize", "summarise", "recap", "review", "outline"},
    "explain": {"explain", "describe"},
}
_ALL_WORK_VERBS = set().union(*_WORK_VERB_GROUPS.values())
_WORD_RE = re.compile(r"[a-z0-9']+")


def _content_words(text: str) -> List[str]:
    return [
        re.sub(r"'s$", "", w) for w in _WORD_RE.findall((text or "").lower())
    ]


def _light_stem(word: str) -> str:
    """Minimal morphology fold so 'prices'/'price' and
    'quantities'/'quantity' compare equal — NOT a real stemmer, just
    enough for object identity."""
    w = word or ""
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


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


# THREE distinct operations on a completed read (2026-09-24 review
# round 3) — re-deliver / re-run / refresh are NOT the same instruction:
# - re-deliver: return the stored result (an approval);
# - re-run: search the currently available COPY again ("search again") —
#   the materialized copy is the accepted source for that turn;
# - refresh: verify the UPSTREAM version and retrieve updated content
#   ("latest version", "refresh", "updated") — the copy alone is NOT an
#   acceptable answer without a source check; a refresh answer must
#   state its freshness verdict, never present an old copy as current.
_SOURCE_REFRESH_RE = re.compile(
    r"\b(?:latest|newest|up-?to-?date|up\s+to\s+date|updated?|"
    r"update\s+the|current\s+version|newer|refresh|"
    r"has\s+it\s+changed|changed\s+since|fresh)\b",
    re.IGNORECASE,
)
_RERUN_RE = re.compile(
    r"\b(?:re-?run|re-?read|re-?retrieve|re-?scan|re-?check|re-?fetch)\b"
    r"|\b(?:check|search|read|look|pull|fetch|scan|try)\s+"
    r"[^\n]{0,40}\bagain\b",
    re.IGNORECASE,
)


def is_source_refresh_request(message: str) -> bool:
    """A SOURCE-freshness request: the upstream version must be checked
    and updated content retrieved — stronger than re-running the copy."""
    t = (message or "").strip()
    return bool(t) and bool(_SOURCE_REFRESH_RE.search(t))


def is_rerun_request(message: str) -> bool:
    """An explicit re-run of the lookup against the currently available
    copy ("search the file again", "re-read the workbook")."""
    t = (message or "").strip()
    if not t:
        return False
    return bool(_FILE_RETRY_RE.search(t) or _RERUN_RE.search(t))


def is_retrieval_refresh_request(message: str) -> bool:
    """Any re-retrieval operation (re-run OR source refresh) — an explicit
    request to run the lookup again, as opposed to an approval ("go
    ahead"), which may re-deliver an already completed result."""
    return is_source_refresh_request(message) or is_rerun_request(message)


def classify_file_operation(message: str) -> str:
    """Which of the three operations a continuation turn asks for:
    "refresh" (source check required) wins over "re-run" (copy search);
    approvals re-deliver. Unclassified read-shaped turns are "read"."""
    t = message or ""
    if is_source_refresh_request(t):
        return "refresh"
    if is_rerun_request(t):
        return "re-run"
    if is_filename_confirmation(t):
        return "re-deliver"
    return "read"


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
    objective), the attempt is counted, and the revival is stamped.
    An EXTENDING follow-up (``request_extends_objective`` — a new source,
    changed requested information) is a new objective even when retry- or
    confirmation-shaped: it replaces the task, never merges into the old
    ask (2026-09-29 cross-source incident)."""
    refresh = is_retrieval_refresh_request(message)
    was_terminal = isinstance(existing, dict) and existing.get(
        "status") in ("served", "retrieved", "delivered")
    if (isinstance(existing, dict) and existing.get("original_message")
            and (existing.get("status") not in ("served", "retrieved",
                                                "delivered") or refresh)
            and (is_filename_confirmation(message) or refresh)
            and not request_extends_objective(message, existing)):
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
    replacement = build_pending_task(message, mention, disambiguation)
    if isinstance(existing, dict) and existing.get("task_id"):
        # CONTEXT PRESERVATION + EXECUTABLE INHERITANCE (2026-09-24
        # review round 5): a replacement records WHICH objective it
        # supersedes (audit), and INHERITS the context needed to execute
        # the new objective against the same source — the resolved
        # resource, the confirmed mention, and the disambiguation
        # constraints (unless the new ask states its own). "check
        # availability" on the same workbook executes with the same
        # resource pin and the same region/organization constraints; the
        # direct reader consumes disambiguation, so inheritance is
        # behavior, not bookkeeping.
        if existing.get("resolved_file") and not replacement.get(
                "resolved_file"):
            replacement["resolved_file"] = existing["resolved_file"]
        if existing.get("confirmed_mention") and not replacement.get(
                "confirmed_mention"):
            replacement["confirmed_mention"] = existing["confirmed_mention"]
        if existing.get("disambiguation") and not replacement.get(
                "disambiguation"):
            replacement["disambiguation"] = existing["disambiguation"]
        replacement["supersedes"] = {
            "task_id": existing.get("task_id"),
            "original_message": str(
                existing.get("original_message") or "")[:500],
            "mention": existing.get("mention"),
        }
    return replacement


def supersedes_pending_task(pending: Optional[Any], message: str) -> bool:
    """Whether a new turn should discard a resumable file task."""
    if not isinstance(pending, dict) or not (message or "").strip():
        return False
    text = (message or "").strip()
    # AN EXTENDED FOLLOW-UP IS A NEW OBJECTIVE, NOT A RETRY (2026-09-29
    # cross-source incident). "check <person>'s email and or description
    # in workbook to find correct sheet" matches the loose retry shape
    # (check … workbook … sheet) and is classified confirmation AND
    # re-run — both exemptions below would keep the stored ask alive,
    # and the resume lane would then answer the NEW request by re-running
    # the OLD read. When the turn asks for work the stored objective does
    # not cover, it supersedes here: the caller pops the task and
    # preserves its context (resource pin, constraints) for the turn's
    # own execution. Questions stay exempt (unchanged behavior).
    if "?" not in text:
        try:
            if request_extends_objective(message, pending):
                return True
        except Exception:  # noqa: BLE001 — legacy checks still decide
            pass
    if is_filename_confirmation(message):
        return False
    if is_retrieval_refresh_request(message):
        # An explicit re-run/refresh CONTINUES the task — live intent, the
        # opposite of superseding it (live 2026-09-24: "check the latest
        # version of the workbook" popped the stored ask before the
        # matcher could resume it, and the turn died in narration).
        return False
    if "?" in text:
        return False
    # AN ENTITY-SET EDIT IS LINEAGE, NOT SUPERSESSION (2026-09-27).
    # "Replace U-22 with U-38" edits the objective this task carries; it does
    # not abandon it. Popping the stored task here (chat_orchestrator.py:4230)
    # discarded the objective before anything downstream could revise it, which
    # is precisely why the turn came back with the previous list: the task that
    # held the item set had already been thrown away. The same object the user
    # is editing must survive so it can be revised in place, which is what
    # preserves item ORDER across a replacement.
    #
    # Checked before the verb scan because that scan treats "replace" as a
    # mutation verb and would otherwise discard the task for the right verb
    # applied to the wrong object.
    try:
        if entity_set_edit(message) is not None:
            return False
    except Exception:  # noqa: BLE001 — never let the guard break supersession
        pass
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


def _work_signature(
    text: str, mentions: Optional[List[str]] = None,
    extra_anchor: Optional[set] = None,
) -> "tuple[Optional[str], frozenset]":
    """The (action group, requested objects) a turn asks for — the
    structured half of task identity. Objects are mention-stripped,
    verb- and filler-free, lightly stemmed; action is the coarsest verb
    group present (seek/compare/verify/summarize/explain)."""
    stripped = _strip_mentions(text, mentions)
    fillers = _CONTINUATION_VOCABULARY | (extra_anchor or set())
    words = _content_words(stripped)
    verbs = [w for w in words if w in _ALL_WORK_VERBS]
    group = next(
        (g for g, vs in _WORK_VERB_GROUPS.items() if set(verbs) & vs),
        None,
    )
    objects = frozenset(
        _light_stem(w) for w in words
        if w not in _ALL_WORK_VERBS and w not in fillers
    )
    return group, objects


def _is_affirmation_only(text: str) -> bool:
    """Affirmative confirmation vs requested correction/verification.

    An APPROVAL PHRASE ("yes", "ok proceed", "sounds good") or a bare
    confirmation word ("correct.") carrying at most ONE content word of
    its own ("yes the September one") affirms a prior exchange. Anything
    else — no approval wording at all ("find the correct row", "check …
    for confirmation"), or an approval naming its own instruction ("yes
    please search Gmail for the quotes") — is a REQUEST, not an approval.
    Mirrors the approval-with-its-own-instruction rule in
    ``is_filename_confirmation`` (2026-09-29 cross-source incident: the
    confirmation-word bail in ``_introduces_new_work`` treated "correct
    sheet" as an approval and swallowed the whole request).
    """
    t = (text or "").strip()
    if not t:
        return False
    if not (_CONFIRMATION_PHRASE_RE.search(t)
            or _BARE_CONFIRMATION_RE.match(t)):
        return False
    subject_words = _CONFIRMATION_VOCABULARY | _mention_words(t)
    others = [w for w in _content_words(t) if w not in subject_words]
    return len(others) <= 1


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

    Compared on STRUCTURED task attributes, with lexical signals as
    support only: a NEW requested object ("availability" vs "prices", a
    changed constraint like "north region only") or a different ACTION
    group ("compare" vs "find") is a new task; verbose retries ("search
    again more thoroughly") and pronoun-led refinements ("find its
    prices") are not. AFFIRMATION wording is lineage, but only an actual
    approval (``_is_affirmation_only``) — confirmation VOCABULARY inside
    a seek-shaped request ("find the correct row", "check … for
    confirmation") is requested verification, not approval. Uncertainty
    resolves to a NEW task — the normal flows own it, and nothing is
    silently continued on a guess.
    """
    new_group, new_objects = _work_signature(
        turn_text, mentions, extra_anchor)
    old_group, old_objects = _work_signature(
        original_message or "", None, extra_anchor)
    unseen = new_objects - old_objects
    group_changed = bool(new_group and old_group and new_group != old_group)
    if not unseen and not group_changed:
        return False  # nothing beyond the stored objective — lineage
    if _is_affirmation_only(turn_text):
        return False  # approval wording, not requested work
    return True


# Retrieval-OPERATION vocabulary that rides a retry/refresh turn without
# changing the objective (2026-09-29 cross-source incident): freshness
# words ("check the latest version") and presentation/style words
# ("search again and give me a clean response") name HOW the same read is
# re-run or shown, never WHAT is asked for. Anchored as fillers for the
# CURRENT-message coverage check only (``request_extends_objective``);
# the history-lineage scans keep their narrower retry anchor.
_RETRIEVAL_OPERATION_VOCABULARY = {
    # source-freshness operation words (mirror _SOURCE_REFRESH_RE)
    "latest", "newest", "version", "versions", "updated", "update",
    "current", "newer", "refresh", "fresh", "freshest", "changed",
    "uptodate",
    # presentation/style words (mirror the NLU continuation layer's
    # _PRESENTATION_* vocabulary)
    "clean", "cleaner", "cleanest", "cleanup", "readable", "easier",
    "concise", "shorter", "brief", "briefer", "briefly", "simpler",
    "simplify", "simplified", "tidy", "tidier", "neat", "neater",
    "compact", "table", "tabular", "tabulate", "format", "formatted",
    "formatting", "style", "present", "presentation", "response",
    "summary", "summarize", "bullet", "bullets", "display",
}


def request_extends_objective(
    message: str, task: Optional[Any],
) -> bool:
    """Whether a continuation-shaped turn asks for work the stored task's
    read does NOT cover (2026-09-29 original-canvas incident).

    True means completing the CURRENT message requires more than
    re-running or re-delivering the stored read: it adds a source
    ("check <person>'s email and the workbook descriptions"), changes the
    requested information ("use the description to identify the correct
    row"), or otherwise names objects the stored objective never asked
    for. Such a turn supersedes the stored objective (context survives
    via the caller) and belongs to normal planning — deterministic
    delivery of the stored read is allowed only when this returns False.

    False for: pure/verbose retries ("search the file again"), refresh
    wording ("check the latest version"), compound retry+presentation
    ("search again and give me a clean response"), approvals ("yes the
    September one"), entity-set edits ("replace U-22 with U-38" revises
    the SAME objective), and a missing/unusable stored task. This is the
    single authoritative coverage decision — matching, supersession,
    legacy recovery, merge and the NLU continuation layer all consult it
    instead of each re-deriving a slightly different policy.
    """
    if not isinstance(task, dict):
        return False
    original = str(task.get("original_message") or "").strip()
    if not original or not (message or "").strip():
        return False
    try:
        if entity_set_edit(message) is not None:
            return False  # a revision of THIS objective, not an extension
    except Exception:  # noqa: BLE001 — fail toward "not extending"
        pass
    try:
        from core.agent_file_context import detect_file_task_mentions

        mentions = detect_file_task_mentions(message)
    except Exception:  # noqa: BLE001 — belt-only
        mentions = []
    return _introduces_new_work(
        message, original, mentions,
        extra_anchor=_RETRY_LINEAGE_VOCABULARY
        | _RETRIEVAL_OPERATION_VOCABULARY,
    )


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
    # AN ENTITY-SET EDIT NEEDS A FRESH ATTEMPT, exactly like a refresh.
    # "Replace U-22 with U-38" asks for different items, so the delivered
    # evidence cannot answer it -- and reusing that evidence is precisely the
    # defect: the previous list is what the user was shown instead. So a
    # set-edit turn is eligible to resume a terminal task for a RE-READ, the
    # same way an explicit "search again" is. It is still not a bare approval:
    # the delivery path (which re-renders the persisted result without reading)
    # is not what serves this turn, so eligibility here routes to a new attempt
    # with the edited item set, not to a re-render.
    set_edit = None
    if not refresh:
        try:
            set_edit = entity_set_edit(message)
        except Exception:  # noqa: BLE001
            set_edit = None
    if pending.get("status") in ("served", "retrieved", "delivered"):
        if not refresh and set_edit is None:
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
    if not (is_filename_confirmation(message) or refresh
            or set_edit is not None):
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
    # COVERAGE OF THE CURRENT REQUEST (2026-09-29 cross-source incident):
    # a continuation may resume the stored task only when re-running that
    # read can satisfy the WHOLE current message. A follow-up that adds a
    # source, changes the requested information, or asks to compare
    # descriptions / resolve identities does not — the refresh branch
    # below used to return the stored task before any new-work check,
    # and the orchestrator then answered "check <person>'s email and the
    # workbook descriptions" with a fresh price extraction. The stored
    # items and pins survive as context (supersession stashes them);
    # normal planning owns the turn.
    try:
        if request_extends_objective(message, pending):
            return None
    except Exception:  # noqa: BLE001 — resume eligibility is best-effort
        pass
    if refresh or set_edit is not None:
        # An explicit re-retrieval, or an entity-set edit, continues THIS task
        # (the mention agreement above is the identity check) — no lineage
        # scan: the message names the operation or edits the item list, not a
        # new objective.
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

# An objective's entity set is an EXPLICIT ENUMERATION in the ask
# ("...these 8 machines: 381, U-22, ... and U-38" or a numbered list),
# not any identifier appearing anywhere in a same-file message (2026-09-25
# review: unioning same-file mentions mixes superseded asks, and user
# messages are NOT clean by construction — this conversation carries
# pasted prices and delivery terms).
# SEPARATORS NEVER SPLIT DECIMAL AMOUNTS: a comma between digits
# ("$2,902.00") is a thousands separator — splitting on bare ',' made
# '902.00' a standalone entity (2026-09-25 review round 4). Newlines
# separate numbered/bulleted list items.
_ENUMERATION_SPLIT_RE = re.compile(r",(?!\d)|;|\s+and\s+|\s+&\s+|\n")
_LIST_LINE_RE = re.compile(r"^\s*(?:\d+[.)]|[-•*])\s+(.{3,80})$")
# Cut an enumerated item at a value/delivery/correction tail: spaced dash
# (" — "), currency (with its decimal tail), bare-number+unit run, or a
# negation correction ("…No. 381 (not 0381)"). UNspaced hyphens stay —
# model syntax (SLE24-16, U-22).
_ITEM_TAIL_RE = re.compile(
    r"\s+[-–—]\s+|[$€£¥₹]\s*\d|[$€£¥₹]|\b(?:CAD|USD)\b"
    r"|\b\d[\d,]*\.\d{2}\b|\b\d+\s+(?:weeks?|days?|months?)\b"
    r"|\s*\(?\b(?:not|formerly)\b[^)]*\)?",
    re.IGNORECASE,
)
# A REMOVAL item never enters the objective set ("drop U-38", "not
# 0381"). 'No.' is NUMERO, never negation — "No. 381" must survive.
_ITEM_NEGATION_RE = re.compile(
    r"^\s*(?:not|without|drop|remove|minus|exclude|except|skip)\b"
    r"[\s:,]*|^\s*no\b(?![.\d])[\s:,]*",
    re.IGNORECASE,
)
# Items that are pure value/attribute noise after tail-cutting.
_ITEM_JUNK = {
    "cad", "usd", "tbd", "each", "in stock", "stock", "units", "total",
    "and", "tax", "taxes", "valid", "quote",
}
_ADDITION_RE = re.compile(
    r"^\s*(?:also|and|add|plus|include|including)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# ENTITY-SET EDITS ("replace U-22 with U-38", "drop No. 622", "add U-38")
#
# WHY THIS EXISTS. The active objective's item set had exactly two operators:
# "the turn's own explicit list replaces everything" and "inherit verbatim"
# (chat_tool_planner._resolve_active_items). There was no add / remove /
# replace-one operator, so a user asking to swap one item got neither: the
# turn matched the outbound-verb guard (`replace` is in
# _CONFIRMATION_ACTION_RE), was classified as NOT a continuation, fell through
# to model narration with no structured read, and was answered with the
# PREVIOUS list. The durable task was never revised, and nothing detected
# that the displayed list no longer matched the request.
#
# The hard part is that "replace" means two different things in this product:
#   * "replace U-22 with U-38"          -> an edit to the TARGET LIST
#   * "replace the logo in the draft"   -> an outbound/mutation action
# Both contain the same verb. `_CONFIRMATION_ACTION_RE` treats the verb as the
# second, which is the safe default (never execute a mutation because a word
# appeared) but it also silently swallows the first. So the list-edit sense is
# recognised ONLY when the text around the verb actually names entity-shaped
# tokens, judged on the text with file mentions BLANKED OUT -- the same
# `_strip_mentions` idiom `_seek_shaped` already uses, for the same reason:
# vocabulary inside a filename must not classify the turn.
#
# Fail-closed by construction: a verb match alone is never enough. No
# entity-shaped token on the relevant side of the verb => no edit => the turn
# keeps whatever classification it had.
# ---------------------------------------------------------------------------
_ENTITY_SET_VERBS = r"(?:replace|swap|substitute|switch|exchange|change)"
_ENTITY_DROP_VERBS = r"(?:drop|remove|delete|exclude|omit|leave out|take out)"
_ENTITY_ADD_VERBS = r"(?:add|include|also include|append)"
# A connector that introduces the INCOMING item of a swap.
_ENTITY_SWAP_WITH = re.compile(
    r"\b(?:with|for|by|instead of)\b", re.IGNORECASE)


def _entity_shaped(token: str) -> bool:
    """Whether a token looks like a requested item rather than prose.

    Reuses the same identity test as `_clean_enumeration_item`: a model code
    carries a digit, a product name carries a capitalised word. Lowercase
    connective words ("with", "instead", "the") fail both, which is what keeps
    "replace the price with the cost" from reading as an entity swap."""
    t = (token or "").strip(" .,:;\"'")
    if not t or len(t) > 60 or len(t.split()) > 6:
        return False
    if _ITEM_NEGATION_RE.match(t) or t.lower() in _ITEM_JUNK:
        return False
    if re.match(r"^(?:the|a|an|and|or|with|for|instead|that|this|it)$",
                t, re.IGNORECASE):
        return False
    return bool(any(ch.isdigit() for ch in t)
                or any(w[:1].isupper() for w in t.split()))


def _entity_tokens(text: str) -> List[str]:
    """Entity-shaped tokens in a fragment, in order, deduplicated.

    Trims the grammar that surrounds an item inside an instruction before
    testing it, because an item name is only a NAME: "use U-38 instead of
    U-22" must yield ``U-38``, and "remove TK 1624 from the list" must yield
    ``TK 1624``. Without this, the leading verb and the trailing prepositional
    phrase both get glued onto the name, the token stops matching the active
    set, and the fail-closed membership guard silently rejects the whole
    instruction -- a correct request that then does nothing, which is the same
    class of failure this change exists to remove.
    """
    out: List[str] = []
    for raw in re.split(r"[,;]|\band\b", text or ""):
        frag = (raw or "").strip()
        # A user quoting an identifier ("Replace 'U-22' with \"U-38\"") means
        # exactly the same item as the bare form. Strip the quoting before any
        # shape test, or the quotes become part of the name and the token stops
        # matching the active set.
        frag = frag.strip("\"'“”‘’`").strip()
        # leading instruction verbs / fillers
        frag = re.sub(
            r"^(?:please\s+|can\s+you\s+|could\s+you\s+|i\s+want\s+to\s+|"
            r"i(?:'d)?\s+like\s+to\s+|let'?s\s+|now\s+|then\s+|also\s+|"
            r"use|using|show|give|tell|list|include|add|replace|swap|"
            r"substitute|switch|drop|remove|delete|with)\b\s*",
            "", frag, flags=re.IGNORECASE).strip()
        # trailing prepositional phrases
        frag = re.sub(
            r"\s+(?:from|in|off|out\s+of|to|for)\s+.*$", "", frag,
            flags=re.IGNORECASE).strip()
        frag = re.sub(r"\s+(?:as\s+well|instead|too|please)\b.*$", "", frag,
                      flags=re.IGNORECASE).strip()
        tok = _clean_enumeration_item(frag)
        if tok and _entity_shaped(tok) and tok not in out:
            out.append(tok)
    return out


def entity_set_edit(
    message: str,
    active_items: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """A user instruction that EDITS the active objective's item set.

    Returns ``None`` when the turn is not a set edit. Otherwise a dict:

        {"operation": "replace" | "drop" | "add",
         "removed": [...],   # items leaving the set
         "added":   [...],   # items entering the set
         "items":   [...]}   # the resulting ordered set

    ``items`` is the RESULT, computed against ``active_items`` so callers do not
    re-derive the set arithmetic (and cannot get it subtly different). Order is
    preserved: a replaced item takes the removed item's position, an appended
    item goes last, a dropped item leaves no hole. With no ``active_items`` the
    caller gets ``items`` = ``added`` only, which is the correct seed for a
    task that has no item set yet.
    """
    raw = (message or "").strip()
    if not raw:
        return None
    mentions: List[str] = []
    try:
        from core.agent_file_context import detect_file_mentions
        mentions = list(detect_file_mentions(raw) or [])
    except Exception:  # noqa: BLE001 — a pure helper must not gate the rest
        mentions = []
    # Judge on the text with filenames blanked out, so "replace" inside a
    # filename cannot read as a set edit (mirrors _seek_shaped).
    text = _strip_mentions(raw, mentions)
    active = [str(v).strip() for v in (active_items or []) if str(v).strip()]

    # --- replace / swap: "<verb> A with B"  (also "B instead of A") --------
    m = re.search(rf"\b{_ENTITY_SET_VERBS}\b\s+(.+?)"
                  rf"(?=\b{_ENTITY_SWAP_WITH.pattern}\b|$)", text,
                  re.IGNORECASE | re.DOTALL)
    if m:
        left = _entity_tokens(m.group(1))
        tail = text[m.end(1):]
        tm = _ENTITY_SWAP_WITH.search(tail)
        right = _entity_tokens(tail[tm.end():]) if tm else []
        if left and right:
            # Only a set edit if at least one side names something already in
            # the active set, or the active set is unknown. Without that, a
            # phrase like "replace the price with the cost" (no entity tokens)
            # never reaches here, and "replace the logo in the draft" has no
            # entity tokens either.
            if not active or any(t in active for t in left + right):
                return _apply_set_edit(active, "replace", left, right)

    # --- "<verb> A with B" reversed: "U-38 instead of U-22" ----------------
    m = re.search(rf"(.+?)\s+instead\s+of\s+(.+)$", text,
                  re.IGNORECASE | re.DOTALL)
    if m:
        incoming = _entity_tokens(m.group(1))
        outgoing = _entity_tokens(m.group(2))
        if incoming and outgoing and (
                not active or any(t in active for t in incoming + outgoing)):
            return _apply_set_edit(active, "replace", outgoing, incoming)

    # --- drop / remove ------------------------------------------------------
    m = re.search(rf"\b{_ENTITY_DROP_VERBS}\b\s+(.+)$", text,
                  re.IGNORECASE | re.DOTALL)
    if m:
        dropped = _entity_tokens(m.group(1))
        if dropped and (not active or any(t in active for t in dropped)):
            return _apply_set_edit(active, "drop", dropped, [])

    # --- add / also include ------------------------------------------------
    m = re.search(rf"\b{_ENTITY_ADD_VERBS}\b\s+(.+)$", text,
                  re.IGNORECASE | re.DOTALL)
    if m:
        added = _entity_tokens(m.group(1))
        if added and (not active or any(t not in active for t in added)):
            return _apply_set_edit(active, "add", [], added)
    return None


def _apply_set_edit(
    active: List[str],
    operation: str,
    removed: List[str],
    added: List[str],
) -> Dict[str, Any]:
    """Apply one set operation to ``active``, preserving order.

    A replaced item is substituted IN PLACE, so the user's requested ordering
    survives: swapping U-22 for U-38 in an 8-item list yields the same 8
    positions, not a 7-item list with U-38 appended. That is the whole point of
    applying the change to the task rather than re-deriving a list."""
    items = list(active)
    for item in removed:
        # A dropped item that is not in the set is not an error, but it must
        # not silently add a phantom: only items actually present are removed.
        while item in items:
            items.remove(item)
    for item in added:
        if item in items:
            continue
        if operation == "replace" and removed:
            # Substitute at the earliest removed item's original position.
            anchor = next((i for i, v in enumerate(active) if v in removed),
                          None)
            if anchor is not None and anchor <= len(items):
                items.insert(anchor, item)
                continue
        items.append(item)
    return {"operation": operation, "removed": list(removed),
            "added": list(added), "items": items}



def _clean_enumeration_item(raw: str) -> Optional[str]:
    """One enumerated item → its entity name, or None when the fragment
    is noise (a price tail, a negation/removal, currency/unit words).
    The FULL cleaned name is preserved — 'TK Manual Flanger' stays
    'TK Manual Flanger'; it is not reduced to a bare code (2026-09-25
    review round 4: preserve entity names and attributes)."""
    item = _ITEM_TAIL_RE.split(raw.strip())[0].strip(" .,:;")
    item = re.sub(r"^\d+[.)]\s*", "", item)  # numbered-list residue
    if not item:
        return None
    if _ITEM_NEGATION_RE.match(raw.strip()):
        return None  # a removal/correction target, not an entity
    if item.lower() in _ITEM_JUNK:
        return None
    if len(item.split()) > 6 or len(item) > 60:
        return None  # prose, not an enumeration item
    # Identity-shaped: carries a digit (model code) or a capitalized word
    # (proper name); bare lowercase prose fragments are not entities.
    if not (any(ch.isdigit() for ch in item)
            or any(word[:1].isupper() for word in item.split())):
        return None
    return item


def _enumeration_items(text: str) -> List[str]:
    """The explicit item list from an ask, or [] when the ask has none.
    Two accepted forms (2026-09-25 review round 4: colon-only was too
    narrow — the original quote ask is a NUMBERED list with prices):
    (a) a colon-introduced comma/and list; (b) numbered/bulleted lines.
    Decimal amounts never split; negation items are dropped; each item
    keeps its full entity name."""
    candidates: List[List[str]] = []
    colon = text.rfind(":")
    if 0 <= colon < len(text) - 1:
        tail = text[colon + 1:].strip()
        if tail and len(tail) <= 400:
            candidates.append(_ENUMERATION_SPLIT_RE.split(tail))
    list_lines = [
        match.group(1)
        for match in (_LIST_LINE_RE.match(line)
                      for line in text.splitlines())
        if match
    ]
    if len(list_lines) >= 2:
        candidates.append(list_lines)
    best: List[str] = []
    for parts in candidates:
        items = [
            cleaned
            for cleaned in (
                _clean_enumeration_item(part) for part in parts
            )
            if cleaned
        ]
        if len(items) > len(best):
            best = items
    return best if len(best) >= 2 else []


def identifier_targets_from_user_history(
    history: Optional[List[Dict[str, Any]]], mention: str = "",
) -> List[str]:
    """Resolve the ACTIVE objective's entity set from the user's own asks.

    2026-09-25 review round 2: the previous union-over-same-file-mentions
    harvest was both too broad (merged items from superseded asks about
    the same file) and too restrictive (required every message to name
    the file). The active objective's set is the NEWEST explicit
    enumeration in a user ask — file-named or not (a follow-up
    "…machines: 381, U-22, …" belongs to the file objective established
    around it) — plus pure-addition follow-ups ("also check TK 1624").
    A later enumeration naming a DIFFERENT file supersedes and returns
    that set alone. Assistant renders never contribute (they carry the
    canvas value tables).
    """
    out: List[str] = []
    seen: set = set()
    try:
        from core.agent_file_context import detect_file_task_mentions
        from core.workbook_read_artifact import extract_targets

        def _add(items: Iterable[str]) -> None:
            for item in items:
                text = str(item or "").strip()
                if not text:
                    continue
                key = re.sub(r"[^A-Z0-9]+", "", text.upper())
                if not key or key in seen:
                    continue
                seen.add(key)
                out.append(text)

        user_texts: List[str] = []
        for entry in (history or [])[-_RECOVERY_WINDOW:]:
            if not isinstance(entry, dict):
                continue
            role = str(entry.get("role") or "").lower()
            if role == "assistant":
                continue
            text = str(
                entry.get("message")
                or (entry.get("content") if role == "user" else "")
                or ""
            ).strip()
            if text:
                user_texts.append(text)

        enumerated: Optional[tuple] = None  # (items, file_named, text_idx)
        for index, text in enumerate(user_texts):
            items = _enumeration_items(text)
            if not items:
                continue
            mentions = detect_file_task_mentions(text)
            named = any(
                _same_file_identity(m, mention) for m in mentions
            ) if mention else True
            foreign = mention and mentions and not named
            if enumerated is None:
                if not foreign:
                    enumerated = (items, bool(mentions), index)
                continue
            # A later enumeration: same-file (or file-agnostic) EXTENDS the
            # active set only when it plausibly re-lists the objective
            # (same file); a foreign enumeration SUPERSEDES.
            if foreign:
                return []  # a different objective owns the newest ask
            if enumerated[1] and not mentions:
                continue  # file-agnostic re-listing — additions handle it
            enumerated = (items, bool(mentions) or enumerated[1], index)
        if enumerated is None:
            return []
        # FULL entity names, not reduced identifiers: 'TK Manual Flanger'
        # stays intact so brand/series attributes ride with the target
        # (2026-09-25 review round 4) — the reader's own derivation and
        # the artifact's alias lane consume the full name.
        _add(enumerated[0])
        # Pure-addition follow-ups after the chosen enumeration
        # ("also check TK 1624 while you're in there").
        for text in user_texts[enumerated[2] + 1:]:
            if _ADDITION_RE.match(text):
                _add(
                    cleaned
                    for cleaned in (
                        _clean_enumeration_item(part)
                        for part in _ENUMERATION_SPLIT_RE.split(
                            _ITEM_TAIL_RE.split(text)[0])
                    )
                    if cleaned
                )
        return out[:64]
    except Exception as e:  # noqa: BLE001 — harvest is best-effort
        logger.debug(f"pending file task: user-history targets skipped: {e}")
    return []


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
            # IDENTIFIER INHERITANCE (2026-09-25): the recovered objective
            # is the NEWEST seek-shaped ask — which can be vaguer than the
            # identifier-rich ask it superseded. Carry the user's explicit
            # identifiers forward so the resumed read searches the
            # machines, not the canvas title's phrases.
            _user_targets = identifier_targets_from_user_history(
                history, mention)
            if _user_targets:
                task["requested_targets"] = _user_targets
            # THE SAME COVERAGE RULE (2026-09-29 cross-source incident):
            # recovery reconstructs an earlier objective for a RETRY or
            # approval to resume. When the CURRENT instruction itself
            # asks for work beyond that objective (cross-source
            # disambiguation), recovery must not resurrect the old ask as
            # the turn's contract — the normal flows own the turn.
            if request_extends_objective(message, task):
                return None
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
