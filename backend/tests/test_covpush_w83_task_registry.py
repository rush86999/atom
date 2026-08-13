# -*- coding: utf-8 -*-
"""Coverage wave 83 — core/agent_task_registry.py to >=95% (asyncio task
registry; singleton reset between tests; no LLM, no network).

Covers:
- AgentTask dataclass: cancel on running task, cancel on done task (False).
- register/unregister round trip, unregister unknown id (no-op), agent-id
  set cleanup when empty.
- cancel_task: unknown id -> False, cancel + unregister, timeout on a task
  that ignores cancellation.
- cancel_agent_tasks: unknown agent -> 0, multiple tasks counted.
- cancel_agent_run: unknown run -> False, known run -> True.
- get_task / get_agent_tasks (missing + present) / is_agent_running /
  get_task_id_by_run / get_all_running_agents.
- cleanup_completed_tasks: removes done tasks, leaves running ones.
- module-level register_agent_task helper (uuid task id).
"""
import asyncio
import uuid
from unittest.mock import patch

import pytest

from core.agent_task_registry import AgentTask, AgentTaskRegistry, agent_task_registry


@pytest.fixture(autouse=True)
def _clean_registry():
    agent_task_registry._reset()
    yield
    agent_task_registry._reset()


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _never_finish():
    await asyncio.Event().wait()


async def _finish():
    return "done"


async def _cancellable():
    try:
        await asyncio.sleep(30)
    except asyncio.CancelledError:
        raise


# ============================================================================
# AgentTask
# ============================================================================

def test_agent_task_cancel_running_task():
    task = asyncio.new_event_loop().create_task(_cancellable())
    at = AgentTask("t1", "a1", "r1", task, "u1")
    assert at.cancel() is True
    assert at.status == "cancelled"


def test_agent_task_cancel_done_task_returns_false():
    loop = asyncio.new_event_loop()
    task = loop.create_task(_finish())
    loop.run_until_complete(task)
    at = AgentTask("t1", "a1", "r1", task, "u1")
    assert at.cancel() is False
    assert at.status == "running"


def test_agent_task_defaults():
    task = asyncio.new_event_loop().create_task(_finish())
    at = AgentTask("t1", "a1", "r1", task, "u1")
    assert at.started_at is not None
    assert at.status == "running"


# ============================================================================
# register / unregister
# ============================================================================

def test_register_and_unregister_round_trip():
    task = asyncio.new_event_loop().create_task(_finish())
    agent_task_registry.register_task("t1", "a1", "r1", task, "u1")
    assert agent_task_registry.get_task("t1").user_id == "u1"
    assert agent_task_registry.get_task_id_by_run("r1") == "t1"
    assert agent_task_registry.is_agent_running("a1") is True
    agent_task_registry.unregister_task("t1")
    assert agent_task_registry.get_task("t1") is None
    assert agent_task_registry.is_agent_running("a1") is False
    assert agent_task_registry.get_task_id_by_run("r1") is None


def test_unregister_unknown_task_is_noop():
    agent_task_registry.unregister_task("ghost")  # must not raise


def test_unregister_last_task_removes_agent_key():
    task = asyncio.new_event_loop().create_task(_finish())
    agent_task_registry.register_task("t1", "a1", "r1", task, "u1")
    agent_task_registry.unregister_task("t1")
    assert "a1" not in agent_task_registry._agent_tasks


def test_register_multiple_tasks_same_agent():
    task = asyncio.new_event_loop().create_task(_finish())
    agent_task_registry.register_task("t1", "a1", "r1", task, "u1")
    agent_task_registry.register_task("t2", "a1", "r2", task, "u1")
    assert len(agent_task_registry.get_agent_tasks("a1")) == 2


# ============================================================================
# cancel_task
# ============================================================================

def test_cancel_task_unknown_returns_false():
    assert _run(agent_task_registry.cancel_task("ghost")) is False


def test_cancel_task_cancels_and_unregisters():
    loop = asyncio.new_event_loop()
    task = loop.create_task(_cancellable())
    agent_task_registry.register_task("t1", "a1", "r1", task, "u1")
    ok = loop.run_until_complete(agent_task_registry.cancel_task("t1"))
    assert ok is True
    assert agent_task_registry.get_task("t1") is None
    assert task.cancelled() is True


def test_cancel_task_timeout_when_task_ignores_cancel():
    loop = asyncio.new_event_loop()
    task = loop.create_task(_never_finish())
    agent_task_registry.register_task("t1", "a1", "r1", task, "u1")
    with patch("core.agent_task_registry.asyncio.wait_for", side_effect=asyncio.TimeoutError):
        ok = loop.run_until_complete(agent_task_registry.cancel_task("t1"))
    assert ok is True
    assert agent_task_registry.get_task("t1") is None
    task.cancel()


def test_cancel_task_cancelled_error_is_swallowed():
    loop = asyncio.new_event_loop()
    task = loop.create_task(_cancellable())
    agent_task_registry.register_task("t1", "a1", "r1", task, "u1")
    loop.run_until_complete(agent_task_registry.cancel_task("t1"))
    assert agent_task_registry.get_task("t1") is None


# ============================================================================
# cancel_agent_tasks / cancel_agent_run
# ============================================================================

def test_cancel_agent_tasks_unknown_agent_zero():
    assert _run(agent_task_registry.cancel_agent_tasks("ghost")) == 0


def test_cancel_agent_tasks_counts_cancelled():
    loop = asyncio.new_event_loop()
    t1 = loop.create_task(_cancellable())
    t2 = loop.create_task(_cancellable())
    agent_task_registry.register_task("t1", "a1", "r1", t1, "u1")
    agent_task_registry.register_task("t2", "a1", "r2", t2, "u1")
    count = loop.run_until_complete(agent_task_registry.cancel_agent_tasks("a1"))
    assert count == 2
    assert agent_task_registry.get_agent_tasks("a1") == []


def test_cancel_agent_run_unknown_returns_false():
    assert _run(agent_task_registry.cancel_agent_run("ghost")) is False


def test_cancel_agent_run_known_returns_true():
    loop = asyncio.new_event_loop()
    task = loop.create_task(_cancellable())
    agent_task_registry.register_task("t1", "a1", "r1", task, "u1")
    ok = loop.run_until_complete(agent_task_registry.cancel_agent_run("r1"))
    assert ok is True
    assert agent_task_registry.get_task("t1") is None


# ============================================================================
# queries / cleanup
# ============================================================================

def test_get_agent_tasks_unknown_agent_empty():
    assert agent_task_registry.get_agent_tasks("ghost") == []


def test_get_all_running_agents():
    loop = asyncio.new_event_loop()
    task = loop.create_task(_cancellable())
    agent_task_registry.register_task("t1", "a1", "r1", task, "u1")
    agent_task_registry.register_task("t2", "a2", "r2", task, "u1")
    agents = agent_task_registry.get_all_running_agents()
    assert agents["a1"] == ["t1"]
    assert agents["a2"] == ["t2"]
    task.cancel()


def test_cleanup_completed_tasks_removes_done_only():
    loop = asyncio.new_event_loop()
    done = loop.create_task(_finish())
    loop.run_until_complete(done)
    running = loop.create_task(_cancellable())
    agent_task_registry.register_task("done1", "a1", "r1", done, "u1")
    agent_task_registry.register_task("run1", "a2", "r2", running, "u1")
    removed = _run(agent_task_registry.cleanup_completed_tasks())
    assert removed == 1
    assert agent_task_registry.get_task("done1") is None
    assert agent_task_registry.get_task("run1") is not None
    running.cancel()


def test_cleanup_completed_tasks_none_done():
    loop = asyncio.new_event_loop()
    running = loop.create_task(_cancellable())
    agent_task_registry.register_task("run1", "a2", "r2", running, "u1")
    assert _run(agent_task_registry.cleanup_completed_tasks()) == 0
    running.cancel()


# ============================================================================
# module-level helper
# ============================================================================

def test_register_agent_task_helper():
    from core.agent_task_registry import register_agent_task
    loop = asyncio.new_event_loop()
    task = loop.create_task(_finish())
    task_id = register_agent_task("a1", "r1", task, "u1")
    assert uuid.UUID(task_id)
    assert agent_task_registry.get_task(task_id) is not None
    assert agent_task_registry.get_task_id_by_run("r1") == task_id


def test_singleton_pattern():
    assert AgentTaskRegistry() is agent_task_registry


def test_init_reentrant_returns_early():
    # Second __init__ on an initialized singleton is a no-op (line 58).
    agent_task_registry.__init__()  # post-reset: re-initializes
    agent_task_registry.__init__()  # initialized: early return
    assert agent_task_registry._initialized is True
