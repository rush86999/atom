"""
Turn Fact Extractor — per-turn durable-fact extraction (Hermes-style memory layer)

Two entrypoints (shared `_extract` core):

* `extract_from_turn(...)` — the `sync_turn()` hook. Called after a ReAct step is
  persisted. Fire-and-forget via `asyncio.create_task`.
* `extract_from_prompt_before_truncation(...)` — the `on_pre_compress()` hook.
  Called when a prompt is about to be truncated. Drained by the ExtractionQueue
  worker — never blocks the user-visible response.

Design contract (see docs/architecture/CONTEXT_MEMORY.md):
  - NEVER raise. Every public method catches all exceptions and returns ``[]``.
  - NEVER silently drop a fact. On hash collision: bump confidence (EWMA) or
    supersede the existing row if new confidence beats it by >0.1.
  - SQL row is the source of truth; LanceDB vector write is best-effort.
  - Regex pre-filter skips ~40% of turns before any LLM call.
  - ``model="fast"`` (haiku/4o-mini/flash) — extraction is classification, not
    reasoning; we deliberately do NOT use ``quality``.
  - 2s timeout (mirrors ``canvas_summary_service.py``).
  - Anti-thrashing via ``TTLCache(ttl=300)`` — self-heals, never permanent lock.
  - Maturity gate: STUDENT agents are read-only; skip extraction entirely.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import string
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.llm_service import get_llm_service
from core.models import TurnFact
from core.turn_fact_categories import ALL_FACT_CATEGORIES, FactCategory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Feature flags (defaults match CLAUDE.md)
# ---------------------------------------------------------------------------
TURN_FACT_EXTRACTION_ENABLED = (
    os.getenv("TURN_FACT_EXTRACTION_ENABLED", "false").lower() == "true"
)
TURN_FACT_PRE_COMPRESS_ENABLED = (
    os.getenv("TURN_FACT_PRE_COMPRESS_ENABLED", "true").lower() == "true"
)
TURN_FACT_VECTOR_RECALL_ENABLED = (
    os.getenv("TURN_FACT_VECTOR_RECALL_ENABLED", "false").lower() == "true"
)
TURN_FACT_MAX_PER_TURN = int(os.getenv("TURN_FACT_MAX_PER_TURN", "5"))
TURN_FACT_EXTRACTION_SAMPLE_RATE = float(
    os.getenv("TURN_FACT_EXTRACTION_SAMPLE_RATE", "1.0")
)

# Tunables
_EXTRACTION_TIMEOUT_S = 2.0
_CONFIDENCE_BEAT_MARGIN = 0.1     # supersede only if new beats old by >0.1
_EWMA_ALPHA = 0.3                 # confidence blend factor on hash collision
_ANTI_THRASH_TTL_S = 300          # 5 min — self-heals, not a permanent lock


# ---------------------------------------------------------------------------
# Regex pre-filter — bail before any LLM call when a turn obviously has no fact
# ---------------------------------------------------------------------------
_DIGIT = re.compile(r"\d")
_CURRENCY = re.compile(r"[$€£¥₹]\s*\d|\d+\s*(?:USD|EUR|GBP|JPY|INR|K|M\b)", re.I)
_DATE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"  # 12/31/26
    r"\d{4}-\d{2}-\d{2}|"                    # 2026-06-24
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?)\b",
    re.I,
)
_MODAL = re.compile(
    r"\b(?:must|should|need(?:\s+to)?|have\s+to|require[ds]?|cannot|can't|do\s+not|don't)\b",
    re.I,
)
_DECISION = re.compile(
    r"\b(?:because|decided|chose|chosen|picked|selected|rejected|opted(?:\s+for)?)\b",
    re.I,
)
_PREFERENCE = re.compile(
    r"\b(?:prefer(?:s|red|ring)?|rather|always|never|usually|want(?:s)?|like(?:s)?)\b",
    re.I,
)
_DEPENDENCY = re.compile(
    r"\b(?:blocks?|depends?\s+on|unblocks?|prerequisite|after\s+that|then\s+we)\b",
    re.I,
)


def _likely_contains_fact(text: str) -> bool:
    """Cheap regex gate. Returns True iff the text *might* contain a durable fact."""
    if not text or len(text) < 5:
        return False
    return bool(
        _CURRENCY.search(text)
        or _DATE.search(text)
        or _MODAL.search(text)
        or _DECISION.search(text)
        or _PREFERENCE.search(text)
        or _DEPENDENCY.search(text)
        or _DIGIT.search(text)
    )


# ---------------------------------------------------------------------------
# Hash normalization — matches must be order-agnostic to surface changes
# ---------------------------------------------------------------------------
_PUNCT_RE = re.compile(r"[" + re.escape(string.punctuation) + r"]")
_WS_RE = re.compile(r"\s+")


def _normalize_fact_text(text: str) -> str:
    """Aggressive normalization so paraphrases hash to the same key."""
    if not text:
        return ""
    t = text.lower().strip()
    t = _PUNCT_RE.sub(" ", t)
    t = _WS_RE.sub(" ", t).strip()
    return t


def compute_content_hash(workspace_id: str, fact_text: str) -> str:
    """Deterministic dedup key. Workspace-scoped so two tenants don't collide."""
    norm = _normalize_fact_text(fact_text)
    raw = f"{workspace_id or ''}::{norm}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Minimal anti-thrashing cache — TTLCache without adding a dep
# ---------------------------------------------------------------------------
class _TTLSet:
    """
    Append-only TTL set. Self-heals after ``ttl`` seconds.
    NOT a permanent lock (Hermes bug). Used only to avoid re-extracting
    the same hash within a short window while a write is in flight.
    """

    __slots__ = ("_store", "ttl", "maxsize")

    def __init__(self, maxsize: int = 10000, ttl: int = _ANTI_THRASH_TTL_S):
        self._store: Dict[str, float] = {}
        self.ttl = ttl
        self.maxsize = maxsize

    def add(self, key: str) -> None:
        self._prune()
        if len(self._store) >= self.maxsize:
            # Drop oldest to bound memory
            oldest = min(self._store.items(), key=lambda kv: kv[1])[0]
            self._store.pop(oldest, None)
        self._store[key] = time.time()

    def __contains__(self, key: str) -> bool:
        ts = self._store.get(key)
        if ts is None:
            return False
        if (time.time() - ts) > self.ttl:
            self._store.pop(key, None)
            return False
        return True

    def _prune(self) -> None:
        if not self._store:
            return
        now = time.time()
        expired = [k for k, ts in self._store.items() if (now - ts) > self.ttl]
        for k in expired:
            self._store.pop(k, None)


# ---------------------------------------------------------------------------
# Extraction prompt — Mem0's 5 categories verbatim, strict output contract
# ---------------------------------------------------------------------------
_EXTRACTION_PROMPT = """You extract DURABLE facts from a single agent turn. A durable fact is something that is:
  - true for a long time (not a transient status), AND
  - useful to recall in future sessions.

Extract ONLY facts in these 5 categories:

1. exact_value      — concrete numbers, dates, amounts, SLAs, thresholds.
                      e.g. "$50K MRR", "7-day SLA", "launch on Mar 14"
2. hard_constraint  — non-negotiable rules or prohibitions.
                      e.g. "must use Stripe", "no PII to OpenAI"
3. decision_reason  — WHY a choice was made, with the rationale.
                      e.g. "chose Postgres for X", "rejected Option B because ..."
4. cross_task_dep   — a dependency or blocker between work items.
                      e.g. "blocks onboarding v2", "depends on auth service"
5. implicit_pref    — a revealed user/agent preference or habit.
                      e.g. "prefers terse responses", "wants bullet points"

RULES:
- Do NOT extract transient state ("currently running", "just sent the email").
- Do NOT extract generic paraphrases ("the user said X" → drop).
- Each fact must fit EXACTLY ONE category. Use the literal category string.
- State the fact as a self-contained sentence (no pronouns, no "as mentioned").
- Maximum {max_facts} facts, ranked by durability. If none qualify, return [].

Return a JSON array (and NOTHING else):
[
  {{"fact": "...", "category": "exact_value", "domain": "finance", "confidence": 0.9}},
  ...
]

If there are no durable facts, return: []

Turn content:
<<<
{text}
>>>
"""


# ---------------------------------------------------------------------------
# Maturity gate
# ---------------------------------------------------------------------------
def _maturity_allows(maturity: Optional[str]) -> bool:
    """
    STUDENT agents are read-only — they must not learn from untrusted input.
    Anything >= INTERN may extract. ``None``/unknown → allow (defensive default
    keeps the feature useful when graduation service is not wired).
    """
    if maturity is None:
        return True
    return str(maturity).upper() != "STUDENT"


# ---------------------------------------------------------------------------
# TurnFactExtractor
# ---------------------------------------------------------------------------
class TurnFactExtractor:
    """
    Single shared extraction core. Two thin public entrypoints.

    Never raises. Failures are logged + return ``[]``.
    """

    EXTRACTION_PROMPT = _EXTRACTION_PROMPT

    def __init__(self, workspace_id: str = "default", tenant_id: str = "default"):
        self.workspace_id = workspace_id or "default"
        self.tenant_id = tenant_id or "default"
        self.llm = get_llm_service(workspace_id=workspace_id, tenant_id=tenant_id)
        self._recent_hashes = _TTLSet()

    # ------------------------------------------------------------------ public

    async def extract_from_turn(
        self,
        *,
        user_request: str,
        thought: Optional[str] = None,
        action: Optional[Any] = None,
        observation: Optional[str] = None,
        final_answer: Optional[str] = None,
        execution_id: Optional[str] = None,
        reasoning_step_id: Optional[str] = None,
        episode_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        maturity: Optional[str] = None,
    ) -> List[TurnFact]:
        """The ``sync_turn()`` hook — compose text from the ReAct step, then extract."""
        try:
            if not _maturity_allows(maturity):
                return []

            # Sample rate — dial down in cost crunch
            if TURN_FACT_EXTRACTION_SAMPLE_RATE < 1.0:
                import random
                if random.random() > TURN_FACT_EXTRACTION_SAMPLE_RATE:
                    return []

            text = _compose_turn_text(
                user_request=user_request,
                thought=thought,
                action=action,
                observation=observation,
                final_answer=final_answer,
            )
            return await self._extract(
                text=text,
                extraction_source="turn",
                execution_id=execution_id,
                reasoning_step_id=reasoning_step_id,
                episode_id=episode_id,
                session_id=session_id,
                user_id=user_id,
            )
        except Exception as e:  # NEVER raise
            logger.warning("turn_fact extract_from_turn failed: %s", e)
            return []

    async def extract_from_prompt_before_truncation(
        self,
        *,
        prompt: str,
        execution_id: Optional[str] = None,
        episode_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[TurnFact]:
        """The ``on_pre_compress()`` hook — drain a prompt before truncation drops facts."""
        try:
            return await self._extract(
                text=prompt,
                extraction_source="pre_compress",
                execution_id=execution_id,
                reasoning_step_id=None,
                episode_id=episode_id,
                session_id=session_id,
                user_id=user_id,
            )
        except Exception as e:  # NEVER raise
            logger.warning("turn_fact extract_from_prompt failed: %s", e)
            return []

    # ------------------------------------------------------------------ core

    async def _extract(
        self,
        *,
        text: str,
        extraction_source: str,
        execution_id: Optional[str],
        reasoning_step_id: Optional[str],
        episode_id: Optional[str],
        session_id: Optional[str],
        user_id: Optional[str],
    ) -> List[TurnFact]:
        if not text:
            return []

        # 1) Regex pre-filter — bail before any LLM call
        if not _likely_contains_fact(text):
            return []

        # 2) LLM call with 2s timeout, model="fast"
        prompt = self.EXTRACTION_PROMPT.format(
            max_facts=TURN_FACT_MAX_PER_TURN, text=text[:8000]
        )
        try:
            raw = await asyncio.wait_for(
                self.llm.generate(
                    prompt=prompt,
                    system_instruction=(
                        "You extract durable facts. Return ONLY a JSON array. "
                        "If none, return []."
                    ),
                    model="fast",
                    temperature=0.0,
                    max_tokens=800,
                ),
                timeout=_EXTRACTION_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            logger.debug("turn_fact LLM call timed out (2s)")
            _increment_failure_counter("timeout")
            return []
        except Exception as e:
            logger.debug("turn_fact LLM call failed: %s", e)
            _increment_failure_counter("llm_error")
            return []

        # 3) Parse — reuse the robust JSON-array extractor logic
        parsed = _extract_json_array(raw)
        if parsed is None:
            logger.warning(
                "turn_fact parse failure — raw output (truncated): %.400s", raw
            )
            _increment_failure_counter("parse_error")
            return []

        # 4) Validate + cap
        facts: List[Dict[str, Any]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            fact_text = (item.get("fact") or "").strip()
            category = (item.get("category") or "").strip()
            if not fact_text or category not in ALL_FACT_CATEGORIES:
                continue
            facts.append(
                {
                    "fact_text": fact_text,
                    "category": category,
                    "domain": (item.get("domain") or "general").strip()[:64],
                    "confidence": _clamp(float(item.get("confidence", 0.8)), 0.0, 1.0),
                    "tags": item.get("tags") if isinstance(item.get("tags"), list) else None,
                }
            )
            if len(facts) >= TURN_FACT_MAX_PER_TURN:
                break

        if not facts:
            return []

        # 5) Persist with dedup
        persisted: List[TurnFact] = []
        for f in facts:
            row = self._persist_one(
                fact_text=f["fact_text"],
                category=f["category"],
                domain=f["domain"],
                confidence=f["confidence"],
                tags=f["tags"],
                extraction_source=extraction_source,
                execution_id=execution_id,
                reasoning_step_id=reasoning_step_id,
                episode_id=episode_id,
                session_id=session_id,
                user_id=user_id,
            )
            if row is not None:
                persisted.append(row)

        # 6) Best-effort LanceDB write — never blocks SQL success.
        #    SQL rows are already committed; this MUST NOT raise.
        if persisted:
            try:
                self._write_vectors_best_effort(persisted, text)
            except Exception as e:
                logger.debug("turn_fact vector write swallowed: %s", e)

        return persisted

    # ------------------------------------------------------------------ persist

    def _persist_one(
        self,
        *,
        fact_text: str,
        category: str,
        domain: str,
        confidence: float,
        tags: Optional[List[str]],
        extraction_source: str,
        execution_id: Optional[str],
        reasoning_step_id: Optional[str],
        episode_id: Optional[str],
        session_id: Optional[str],
        user_id: Optional[str],
    ) -> Optional[TurnFact]:
        """Insert with dedup. Returns the canonical row (newly inserted or updated existing)."""
        content_hash = compute_content_hash(self.workspace_id, fact_text)

        # Anti-thrashing — a recent write is already in flight for this hash
        if content_hash in self._recent_hashes:
            return None

        try:
            with SessionLocal() as db:
                existing = (
                    db.query(TurnFact)
                    .filter(
                        TurnFact.workspace_id == self.workspace_id,
                        TurnFact.content_hash == content_hash,
                    )
                    .first()
                )

                if existing is None:
                    row = TurnFact(
                        id=str(uuid.uuid4()),
                        tenant_id=self.tenant_id if self.tenant_id != "default" else None,
                        workspace_id=self.workspace_id,
                        user_id=user_id,
                        execution_id=execution_id,
                        reasoning_step_id=reasoning_step_id,
                        episode_id=episode_id,
                        session_id=session_id,
                        extraction_source=extraction_source,
                        fact_text=fact_text,
                        category=category,
                        domain=domain,
                        tags=tags,
                        confidence=confidence,
                        content_hash=content_hash,
                        status="active",
                    )
                    db.add(row)
                    try:
                        db.commit()
                    except IntegrityError:
                        # Race: another worker inserted first. EWMA-bump the winner.
                        db.rollback()
                        return self._ewma_bump_existing(db, content_hash, confidence)
                    db.refresh(row)
                    self._recent_hashes.add(content_hash)
                    return row

                # Collision — supersede or EWMA bump
                if confidence > (existing.confidence or 0.0) + _CONFIDENCE_BEAT_MARGIN:
                    # New fact meaningfully stronger — supersede + insert
                    existing.status = "superseded"
                    existing.superseded_at = func_now()
                    row = TurnFact(
                        id=str(uuid.uuid4()),
                        tenant_id=self.tenant_id if self.tenant_id != "default" else None,
                        workspace_id=self.workspace_id,
                        user_id=user_id,
                        execution_id=execution_id,
                        reasoning_step_id=reasoning_step_id,
                        episode_id=episode_id,
                        session_id=session_id,
                        extraction_source=extraction_source,
                        fact_text=fact_text,
                        category=category,
                        domain=domain,
                        tags=tags,
                        confidence=confidence,
                        content_hash=content_hash,
                        status="active",
                    )
                    db.add(row)
                    db.commit()
                    db.refresh(row)
                    self._recent_hashes.add(content_hash)
                    return row

                # Else: confidence close — EWMA bump + touch created_at
                return self._ewma_bump_existing(db, content_hash, confidence)
        except Exception as e:
            logger.warning("turn_fact persist failed (hash=%s): %s", content_hash[:10], e)
            return None

    def _ewma_bump_existing(
        self, db: Session, content_hash: str, new_conf: float
    ) -> Optional[TurnFact]:
        existing = (
            db.query(TurnFact)
            .filter(
                TurnFact.workspace_id == self.workspace_id,
                TurnFact.content_hash == content_hash,
                TurnFact.status == "active",
            )
            .first()
        )
        if existing is None:
            return None
        blended = ((1.0 - _EWMA_ALPHA) * (existing.confidence or 0.0)) + (
            _EWMA_ALPHA * new_conf
        )
        existing.confidence = _clamp(blended, 0.0, 1.0)
        # Touch created_at so the row stays "fresh" for recency-based retrieval
        existing.created_at = func_now()
        db.commit()
        db.refresh(existing)
        self._recent_hashes.add(content_hash)
        return existing

    # ------------------------------------------------------------------ vector

    def _write_vectors_best_effort(self, rows: List[TurnFact], source_text: str) -> None:
        """
        Best-effort LanceDB write. SQL row is already committed.
        If this fails, we log + continue (SQL row still queryable via Tier-1).
        """
        try:
            from core.turn_fact_vector_store import write_turn_fact_vectors

            write_turn_fact_vectors(rows=rows, source_text=source_text)
        except Exception as e:
            logger.debug("turn_fact LanceDB write skipped: %s", e)


# ---------------------------------------------------------------------------
# Compose helpers + small utilities
# ---------------------------------------------------------------------------
def _compose_turn_text(
    *,
    user_request: str,
    thought: Optional[str],
    action: Optional[Any],
    observation: Optional[str],
    final_answer: Optional[str],
) -> str:
    parts: List[str] = []
    if user_request:
        parts.append(f"USER: {user_request}")
    if thought:
        parts.append(f"THOUGHT: {thought}")
    if action:
        # action may be a dict (ReAct action) or a string
        if isinstance(action, (dict,)):
            parts.append(f"ACTION: {json.dumps(action)[:500]}")
        else:
            parts.append(f"ACTION: {str(action)[:500]}")
    if observation:
        parts.append(f"OBSERVATION: {observation}")
    if final_answer:
        parts.append(f"ANSWER: {final_answer}")
    return "\n".join(parts)


def _extract_json_array(raw: str) -> Optional[List[Any]]:
    """
    Robust JSON-array extraction. Mirrors PolicyFactExtractor._extract_json but
    returns ``None`` (not ``[]``) on hard parse failure so the caller can
    increment a distinct failure counter — never a silent drop (Hermes bug).
    """
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        # Some models wrap in {"facts": [...]}
        if isinstance(data, dict):
            for k in ("facts", "result", "data"):
                v = data.get(k)
                if isinstance(v, list):
                    return v
        return None
    except Exception:
        pass

    # Fallback — locate the outermost array
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end > start:
        try:
            data = json.loads(raw[start : end + 1])
            if isinstance(data, list):
                return data
        except Exception:
            return None
    return None


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def func_now():
    """Lazy import of timezone-aware now to avoid module-level SQLAlchemy dep."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Failure counter (Prometheus-style, log-backed for now)
# ---------------------------------------------------------------------------
_FAILURE_COUNTS: Dict[str, int] = {"timeout": 0, "llm_error": 0, "parse_error": 0}


def _increment_failure_counter(kind: str) -> None:
    _FAILURE_COUNTS[kind] = _FAILURE_COUNTS.get(kind, 0) + 1
    # Structured log — operators can wire Prometheus from this
    logger.warning("turn_fact_extraction_failure total=%s", _FAILURE_COUNTS)


def get_failure_counts() -> Dict[str, int]:
    """Read-only snapshot for /health/metrics or admin dashboards."""
    return dict(_FAILURE_COUNTS)


# ---------------------------------------------------------------------------
# Singleton accessor — mirrors get_policy_fact_extractor
# ---------------------------------------------------------------------------
_extractors: Dict[str, TurnFactExtractor] = {}


def get_turn_fact_extractor(
    workspace_id: str = "default", tenant_id: str = "default"
) -> TurnFactExtractor:
    """Get or create a TurnFactExtractor for the workspace."""
    cache_key = f"{workspace_id}:{tenant_id}"
    if cache_key not in _extractors:
        _extractors[cache_key] = TurnFactExtractor(workspace_id, tenant_id)
    return _extractors[cache_key]


# ---------------------------------------------------------------------------
# Tier-1 retrieval helper — pure SQL, used in prompt assembly
# ---------------------------------------------------------------------------
def get_active_facts_for_prompt(
    db: Session,
    workspace_id: str,
    limit: int = 5,
    categories: Optional[Tuple[str, ...]] = None,
) -> List[TurnFact]:
    """
    Pure-SQL Tier-1 recall. Latency ~1-3ms SQLite, sub-ms Postgres.
    Returns the most recent ``limit`` active facts for the workspace.

    Optional ``categories`` filter — pass a subset of FactCategory values to
    restrict (e.g. hard constraints only).
    """
    try:
        q = db.query(TurnFact).filter(
            TurnFact.workspace_id == workspace_id,
            TurnFact.status == "active",
        )
        if categories:
            q = q.filter(TurnFact.category.in_(categories))
        return (
            q.order_by(TurnFact.created_at.desc(), TurnFact.confidence.desc())
            .limit(limit)
            .all()
        )
    except Exception as e:
        logger.warning("get_active_facts_for_prompt failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Tier-2 retrieval — LanceDB-backed semantic recall (opt-in)
# ---------------------------------------------------------------------------
_TRIVIAL_QUERIES = {"hi", "hey", "hello", "thanks", "thank you", "ok", "okay", "yo"}


def prefetch_relevant_facts(
    workspace_id: str,
    query: str,
    limit: int = 5,
) -> List[TurnFact]:
    """
    Tier-2 recall — called ONCE at execute() entry (not per ReAct step, to avoid
    N× embedding cost). Embeds the query via FastEmbed/OpenAI (10-20ms), searches
    the LanceDB ``turn_facts`` table, hydrates from SQL via ``vector_id``.

    Skipped for trivial queries ("hi", "thanks", ...).
    Gated by ``TURN_FACT_VECTOR_RECALL_ENABLED`` (default OFF — adds embedding latency).
    Never raises.
    """
    if not TURN_FACT_VECTOR_RECALL_ENABLED:
        return []
    if not query or query.strip().lower() in _TRIVIAL_QUERIES:
        return []
    if len(query.strip()) < 4:
        return []

    try:
        from core.turn_fact_vector_store import search_relevant_fact_ids

        ids = search_relevant_fact_ids(
            workspace_id=workspace_id, query=query, limit=limit
        )
        if not ids:
            return []
        with SessionLocal() as db:
            rows = (
                db.query(TurnFact)
                .filter(
                    TurnFact.id.in_(ids),
                    TurnFact.status == "active",
                )
                .all()
            )
            # Preserve relevance order from LanceDB
            order = {rid: i for i, rid in enumerate(ids)}
            rows.sort(key=lambda r: order.get(r.id, 999))
            return rows
    except Exception as e:
        logger.debug("prefetch_relevant_facts failed: %s", e)
        return []
