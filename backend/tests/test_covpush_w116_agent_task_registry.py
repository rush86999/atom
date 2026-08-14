"""
Backend depth wave 116 (2026-08-13) — coverage push for core/agent_task_registry.py.

Covers task registration/unregistration, cancellation paths (task done/not
found/timeout), agent-run lookup, cleanup, and the module-level helper.
Fully mocked with real asyncio tasks — zero LLM spend.
"""

import asyncio

import pytest

from core.agent_task_registry import (
    AgentTask,
    AgentTaskRegistry,
    agent_task_registry,
    register_agent_task,
)


@pytest.fixture(autouse=True)
def reset_registry():
    agent_task_registry._reset()
    yield
    agent_task_registry._reset()


def _done_task() -> asyncio.Task:
    """A fully-completed task (self-contained loop — safe across tests)."""
    loop = asyncio.new_event_loop()
    try:
        task = loop.create_task(_finished())
        loop.run_until_complete(task)
        return task
    finally:
        loop.close()


def _spawn(coro) -> asyncio.Task:
    """Create a task on the currently running loop (async tests only)."""
    return asyncio.get_running_loop().create_task(coro)


async def _finished():
    return "done"


class TestAgentTask:
    """Cover AgentTask.cancel branches (lines 30-34)."""

    @pytest.mark.asyncio
    async def test_cancel_running_task_marks_cancelled(self):
        async def _forever():
            while True:
                await asyncio.sleep(3600)

        task = _spawn(_forever())
        at = AgentTask(
            task_id="t1",
            agent_id="a1",
            agent_run_id="r1",
            task=task,
            user_id="u1",
        )
        assert at.cancel() is True
        assert at.status == "cancelled"

    def test_cancel_done_task_returns_false(self):
        task = _done_task()
        assert task.done()
        at = AgentTask(
            task_id="t1",
            agent_id="a1",
            agent_run_id="r1",
            task=task,
            user_id="u1",
        )
        assert at.cancel() is False


class TestRegistration:
    """Cover register/unregister (lines 58, 75-93, 97-115)."""

    def test_init_is_idempotent(self):
        agent_task_registry.register_task(
            task_id="t0", agent_id="a0", agent_run_id="r0",
            task=_done_task(), user_id="u0",
        )
        agent_task_registry._initialized = True
        agent_task_registry.__init__()
        assert agent_task_registry._tasks["t0"] is not None

    def test_register_multiple_agents_sets_index(self):
        for i in range(3):
            agent_task_registry.register_task(
                task_id=f"t{i}", agent_id=f"a{i % 2}", agent_run_id=f"r{i}",
                task=_done_task(), user_id="u1",
            )
        assert len(agent_task_registry._agent_tasks["a0"]) == 2
        assert agent_task_registry.get_task_id_by_run("r2") == "t2"

    def test_unregister_removes_all_indexes(self):
        agent_task_registry.register_task(
            task_id="t1", agent_id="a1", agent_run_id="r1",
            task=_done_task(), user_id="u1",
        )
        agent_task_registry.unregister_task("t1")
        assert agent_task_registry.get_task("t1") is None
        assert "a1" not in agent_task_registry._agent_tasks
        assert "r1" not in agent_task_registry._run_tasks

    def test_unregister_unknown_task_is_noop(self):
        agent_task_registry.unregister_task("ghost")
        assert agent_task_registry._tasks == {}

    def test_unregister_keeps_other_tasks_of_agent(self):
        for i in range(2):
            agent_task_registry.register_task(
                task_id=f"t{i}", agent_id="a1", agent_run_id=f"r{i}",
                task=_done_task(), user_id="u1",
            )
        agent_task_registry.unregister_task("t0")
        assert agent_task_registry._agent_tasks["a1"] == {"t1"}


class TestCancellation:
    """Cover cancel_task/cancel_agent_tasks/cancel_agent_run (lines 117-168)."""

    @pytest.mark.asyncio
    async def test_cancel_task_not_found(self):
        assert await agent_task_registry.cancel_task("ghost") is False

    @pytest.mark.asyncio
    async def test_cancel_task_success_wait_and_unregister(self):
        async def _stoppable():
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                raise

        task = asyncio.get_running_loop().create_task(_stoppable())
        agent_task_registry.register_task(
            task_id="t1", agent_id="a1", agent_run_id="r1",
            task=task, user_id="u1",
        )
        assert await agent_task_registry.cancel_task("t1") is True
        assert agent_task_registry.get_task("t1") is None

    @pytest.mark.asyncio
    async def test_cancel_agent_tasks_counts_successes(self):
        async def _stoppable():
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                raise

        for i in range(3):
            agent_task_registry.register_task(
                task_id=f"t{i}", agent_id="a1", agent_run_id=f"r{i}",
                task=asyncio.get_running_loop().create_task(_stoppable()),
                user_id="u1",
            )
        # One task already done → cancel returns False
        done = _spawn(_finished())
        await done
        agent_task_registry._tasks["t2"].task = done
        assert await agent_task_registry.cancel_agent_tasks("a1") == 2

    @pytest.mark.asyncio
    async def test_cancel_agent_tasks_no_tasks(self):
        assert await agent_task_registry.cancel_agent_tasks("nobody") == 0

    @pytest.mark.asyncio
    async def test_cancel_agent_run_not_found(self):
        assert await agent_task_registry.cancel_agent_run("ghost") is False

    @pytest.mark.asyncio
    async def test_cancel_agent_run_found(self):
        async def _stoppable():
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                raise

        task = asyncio.get_running_loop().create_task(_stoppable())
        agent_task_registry.register_task(
            task_id="t1", agent_id="a1", agent_run_id="r1",
            task=task, user_id="u1",
        )
        assert await agent_task_registry.cancel_agent_run("r1") is True

    @pytest.mark.asyncio
    async def test_cancel_task_timeout_tolerated(self):
        async def _ignores_cancel():
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                await asyncio.sleep(3600)

        task = asyncio.get_running_loop().create_task(_ignores_cancel())
        agent_task_registry.register_task(
            task_id="t1", agent_id="a1", agent_run_id="r1",
            task=task, user_id="u1",
        )
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(asyncio, "wait_for", _fake_wait_for_timeout)
            assert await agent_task_registry.cancel_task("t1") is True
        assert agent_task_registry.get_task("t1") is None


async def _fake_wait_for_timeout(*args, **kwargs):
    raise asyncio.TimeoutError()


class TestQueries:
    """Cover get_task/get_agent_tasks/is_agent_running/cleanup (lines 170-213)."""

    def test_get_task_returns_registered(self):
        agent_task_registry.register_task(
            task_id="t1", agent_id="a1", agent_run_id="r1",
            task=_done_task(), user_id="u1",
        )
        assert agent_task_registry.get_task("t1").agent_id == "a1"
        assert agent_task_registry.get_task("missing") is None

    def test_get_agent_tasks_returns_list(self):
        for i in range(2):
            agent_task_registry.register_task(
                task_id=f"t{i}", agent_id="a1", agent_run_id=f"r{i}",
                task=_done_task(), user_id="u1",
            )
        tasks = agent_task_registry.get_agent_tasks("a1")
        assert len(tasks) == 2

    def test_is_agent_running(self):
        assert agent_task_registry.is_agent_running("a1") is False
        agent_task_registry.register_task(
            task_id="t1", agent_id="a1", agent_run_id="r1",
            task=_done_task(), user_id="u1",
        )
        assert agent_task_registry.is_agent_running("a1") is True

    def test_get_task_id_by_run(self):
        agent_task_registry.register_task(
            task_id="t1", agent_id="a1", agent_run_id="r1",
            task=_done_task(), user_id="u1",
        )
        assert agent_task_registry.get_task_id_by_run("r1") == "t1"
        assert agent_task_registry.get_task_id_by_run("nope") is None

    @pytest.mark.asyncio
    async def test_cleanup_completed_tasks(self):
        done_tasks = []
        for i in range(2):
            task = asyncio.get_running_loop().create_task(_finished())
            await task
            done_tasks.append(task)
            agent_task_registry.register_task(
                task_id=f"done{i}", agent_id="a1", agent_run_id=f"r{i}",
                task=task, user_id="u1",
            )
        agent_task_registry.register_task(
            task_id="running1", agent_id="a1", agent_run_id="r3",
            task=asyncio.get_running_loop().create_task(_never()),
            user_id="u1",
        )
        cleaned = await agent_task_registry.cleanup_completed_tasks()
        assert cleaned == 2
        assert agent_task_registry.get_task("done0") is None
        assert agent_task_registry.get_task("running1") is not None

    @pytest.mark.asyncio
    async def test_cleanup_nothing_to_remove(self):
        assert await agent_task_registry.cleanup_completed_tasks() == 0

    def test_get_all_running_agents(self):
        for i in range(2):
            agent_task_registry.register_task(
                task_id=f"t{i}", agent_id="a1", agent_run_id=f"r{i}",
                task=_done_task(), user_id="u1",
            )
        running = agent_task_registry.get_all_running_agents()
        assert set(running["a1"]) == {"t0", "t1"}

    def test_get_agent_tasks_unknown_agent_returns_empty(self):
        assert agent_task_registry.get_agent_tasks("ghost") == []


async def _never():
    await asyncio.sleep(3600)


class TestModuleHelper:
    """Cover register_agent_task helper (lines 239-248)."""

    def test_register_agent_task_returns_uuid_and_registers(self):
        task_id = register_agent_task(
            agent_id="a1",
            agent_run_id="r1",
            task=_done_task(),
            user_id="u1",
        )
        assert task_id
        assert agent_task_registry.get_task(task_id) is not None
        assert agent_task_registry.get_task_id_by_run("r1") == task_id
