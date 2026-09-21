"""Source handles a conversation has already located, extracted from its
own transcript.

RCA 2026-09-17 finding 3: the PRICE VIPUL workbook was found and opened on
the derivation turn, and one turn later the reply denied any such file
exists — nothing carried the discovery forward. The durable store here is
the transcript itself: assistant replies name the files they used, so
re-extracting the names needs no new state, survives restarts, and cannot
go stale the way a cache would. What this enables: the planner prompt and
corrective guards can say "this file WAS located earlier — reopen it
instead of asserting absence."

Bounded by design: recent window only, capped count, capped name length.
"""

import re
from typing import Any, Dict, Iterable, List

#: Body excludes "." and "," so a match cannot cross sentence or list
#: punctuation ("...chain. See also report_v2.pdf" must not become one
#: 60-char "name"); ")" is allowed just before the extension dot because
#: real files are named "PRICE VIPUL (6).xlsx".
_FILENAME_RE = re.compile(
    # The body may contain a dot ONLY when it continues into a word, which is
    # what separates "PRICE VIPUL (6).xlsx" from a sentence end
    # ("...chain. See also report_v2"): a comma is never allowed, and a period
    # must be followed immediately by a letter, digit or "(".
    r"([A-Za-z0-9][A-Za-z0-9 ()&+'_\-]{0,62}"
    r"(?:\.[A-Za-z0-9(][A-Za-z0-9 ()&+'_\-]{0,62})?)"
    r"\.(xlsx|xlsm|xlsb|xls|csv|tsv|pdf|docx|doc|pptx|ppt|txt|json|md)\b",
    re.IGNORECASE,
)

#: Words that begin an English sentence rather than a file name. Trimmed from the
#: LEFT of a candidate so "See also report_v2" becomes "report_v2".
_LEADING_STOPWORDS = {
    "the", "a", "an", "see", "also", "and", "or", "for", "from", "in", "on",
    "at", "to", "of", "with", "opened", "open", "using", "use", "via", "per",
    "this", "that", "these", "those", "its", "it", "was", "is", "are", "as",
    "by", "into", "then", "than", "so", "but", "not", "no", "we", "i", "you",
    "your", "our", "my", "their", "read", "found", "attached", "saved",
    # request verbs that precede a name the user is ASKING about ("Find
    # vendor_scorecard.xlsx") — the verb is not part of the handle
    "find", "search", "locate", "try",
    # narrative connectives that precede a re-mention of the same file
    "later", "earlier", "then", "again", "next", "finally", "also", "same",
    "both", "each", "all", "here", "there", "which", "where", "when",
}


def _candidate_stem(raw: str) -> str:
    """The file name inside a greedy match, or "" when there is none.

    The regex above cannot avoid spanning prose: its character class includes
    spaces (real file names have them) and the match is greedy, so
    "The PRICE VIPUL (6).xlsx workbook, Sheet1, row 235 gives the chain. See also
    report_v2.pdf" yields the whole span ending at each extension. Measured against
    the 71 file names in this install's catalog, that made extraction recover the
    right name for **0** of them.

    The file name is the TAIL of the match, so this trims from the smallest
    suffix that still looks like a name:

    * a comma means prose — the name starts after the last one;
    * leading sentence words are dropped ("See also report_v2" -> "report_v2"),
      which also lets a short genuine name ("report_v2") beat a long prose tail
      ("row 235 gives the chain. See also report_v2");
    * a multi-word, all-lowercase candidate with no digit or underscore is prose
      ("gives the chain"), not a name.

    Deliberately returns "" rather than guessing: a WRONG source handle would make
    the reply confidently reopen the wrong file, which is worse than no handle.
    """
    words = " ".join(str(raw or "").split()).split(", ")[-1].split()
    if not words:
        return ""
    while words and words[0].lower().strip("'\"") in _LEADING_STOPWORDS:
        words.pop(0)
    best = ""
    for start in range(len(words)):
        cand = " ".join(words[start:]).strip(" -_")
        if not cand:
            continue
        if len(cand) > 64:
            continue
        if len(cand.split()) >= 2 and not any(
            c.isupper() or c.isdigit() or c == "_" for c in cand
        ):
            continue  # multi-word and entirely lowercase: prose, not a name
        best = best or cand
    return best


_WINDOW = 12
_CAP = 8

#: Leading prose tokens absorb into the match ("Opened PRICE VIPUL
#: (6).xlsx"): strip all-letter leading words while more than three tokens
#: remain, so the handle is the file, not the sentence around it.
def _trim_name(name: str) -> str:
    """The file name inside a match, with leading prose removed.

    The pattern cannot avoid starting a word or two early: both
    "The PRICE VIPUL (6).xlsx" and "See also report_v2.pdf" begin with words that
    belong to the sentence, not the name. Leading stopwords are dropped and a
    candidate that is ENTIRELY stopwords is rejected (in "convert it to .pdf" the
    match is "to", and a stopword is never a file name).

    Known limitation, measured against this install's 71 catalog names: a file
    whose name BEGINS with a stopword loses that word ("All Prices For All
    Parts …" -> "Prices For All Parts …"). Distinguishing that from a prose head
    by shape was tried and made things worse (four variations, 51-61 of 71), so
    the simple rule is kept and the limitation is stated rather than papered over
    — a slightly trimmed handle still resolves, while a wrong one reopens the
    wrong file.
    """
    parts = " ".join(str(name or "").split()).split()
    while parts and parts[0].lower().strip("'\"") in _LEADING_STOPWORDS:
        parts.pop(0)
    if not parts or parts[-1].lower().strip("'\"") in _LEADING_STOPWORDS:
        return ""
    return " ".join(parts).strip(" -_")


def extract_source_handles(texts: Iterable[str], cap: int = _CAP) -> List[str]:
    """File names mentioned in ``texts``, first-seen order, deduped
    case-insensitively. Callers pass NEWEST FIRST so recent sources win
    the cap."""
    seen: set = set()
    out: List[str] = []
    for text in texts:
        if not text:
            continue
        for m in _FILENAME_RE.finditer(str(text)):
            # group(1) is the basename INCLUDING the extension, and the match can
            # SPAN PROSE ("PRICE VIPUL (6).xlsx workbook, Sheet1, ... See also
            # report_v2.pdf"), so `rfind(".")` finds a LATER sentence's dot and
            # strips to "pdf". The extension's own length is the only reliable
            # offset.
            _base = " ".join(m.group(1).split())
            _ext = m.group(2)
            if _ext and _base.lower().endswith(_ext.lower()):
                _base = _base[: -len(_ext)].rstrip(".")
            name = _trim_name(_base)
            if not name:
                continue
            name = f"{name}.{_ext}"  # the handle must be the real file name
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(name)
            if len(out) >= cap:
                return out
    return out


#: The reply DID NOT retrieve the file. Detecting these is what separates a
#: discovery from a mention, and a false negative here is what R1 exposed.
_RETRIEVAL_FAILURE_RE = re.compile(
    r"\b(could not|couldn't|cannot|can't|unable to|not able to|failed to|"
    r"no such file|does not exist|doesn't exist|not found|no file (?:with|named)|"
    r"nothing (?:matched|found)|returned no|no results?)\b",
    re.IGNORECASE,
)

#: A reply that shows an OPENABLE source path retrieved it — `documents.read` /
#: `documents.cat` paths and the evidence legs' `full:`/`open:` markers are
#: produced only after a successful read.
_OPENABLE_RE = re.compile(r"(?:knowledge/(?:documents|conversations|files)/)", re.IGNORECASE)


def _reply_evidence_of_retrieval(reply: str) -> bool:
    """Did this reply actually RETRIEVE the file it mentions?

    R1 (2026-09-17): the previous version treated any filename in any text as a
    located source, so the USER'S OWN QUESTION ("Find vendor_scorecard.xlsx") was
    promoted to "already found once" while the assistant's next line said it could
    not be located — and the planner was then told to REUSE it instead of
    searching. That is the false-source behaviour the scorecard control exists to
    prevent.

    A discovery requires positive evidence: an openable source path, or a reply
    that neither reports failure nor merely echoes the request.
    """
    text = str(reply or "")
    if not text.strip():
        return False
    if _OPENABLE_RE.search(text):
        return True
    if _RETRIEVAL_FAILURE_RE.search(text):
        return False
    return True


def conversation_source_names(history: List[Dict[str, Any]],
                              window: int = _WINDOW) -> List[str]:
    """Handles the conversation CONFIRMED, newest first — assistant replies that
    show a real retrieval and report no failure.

    User messages are deliberately excluded: asking about a file is not finding
    one. Error turns are skipped, as before."""
    texts: List[str] = []
    for h in reversed(list(history or [])[-window:]):
        h = h or {}
        if h.get("error"):
            continue
        resp = str((h.get("response") or {}).get("message") or "")
        if resp and _reply_evidence_of_retrieval(resp):
            texts.append(resp)
    return extract_source_handles(texts)


#: An openable VFS path as evidence lines and replies cite it — the durable
#: identity of a retrieved source (the display name is not: two stores can
#: hold same-named files, and the review's Step-2 row was exactly that
#: collision). Captures the path itself, not just its branch.
_SOURCE_PATH_RE = re.compile(
    r"\b(?:full|open|read):\s*"
    r"(knowledge/[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)*)",
    re.IGNORECASE,
)


def _reply_source_paths(reply: str) -> List[str]:
    """Distinct openable VFS paths a reply cites, in order, deduped."""
    out: List[str] = []
    seen: set = set()
    for m in _SOURCE_PATH_RE.finditer(str(reply or "")):
        p = m.group(1).rstrip(".")
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def conversation_source_refs(history: List[Dict[str, Any]],
                             window: int = _WINDOW) -> "List[Dict[str, str]]":
    """``[{"name": …, "path": …}]`` for sources the conversation CONFIRMED —
    the Step-2 durable-identity layer over :func:`conversation_source_names`.

    The openable ``knowledge/…`` path is what a reopen actually resolves
    against, so it — not the display name — disambiguates same-named files:
    two different paths under one name BOTH survive as separate refs (the
    name-collision acceptance row). Pairing is deliberately conservative: a
    path is attached only when the reply names exactly one file and cites
    exactly one distinct path — a wrong (name, path) pairing would reopen
    the WRONG file, which is worse than a name-only hint (the module's own
    principle). Newest first, bounded by the window and cap.
    """
    refs: "List[Dict[str, str]]" = []
    seen: set = set()
    for h in reversed(list(history or [])[-window:]):
        h = h or {}
        if h.get("error"):
            continue
        resp = str((h.get("response") or {}).get("message") or "")
        if not resp or not _reply_evidence_of_retrieval(resp):
            continue
        handles = extract_source_handles([resp])
        paths = _reply_source_paths(resp)
        for name in handles:
            path = ""
            if (len(handles) == 1 and len(paths) == 1
                    and _single_clean_file(name)):
                path = paths[0]
            key = (name.lower(), path.lower())
            if key in seen:
                continue
            seen.add(key)
            refs.append({"name": name, "path": path})
            if len(refs) >= _CAP:
                return refs
    return refs


def _single_clean_file(name: str) -> bool:
    """The handle is one stem + one extension, nothing else.

    The extractor's prose-spanning is a documented limitation: "Opened
    price list.xlsx and notes.docx" yields the GLUED handle "price
    list.xlsx and notes.docx" (an interior extension dot). Attaching a
    path to such a handle would reopen one specific file under a name
    covering two — refuse pairing there; the handle still serves as a
    name-only hint.
    """
    stem = str(name or "").rsplit(".", 1)[0]
    return "." not in stem


def conversation_mentioned_names(history: List[Dict[str, Any]],
                                 window: int = _WINDOW) -> List[str]:
    """File names the conversation MENTIONED but did not confirm — the user's own
    references. Useful as search HINTS; never as provenance."""
    texts: List[str] = []
    for h in reversed(list(history or [])[-window:]):
        h = h or {}
        msg = str(h.get("message") or "")
        if msg:
            texts.append(msg)
    return extract_source_handles(texts)


def conversation_sources_block(history: List[Dict[str, Any]]) -> str:
    """Planner-prompt block naming previously located sources, or "".

    States the provenance it actually has. A confirmed source may be reused; a
    merely MENTIONED name is a search hint and the prompt says so, because
    instructing the planner to "REUSE" an unconfirmed name is how a nonexistent
    file becomes asserted fact (R1). A confirmed source WITH an openable path
    is reopened BY THE PATH (the durable identity — same-named files in
    different stores are distinct refs, listed with their paths).
    """
    refs = conversation_source_refs(history)
    located = [r["name"] for r in refs]
    mentioned = [
        n for n in conversation_mentioned_names(history)
        if n.lower() not in {x.lower() for x in located}
    ]
    parts: List[str] = []
    if refs:
        rendered = []
        for r in refs:
            if r.get("path"):
                rendered.append(
                    f"{r['name']} [reopen by path: {r['path']} via "
                    "documents.read; or datasets.search its filename]")
            else:
                rendered.append(r["name"])
        parts.append(
            "SOURCES RETRIEVED EARLIER IN THIS CONVERSATION: "
            + "; ".join(rendered)
            + ". These were actually retrieved — plan a lookup that REUSES one "
            "(documents/datasets) when the current request needs it again, "
            "instead of searching elsewhere or concluding it is missing. When a "
            "path is shown, target THAT path — the display name alone can be "
            "ambiguous. If a retrieved source no longer resolves, say so "
            "rather than asserting its contents."
        )
    if mentioned:
        parts.append(
            "NAMES MENTIONED BUT NOT CONFIRMED AS RETRIEVED: "
            + "; ".join(mentioned)
            + ". These were asked about or referenced, NOT shown to exist — "
            "verify with a lookup before relying on them, and never report them "
            "as already found."
        )
    return " ".join(parts)
