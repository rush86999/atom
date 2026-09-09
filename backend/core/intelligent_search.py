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
    "best", "sincerely", "cheers", "yes", "no", "ok", "okay", "done",
    # email-subject / spec-sheet prose that pattern-matches as "entities"
    # (live 2026-09-08: 'blumetric Re Equivalent …' pushed the actual
    # machines out of the search query head)
    "re", "fw", "fwd", "equivalent", "comparison", "inquiry", "quote",
    "form", "forms", "stock", "cad", "usd", "semi", "automatic", "double",
    "miter",
    "and", "but",
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
    r"(?:(?:can|could|would|will)\s+you\s+|(?:you\s+)|(?:please\s+)"
    r"|(?:web|internet|online)\s+)?"
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
# Bare domains in the query itself ("brennan.ca bandsaw model"): a domain IS
# a named subject even in lowercase, where the capitalized-sequence regex
# sees nothing (live 2026-09-08: that read made an already-specific planner
# query look subject-less, so context entities got PREPENDED to it).
_BARE_DOMAIN = re.compile(
    r"(?<![\w@.])((?:[a-z0-9-]+\.)+(?:com|ca|org|net|io|co|ai|dev|info|biz"
    r"|us|uk|de|fr|au|in|shop|store|app))(?:/[^\s]*)?",
    re.IGNORECASE,
)

# Machinery/product model codes: letters+digits with optional dashes and
# letter suffixes — WG-350DSAV, DM10, DM-10, 330B, BS-350M, SU-280. At
# least one letter AND one digit required, so years/prices ("2026", "350")
# never match. These are the STRONGEST search identifiers in industrial
# queries: the caps-sequence regex splits them ("WG" alone, "350DSAV"
# unmatched — digit-led), which is how a bandsaw research query lost both
# machine models (live 2026-09-08).
_MODEL_CODE_RE = re.compile(
    r"\b[A-Z]{1,4}-?\d{2,}[A-Z][A-Z0-9-]*\b"      # WG-350DSAV, BS-350M
    r"|\b[A-Z]{1,4}-?\d{2,}(?:-[A-Z0-9]+)*\b"     # DM10, DM-10, SU-280
    r"|\b\d{2,}[A-Z][A-Z0-9-]*\b"                 # 330B (digit-led codes)
)

# Quote-research intent: the words a sales/quote research ask carries when
# it needs AUTHORITATIVE product data — not just snippets. Industry-
# standard quoting research resolves specs/prices from the OEM or primary
# listing, not vendor blogs (CPQ practice: authoritative-source-first).
_RESEARCH_INTENT_RE = re.compile(
    r"\b(?:spec(?:s|ifications)?|datasheet|data\s+sheet|price|pricing|"
    r"cost|list\s+price|quote|compare|comparison|equivalent|alternative|"
    r"vs\.?|versus|review|capacity|dimensions|model|part\s+number|sku)\b",
    re.IGNORECASE,
)


def _research_intent(text: str) -> bool:
    """True when the text carries quote-research intent words — specs,
    pricing, comparison. Used to gate the authoritative-page deep fetch for
    products WITHOUT model codes (branded goods, services: "Weber Genesis
    grill specifications")."""
    return bool(_RESEARCH_INTENT_RE.search(text or ""))

# Sentences that are pure instruction scaffolding — they carry intent, not
# search signal ("give me a response but don't update the draft"). Dropped
# only when they hold NO entity and NO model code, so a sentence that names
# the subject always survives.
_INSTRUCTION_SENTENCE_RE = re.compile(
    r"^\s*(?:please\s+|kindly\s+)?"
    r"(?:give|show|tell|reply|respond|send|keep|leave|make|check|confirm|"
    r"don'?t|do\s+not|doesn'?t|no)\b",
    re.IGNORECASE,
)


def _model_refs(text: str) -> List[str]:
    """Model codes with their adjacent brand word — the subject-of-record
    for machinery/equipment lookups: "Hydmech DM10", "Linmac WG-350DSAV".
    Brand = up to two capitalized words immediately before the code."""
    if not text:
        return []
    refs: List[str] = []
    seen = set()
    accepted_spans: List[Any] = []
    for m in _MODEL_CODE_RE.finditer(text):
        code = m.group(0).strip("-")
        # volt/amp/watt ratings are not product codes ("Bandsaw 230V")
        if re.fullmatch(r"\d{2,3}[VAW]", code):
            continue
        # nested double-match ("WG-350DSAV" also yields "350DSAV"): skip
        # any match fully contained inside an already-accepted one
        if any(a.start() <= m.start() and m.end() <= a.end()
               for a in accepted_spans):
            continue
        accepted_spans.append(m)
        # dash-insensitive dedup: DM10 and DM-10 are the same machine
        key = code.upper().replace("-", "")
        if key in seen:
            continue
        seen.add(key)
        seen.add(key)
        before = text[:m.start()].rstrip()
        words: List[str] = []
        for _ in range(2):
            wm = re.search(r"([A-Z][a-zA-Z0-9]+|\d+[A-Z][A-Z0-9]*)$", before)
            if not wm:
                break
            words.insert(0, wm.group(1))
            before = before[: wm.start()].rstrip()
        refs.append(" ".join(words + [code]))
    return refs


def _drop_instruction_sentences(text: str) -> str:
    """Remove pure-imperative sentences that contain neither entities nor
    model codes — the trailing "give me a response but don't update the
    draft" class that otherwise rides along to the search API."""
    if not text:
        return text
    kept = []
    for sentence in re.split(r"(?<=[.!?;])\s+", text):
        s = sentence.strip()
        if not s:
            continue
        if (_INSTRUCTION_SENTENCE_RE.match(s)
                and not _model_refs(s)
                and not _entities(s)):
            continue
        kept.append(s)
    return " ".join(kept)


def _strong_entities(text: str) -> List[str]:
    """Unambiguous identifiers only: email domains, URL hosts, bare domains.

    Used for text the ASSISTANT authored (its replies, link dumps) where a
    capitalized word is prose, not a subject — live 2026-09-08: "DONE" and
    "Notes" from prior replies were extracted as entities and prepended to
    an already-specific search query, and Tavily returned nothing."""
    if not text:
        return []
    found: List[str] = []
    for m in _EMAIL.finditer(text):
        found.append(m.group(1))
    for m in _URL.finditer(text):
        found.append(m.group(1))
    for m in _BARE_DOMAIN.finditer(text):
        found.append(m.group(1).lower())
    deduped: List[str] = []
    seen = set()
    for entity in found:
        if entity.lower() not in seen:
            seen.add(entity.lower())
            deduped.append(entity)
    return deduped


def _entities(text: str) -> List[str]:
    """Distinct entity candidates from one text: email domains, URL hosts,
    bare domains, capitalized sequences minus the common-word list."""
    if not text:
        return []
    found: List[str] = []
    for m in _EMAIL.finditer(text):
        found.append(m.group(1))
    for m in _URL.finditer(text):
        found.append(m.group(1))
    for m in _BARE_DOMAIN.finditer(text):
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

    Resolution order for the subject: MODEL CODES beat named entities IN the
    message, which beat the conversation transcript, which beats the open
    canvas (To/Subject/body — an email's recipient domain is itself a strong
    entity). The message's own question terms ("end user or dealer") are
    preserved alongside the resolved entity, because the user's question is
    the search intent.

    Returns a cleaned query; when nothing resolvable exists anywhere, the
    de-scaffolded message (still better than the raw instruction sentence).
    """
    cleaned = _drop_instruction_sentences(_clean_message(message))
    msg_entities = _entities(message)

    # MODEL CODES FIRST: "Hydmech DM10 Linmac WG-350DSAV …" is the query a
    # subject-matter expert would type. Prose entities (recipient domains,
    # subject-line words) must never push codes out of the head — live
    # 2026-09-08: 'blumetric Re Equivalent …' did, and the search returned
    # consumer woodworking saws for an industrial-machinery comparison.
    model_refs: List[str] = _model_refs(message)
    if not model_refs:
        for turn in reversed(list(history_turns or [])):
            if isinstance(turn, dict):
                user_text = str(turn.get("message") or "")
                resp = turn.get("response")
                assistant_text = (
                    str(resp.get("message") or "")
                    if isinstance(resp, dict) else str(resp or "")
                )
            else:
                user_text, assistant_text = str(turn or ""), ""
            model_refs = (_model_refs(user_text)
                          or _model_refs(assistant_text))
            if model_refs:
                break
    if not model_refs and canvas_content and isinstance(canvas_content, dict):
        canvas_text = " ".join(
            str(canvas_content.get(k) or "")
            for k in ("subject", "to", "cc", "body", "title")
        )
        model_refs = _model_refs(canvas_text)

    if model_refs:
        head = " ".join(model_refs[:3])
        tail = cleaned
        # Truncate the TAIL (message prose), never the codes — the old
        # blind cut could drop the machines and keep "don't update the
        # draft".
        room = max_length - len(head) - 1
        if len(tail) > room:
            tail = tail[:max(0, room)].rsplit(" ", 1)[0]
        return re.sub(r"\s+", " ", f"{head} {tail}").strip()

    if msg_entities:
        query = cleaned
    else:
        context_entities: List[str] = []
        seen = set()
        # most recent turns first — the last-mentioned subject wins
        for turn in reversed(list(history_turns or [])):
            if isinstance(turn, dict):
                user_text = str(turn.get("message") or "")
                resp = turn.get("response")
                assistant_text = (
                    str(resp.get("message") or "")
                    if isinstance(resp, dict) else str(resp or "")
                )
            else:
                user_text, assistant_text = str(turn or ""), ""
            # The user's own words name the subject; assistant prose does
            # not ("DONE", "Notes", markdown) — from replies take only
            # unambiguous identifiers (links, email/inline domains).
            for text, extractor in ((user_text, _entities),
                                    (assistant_text, _strong_entities)):
                for entity in extractor(text):
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
