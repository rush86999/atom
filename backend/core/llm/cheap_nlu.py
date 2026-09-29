# -*- coding: utf-8 -*-
"""Cheap-NLU micro-classifiers for the residue deterministic rules miss.

Why this module exists. Routing and constraint rules in this repo start
as deterministic lexical floors (regex/vocabulary) — fast, testable,
fail-closed. Some judgments, however, are SEMANTIC and every noun-list
regex for them lags the world: "Priya's text message" (a source to
search) vs "Brennan Machinery's quote" (a row attribute); "find this in
the workbook/document/tracker" (the conversation's resolved file) vs a
request about something else. Hardcoding those noun lists makes behavior
business- and domain-dependent.

This module is the established tiebreaker pattern of
``core/llm/match_confidence_tiebreaker.py`` applied to NLU: a
budget-tier LLM (``model="auto"`` BPC routing) answers a strictly
scoped yes/no micro-question, with:

  - a bounded TTL result cache (repeat phrases amortize to zero cost);
  - a circuit breaker (consecutive failures open a cooldown);
  - ``TESTING=1`` and ``ATOM_CHEAP_NLU_LLM=0`` disable every call
    (tests and offline runs stay on the deterministic floor);
  - NEVER raising: any doubt returns ``None`` and the caller keeps its
    deterministic-floor behavior (fail-closed).

Callers must be built so that ``None`` (or "no") preserves their
existing deterministic path — the LLM may only REFINE, never gate.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


def switch_enabled() -> bool:
    """Master switch, evaluated at CALL time (never frozen at import —
    a test or harness may set TESTING before/after this module loads).

    Off under ``TESTING=1`` so unit tests never make LLM calls;
    ``ATOM_CHEAP_NLU_LLM=false`` is the production kill switch.
    """
    if os.getenv("TESTING") == "1":
        return False
    return os.getenv("ATOM_CHEAP_NLU_LLM", "true").lower() != "false"

_CHEAP_NLU_TIMEOUT_S = float(
    os.getenv("ATOM_CHEAP_NLU_TIMEOUT_SECONDS", "6") or 6)
_CACHE_MAX = 512
_CACHE_TTL_S = 1800  # 30 min — phrases repeat across turns in a session
_cache: "OrderedDict[str, tuple[Optional[bool], float]]" = OrderedDict()

# Circuit breaker: N consecutive failures open a cooldown (pattern and
# thresholds mirrored from the selector-confidence tiebreaker).
_BREAKER_THRESHOLD = 3
_BREAKER_COOLDOWN_S = 60.0
_breaker_failures = 0
_breaker_opened_at: Optional[float] = None


def _breaker_tripped() -> bool:
    global _breaker_failures, _breaker_opened_at
    if _breaker_opened_at is None:
        return False
    if time.time() - _breaker_opened_at > _BREAKER_COOLDOWN_S:
        _breaker_opened_at = None
        _breaker_failures = 0
        return False
    return True


def _record(success: bool) -> None:
    global _breaker_failures, _breaker_opened_at
    if success:
        _breaker_failures = 0
        return
    _breaker_failures += 1
    if _breaker_failures >= _BREAKER_THRESHOLD:
        _breaker_opened_at = time.time()
        logger.warning(
            "cheap-nlu circuit breaker open for %.0fs after %d failures",
            _BREAKER_COOLDOWN_S, _breaker_failures)


def _cache_key(kind: str, subject: str, text: str) -> str:
    raw = f"{kind}\x1f{subject}\x1f{text}".encode("utf-8", "replace")
    return hashlib.sha256(raw).hexdigest()


def _cache_get(key: str) -> Optional[bool]:
    hit = _cache.get(key)
    if hit is None:
        return None
    verdict, expires_at = hit
    if time.time() > expires_at:
        _cache.pop(key, None)
        return None
    _cache.move_to_end(key)
    return verdict


def _cache_put(key: str, verdict: Optional[bool]) -> None:
    _cache[key] = (verdict, time.time() + _CACHE_TTL_S)
    _cache.move_to_end(key)
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)


def reset_for_tests() -> None:
    """Clear cache + breaker state (test-only)."""
    global _breaker_failures, _breaker_opened_at
    _cache.clear()
    _breaker_failures = 0
    _breaker_opened_at = None


def _parse_yes_no(text: str) -> Optional[bool]:
    """First YES/NO token, or None when the answer is not clean."""
    for token in str(text or "").strip().upper().split():
        if token in ("YES", "YES.", "YES,"):
            return True
        if token in ("NO", "NO.", "NO,"):
            return False
        if token.startswith("YES") or token.startswith('"YES'):
            return True
        if token.startswith("NO") or token.startswith('"NO'):
            return False
        return None
    return None


async def binary(
    kind: str,
    question: str,
    subject: str,
    llm_service: Any = None,
) -> Optional[bool]:
    """One strictly-scoped yes/no micro-classification.

    Returns True/False on a clean verdict, None when disabled, cached
    as None, timed out, failed, or the answer was anything but a clean
    yes/no. Never raises; callers treat None as "keep the deterministic
    floor".
    """
    if not switch_enabled() or _breaker_tripped():
        return None
    key = _cache_key(kind, subject, question)
    if key in _cache:
        return _cache_get(key)
    if llm_service is None:
        try:
            from core.llm_service import get_llm_service

            llm_service = get_llm_service()
        except Exception as exc:  # noqa: BLE001 — floor behavior follows
            logger.debug("cheap-nlu llm service unavailable: %r", exc)
            return None
    try:
        raw = await asyncio.wait_for(
            llm_service.generate_completion(
                messages=[
                    {"role": "system", "content": (
                        "You answer strict yes/no questions. "
                        "Reply with exactly YES or NO and nothing else.")},
                    {"role": "user", "content": question},
                ],
                model="auto",
                temperature=0.0,
                max_tokens=8,
            ),
            timeout=_CHEAP_NLU_TIMEOUT_S,
        )
    except Exception as exc:  # noqa: BLE001 — includes asyncio.TimeoutError
        _record(False)
        logger.debug("cheap-nlu call failed (%s): %r", kind, exc)
        return None
    text = ""
    if isinstance(raw, dict):
        text = raw.get("text") or raw.get("content") or ""
    elif isinstance(raw, str):
        text = raw
    verdict = _parse_yes_no(text)
    _record(verdict is not None)
    _cache_put(key, verdict)
    return verdict


# ---------------------------------------------------------------------------
# Task-specific prompts (thin, generic across persons/surfaces/domains)
# ---------------------------------------------------------------------------

async def is_source_reference(
    possessive_phrase: str,
    following_noun: str,
    llm_service: Any = None,
) -> Optional[bool]:
    """Is "<Name>'s <noun>" a SOURCE reference (where information came
    from — whose message/email/note to search) rather than an attribute
    the desired data rows carry (manufacturer, owner, organization)?

    The deterministic floor (communication-noun list in
    ``workbook_read_artifact``) answers the obvious cases; this judges
    the tail so behavior does not depend on a noun list staying current.
    None keeps the floor's decision.
    """
    question = (
        'In the phrase "%s\'s %s", does the possessor name WHERE the '
        "information came from (a person or system whose message, "
        "document, or communication should be searched), rather than an "
        "attribute of the data rows being looked up (such as a "
        "manufacturer, vendor, or owner recorded in the rows)? "
        "Answer YES if it is a source/where-to-look reference, NO if it "
        "is a row attribute." % (possessive_phrase, following_noun)
    )
    return await binary(
        "possessive_source_reference", question,
        f"{possessive_phrase}'s {following_noun}", llm_service)


async def refers_to_resolved_file(
    message: str,
    file_name: str,
    llm_service: Any = None,
) -> Optional[bool]:
    """Does this message ask to look something up inside the file the
    conversation already resolved, referring to it generically ("the
    workbook", "the document", "the list") without naming it?

    None keeps the deterministic floor's decision (do not resolve).
    """
    question = (
        'The conversation previously resolved the file "%s". Does the '
        "following message ask to look something up INSIDE that file, "
        "referring to it generically (e.g. \"the workbook\", \"the "
        "document\", \"the list\", \"the sheet\") without naming a "
        "different file?\n\nMessage: %s\n\nAnswer YES only if the "
        "message clearly asks to search inside that resolved file." % (
            file_name, (message or "")[:1500])
    )
    return await binary(
        "anaphoric_file_reference", question, file_name, llm_service)
