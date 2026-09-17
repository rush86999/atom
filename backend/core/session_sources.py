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
from typing import Any, Iterable, List

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


def conversation_source_names(history: List[Dict[str, Any]],
                              window: int = _WINDOW) -> List[str]:
    """Handles from the most recent ``window`` exchanges, newest first.
    Error turns are skipped: a failed attempt never located anything."""
    texts: List[str] = []
    for h in reversed(list(history or [])[-window:]):
        h = h or {}
        if h.get("error"):
            continue
        msg = str(h.get("message") or "")
        resp = str((h.get("response") or {}).get("message") or "")
        for part in (msg, resp):
            if part:
                texts.append(part)
    return extract_source_handles(texts)


def conversation_sources_block(history: List[Dict[str, Any]]) -> str:
    """Planner-prompt block naming previously located sources, or "" when
    the conversation has named none."""
    handles = conversation_source_names(history)
    if not handles:
        return ""
    return (
        "SOURCES LOCATED EARLIER IN THIS CONVERSATION: "
        + "; ".join(handles)
        + ". A file named here was already found once — plan a lookup that "
        "REUSES it (documents/datasets) when the current request needs it "
        "again, instead of searching elsewhere or concluding it is missing."
    )
