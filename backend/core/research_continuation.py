# -*- coding: utf-8 -*-
"""Durable research continuation — finish authorized read jobs after the
interactive turn ends (rounds 52-53).

Substrate: the recurring-task pattern of async_turn_continuation's
terminal-delivery recovery — a lifespan-started loop reading DURABLE
state (the job-work ledger), independent of the scheduler, surviving
restarts.

Round 53 corrections (reviewer):
- PER-ITEM EVIDENCE: a document-level receipt never resolves grouped
  items. Each item is matched individually against structured find_all
  results; only a match carrying the item's own price/value (price-shaped
  column or value) resolves it. Identity-only matches ("located") and
  no-matches leave the question open with the exact next step recorded.
- DURABLE CLAIMS: execution claims live on the questions themselves
  (claim_questions_for_execution, TTL-bounded) — attempt counters are
  retry bounds, not locks. Eligibility is RE-CHECKED against the task
  revision immediately before execution, and jobs whose session ends
  with an unanswered user message are skipped (the interactive lane
  owns them).
- GLOBAL CYCLE BUDGET: at most _CYCLE_MAX_READS document executions per
  CYCLE across all jobs.
- STRUCTURED INPUTS: read actions dispatch from the question's
  structured inputs (item + document) when present; prose is only the
  legacy fallback.
- DELIVERY: the terminal note appends to a FRESHLY re-read session
  history.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_CYCLE_MAX_READS = int(os.getenv("ATOM_RESEARCH_CONTINUATION_MAX_READS",
                                 "4") or 4)
_READ_TIMEOUT_SECONDS = float(
    os.getenv("ATOM_RESEARCH_CONTINUATION_READ_TIMEOUT", "25") or 25)
_INTERVAL_SECONDS = float(
    os.getenv("ATOM_RESEARCH_CONTINUATION_INTERVAL_SECONDS", "45") or 45)
_CLAIM_TTL_SECONDS = float(
    os.getenv("ATOM_RESEARCH_CONTINUATION_CLAIM_TTL", "120") or 120)

_RECOVERY_TASK: "asyncio.Task | None" = None
_WORKER_ID = f"research-worker-{os.getpid()}"

_PRICE_COLUMN_RE = re.compile(
    r"price|cost|list|dealer|net\b|cad\b|us\b", re.IGNORECASE)
_PRICE_VALUE_RE = re.compile(
    r"^[$€£\s]*\d{1,3}(?:[,.]\d{3})*(?:[.,]\d{1,2})?[$\s]*$")


def research_continuation_enabled() -> bool:
    return os.getenv(
        "ATOM_RESEARCH_CONTINUATION_DISABLED", "").strip() not in (
        "1", "true", "yes")


def _lifecycle_for_default_tenant():
    from core.database import get_db_session
    from core.goals.goal_run_service import GoalRunService
    from core.goals.goal_service import GoalService
    from core.task_lifecycle import TaskLifecycle

    return TaskLifecycle(
        GoalRunService(workspace_id="default", tenant_id="default",
                       session_factory=get_db_session),
        GoalService(workspace_id="default", tenant_id="default",
                    session_factory=get_db_session))


def _read_actions(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Eligible read actions, dispatched from STRUCTURED INPUTS when
    present (item + document); prose is the legacy fallback."""
    out = []
    for a in actions or []:
        inputs = a.get("inputs") if isinstance(a.get("inputs"), dict) else {}
        doc = str(inputs.get("file") or "").strip()
        item = str(inputs.get("item") or a.get("item") or "").strip()
        if not doc:
            na = str(a.get("next_action") or "")
            if not na.lower().startswith("read "):
                continue
            doc = na[5:].rsplit(" for ", 1)[0].strip()
            item = item or na[5:].rsplit(" for ", 1)[-1].strip()
        if doc and item:
            out.append({"item": item, "file": doc,
                        "question_id": a.get("question_id")})
    return out


def _classify_match(match: Dict[str, Any]) -> str:
    """"matched" (carries the item's own value), "located" (identity
    only — the price cell was not read), or "" (noise)."""
    column = str(match.get("column") or "")
    value = str(match.get("value") or "")
    if _PRICE_COLUMN_RE.search(column) or (
            value and _PRICE_VALUE_RE.match(value)):
        return "matched"
    return "located"


async def _execute_document_read(
        lifecycle: Any, run_id: str,
        user_id: str, workspace_id: str, file_name: str,
        items: List[str]) -> Dict[str, Any]:
    """One document execution resolving EACH item against its own
    structured find_all matches. Settles on the JOB's run."""
    from core.sheet_dataset_service import find_all_occurrences_sync
    from core.task_lifecycle import (
        finish_retrieval_turn, record_read_outcome)

    statuses: Dict[str, str] = {}
    evidence: List[str] = []
    any_executed = False
    for item in items:
        try:
            scan = await asyncio.wait_for(
                asyncio.to_thread(
                    find_all_occurrences_sync, item, user_id,
                    workspace_id, file_name=file_name, max_matches=8),
                timeout=_READ_TIMEOUT_SECONDS)
            any_executed = True
        except Exception as exc:  # noqa: BLE001 — per-item isolation
            statuses[item] = ""
            evidence.append(f"{item}: lookup failed "
                            f"({type(exc).__name__})")
            continue
        matches = (scan or {}).get("matches") or []
        classified = [(m, _classify_match(m)) for m in matches]
        matched = [m for m, c in classified if c == "matched"]
        if matched:
            statuses[item] = "matched"
            best = matched[0]
            evidence.append(
                f"{item}: price at {best.get('sheet')}/{best.get('cell')}"
                f" = {best.get('value')} (column {best.get('column')})")
        elif classified:
            statuses[item] = "located"
            first = classified[0][0]
            evidence.append(
                f"{item}: located at {first.get('sheet')}/"
                f"{first.get('cell')} (column {first.get('column')}) — "
                "price cell NOT read; question stays open")
        else:
            statuses[item] = ""
            evidence.append(
                f"{item}: no match in this document — question stays open")

    op = lifecycle.create_operation(
        run_id, op_type="retrieve",
        requested_change=(
            f"research continuation read: {file_name[:120]}"))
    _exec_facts = {
        "invoked": any_executed,
        "outcome": ("read_succeeded" if any(
            s == "matched" for s in statuses.values())
            else "read_returned_no_receipt" if any_executed
            else "read_failed"),
        "served_basis": ("saved_copy" if any_executed else "none"),
        "failure_stage": None,
        "items": statuses,
    }
    finish_retrieval_turn(
        lifecycle, run_id, op["operation_id"], {}, None,
        bool(_exec_facts["outcome"] == "read_succeeded"),
        execution=_exec_facts)
    record_read_outcome(
        lifecycle, run_id, op["operation_id"], structured_result=None,
        freshness=None, execution=_exec_facts)
    return {"file": file_name, "statuses": statuses,
            "evidence": evidence}


def _session_owned_by_interactive(sess: Dict[str, Any]) -> bool:
    """True when the session ends with an UNANSWERED user message — the
    interactive lane owns it; the worker must not race it."""
    hist = sess.get("history") or []
    for entry in reversed(hist):
        if not isinstance(entry, dict):
            continue
        msg = str(entry.get("message") or "").strip()
        resp = str(entry.get("response") or "").strip()
        if msg and not resp:
            return True
        if msg or resp:
            return False
    return False


async def research_continuation_cycle(max_reads: int = _CYCLE_MAX_READS
                                      ) -> Dict[str, int]:
    """One bounded pass. The read budget is GLOBAL across jobs."""
    from core.task_lifecycle import (
        claim_questions_for_execution, next_unfinished_work,
        open_unresolved_questions)

    out = {"jobs": 0, "reads": 0, "items_matched": 0,
           "items_located": 0, "failed_reads": 0}
    if not research_continuation_enabled():
        return out
    try:
        from core.chat_session_manager import chat_session_manager

        lifecycle = _lifecycle_for_default_tenant()
        runs = lifecycle.runs.list_runs(include_terminal=False, limit=100)
    except Exception as exc:  # noqa: BLE001
        logger.debug("[research-continuation] enumerate failed: %r", exc)
        return out
    budget = max_reads
    for run in runs or []:
        if budget <= 0:
            break
        run_id = str(run.get("id"))
        try:
            record = lifecycle.get_task(run_id)
            if record is None:
                continue
            work = next_unfinished_work(record)
            acts = _read_actions(work.get("actions") or [])
            if not acts:
                continue
            conv = record.get("conversation_id") or ""
            sess = chat_session_manager.get_session(conv) if conv else None
            if not sess or not str(sess.get("user_id") or "").strip():
                continue
            if _session_owned_by_interactive(sess):
                continue  # the interactive lane owns this job right now
            user_id = str(sess["user_id"])
            workspace_id = str(sess.get("workspace_id") or "default")
            groups: Dict[str, List[Dict[str, Any]]] = {}
            for a in acts:
                groups.setdefault(a["file"], []).append(a)
            out["jobs"] += 1
            notes: List[str] = []
            for fname, group in list(groups.items()):
                if budget <= 0:
                    break
                # ELIGIBILITY RE-CHECK + DURABLE CLAIM (exclusive).
                fresh = lifecycle.get_task(run_id)
                still_open = {
                    str(q.get("question_id"))
                    for q in open_unresolved_questions(fresh or {})}
                qids = [g["question_id"] for g in group
                        if g.get("question_id") in still_open]
                if not qids:
                    continue
                claimed = claim_questions_for_execution(
                    lifecycle, run_id, qids, by=_WORKER_ID,
                    ttl_seconds=_CLAIM_TTL_SECONDS)
                if not claimed:
                    continue  # another worker holds a fresh claim
                budget -= 1
                out["reads"] += 1
                res = await _execute_document_read(
                    lifecycle, run_id, user_id, workspace_id, fname,
                    [g["item"] for g in group])
                # IDENTICAL-REDISCOVERY BOUND (round 53): items this
                # execution did NOT match consume an attempt — the cap
                # eventually exhausts a located-only loop instead of
                # re-reading the same document forever.
                from core.task_lifecycle import bump_question_attempts

                bump_question_attempts(
                    lifecycle, run_id,
                    [g["question_id"] for g, it in zip(
                        group, [g["item"] for g in group])
                        if res["statuses"].get(it) != "matched"
                        and g.get("question_id")])
                out["items_matched"] += sum(
                    1 for s in res["statuses"].values() if s == "matched")
                out["items_located"] += sum(
                    1 for s in res["statuses"].values() if s == "located")
                notes.append(f"{fname}: " + "; ".join(res["evidence"]))
            if notes:
                try:
                    fresh_sess = chat_session_manager.get_session(conv)
                    if fresh_sess and not _session_owned_by_interactive(
                            fresh_sess):
                        hist = list(fresh_sess.get("history") or [])
                        hist.append({
                            "message": "",
                            "response": (
                                "Background research update — completed "
                                "while you were away: "
                                + " | ".join(notes)
                                + ". Remaining work stays on the job "
                                  "record."),
                            "timestamp": time.time(),
                        })
                        chat_session_manager.update_session_activity(
                            conv, history=hist)
                except Exception:  # noqa: BLE001 — ledger is the record
                    pass
        except Exception as exc:  # noqa: BLE001 — per-job isolation
            out["failed_reads"] += 1
            logger.warning("[research-continuation] job %s failed: %r",
                           str(run_id)[:8], exc)
    if out["reads"]:
        logger.info("[research-continuation] cycle: %s", out)
    return out


async def _research_continuation_loop() -> None:
    logger.info("[research-continuation] durable research worker started "
                "(interval %.0fs, max %d reads/cycle GLOBAL)",
                _INTERVAL_SECONDS, _CYCLE_MAX_READS)
    while True:
        try:
            await research_continuation_cycle()
        except asyncio.CancelledError:
            logger.info("[research-continuation] worker stopped")
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("[research-continuation] cycle error: %r", exc)
        await asyncio.sleep(_INTERVAL_SECONDS)


def start_research_continuation() -> bool:
    global _RECOVERY_TASK
    if _RECOVERY_TASK is not None and not _RECOVERY_TASK.done():
        return False
    try:
        _RECOVERY_TASK = asyncio.get_running_loop().create_task(
            _research_continuation_loop())
        return True
    except RuntimeError:
        logger.debug("research continuation not started: no running loop")
        return False


async def stop_research_continuation() -> None:
    global _RECOVERY_TASK
    task = _RECOVERY_TASK
    _RECOVERY_TASK = None
    if task is None:
        return
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):  # noqa: BLE001
        pass
