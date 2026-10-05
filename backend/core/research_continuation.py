# -*- coding: utf-8 -*-
"""Durable research continuation — finish authorized read jobs after the
interactive turn ends (round 52, the autonomous-completion milestone).

The substrate is the same pattern as async_turn_continuation's terminal-
delivery recovery: a recurring task started at app lifespan, independent
of the scheduler, that reads DURABLE state (the job-work ledger on
GoalRun parameters) and acts on it — so it survives restarts and never
depends on a live websocket or an operator pressing "continue".

What a cycle does, per active job with eligible pending reads:
1. SELECT: next_unfinished_work actions whose next_action is a targeted
   read ("read <document> for <item>"), grouped per document (one
   execution serves every co-targeted item).
2. CLAIM: bump_question_attempts — the attempt counter is both the
   dedup marker and the retry bound; a crash mid-execution leaves a
   bounded, honest attempt.
3. EXECUTE: the datasets read path via execute_tool_plan (read-only —
   no edit/send authority exists in this lane).
4. SETTLE: begin/finish/record_read_outcome with execution facts; the
   completion rule retires the read questions (verification-kind only)
   and spawns the freshness successor automatically.
5. DELIVER: a truthful terminal note appended to the session history —
   what was read, what remains, what needs the owner.

Budgets: <= _CYCLE_MAX_READS document executions per cycle, <= _READ_
TIMEOUT_SECONDS each, and the per-question attempt cap bounds retries
across cycles. Authorization: this lane only ever executes READ
operations against cataloged documents — the scope the job's research
authorization already covers.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_CYCLE_MAX_READS = int(os.getenv("ATOM_RESEARCH_CONTINUATION_MAX_READS",
                                 "4") or 4)
_READ_TIMEOUT_SECONDS = float(
    os.getenv("ATOM_RESEARCH_CONTINUATION_READ_TIMEOUT", "25") or 25)
_INTERVAL_SECONDS = float(
    os.getenv("ATOM_RESEARCH_CONTINUATION_INTERVAL_SECONDS", "45") or 45)

_RECOVERY_TASK: "asyncio.Task | None" = None
_IN_FLIGHT: set = set()


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


def _group_read_actions(actions: List[Dict[str, Any]]) -> Dict[str, List[
        Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for a in actions or []:
        na = str(a.get("next_action") or "")
        if not na.lower().startswith("read "):
            continue
        fname = na[5:].rsplit(" for ", 1)[0].strip()
        if fname:
            groups.setdefault(fname, []).append(a)
    return groups


async def _execute_one_read(
        lifecycle: Any, run_id: str,
        user_id: str, workspace_id: str, agent_id: str, file_name: str,
        items: List[str], history_tail: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """One grouped read execution + settle ON THE JOB'S RUN (the settle
    must retire the job's own questions — a worker-owned task would
    strand them). Returns per-item results."""
    from core.chat_tool_planner import ToolPlan, execute_tool_plan
    from core.task_lifecycle import (
        finish_retrieval_turn, record_read_outcome)

    op = lifecycle.create_operation(
        run_id, op_type="retrieve",
        requested_change=(
            f"research continuation read: {file_name[:120]}"))
    op_id = op["operation_id"]
    plan = ToolPlan(use_tool=True, service="datasets", intent="read",
                    query=file_name)
    block = None
    err = ""
    try:
        block = await asyncio.wait_for(
            execute_tool_plan(
                plan, user_id, "default",
                context={"agent_id": agent_id, "message": file_name,
                         "history": history_tail,
                         "workspace_id": workspace_id},
                llm_service=None),
            timeout=_READ_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 — recorded, never raised
        err = f"{type(exc).__name__}: {str(exc)[:120]}"
    meta = getattr(plan, "_result_meta", None) or {}
    receipt_keys = [k for k in ("storage_read", "file_read",
                                "structured_result", "workbook_read")
                    if isinstance(meta.get(k), dict) and meta[k]]
    read_ok = bool(receipt_keys) and not err
    _exec_facts = {
        "invoked": block is not None or bool(receipt_keys),
        "outcome": ("read_succeeded" if read_ok else
                    "read_failed" if err else
                    "read_returned_no_receipt"),
        "served_basis": ("saved_copy" if read_ok else
                         "live" if (block or receipt_keys) else "none"),
        "failure_stage": err or None,
        "items": {i: ("single" if read_ok else "") for i in items},
    }
    finish_retrieval_turn(
        lifecycle, run_id, op_id, {}, None, read_ok,
        execution=_exec_facts)
    # The RETIREMENT rule reads record_read_outcome's execution param —
    # passing it here is what resolves the read questions and spawns the
    # freshness successors on the JOB's run.
    record_read_outcome(
        lifecycle, run_id, op_id, structured_result=None, freshness=None,
        execution=_exec_facts)
    return {"file": file_name, "ok": read_ok, "items": items,
            "block": (block or "")[:4000], "error": err}


async def research_continuation_cycle(max_reads: int = _CYCLE_MAX_READS
                                      ) -> Dict[str, int]:
    """One bounded pass over durable jobs with eligible pending reads."""
    from core.task_lifecycle import (
        bump_question_attempts, next_unfinished_work)

    out = {"jobs": 0, "reads": 0, "completed_items": 0, "failed_reads": 0}
    if not research_continuation_enabled():
        return out
    try:
        from core.chat_session_manager import chat_session_manager
        from core.task_lifecycle import TaskLifecycle  # noqa: F401

        lifecycle = _lifecycle_for_default_tenant()
        runs = lifecycle.runs.list_runs(include_terminal=False, limit=100)
    except Exception as exc:  # noqa: BLE001 — cycle is best-effort
        logger.debug("[research-continuation] enumerate failed: %r", exc)
        return out
    for run in runs or []:
        run_id = str(run.get("id"))
        if run_id in _IN_FLIGHT:
            continue
        try:
            record = lifecycle.get_task(run_id)
            if record is None:
                continue
            work = next_unfinished_work(record)
            groups = _group_read_actions(work.get("actions") or [])
            if not groups:
                continue
            conv = record.get("conversation_id") or ""
            sess = chat_session_manager.get_session(conv) if conv else None
            if not sess or not str(sess.get("user_id") or "").strip():
                continue  # no execution identity — leave durable + listed
            user_id = str(sess["user_id"])
            workspace_id = str(sess.get("workspace_id") or "default")
            agent_id = str(sess.get("agent_id") or "") or None
            history_tail = [
                {"message": str(h.get("message") or "")[:400],
                 "response": ""}
                for h in (sess.get("history") or [])[-6:]
                if isinstance(h, dict)]
            _IN_FLIGHT.add(run_id)
            out["jobs"] += 1
            notes: List[str] = []
            done_now = 0
            for fname, acts in list(groups.items())[:max_reads]:
                items = [str(a.get("item") or "") for a in acts
                         if str(a.get("item") or "")] or [""]
                # CLAIM (dedup + retry bound): bump before executing.
                bump_question_attempts(
                    lifecycle, run_id,
                    [a["question_id"] for a in acts
                     if a.get("question_id")])
                res = await _execute_one_read(
                    lifecycle, run_id, user_id, workspace_id, agent_id,
                    fname, items, history_tail)
                out["reads"] += 1
                if res["ok"]:
                    done_now += len(items)
                    notes.append(
                        f"read {fname}: {', '.join(i for i in items)}"
                        " — evidence recorded")
                else:
                    out["failed_reads"] += 1
                    notes.append(
                        f"read {fname}: not completed"
                        + (f" ({res['error']})" if res["error"] else
                           " (no receipt)"))
            out["completed_items"] += done_now
            # TRUTHFUL TERMINAL NOTE: appended to the session history so
            # the user sees durable progress without a "continue".
            if notes:
                try:
                    hist = list(sess.get("history") or [])
                    hist.append({
                        "message": "",
                        "response": (
                            "Background research update — completed while "
                            "you were away: " + "; ".join(notes)
                            + ". Remaining work stays on the job record."),
                        "timestamp": time.time(),
                    })
                    chat_session_manager.update_session_activity(
                        conv, history=hist)
                except Exception:  # noqa: BLE001 — ledger is the record
                    pass
        except Exception as exc:  # noqa: BLE001 — per-job isolation
            logger.warning("[research-continuation] job %s failed: %r",
                           str(run_id)[:8], exc)
        finally:
            _IN_FLIGHT.discard(run_id)
    if out["reads"]:
        logger.info("[research-continuation] cycle: %s", out)
    return out


async def _research_continuation_loop() -> None:
    logger.info("[research-continuation] durable research worker started "
                "(interval %.0fs, max %d reads/cycle)",
                _INTERVAL_SECONDS, _CYCLE_MAX_READS)
    while True:
        try:
            await research_continuation_cycle()
        except asyncio.CancelledError:
            logger.info("[research-continuation] worker stopped")
            raise
        except Exception as exc:  # noqa: BLE001 — the loop must survive
            logger.warning("[research-continuation] cycle error: %r", exc)
        await asyncio.sleep(_INTERVAL_SECONDS)


def start_research_continuation() -> bool:
    """Start the recurring worker once. Idempotent; survives restarts by
    being started from the FastAPI lifespan like terminal recovery."""
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
