"""Intelligent search queries for every agent's web/integration lookups.

The live failure this fixes (2026-09-01): a co-editor agent asked to
"research the lead … determine if end user or dealer" and the planned Tavily
query was literally "determine if lead is end user or dealer" — the search
engine returned results about the METAL lead. The prompt-level rule added to
the tool planner helps strong models; this module is the deterministic
execution-time guarantee, shared by every agent funneling through the chat
tool planner: whatever query reaches the search API must carry the subject's
actual names, resolved from the conversation or the open canvas when the
message itself only says "the lead" / "the company".

Deliberately heuristic and dependency-free: entity extraction is capitalized
sequence + email-domain based, not an NER model. Search engines forgive
slightly noisy entity terms but not missing ones.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

# Common capitalized words that are almost never entities when they appear
# alone (sentence starts, greetings, sign-offs, instruction verbs).
_COMMON_CAPS = {
    "i", "the", "this", "that", "these", "those", "a", "an", "if", "is",
    "are", "was", "were", "be", "do", "does", "did", "can", "could", "would",
    "should", "shall", "will", "may", "might", "must", "have", "has", "had",
    "hi", "hello", "hey", "dear", "thanks", "thank", "please", "regards",
    "best", "sincerely", "cheers", "yes", "no", "ok", "okay", "and", "but",
    "or", "so", "then", "when", "what", "which", "who", "whom", "whose",
    "why", "how", "where", "there", "here", "it", "its", "we", "our", "you",
    "your", "he", "she", "they", "them", "their", "my", "me", "us",
    # instruction verbs — a capitalized sentence start is usually the verb
    "research", "check", "determine", "find", "search", "look", "verify",
    "confirm", "decide", "figure", "see", "tell", "show", "give", "get",
    "make", "update", "draft", "write", "send", "review", "analyze",
    "investigate", "identify", "classify", "compare", "summarize",
}

# Instruction scaffolding stripped from the message before using its words
# as query terms — these verbs carry intent, not search signal.
_INSTRUCTION_PREFIX = re.compile(
    r"^\s*(?:(?:please|kindly)\s+)*"
    r"(?:(?:can|could|would|will)\s+you\s+|(?:you\s+)|(?:please\s+))?"
    r"(?:research|look\s*up|search(?:\s+(?:the\s+)?(?:web|internet|online))?(?:\s+for)?|"
    r"find\s+(?:out|info(?:rmation)?(?:\s+about)?)?|check|verify|confirm|"
    r"determine|figure\s+out|google|investigate|browse)\b[,:]?\s*",
    re.IGNORECASE,
)
_INSTRUCTION_CLAUSE = re.compile(
    r"\b(?:over|on|via|through|using|from)\s+the\s+(?:web|internet)\b|\b"
    r"(?:on|via|through)\s+(?:google|tavily|the\s+internet)\b|\b"
    r"over\s+the\s+web\b",
    re.IGNORECASE,
)

_EMAIL = re.compile(r"\b[\w.+-]+@([\w-]+)\.[\w.-]+\b")
_CAPS_SEQ = re.compile(r"\b[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*\b")
_URL = re.compile(r"\bhttps?://(?:www\.)?([\w-]+)\.[\w.-]+")


def _entities(text: str) -> List[str]:
    """Distinct entity candidates from one text: email domains, URL hosts,
    capitalized sequences minus the common-word list."""
    if not text:
        return []
    found: List[str] = []
    for m in _EMAIL.finditer(text):
        found.append(m.group(1))
    for m in _URL.finditer(text):
        found.append(m.group(1))
    for m in _CAPS_SEQ.finditer(text):
        candidate = m.group(0).strip()
        tokens = candidate.split()
        # drop pure-stopword sequences ("The", "Check If This")
        kept = [t for t in tokens if t.lower() not in _COMMON_CAPS]
        if kept and " ".join(kept) != candidate:
            candidate = " ".join(kept)
        elif not kept:
            continue
        if candidate.lower() not in _COMMON_CAPS and candidate not in found:
            found.append(candidate)
    return found


def _clean_message(message: str) -> str:
    """Strip instruction scaffolding from the message so its remaining words
    can serve as query terms ("research the lead over the web to determine if
    end user or dealer" → "the lead to determine if end user or dealer")."""
    text = message or ""
    text = _INSTRUCTION_CLAUSE.sub(" ", text)
    for _ in range(3):  # stacked prefixes ("please research look up")
        stripped = _INSTRUCTION_PREFIX.sub("", text)
        if stripped == text:
            break
        text = stripped
    return re.sub(r"\s+", " ", text).strip(" ,.:;")


def build_search_query(
    message: str,
    history_turns: Optional[Iterable[Any]] = None,
    canvas_content: Optional[Dict[str, Any]] = None,
    max_length: int = 160,
) -> str:
    """A search query that names the subject, whatever the user said.

    Resolution order for the subject: named entities IN the message beat the
    conversation transcript, which beats the open canvas (To/Subject/body —
    an email's recipient domain is itself a strong entity). The message's
    own question terms ("end user or dealer") are preserved alongside the
    resolved entity, because the user's question is the search intent.

    Returns a cleaned query; when nothing resolvable exists anywhere, the
    de-scaffolded message (still better than the raw instruction sentence).
    """
    cleaned = _clean_message(message)
    msg_entities = _entities(message)

    if msg_entities:
        query = cleaned
    else:
        context_entities: List[str] = []
        seen = set()
        # most recent turns first — the last-mentioned subject wins
        for turn in reversed(list(history_turns or [])):
            if isinstance(turn, dict):
                text = " ".join(str(turn.get(k) or "") for k in ("message", "response"))
            else:
                text = str(turn or "")
            for entity in _entities(text):
                key = entity.lower()
                if key not in seen:
                    seen.add(key)
                    context_entities.append(entity)
        if canvas_content and isinstance(canvas_content, dict):
            canvas_text = " ".join(
                str(canvas_content.get(k) or "")
                for k in ("subject", "to", "cc", "body", "title")
            )
            for entity in _entities(canvas_text):
                key = entity.lower()
                if key not in seen:
                    seen.add(key)
                    context_entities.append(entity)
        head = context_entities[:3]
        query = (" ".join(head) + " " + cleaned).strip() if head else cleaned

    query = re.sub(r"\s+", " ", query).strip()
    if len(query) > max_length:
        query = query[:max_length].rsplit(" ", 1)[0]
    return query
