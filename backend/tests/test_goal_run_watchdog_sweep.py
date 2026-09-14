"""GoalRun bounded waits + stalled-run sweep (2026-09-13, P2-E).

Before the fix, a NON-timer wait had no deadline: computer-use steps wait
on ``operator_task_done`` pushed from an IN-MEMORY operator registry by a
spawned fire-and-forget task — a restart parked the run in 'waiting'
FOREVER (timers wake; this wait had no deadline), and a crashed delegation
loop left runs 'active' with no driver at all. Now:

* ``_computer_use_work`` waits carry a watchdog deadline (constant 45min,
  env ``ATOM_GOAL_RUN_WATCHDOG_MINUTES``) —
  ``goal_run_events.check_due_watchdog_wakes`` wakes expired waits with an
  honest failure event and the router re-decides.
* the maintenance sweep ``interrupt_stalled_runs_all_workspaces`` marks
  'active' runs with no updated_at progress beyond the threshold
  (``ATOM_GOAL_RUN_STALE_MINUTES``, default 360) as interrupted:
  ``paused_hitl`` + an honest pending ASK_HUMAN resolved through the
  normal resume flow. Never auto-cancels.
"""

import asyncio
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("TESTING", "1")

import core.database as db_mod
from core.goals.goal_run_executors import (
    DEFAULT_OPERATOR_WATCHDOG_MINUTES, GoalRunExecutors,
)
from core.goals.goal_run_service import GoalRunService
from core.models import GoalObjective, GoalRun


@pytest.fixture(autouse=True)
def patched_session(db_session):
    original = db_mod.get_db_session

    @contextmanager
    def _test_session():
        yield db_session

    db_mod.get_db_session = _test_session
    try:
        yield db_session
    finally:
        db_mod.get_db_session = original


@pytest.fixture(autouse=True)
def stub_router(monkeypatch):
    class _Stub:
        async def decide(self, context):
            # SKIP keeps the run ACTIVE (no second wait) — the watchdog
            # behavior under test is the wake, not the next decision.
            return {"decision": "SKIP", "rationale": "stub",
                    "confidence": 0.9}

    monkeypatch.setattr(GoalRunService, "_default_router",
                        lambda self: _Stub())


@pytest.fixture(autouse=True)
def silence_side_effects(monkeypatch):
    monkeypatch.setattr(
        "core.goals.goal_run_notifications.schedule_notification",
        lambda coro: coro.close() if hasattr(coro, "close") else None)


@pytest.fixture
def env(db_session):
    db_session.add(GoalObjective(
        id="g-watchdog", workspace_id="ws-watch", tenant_id="default",
        title="Watchdog goal", status="active"))
    db_session.commit()
    return db_session


def _svc(env):
    return GoalRunService(workspace_id="ws-watch", tenant_id="default")


def _active_run(env, run_id, plan=None, **kw):
    env.add(GoalRun(
        id=run_id, workspace_id="ws-watch", tenant_id="default",
        goal_id="g-watchdog", status="active", supervision_mode="shadow",
        plan=plan or [{"id": "s1", "kind": "canvas_work", "title": "Step"}],
        cursor="s1", **kw))
    env.commit()
    return run_id


# -------------------------------------------------------- the watchdog

class TestOperatorWaitWatchdog:

    def test_operator_wait_carries_a_deadline(self, env, monkeypatch):
        run_id = _active_run(env, "run-op", plan=[
            {"id": "s1", "kind": "computer_use_work",
             "title": "Fill the supplier portal", "directive": "do it"}])
        monkeypatch.setattr(
            "core.operator.tools.operator_start_task",
            AsyncMock(return_value={"success": True,
                                    "operator_run_id": "op-77"}))
        svc = _svc(env)
        run = svc.get_run(run_id)
        result = asyncio.run(
            GoalRunExecutors(svc).execute(run, {"decision": "ADVANCE"}))
        assert result["waiting"] is True
        waiting = svc.get_run(run_id)["waiting_on"]
        assert waiting["event"] == "operator_task_done"
        assert waiting["watchdog"] is True
        deadline = datetime.fromisoformat(waiting["deadline"])
        expected_min = datetime.now(timezone.utc)
        expected_max = expected_min + timedelta(
            minutes=DEFAULT_OPERATOR_WATCHDOG_MINUTES + 1)
        assert expected_min <= deadline <= expected_max

    def test_expired_operator_wait_wakes_with_honest_error(self, env):
        """The restart case: the operator registry is gone (no wake will
        ever arrive) — the deadline wakes the run and the router
        re-decides with the failure in context."""
        run_id = _active_run(env, "run-stuck")
        svc = _svc(env)
        svc.set_wait(run_id, {
            "event": "operator_task_done",
            "match": {"operator_run_id": "op-gone"},
            "deadline": (datetime.now(timezone.utc)
                         - timedelta(minutes=5)).isoformat(),
            "watchdog": True,
        })

        from core.goals.goal_run_events import check_due_watchdog_wakes
        out = asyncio.run(check_due_watchdog_wakes(
            "ws-watch", "default", now=datetime.now(timezone.utc)))
        assert run_id in out["woke"]

        run = svc.get_run(run_id)
        assert run["status"] != "waiting"  # awake again, router re-decided
        assert any(d.get("kind") == "wait_deadline_reached"
                   and "operator_task_done" in str(d.get("rationale"))
                   for d in run["decision_log"])

    def test_future_deadline_does_not_wake(self, env):
        run_id = _active_run(env, "run-ok")
        svc = _svc(env)
        svc.set_wait(run_id, {
            "event": "operator_task_done",
            "match": {"operator_run_id": "op-live"},
            "deadline": (datetime.now(timezone.utc)
                         + timedelta(minutes=30)).isoformat(),
            "watchdog": True,
        })
        from core.goals.goal_run_events import check_due_watchdog_wakes
        out = asyncio.run(check_due_watchdog_wakes(
            "ws-watch", "default", now=datetime.now(timezone.utc)))
        assert out["woke"] == []
        assert svc.get_run(run_id)["status"] == "waiting"

    def test_timer_waits_are_not_touched_by_the_watchdog_path(self, env):
        """Timers keep their own wake path (due_timer_runs) — the watchdog
        scan must not double-fire them."""
        run_id = _active_run(env, "run-timer")
        svc = _svc(env)
        svc.set_wait(run_id, {
            "event": "timer",
            "deadline": (datetime.now(timezone.utc)
                         - timedelta(days=1)).isoformat(),
        })
        from core.goals.goal_run_events import due_watchdog_runs
        assert due_watchdog_runs("ws-watch", "default") == []


# ------------------------------------------------------- the stale sweep

class TestStaleActiveSweep:

    def test_stale_active_run_is_interrupted_not_cancelled(self, env):
        from sqlalchemy import update
        run_id = _active_run(env, "run-stale")
        old = datetime.now(timezone.utc) - timedelta(hours=48)
        env.execute(update(GoalRun).where(GoalRun.id == run_id).values(
            updated_at=old))
        env.commit()

        from core.goals.goal_run_events import (
            interrupt_stalled_runs_all_workspaces)
        out = interrupt_stalled_runs_all_workspaces()
        assert run_id in out["interrupted"]

        run = _svc(env).get_run(run_id)
        assert run["status"] == "paused_hitl"  # surfaced, NOT cancelled
        assert run["pending_decision"]["decision"] == "ASK_HUMAN"
        assert any(d.get("kind") == "stalled_interrupted"
                   for d in run["decision_log"])

        # recoverable through the normal resume flow
        resumed = asyncio.run(_svc(env).resume(run_id, approved=True))
        assert resumed["resumed"] is True
        assert _svc(env).get_run(run_id)["status"] == "active"

    def test_fresh_active_runs_are_left_alone(self, env):
        run_id = _active_run(env, "run-fresh")
        from core.goals.goal_run_events import (
            interrupt_stalled_runs_all_workspaces)
        out = interrupt_stalled_runs_all_workspaces()
        assert run_id not in out["interrupted"]
        assert _svc(env).get_run(run_id)["status"] == "active"

    def test_terminal_runs_are_never_swept(self, env):
        run_id = _active_run(env, "run-done")
        _svc(env).transition(run_id, "achieved")
        from core.goals.goal_run_events import (
            interrupt_stalled_runs_all_workspaces)
        out = interrupt_stalled_runs_all_workspaces()
        assert run_id not in out["interrupted"]
        assert _svc(env).get_run(run_id)["status"] == "achieved"
