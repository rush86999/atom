"""Failure taxonomy — WHY a supervisor correction happened (Installation
Adaptation Plan Phase 2). Pure rules over the (original → corrected) diff,
so classification is deterministic and unit-testable; the label drives
which regression property an IncidentEval carries and what the weekly
report aggregates.

Classes: grounding | identity | persistence | process | tone | other

Live anchors (canvas da27bb76…, 2026-09-02): the "Chandrakant" signature
swap classifies as identity; restoring a hedged wording over an asserted
"480V available" classifies as grounding; the template-questions rewrites
classify as process.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

_CLASSES = ("grounding", "identity", "persistence", "process", "tone", "other")

# Hedged / in-progress wording — the assertive-vs-hedged contrast is the
# grounding signal (mirrors evidence_grounding's detector vocabulary).
_HEDGE_RE = re.compile(
    r"\b(we are confirming|we're confirming|confirming|to be confirmed|"
    r"will confirm|can confirm|not yet (verified|confirmed)|"
    r"(may|might|could) (be|have)|subject to|pending|"
    r"need to (verify|check|confirm)|before we (can|confirm))\b",
    re.IGNORECASE,
)
_ASSERT_RE = re.compile(
    r"\b(is available|are available|available in|in stock|we can supply|"
    r"we have|confirmed|guaranteed|comes with|includes)\b",
    re.IGNORECASE,
)
# Signature/name region markers — a change here is identity, not prose.
_SIG_MARKERS = (
    "regards", "sincerely", "thanks,", "cheers",
    "brennan", "signature",
)
_NAME_LIKE = re.compile(r"\b[A-Z][a-z]{2,}\b")
# Capitalized words that are prose, not names — "The cross-sectional
# dimensions" must not read as a name change.
_NAME_STOPWORDS = {
    "the", "this", "that", "best", "regards", "kind", "warm", "hi",
    "hello", "we", "our", "once", "thank", "thanks", "please",
    "sincerely", "dear", "yes", "also", "all", "but", "for", "and",
}


def _names(text: str) -> List[str]:
    return [n for n in _NAME_LIKE.findall(text or "")
            if n.lower() not in _NAME_STOPWORDS]


def _plain(content: Any) -> str:
    """Render dict-shaped (email) or string content to comparable text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        parts = []
        for key in ("to", "cc", "subject", "body"):
            if key in content:
                parts.append(str(content.get(key) or ""))
        parts.extend(str(v) for k, v in content.items()
                     if k not in ("to", "cc", "subject", "body"))
        return "\n".join(parts)
    return str(content)


def _tail(text: str, chars: int = 400) -> str:
    return text[-chars:] if text else ""


def classify_correction(
    original: Any,
    corrected: Any,
    meta: Optional[Dict[str, Any]] = None,
) -> Tuple[str, List[str]]:
    """Classify a supervisor correction. Returns (label, signals[]). The
    label is the FIRST matching class in evidence order — grounding and
    identity outrank tone, because they are the classes with hard gates."""
    meta = meta or {}
    before, after = _plain(original), _plain(corrected)
    signals: List[str] = []

    if not after.strip():
        return "other", ["empty_correction"]

    if before.strip() == after.strip():
        return "persistence", ["identical_content"]

    # IDENTITY: a NAME disappeared from the signature region (the
    # "Chandrakant"→"Rish M." swap), or identity metadata moved.
    before_names = set(_names(_tail(before)))
    after_names = set(_names(_tail(after)))
    removed_names = before_names - after_names
    if removed_names and (any(m in after.lower() for m in _SIG_MARKERS)
                          or isinstance(original, dict)):
        signals.append("signature_or_name_changed")
    if isinstance(original, dict) and isinstance(corrected, dict):
        for field in ("to", "cc", "subject"):
            if (original.get(field) or "") != (corrected.get(field) or ""):
                signals.append(f"header_{field}_changed")
    if signals and any(s.startswith(("signature", "header")) for s in signals):
        return "identity", signals

    # GROUNDING: an assertion was softened into a hedge (the 480V case),
    # or hedges were ADDED while assertions were kept/removed.
    added_hedges = _HEDGE_RE.findall(after) and not _HEDGE_RE.findall(before)
    dropped_assertions = _ASSERT_RE.findall(before) and not _ASSERT_RE.findall(after)
    if added_hedges or dropped_assertions:
        signals.append("assertion_softened")
        return "grounding", signals

    # PROCESS: template structure added (questions / numbered steps) — the
    # supervisor taught the draft a procedure it was missing.
    after_q = after.count("?")
    before_q = before.count("?")
    bullets_after = len(re.findall(r"(?:^|\n)\s*[-*\u2022\d]", after))
    bullets_before = len(re.findall(r"(?:^|\n)\s*[-*\u2022\d]", before))
    if (after_q - before_q) >= 2 or (bullets_after - bullets_before) >= 2:
        signals.append("questions_or_steps_added")
        return "process", signals

    if meta.get("noop_claim"):
        signals.append("claimed_change_but_identical")
        return "persistence", signals

    # TONE: word-level edits with no structural change.
    bw, aw = set(re.findall(r"[a-z']+", before.lower())), set(re.findall(r"[a-z']+", after.lower()))
    changed = len((bw - aw) | (aw - bw))
    if 0 < changed <= 12:
        signals.append(f"small_wording_change({changed})")
        return "tone", signals

    return "other", signals or ["unclassified_diff"]


def property_for(taxonomy: str, original: Any, corrected: Any) -> Dict[str, Any]:
    """The regression property an IncidentEval carries for the class —
    programmatic (no LLM-judge) so the runner stays deterministic:
      identity  → excludes: the WRONG token must never reappear
      grounding → no_unverified: the softened claim must stay hedged/excluded
      process   → includes: the added template line must be present
      persistence→ changed: output must differ from input or report no_change
    """
    before, after = _plain(original), _plain(corrected)
    if taxonomy == "identity":
        wrong = _token_removed(before, after)
        return {"kind": "excludes", "value": wrong or ""}
    if taxonomy == "grounding":
        claim = next((a for a in _ASSERT_RE.findall(before)), "")
        return {"kind": "no_unverified", "value": claim}
    if taxonomy == "process":
        added = _added_line(after, before)
        return {"kind": "includes", "value": added}
    return {"kind": "changed", "value": ""}


def _token_removed(before: str, after: str) -> str:
    """A distinctive name-like token present before and gone after — the
    "Chandrakant" the draft must never sign again."""
    for name in reversed(_names(_tail(before))):
        if name not in set(_names(_tail(after))):
            return name
    return ""


def _added_line(after: str, before: str) -> str:
    before_lines = {ln.strip().lower() for ln in before.splitlines() if ln.strip()}
    for ln in after.splitlines():
        s = ln.strip()
        if s and s.lower() not in before_lines and ("?" in s or len(s) > 20):
            return s[:200]
    return ""
