"""
Exchange memory maintenance — the sleep-time half of the rated-exchange
learning loop (Letta sleep-time-compute pattern: reads at turn time, upkeep
on its own schedule).

One cycle, three fault-isolated steps over the ExchangeExample corpus:

1. BACKFILL — re-embed rows whose LanceDB vector write failed at capture
   time (embedding model cold-start, LanceDB down). Without this, captured
   examples silently never become retrievable.

2. DISTILL — recurring comment-bearing rejections (>= ATOM_EXCHANGE_DISTILL_MIN
   in the same coarse topic) are distilled into ONE pattern-level
   human_correction lesson via the teaching circuit. Single corrections are
   taught per-event at capture; this catches the "the same thing keeps going
   wrong" signal that one-off lessons miss. Rows are marked consolidated so
   each pattern is distilled once.

3. AUTO-PROMOTE — opt-in (ATOM_EXCHANGE_AUTO_PROMOTE): latch
   ATOM_EXCHANGE_MEMORY shadow→enforce via the runtime-settings row once the
   corpus is big enough to retrieve from (default 20 examples, >=3 of each
   label). An explicit env var always wins as kill-switch and is never
   fought by automation; promotion is one-way (never auto-demotes).

Runs from the app lifespan like the other consolidation loops
(main_api_app.py), gated on ENABLE_SCHEDULER/test-mode there.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_MODE_FLAG = "ATOM_EXCHANGE_MEMORY"
_INTERVAL_ENV = "ATOM_EXCHANGE_MAINTENANCE_INTERVAL_MIN"   # default 60
_FIRST_RUN_DELAY_S = 120          # stay out of boot warmup's way
_BACKFILL_CAP = 200               # rows re-embedded per cycle
_DISTILL_MIN_ENV = "ATOM_EXCHANGE_DISTILL_MIN"
_DISTILL_MIN_DEFAULT = 3          # rejections per topic before distilling
_DISTILL_CAP_PER_CYCLE = 5
_AUTOPROMOTE_ENV = "ATOM_EXCHANGE_AUTO_PROMOTE"            # default: off
_AUTOPROMOTE_MIN_TOTAL = 20
_AUTOPROMOTE_MIN_PER_LABEL = 3


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Step 1: backfill missing vectors
# ---------------------------------------------------------------------------

def _backfill_vectors(db) -> int:
    from core.exchange_example_service import _write_vector
    from core.models import ExchangeExample

    rows = (
        db.query(ExchangeExample)
        .filter(ExchangeExample.embedded.is_(False))
        .limit(_BACKFILL_CAP)
        .all()
    )
    fixed = 0
    for row in rows:
        if _write_vector(row):
            row.embedded = True
            fixed += 1
    if fixed:
        db.commit()
    return fixed


# ---------------------------------------------------------------------------
# Step 2: distill recurring comment-bearing rejections
# ---------------------------------------------------------------------------

def _topic_key(query: str) -> str:
    """Coarse grouping key: the query's top content words, order-normalized
    ("email the customer" and "customer email please" must land in one
    bucket). Deliberately coarse — a missed grouping only delays
    distillation by one cycle, while an over-broad one is prevented by the
    count threshold."""
    from core.exchange_example_service import _topic_for_query

    return " ".join(sorted(_topic_for_query(query).split()))


def _distill_lesson(community: List[Any]) -> str:
    """One pattern-level lesson text from a bucket of comment-bearing
    rejections. Quotes a couple of representative reasons — the lesson must
    be actionable, not 'avoid that'."""
    reasons = []
    for r in community:
        c = (getattr(r, "comment", "") or "").strip()
        if c and c.lower() != "regenerated" and c not in reasons:
            reasons.append(c)
    reasons = reasons[:3]
    reason_text = " / ".join(f"\"{r[:120]}\"" for r in reasons) or "no reason recorded"
    sample_query = (getattr(community[0], "user_query", "") or "")[:120]
    return (
        f"Recurring correction — {len(community)} similar answers were rejected "
        f"by humans for requests like \"{sample_query}\". Reported problems: "
        f"{reason_text}. For requests of this kind, avoid the rejected "
        f"approach and address the reported problems explicitly."
    )


async def _consolidate_recurring_negatives(db) -> Dict[str, Any]:
    from core.models import ExchangeExample
    from core.student_learning_service import auto_observe

    unconsolidated = (
        db.query(ExchangeExample)
        .filter(
            ExchangeExample.label == "negative",
            ExchangeExample.consolidated.is_(False),
            ExchangeExample.comment.isnot(None),
        )
        .order_by(ExchangeExample.created_at.asc())
        .limit(500)
        .all()
    )
    min_community = _env_int(_DISTILL_MIN_ENV, _DISTILL_MIN_DEFAULT)

    buckets: Dict[tuple, List[Any]] = {}
    for row in unconsolidated:
        # A workspace is the teaching scope (students learn per-workspace).
        buckets.setdefault(
            (row.workspace_id or "default", _topic_key(row.user_query)), []
        ).append(row)

    distilled: Dict[str, Any] = {"lessons": 0, "topics": [], "rows_marked": 0}
    for (workspace_id, topic), community in buckets.items():
        if len(community) < min_community:
            continue
        if distilled["lessons"] >= _DISTILL_CAP_PER_CYCLE:
            break
        await auto_observe(
            workspace_id=workspace_id,
            observation_type="human_correction",
            summary=_distill_lesson(community),
            details={
                "distilled": True,
                "topic": topic,
                "example_count": len(community),
                "example_ids": [r.id for r in community][:20],
            },
        )
        for row in community:
            row.consolidated = True
        distilled["lessons"] += 1
        distilled["topics"].append(topic)
        distilled["rows_marked"] += len(community)

    if distilled["rows_marked"]:
        db.commit()
    return distilled


# ---------------------------------------------------------------------------
# Step 3: opt-in auto-promotion (shadow → enforce latch)
# ---------------------------------------------------------------------------

def _exchange_counts(db) -> Dict[str, int]:
    from core.models import ExchangeExample

    rows = db.query(ExchangeExample.label).all()
    labels = [r[0] for r in rows]
    return {
        "positive": sum(1 for l in labels if l == "positive"),
        "negative": sum(1 for l in labels if l == "negative"),
    }


def _maybe_auto_promote(db) -> Dict[str, Any]:
    from core.exchange_example_service import exchange_memory_mode

    if os.getenv(_AUTOPROMOTE_ENV, "").strip().lower() not in ("1", "true", "yes", "on"):
        return {"promoted": False, "reason": "auto_promote_disabled"}
    # An explicit env var is the operator's kill-switch: never fight it.
    if _MODE_FLAG in os.environ:
        return {"promoted": False, "reason": "explicit_env_kill_switch"}
    current = exchange_memory_mode()
    if current != "shadow":
        return {"promoted": False, "reason": f"mode_is_{current}"}

    counts = _exchange_counts(db)
    total = counts["positive"] + counts["negative"]
    if (
        total < _AUTOPROMOTE_MIN_TOTAL
        or counts["positive"] < _AUTOPROMOTE_MIN_PER_LABEL
        or counts["negative"] < _AUTOPROMOTE_MIN_PER_LABEL
    ):
        return {"promoted": False, "reason": "corpus_too_small", "counts": counts}

    from core.models import RuntimeSetting
    from core.runtime_settings import invalidate_settings_cache

    row = db.query(RuntimeSetting).filter(RuntimeSetting.key == _MODE_FLAG).first()
    if row is None:
        row = RuntimeSetting(key=_MODE_FLAG, updated_by="exchange_maintenance")
        db.add(row)
    row.value_json = "enforce"
    db.commit()
    invalidate_settings_cache()
    logger.info(
        "exchange memory: corpus healthy (%d pos / %d neg) — latched "
        "ATOM_EXCHANGE_MEMORY shadow→enforce via runtime settings",
        counts["positive"], counts["negative"],
    )
    return {"promoted": True, "counts": counts}


# ---------------------------------------------------------------------------
# Cycle + loop
# ---------------------------------------------------------------------------

async def run_maintenance_cycle(db) -> Dict[str, Any]:
    """All three steps, each fault-isolated — a failing store never blocks
    the others. Returns a summary for the log."""
    summary: Dict[str, Any] = {"backfilled": 0, "distilled": {}, "promoted": {}}
    try:
        summary["backfilled"] = _backfill_vectors(db)
    except Exception as e:
        logger.debug("exchange backfill step failed: %s", e)
    try:
        summary["distilled"] = await _consolidate_recurring_negatives(db)
    except Exception as e:
        logger.debug("exchange distill step failed: %s", e)
    try:
        summary["promoted"] = _maybe_auto_promote(db)
    except Exception as e:
        logger.debug("exchange auto-promote step failed: %s", e)
    return summary


async def exchange_maintenance_loop() -> None:
    """Background loop — mirrors the POMDP consolidation loop wiring in
    main_api_app.py: SessionLocal per cycle (returned to pool), never raises.
    """
    from core.database import SessionLocal

    interval_s = max(5, _env_int(_INTERVAL_ENV, 60)) * 60
    await asyncio.sleep(_FIRST_RUN_DELAY_S)
    while True:
        db = SessionLocal()
        try:
            summary = run_maintenance_cycle(db)
            logger.info("✓ exchange memory maintenance: %s", summary)
        except Exception as e:
            logger.warning(f"exchange memory maintenance failed (non-fatal): {e}")
        finally:
            db.close()
        await asyncio.sleep(interval_s)
