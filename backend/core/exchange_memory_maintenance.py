"""
Exchange memory maintenance — the sleep-time half of the learning loops
(Letta sleep-time-compute pattern: reads at turn time, upkeep on its own
schedule).

One cycle, four fault-isolated steps:

1. BACKFILL — re-embed rows whose LanceDB vector write failed at capture
   time (embedding model cold-start, LanceDB down). Without this, captured
   examples silently never become retrievable.

2. DISTILL — recurring comment-bearing rejections (>= ATOM_EXCHANGE_DISTILL_MIN
   in the same coarse topic) are distilled into ONE pattern-level
   human_correction lesson via the teaching circuit. Single corrections are
   taught per-event at capture; this catches the "the same thing keeps going
   wrong" signal that one-off lessons miss. Rows are marked consolidated so
   each pattern is distilled once.

3. AUTO-PROMOTE (exchanges) — both mode flags default to ``auto``:
   self-regulating. Auto behaves as shadow until this cycle latches the
   stored value to enforce once the corpus is big enough to retrieve from
   (20+ rated exchanges, 3+ of each). A pinned off/shadow/enforce never
   moves; an env-sourced value is the operator kill-switch and is never
   fought. Promotion is one-way (never auto-demotes).

4. AUTO-PROMOTE (verification panel) — same ``auto`` contract: effective
   shadow (judges vote and are recorded, replies unchanged) until the
   panel's persisted run record (verify_panel_runs, written by verify_reply)
   shows it healthy — enough runs, high ran-rate, meaningful vote agreement
   — then latch to enforce. The panel only ever runs on mission-critical or
   complex turns, which is the built-in cost control.

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
_PANEL_FLAG = "ATOM_VERIFY_PANEL"
_INTERVAL_ENV = "ATOM_EXCHANGE_MAINTENANCE_INTERVAL_MIN"   # default 60 (ops-only, env)
_FIRST_RUN_DELAY_S = 120          # stay out of boot warmup's way
_BACKFILL_CAP = 200               # rows re-embedded per cycle
_DISTILL_CAP_PER_CYCLE = 5
# Exchange-corpus size gate for auto-promotion (fixed defaults; the panel's
# gates are catalog-managed because judges cost money per run, this one
# only needs "enough examples to retrieve from").
_AUTOPROMOTE_MIN_TOTAL = 20
_AUTOPROMOTE_MIN_PER_LABEL = 3

# Opt-ins and health gates are resolved through runtime settings so
# Admin → Learning & Verification manages them (explicit env still wins).


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


def _distill_min() -> int:
    from core.runtime_settings import get_int_setting

    return get_int_setting("ATOM_EXCHANGE_DISTILL_MIN", 3)


def _panel_min_runs() -> int:
    from core.runtime_settings import get_int_setting

    return get_int_setting("ATOM_VERIFY_PANEL_MIN_RUNS", 20)


def _panel_min_ran_rate() -> float:
    from core.runtime_settings import get_float_setting

    return get_float_setting("ATOM_VERIFY_PANEL_MIN_RAN_RATE", 0.9)


def _panel_min_agreement() -> float:
    from core.runtime_settings import get_float_setting

    return get_float_setting("ATOM_VERIFY_PANEL_MIN_AGREEMENT", 0.5)


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
    min_community = _distill_min()

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
    """Latch ATOM_EXCHANGE_MEMORY enforce when mode is ``auto`` (default) and
    the corpus is healthy. A pinned mode (off/shadow/enforce) never moves;
    an env-sourced value is the operator kill-switch and is never fought."""
    from core.exchange_example_service import exchange_memory_setting

    raw, source = exchange_memory_setting(db=db)
    if raw != "auto":
        return {"promoted": False, "reason": f"mode_pinned_{raw}"}
    if source == "env":
        return {"promoted": False, "reason": "explicit_env_kill_switch"}

    counts = _exchange_counts(db)
    total = counts["positive"] + counts["negative"]
    if (
        total < _AUTOPROMOTE_MIN_TOTAL
        or counts["positive"] < _AUTOPROMOTE_MIN_PER_LABEL
        or counts["negative"] < _AUTOPROMOTE_MIN_PER_LABEL
    ):
        return {"promoted": False, "reason": "corpus_too_small", "counts": counts}

    _latch_runtime_setting(db, _MODE_FLAG)
    logger.info(
        "exchange memory: corpus healthy (%d pos / %d neg) — latched "
        "ATOM_EXCHANGE_MEMORY auto→enforce via runtime settings",
        counts["positive"], counts["negative"],
    )
    return {"promoted": True, "counts": counts}


# ---------------------------------------------------------------------------
# Step 4: opt-in verification-panel promotion (shadow → enforce latch)
# ---------------------------------------------------------------------------

def _maybe_auto_promote_panel(db) -> Dict[str, Any]:
    """Latch ATOM_VERIFY_PANEL enforce when mode is ``auto`` (default) and
    the panel's persisted run record is healthy (enough runs, high ran-rate,
    meaningful agreement). A pinned mode never moves; env never fought."""
    from core.runtime_settings import resolve_setting
    from core.verify_panel import get_panel_run_stats

    res = resolve_setting(_PANEL_FLAG, db=db)
    raw = str(res.value or "auto").strip().lower()
    if raw != "auto":
        return {"promoted": False, "reason": f"mode_pinned_{raw}"}
    if res.source == "env":
        return {"promoted": False, "reason": "explicit_env_kill_switch"}

    stats = get_panel_run_stats(db)
    if stats["total"] < _panel_min_runs():
        return {"promoted": False, "reason": "not_enough_runs", "stats": stats}
    if stats["ran_rate"] < _panel_min_ran_rate():
        return {"promoted": False, "reason": "panel_flaky", "stats": stats}
    if stats["mean_agreement"] < _panel_min_agreement():
        return {"promoted": False, "reason": "votes_not_meaningful", "stats": stats}

    _latch_runtime_setting(db, _PANEL_FLAG)
    logger.info(
        "verify panel: healthy over %d runs (ran_rate=%.2f, agreement=%.2f) "
        "— latched ATOM_VERIFY_PANEL auto→enforce via runtime settings",
        stats["total"], stats["ran_rate"], stats["mean_agreement"],
    )
    return {"promoted": True, "stats": stats}


def _latch_runtime_setting(db, key: str) -> None:
    """Upsert the runtime-settings row (env still wins as kill-switch) and
    drop the settings cache so the next read sees the latch."""
    from core.models import RuntimeSetting
    from core.runtime_settings import invalidate_settings_cache

    row = db.query(RuntimeSetting).filter(RuntimeSetting.key == key).first()
    if row is None:
        row = RuntimeSetting(key=key, updated_by="exchange_maintenance")
        db.add(row)
    row.value_json = "enforce"
    db.commit()
    invalidate_settings_cache()


# ---------------------------------------------------------------------------
# Cycle + loop
# ---------------------------------------------------------------------------

async def run_maintenance_cycle(db) -> Dict[str, Any]:
    """All four steps, each fault-isolated — a failing store never blocks
    the others. Returns a summary for the log."""
    summary: Dict[str, Any] = {
        "backfilled": 0, "distilled": {}, "promoted": {}, "promoted_panel": {},
    }
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
    try:
        summary["promoted_panel"] = _maybe_auto_promote_panel(db)
    except Exception as e:
        logger.debug("panel auto-promote step failed: %s", e)
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
