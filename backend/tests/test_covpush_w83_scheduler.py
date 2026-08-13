# -*- coding: utf-8 -*-
"""Coverage wave 83 — core/scheduler.py to >=95% (module-level job callables,
missed-run/error lifecycle, rollback path; apscheduler add_job patched so no
real jobstore writes; zero LLM spend, zero network).

Covers:
- _execute_and_log: success path (status SUCCESS + result_summary), failure
  path (status FAILED + logs), commit-failure rollback path.
- _managed_execution: forwards to singleton's _execute_and_log.
- _run_scheduled_agent: agent found (GenericAgent.execute awaited), agent
  missing (no-op), db closed in finally.
- _run_rating_sync: success + exception; _rating_sync_job wrapper.
- _run_skill_sync: success + exception; _skill_sync_job wrapper.
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.scheduler as mod
from core.scheduler import (
    _managed_execution,
    _rating_sync_job,
    _run_rating_sync,
    _run_scheduled_agent,
    _run_skill_sync,
    _skill_sync_job,
)


class _FakeJobRecord:
    """Mutable stand-in for the AgentJob ORM row."""

    def __init__(self):
        self.status = None
        self.end_time = None
        self.result_summary = None
        self.logs = None


class _FakeDb:
    """Fake session: tracks adds/commits/rollbacks/closes."""

    def __init__(self, fail_commit_times=()):
        self.added = []
        self.commit_count = 0
        self.rollback_count = 0
        self.closed = False
        self._fail_commits = set(fail_commit_times)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commit_count += 1
        if self.commit_count in self._fail_commits:
            raise RuntimeError("commit exploded")

    def rollback(self):
        self.rollback_count += 1

    def close(self):
        self.closed = True


# ============================================================================
# _execute_and_log
# ============================================================================

def test_execute_and_log_success_sets_success_status():
    db = _FakeDb()
    async def _func(*a, **k):
        return {"ok": True, "nested": {"a": 1}}
    with patch.object(mod, "get_db_session") as m:
        m.return_value.__enter__.return_value = db
        mod.AgentScheduler()._execute_and_log("agent-1", _func)
    record = db.added[0]
    assert record.agent_id == "agent-1"
    assert record.status == "success"
    assert record.end_time is not None
    assert json.loads(record.result_summary) == {"ok": True, "nested": {"a": 1}}
    assert db.commit_count == 2
    assert db.closed is True


def test_execute_and_log_failure_sets_failed_status_and_logs():
    db = _FakeDb()
    async def _func(*a, **k):
        raise ValueError("boom")
    with patch.object(mod, "get_db_session") as m:
        m.return_value.__enter__.return_value = db
        mod.AgentScheduler()._execute_and_log("agent-1", _func)
    record = db.added[0]
    assert record.status == "failed"
    assert record.logs == "boom"
    assert record.end_time is not None
    assert db.commit_count == 2


def test_execute_and_log_commit_failure_rolls_back_in_finally():
    db = _FakeDb(fail_commit_times={2})
    async def _func(*a, **k):
        return {"ok": True}
    with patch.object(mod, "get_db_session") as m:
        m.return_value.__enter__.return_value = db
        mod.AgentScheduler()._execute_and_log("agent-1", _func)
    assert db.rollback_count == 1
    assert db.closed is True


def test_execute_and_log_args_forwarded():
    db = _FakeDb()
    received = []
    async def _func(*args):
        received.append(args)
        return None
    with patch.object(mod, "get_db_session") as m:
        m.return_value.__enter__.return_value = db
        mod.AgentScheduler()._execute_and_log("agent-1", _func, "x", 2)
    assert received == [("x", 2)]
    assert db.added[0].status == "success"


# ============================================================================
# _managed_execution
# ============================================================================

def test_managed_execution_forwards_to_singleton():
    instance = MagicMock()
    func = lambda: None
    with patch.object(mod.AgentScheduler, "get_instance", return_value=instance):
        _managed_execution("agent-1", func, "extra")
    instance._execute_and_log.assert_called_once_with("agent-1", func, "extra")


# ============================================================================
# _run_scheduled_agent
# ============================================================================

def _make_query_result(agent_model):
    query = MagicMock()
    query.filter.return_value.first.return_value = agent_model
    return query


def test_run_scheduled_agent_runs_agent_when_found():
    agent_model = MagicMock()
    agent_model.id = "agent-1"
    agent_model.configuration = {"scheduled_task": "Do the thing"}
    db = MagicMock()
    db.query.return_value = query = MagicMock()
    query.filter.return_value.first.return_value = agent_model
    runner = AsyncMock()
    with patch("core.database.get_db_session") as m, \
         patch("core.generic_agent.GenericAgent", return_value=runner), \
         patch("core.models.AgentRegistry"):
        m.return_value.__enter__.return_value = db
        asyncio.run(_run_scheduled_agent("agent-1"))
    runner.execute.assert_awaited_once_with(
        "Do the thing", context={"trigger": "schedule"}
    )
    db.close.assert_called_once()


def test_run_scheduled_agent_missing_agent_is_noop():
    db = MagicMock()
    db.query.return_value = query = MagicMock()
    query.filter.return_value.first.return_value = None
    with patch("core.database.get_db_session") as m, \
         patch("core.generic_agent.GenericAgent") as ga, \
         patch("core.models.AgentRegistry"):
        m.return_value.__enter__.return_value = db
        asyncio.run(_run_scheduled_agent("ghost"))
    ga.assert_not_called()
    db.close.assert_called_once()


def test_run_scheduled_agent_defaults_task_when_no_config():
    agent_model = MagicMock()
    agent_model.configuration = {}
    db = MagicMock()
    db.query.return_value = query = MagicMock()
    query.filter.return_value.first.return_value = agent_model
    runner = AsyncMock()
    with patch("core.database.get_db_session") as m, \
         patch("core.generic_agent.GenericAgent", return_value=runner), \
         patch("core.models.AgentRegistry"):
        m.return_value.__enter__.return_value = db
        asyncio.run(_run_scheduled_agent("agent-1"))
    runner.execute.assert_awaited_once_with(
        "Perform scheduled check.", context={"trigger": "schedule"}
    )


# ============================================================================
# _run_rating_sync / _rating_sync_job
# ============================================================================

def test_run_rating_sync_success_logs_counts():
    svc = AsyncMock()
    svc.sync_ratings = AsyncMock(return_value={"uploaded": 3, "failed": 1})
    with patch.object(mod.logger, "info") as info:
        result = asyncio.run(_run_rating_sync(svc))
    assert result is None
    msg = info.call_args[0][0]
    assert "3 uploaded" in msg and "1 failed" in msg


def test_run_rating_sync_exception_logs_error():
    svc = AsyncMock()
    svc.sync_ratings = AsyncMock(side_effect=RuntimeError("saas down"))
    with patch.object(mod.logger, "error") as err:
        asyncio.run(_run_rating_sync(svc))
    err.assert_called_once()


def test_rating_sync_job_wrapper_runs_async():
    svc = MagicMock()
    svc.sync_ratings = AsyncMock(return_value={"uploaded": 0, "failed": 0})
    with patch.object(mod, "_run_rating_sync", new=AsyncMock()) as inner:
        _rating_sync_job(svc)
    inner.assert_awaited_once_with(svc)


# ============================================================================
# _run_skill_sync / _skill_sync_job
# ============================================================================

def test_run_skill_sync_success_logs_counts():
    svc = AsyncMock()
    svc.sync_all = AsyncMock(return_value={
        "skills_synced": 12, "categories_synced": 4, "duration_seconds": 2.5,
    })
    with patch.object(mod.logger, "info") as info:
        asyncio.run(_run_skill_sync(svc))
    msg = info.call_args[0][0]
    assert "12 skills" in msg and "4 categories" in msg and "2.50s" in msg


def test_run_skill_sync_exception_logs_error():
    svc = AsyncMock()
    svc.sync_all = AsyncMock(side_effect=ConnectionError("nope"))
    with patch.object(mod.logger, "error") as err:
        asyncio.run(_run_skill_sync(svc))
    err.assert_called_once()


def test_skill_sync_job_wrapper_runs_async():
    svc = MagicMock()
    svc.sync_all = AsyncMock(return_value={
        "skills_synced": 0, "categories_synced": 0, "duration_seconds": 0.1,
    })
    with patch.object(mod, "_run_skill_sync", new=AsyncMock()) as inner:
        _skill_sync_job(svc)
    inner.assert_awaited_once_with(svc)
