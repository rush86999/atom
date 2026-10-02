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
  - trigger metrics: every attempt emits one grep-able JSON line
    (``cheap-nlu-metric {...}``) and a counters snapshot is available
    via :func:`metrics_snapshot` — breaker opens, suppressed demand,
    latency, and outcome mix are the recorded expansion triggers for a
    local decision model (RESEARCH_ollaya_jev.md, owner decision +
    Addendum 3);
  - NEVER raising: any doubt returns ``None`` and the caller keeps its
    deterministic-floor behavior (fail-closed).

Callers must be built so that ``None`` (or "no") preserves their
existing deterministic path — the LLM may only REFINE, never gate.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
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
        _emit("breaker_open", cooldown_s=_BREAKER_COOLDOWN_S,
              consecutive_failures=_breaker_failures)


# ---------------------------------------------------------------------------
# Trigger metrics (RESEARCH_ollaya_jev.md owner decision): observability
# ONLY — counters + one JSON log line per event, no behavior change.
# The recorded triggers for expanding to a local decision model are
# (1) breaker opens repeatedly, (2) refinement latency/cost visible in
# real sessions — both readable from these events:
#   grep 'cheap-nlu-metric' backend/logs/uvicorn_*.log | sed 's/.*metric //' | jq -r .event
# ---------------------------------------------------------------------------
_metrics_counters: Dict[str, int] = {}
_metrics_by_kind: Dict[str, Dict[str, int]] = {}
_metrics_latency = {"sum_ms": 0.0, "n": 0, "max_ms": 0.0}

_METRIC_PREFIX = "cheap-nlu-metric"


def _emit(event: str, level: int = logging.INFO, **fields: Any) -> None:
    _metrics_counters[event] = _metrics_counters.get(event, 0) + 1
    kind = fields.get("kind")
    if kind:
        per_kind = _metrics_by_kind.setdefault(str(kind), {})
        per_kind[event] = per_kind.get(event, 0) + 1
    if "latency_ms" in fields:
        _metrics_latency["sum_ms"] += float(fields["latency_ms"])
        _metrics_latency["n"] += 1
        _metrics_latency["max_ms"] = max(
            _metrics_latency["max_ms"], float(fields["latency_ms"]))
    try:
        logger.log(level, "%s %s", _METRIC_PREFIX,
                   json.dumps({"event": event, **fields}, default=str))
    except Exception:  # noqa: BLE001 — metrics must never disturb the floor
        pass


def metrics_snapshot() -> Dict[str, Any]:
    """Counters since process start (or the last ``reset_for_tests``).

    Read-only view for tests, debugging, or a future debug endpoint:
    ``counters`` per event, ``by_kind`` per question kind, and LLM-call
    latency aggregates. The durable trail is the ``cheap-nlu-metric``
    log lines — counters reset on restart, the log does not.
    """
    return {
        "counters": dict(_metrics_counters),
        "by_kind": {k: dict(v) for k, v in _metrics_by_kind.items()},
        "llm_latency": dict(_metrics_latency),
    }


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
    """Clear cache + breaker + metric state (test-only)."""
    global _breaker_failures, _breaker_opened_at
    _cache.clear()
    _breaker_failures = 0
    _breaker_opened_at = None
    _metrics_counters.clear()
    _metrics_by_kind.clear()
    _metrics_latency.update({"sum_ms": 0.0, "n": 0, "max_ms": 0.0})


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
    if not switch_enabled():
        _emit("skipped_disabled", kind=kind)
        return None
    if _breaker_tripped():
        # Suppressed demand is trigger-1 evidence: the floor kept serving
        # while every refinement question bounced off an open breaker.
        _emit("skipped_breaker_open", kind=kind, level=logging.WARNING)
        return None
    key = _cache_key(kind, subject, question)
    if key in _cache:
        _emit("cache_hit", kind=kind)
        return _cache_get(key)
    if llm_service is None:
        try:
            from core.llm_service import get_llm_service

            llm_service = get_llm_service()
        except Exception as exc:  # noqa: BLE001 — floor behavior follows
            logger.debug("cheap-nlu llm service unavailable: %r", exc)
            return None
    started = time.perf_counter()
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
    except asyncio.TimeoutError:
        _emit("llm_call", kind=kind, level=logging.WARNING,
              outcome="timeout", latency_ms=round(
                  (time.perf_counter() - started) * 1000, 1),
              timeout_s=_CHEAP_NLU_TIMEOUT_S)
        _record(False)
        return None
    except Exception as exc:  # noqa: BLE001 — floor behavior follows
        _emit("llm_call", kind=kind, level=logging.WARNING,
              outcome="error", latency_ms=round(
                  (time.perf_counter() - started) * 1000, 1),
              error=type(exc).__name__)
        _record(False)
        logger.debug("cheap-nlu call failed (%s): %r", kind, exc)
        return None
    text = ""
    if isinstance(raw, dict):
        text = raw.get("text") or raw.get("content") or ""
    elif isinstance(raw, str):
        text = raw
    verdict = _parse_yes_no(text)
    _emit("llm_call", kind=kind,
          outcome="ok" if verdict is not None else "unparseable",
          latency_ms=round((time.perf_counter() - started) * 1000, 1))
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
    context_hint: str = "",
) -> Optional[bool]:
    """Is this message's PRIMARY intent a lookup in — or a question about
    the results of lookups in — the file the conversation already
    resolved?

    Covers every indirect-reference shape, not just the generic-noun
    form: "the workbook/the list/our sheet" (generic noun), "search the
    catalog to confirm the rows from the email" (file as direct object,
    other sources as provenance), "what was not found" (results
    reference), "confirm the draft numbers against the book" (verification
    target). The deterministic floors stay the fast path for the shapes
    they know; this judges the residue so behavior does not depend on a
    phrasing list anticipating every user's vocabulary (2026-10-01: ten
    rounds of live phrasing misses proved it cannot).

    None keeps the deterministic floor's decision (do not resolve).
    """
    context = f"\nConversation context: {context_hint[:600]}" if context_hint else ""
    question = (
        'The conversation previously resolved the file "%s" and has been '
        "running lookups against it.%s\n\nDoes the following message's "
        "PRIMARY intent involve THAT file — looking something up inside "
        "it, checking/confirming values against it, or asking about the "
        "results of lookups in it (which items were found / not found / "
        "missing / need confirmation)? The file may be referenced "
        "indirectly (a generic noun like the workbook/the list/the "
        "sheet, or entirely implicitly through its results). Mentioning "
        "another source (e.g. rows found in an email) is fine when the "
        "file is still the target being searched or confirmed against."
        "\n\nAnswer NO if the message primarily asks about a different "
        "source (emails, chats, CRM records on their own), asks to "
        "send/modify/forward something, or has nothing to do with the "
        "file's data.\n\nMessage: %s\n\nAnswer YES only if that file "
        "is what the message needs searched, confirmed, or asked about." % (
            file_name, context, (message or "")[:1500])
    )
    return await binary(
        "anaphoric_file_reference", question, file_name, llm_service)


async def refers_to_prior_retrieval(
    message: str,
    llm_service: Any = None,
) -> Optional[bool]:
    """OBJECTIVE anaphora: does this message refer to lookup RESULTS from
    EARLIER in the conversation (asking to show, re-run, check or refine
    them), rather than asking for the file's/sheet's contents as such?

    The deterministic floor is the retrieval-noun list in
    ``chat_tool_planner`` ("searches", "results", "lookups", …); this
    judges the residue ("pull up what you found before", "go again on
    those") so behavior does not depend on a noun list staying current.
    None keeps the floor's decision.

    Backend note (repo research, 2026-09-29/30): this question KIND is
    the one the local-decision readouts passed on the labeled gate set
    (JevK5-9B 4/4 with margins; Qwen3.5-4B 4/4) — if an expansion
    trigger fires, a local backend slots in behind this interface
    without touching callers.
    """
    question = (
        "Earlier in this conversation, a lookup was run and results were "
        "shown. Does the following message refer to THOSE EARLIER "
        "RESULTS — asking to show them again, re-run the search, check "
        "them, or narrow them — rather than asking to list a file's or "
        "sheet's contents in general?\n\nMessage: %s\n\nAnswer YES only "
        "if the message clearly refers to the earlier lookup results." % (
            (message or "")[:1500])
    )
    return await binary(
        "anaphoric_prior_retrieval", question, "turn", llm_service)
