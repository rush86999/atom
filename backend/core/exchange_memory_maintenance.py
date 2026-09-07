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

5. KNOWLEDGE PATTERNS (WikiSkill wiki layer, W2+W3) — a balanced sample of
   recent failing (≤5) and passing (≤3) traces per active tenant is
   distilled into knowledge_patterns pages (failure modes with root cause +
   workaround, success strategies). Consumed by the OFFLINE evolver prompts
   only; the runtime agent never reads the raw wiki (W4).

Runs from the app lifespan like the other consolidation loops
(main_api_app.py), gated on ENABLE_SCHEDULER/test-mode there.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

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


# ---------------------------------------------------------------------------
# Step 4b: playbook evidence latch (Playbook Journey P5, default OFF)
# ---------------------------------------------------------------------------

_AUTO_APPROVE_RUNS = 3


async def _auto_approve_playbooks(db) -> Dict[str, Any]:
    """ATOM_PLAYBOOKS_AUTO_APPROVE (default off): a `learned` draft whose
    ORIGIN incident evals pass ``_AUTO_APPROVE_RUNS`` consecutive nightly
    replays is promoted without a human click (approved_by=auto_latch) —
    but only where AUTONOMY already allows no-human-gating, the same
    contract the runtime applies to the hires' own actions
    (core.autonomy_policy.tenant_gate_for_topic): the draft's trigger
    canvas type maps to topics, and every topic must be auto-if-mature
    with ALL active hires clearing the maturity×trust bar. An email-surface
    rule, or one whose crew still proposes, stays human-gated — the streak
    freezes (not resets) until autonomy allows no-human-gating again.
    taught/authored drafts never latch: their approval was always the
    supervisor's own act. The flag is the owner's switch for all of this
    (docs/architecture/PLAYBOOK_USER_JOURNEY.md §6)."""
    summary: Dict[str, Any] = {"latched": 0, "replayed": 0, "autonomy_blocked": 0}
    try:
        from core.models import Playbook
        from core.autonomy_policy import (
            OUTCOME_EXECUTE,
            topics_for_canvas,
            tenant_gate_for_topic,
        )
        from core.playbook_service import playbook_mode
        from core.runtime_settings import resolve_setting

        res = resolve_setting("ATOM_PLAYBOOKS_AUTO_APPROVE", db=db)
        if not res.value:
            summary["reason"] = f"latch_off ({res.source})"
            return summary
        if playbook_mode() == "off":
            summary["reason"] = "playbooks_off"
            return summary

        from core.incident_eval_runner import run_evals

        drafts = (db.query(Playbook)
                  .filter(Playbook.approval_state == "draft")
                  .filter(Playbook.source == "learned")
                  .limit(5).all())
        for row in drafts:
            eval_ids = [oid for oid in (row.origin_ids or [])
                        if isinstance(oid, str)]
            if not eval_ids:
                continue  # no replayable evidence — never latches

            # Autonomy gate FIRST: no point burning replays (or accruing a
            # streak) for a rule the maturity contract would still gate.
            blocks = [
                tgate["reason"]
                for topic in topics_for_canvas(row.trigger_canvas_type)
                for tgate in (tenant_gate_for_topic(db, topic, row.tenant_id),)
                if tgate["outcome"] != OUTCOME_EXECUTE
            ]
            if blocks:
                summary["autonomy_blocked"] += 1
                prev = (row.last_eval_result or {}).get("auto_latch") or {}
                stored = dict(row.last_eval_result or {})
                stored["auto_latch"] = {
                    "passes": prev.get("passes") or 0,
                    "threshold": _AUTO_APPROVE_RUNS,
                    "blocked": blocks[0],
                }
                row.last_eval_result = stored
                continue

            gate = await run_evals(db, tenant_id=row.tenant_id or "default",
                                   eval_ids=eval_ids, llm_service=_default_llm())
            summary["replayed"] += 1
            clean = gate.get("ran", 0) > 0 and gate.get("failed", 0) == 0
            prev = (row.last_eval_result or {}).get("auto_latch") or {}
            streak = (prev.get("passes") or 0) + 1 if clean else 0
            stored = dict(row.last_eval_result or {})
            stored["auto_latch"] = {
                "passes": streak,
                "threshold": _AUTO_APPROVE_RUNS,
                "last_replay": {k: gate.get(k) for k in
                                ("ran", "passed", "failed", "skipped")},
            }
            row.last_eval_result = stored
            if streak >= _AUTO_APPROVE_RUNS:
                row.approval_state = "approved"
                row.approved_by = "auto_latch:evidence"
                summary["latched"] += 1
                logger.info(
                    "playbook evidence latch: '%s' approved after %d clean "
                    "origin-eval replays (ATOM_PLAYBOOKS_AUTO_APPROVE, crew "
                    "autonomy gate clear)",
                    row.name, streak,
                )
        db.commit()
    except Exception as e:
        logger.debug("playbook auto-approve step failed: %s", e)
    return summary


def _correction_rule(row) -> tuple:
    """(short name, rule sentence) a supervisor can actually review, from the
    recurring correction's expected property. Live 2026-09-04: the draft used
    to be named after the fingerprint text ("[identity] recurring correction
    on 4c1986b1…") — zero value to the teacher reviewing the queue."""
    ep = row.expected_property or {}
    kind = str(ep.get("kind") or "").strip()
    value = str(ep.get("value") or "").strip()
    if kind == "excludes" and value:
        rule = (f'Never include \u201c{value}\u201d in drafts of this kind '
                f"— the supervisor removed it in recurring corrections.")
        return f'Never include "{value}"', rule
    if kind == "includes" and value:
        rule = f'Include \u201c{value}\u201d in drafts of this kind before they go out.'
        return f'Include "{value}"', rule
    if kind == "no_unverified":
        return ("No unverified claims",
                "Never state unverified facts as established — mark them as "
                "being confirmed instead.")
    if kind == "changed":
        return ("Match corrected wording",
                "Match the supervisor's corrected wording — do not regenerate "
                "the draft from memory.")
    return ("Apply corrected wording",
            f"Apply the supervisor's corrected wording ({row.taxonomy}).")


def _canvas_title(db, canvas_id) -> Optional[str]:
    """Human canvas name for the review card (the UUID fragment taught the
    reviewer nothing). Fault-isolated: None on any lookup failure."""
    if not canvas_id:
        return None
    try:
        from core.models import Canvas

        row = db.query(Canvas).filter(Canvas.id == canvas_id).first()
        if row is None:
            return None
        return (row.name or "").strip() or None
    except Exception:
        return None


def _draft_playbooks(db) -> Dict[str, Any]:
    """Plan Phase 3: recurring corrections (IncidentEval.occurrences >= 3)
    become draft playbooks (source=learned, approval_state=draft) for
    supervisor review. draft_from_pattern is idempotent per fingerprint —
    reruns bump the existing draft instead of stacking rows. Cap per cycle
    keeps the Training panel's review queue human-sized. Fault-isolated by
    the cycle.

    Review-queue value + version hygiene (live 2026-09-04): drafts carry the
    RULE the corrections imply and the real occurrence count, and identical
    re-runs no longer bump the version — a 6h cycle re-seeing the same
    pattern had inflated one draft to v211, which the panel then rendered as
    "seen 211×". Legacy fingerprint-text drafts are retired in the sweep."""
    summary: Dict[str, Any] = {"drafted": 0, "updated": 0, "unchanged": 0,
                               "retired_legacy": 0}
    try:
        from core.models import IncidentEval, Playbook
        from core.playbook_service import PlaybookService, playbook_mode

        if playbook_mode() == "off":
            return summary

        # Retire the legacy fingerprint-text drafts ("… recurring correction
        # on <uuid>…") — unreadable in the review queue; retirement keeps
        # the trail and drops them from "needs review".
        legacy = (db.query(Playbook)
                  .filter(Playbook.source == "learned")
                  .filter(Playbook.approval_state == "draft")
                  .filter(Playbook.name.like("%recurring correction on %"))
                  .all())
        for row in legacy:
            row.approval_state = "retired"
            summary["retired_legacy"] += 1
        if summary["retired_legacy"]:
            db.commit()

        recurring = (db.query(IncidentEval)
                     .filter(IncidentEval.occurrences >= 3)
                     .order_by(IncidentEval.occurrences.desc())
                     .limit(20).all())
        for row in recurring:
            rule_name, rule = _correction_rule(row)
            name = f"[{row.taxonomy}] {rule_name}"[:80]
            title = _canvas_title(db, row.canvas_id)
            where = f" on \u201c{title}\u201d" if title else ""
            description = (f"From {row.occurrences} recurring supervisor "
                           f"corrections{where}. Review, edit, then approve.")
            steps = [rule]
            svc = PlaybookService(db, tenant_id=row.tenant_id)
            existing = svc.find_by_pattern(name)
            if existing is None:
                # The rule text changed since the last cycle (different
                # fingerprint): find this incident's earlier draft via its
                # origin link and refresh it in place instead of orphaning
                # a stale card in the review queue.
                for cand in (db.query(Playbook)
                             .filter(Playbook.source == "learned")
                             .filter(Playbook.approval_state == "draft")
                             .all()):
                    if row.id in (cand.origin_ids or []):
                        existing = cand
                        break
            if existing is not None:
                # Content-version semantics: refresh ONLY when the rule text
                # actually changed; identical re-runs leave the version alone.
                if ((existing.steps or []) != steps
                        or (existing.description or "") != description
                        or (existing.name or "") != name):
                    existing.name = name
                    existing.steps = steps
                    existing.description = description
                    existing.version = (existing.version or 1) + 1
                    db.commit()
                    summary["updated"] += 1
                else:
                    summary["unchanged"] += 1
                continue
            drafted = svc.draft_from_pattern(
                name,
                trigger_canvas_type=row.canvas_type,
                origin_id=row.id,
                steps=steps,
                description=description,
            )
            if drafted is None:
                continue
            summary["drafted"] += 1
            if summary["drafted"] >= 3:
                break
    except Exception as e:
        logger.debug("playbook drafting skipped: %s", e)
    return summary


# ---------------------------------------------------------------------------
# Step 5: knowledge-pattern maintenance (WikiSkill wiki layer, W2+W3)
# ---------------------------------------------------------------------------

async def _maintain_knowledge_patterns(db) -> Dict[str, Any]:
    """One Wiki-Maintainer iteration per active tenant (capped): balanced
    failing+passing trace sample → distilled knowledge_patterns. The LLM
    path is used when providers are configured; the deterministic path
    (incident evals + tool-error signatures) keeps the wiki growing offline.
    Fault-isolated by the cycle."""
    from core.knowledge_pattern_service import distill_from_traces

    from core.models import AgentEpisode

    since = _recent_window()
    tenant_rows = (
        db.query(AgentEpisode.tenant_id)
        .filter(AgentEpisode.created_at >= since)
        .distinct()
        .limit(3)
        .all()
    )
    llm_service = _default_llm()
    out: Dict[str, Any] = {"tenants": 0, "created": 0, "bumped": 0}
    for (tenant_id,) in tenant_rows:
        if not tenant_id:
            continue
        try:
            res = await distill_from_traces(db, tenant_id, llm_service=llm_service)
            out["tenants"] += 1
            out["created"] += res.get("created", 0)
            out["bumped"] += res.get("bumped", 0)
        except Exception as e:
            logger.debug("pattern distill skipped for tenant: %s", e)
    return out


def _recent_window(days: int = 7):
    from datetime import datetime, timedelta, timezone

    return datetime.now(timezone.utc) - timedelta(days=days)


def _default_llm():
    """Best-effort shared LLM probe (same contract as the eval runner)."""
    try:
        from core.incident_eval_runner import _default_llm_service
        return _default_llm_service()
    except Exception:
        return None


async def _validate_pending_imports(db) -> List[Dict[str, Any]]:
    """WikiSkill W6: move quarantined experience-pack imports through
    validation on THIS installation (advisory kinds auto-activate on a
    clean incident-eval replay; skill kinds wait for human review)."""
    from core.experience_marketplace.transfer_safety import validate_pending_imports

    return await validate_pending_imports(db, llm_service=_default_llm())


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
    try:
        summary["playbook_drafts"] = _draft_playbooks(db)
    except Exception as e:
        logger.debug("playbook draft step failed: %s", e)
    try:
        summary["playbook_auto_approved"] = await _auto_approve_playbooks(db)
    except Exception as e:
        logger.debug("playbook auto-approve step failed: %s", e)
    try:
        summary["patterns"] = await _maintain_knowledge_patterns(db)
    except Exception as e:
        logger.debug("knowledge pattern step failed: %s", e)
    try:
        summary["import_validation"] = await _validate_pending_imports(db)
    except Exception as e:
        logger.debug("import validation step failed: %s", e)
    try:
        from core.db_safety import maintenance_db_safety_step

        # OFF-LOOP: the sqlite snapshot copies the whole DB file; on the
        # event loop it froze every endpoint for its duration.
        summary["db_safety"] = await asyncio.to_thread(maintenance_db_safety_step)
    except Exception as e:
        logger.debug("db safety step failed: %s", e)
    try:
        from core.db_safety import lance_version_cleanup_step

        # OFF-LOOP (wedge root cause, 2026-09-06): cleanup_old_versions is a
        # long-running Rust operation (a busy day creates thousands of table
        # versions) — called directly from this loop task it froze the ENTIRE
        # event loop for minutes at a time: health probes dead, every request
        # starved, the chat "open in canvas" button timing out silently. The
        # faulthandler SIGUSR1 dump pinned the main thread inside
        # lance/dataset.py cleanup_old_versions via this exact call.
        summary["lance_cleanup"] = await asyncio.to_thread(lance_version_cleanup_step)
    except Exception as e:
        logger.debug("lance cleanup step failed: %s", e)
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
            # Live bug (2026-09-02, caught by the WikiSkill live check): the
            # await was missing — the loop logged a bare coroutine object and
            # NO maintenance step (backfill/distill/promote/patterns) ever ran.
            summary = await run_maintenance_cycle(db)
            logger.info("✓ exchange memory maintenance: %s", summary)
        except Exception as e:
            logger.warning(f"exchange memory maintenance failed (non-fatal): {e}")
        finally:
            db.close()
        await asyncio.sleep(interval_s)
