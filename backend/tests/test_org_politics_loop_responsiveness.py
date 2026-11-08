"""Responsiveness, context, serialization, and cancellation controls.

These tests exercise the real ``org_politics_automation_loop``. Only the
synchronous certification pass is replaced with a controlled function, so the
loop's tick binding, worker offload, ContextVar copying, and notification
callback scheduling are the production paths. No model, database, network, or
real notification service is touched.

The sleep gate is explicit: tests release one loop tick at a time and wait on
asyncio/threading events with bounded timeouts, not on elapsed sleeps. These
tests were authored statically and were not executed by the author (this
snapshot forbids execution).
"""
from __future__ import annotations

import asyncio
import contextvars
import threading

import pytest


_PROBE = contextvars.ContextVar("org_politics_test_probe", default="unset")


@pytest.fixture()
def automation(monkeypatch):
    """Fresh module state so one control cannot poison another."""
    import core.org_politics_automation as module

    monkeypatch.setattr(module, "_pass_gate", threading.Lock())
    monkeypatch.setattr(module, "_automation_task", None)
    # This control isolates scheduling; do not load runtime settings or a DB.
    monkeypatch.setattr(module, "automation_interval_min", lambda: 0.5)
    return module


class _StepClock:
    """An asyncio sleep that only returns when a test releases one tick."""

    def __init__(self) -> None:
        self._sleeping = asyncio.Event()
        self._release = asyncio.Event()
        self.sleeps = 0

    async def sleep(self, _seconds: float) -> None:
        self.sleeps += 1
        self._sleeping.set()
        await self._release.wait()
        self._release.clear()

    async def tick(self, timeout: float = 2.0) -> None:
        await asyncio.wait_for(self._sleeping.wait(), timeout)
        self._sleeping.clear()
        self._release.set()


class _AsyncioProxy:
    """Replace only the module's ``asyncio.sleep``/``CancelledError`` binding.

    The production loop keeps using the module's ``asyncio`` binding for sleep
    so the existing registered-loop timer shim remains valid, while worker
    offload falls back to the directly imported stdlib functions when a shim
    does not provide them.
    """

    def __init__(self, clock: _StepClock) -> None:
        self._clock = clock
        self.CancelledError = asyncio.CancelledError

    async def sleep(self, seconds: float) -> None:
        await self._clock.sleep(seconds)

    def __getattr__(self, name: str):
        return getattr(asyncio, name)


def _install_clock(monkeypatch, automation, clock: _StepClock) -> None:
    monkeypatch.setattr(automation, "asyncio", _AsyncioProxy(clock))


async def _stop(task: asyncio.Task, timeout: float = 2.0) -> None:
    """Cancel the loop task and wait for its own CancelledError handling."""
    task.cancel()
    await asyncio.wait_for(task, timeout)


def test_heartbeat_progresses_while_the_pass_blocks(automation, monkeypatch):
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        clock = _StepClock()
        _install_clock(monkeypatch, automation, clock)

        heartbeat = threading.Event()
        pass_finished = asyncio.Event()
        observed = {}

        def blocking_pass():
            # This is the negative-control shape from the work order: queue a
            # callback on the application loop, then wait from the worker.
            loop.call_soon_threadsafe(heartbeat.set)
            observed["heartbeat"] = heartbeat.wait(1.0)
            loop.call_soon_threadsafe(pass_finished.set)
            return {}

        monkeypatch.setattr(
            automation, "run_auto_certification", blocking_pass)
        task = loop.create_task(automation.org_politics_automation_loop())
        try:
            await clock.tick()
            await asyncio.wait_for(pass_finished.wait(), 2.0)
            assert observed["heartbeat"] is True, (
                "the application loop must process a queued callback while "
                "the synchronous certification pass is running")
        finally:
            await _stop(task)

    asyncio.run(scenario())


def test_contextvars_are_copied_to_worker_and_isolated_from_loop(
        automation, monkeypatch):
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        clock = _StepClock()
        _install_clock(monkeypatch, automation, clock)
        _PROBE.set("loop")
        observed = {}
        worker_done = asyncio.Event()

        def probe_pass():
            observed["worker"] = _PROBE.get()
            _PROBE.set("worker")  # must remain local to the copied context
            loop.call_soon_threadsafe(worker_done.set)
            return {}

        monkeypatch.setattr(
            automation, "run_auto_certification", probe_pass)
        task = loop.create_task(automation.org_politics_automation_loop())
        try:
            await clock.tick()
            await asyncio.wait_for(worker_done.wait(), 2.0)
            assert observed["worker"] == "loop", (
                "the worker must receive the loop's context snapshot")
            assert _PROBE.get() == "loop", (
                "a worker-thread mutation must not leak back to the loop")
        finally:
            await _stop(task)

    asyncio.run(scenario())


def test_passes_remain_serial(automation, monkeypatch):
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        clock = _StepClock()
        _install_clock(monkeypatch, automation, clock)

        first_started = asyncio.Event()
        second_started = asyncio.Event()
        release_first = threading.Event()
        state = {"active": 0, "max_active": 0, "calls": 0}
        guard = threading.Lock()

        def serial_pass():
            with guard:
                state["active"] += 1
                state["calls"] += 1
                call_no = state["calls"]
                state["max_active"] = max(
                    state["max_active"], state["active"])
            try:
                if call_no == 1:
                    loop.call_soon_threadsafe(first_started.set)
                    release_first.wait(2.0)
                elif call_no == 2:
                    loop.call_soon_threadsafe(second_started.set)
                return {}
            finally:
                with guard:
                    state["active"] -= 1

        monkeypatch.setattr(
            automation, "run_auto_certification", serial_pass)
        task = loop.create_task(automation.org_politics_automation_loop())
        try:
            await clock.tick()
            await asyncio.wait_for(first_started.wait(), 2.0)

            with guard:
                assert state["calls"] == 1
                assert state["active"] == 1
            release_first.set()

            await clock.tick()
            await asyncio.wait_for(second_started.wait(), 2.0)
            with guard:
                assert state["calls"] == 2
                assert state["max_active"] == 1, (
                    "a second tick must not overlap the first pass")
        finally:
            release_first.set()
            await _stop(task)

    asyncio.run(scenario())


def test_exception_is_followed_by_the_next_tick(automation, monkeypatch):
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        clock = _StepClock()
        _install_clock(monkeypatch, automation, clock)

        second_started = asyncio.Event()
        state = {"calls": 0}
        guard = threading.Lock()

        def failing_then_ok():
            with guard:
                state["calls"] += 1
                call_no = state["calls"]
            if call_no == 1:
                raise RuntimeError("controlled pass failure")
            loop.call_soon_threadsafe(second_started.set)
            return {}

        monkeypatch.setattr(
            automation, "run_auto_certification", failing_then_ok)
        task = loop.create_task(automation.org_politics_automation_loop())
        try:
            await clock.tick()
            await clock.tick()
            await asyncio.wait_for(second_started.wait(), 2.0)
            with guard:
                assert state["calls"] == 2
        finally:
            await _stop(task)

    asyncio.run(scenario())


def test_cancellation_does_not_stop_worker_or_overlap_replacement(
        automation, monkeypatch):
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        clock = _StepClock()
        _install_clock(monkeypatch, automation, clock)

        first_started = asyncio.Event()
        first_finished = asyncio.Event()
        release_worker = threading.Event()
        attempts = asyncio.Queue()
        state = {"calls": 0}
        guard = threading.Lock()

        def blocking_pass():
            with guard:
                state["calls"] += 1
            try:
                loop.call_soon_threadsafe(first_started.set)
                release_worker.wait(2.0)
                return {}
            finally:
                loop.call_soon_threadsafe(first_finished.set)

        monkeypatch.setattr(
            automation, "run_auto_certification", blocking_pass)

        real_guarded = automation._run_auto_certification_guarded

        def observed_guarded():
            loop.call_soon_threadsafe(attempts.put_nowait, "attempt")
            return real_guarded()

        monkeypatch.setattr(
            automation, "_run_auto_certification_guarded", observed_guarded)

        first = loop.create_task(automation.org_politics_automation_loop())
        await clock.tick()
        await asyncio.wait_for(first_started.wait(), 2.0)

        # Cancel the awaiter while the worker is still inside the pass.
        first.cancel()
        await asyncio.wait_for(first, 2.0)
        await asyncio.wait_for(attempts.get(), 2.0)
        assert not first_finished.is_set(), (
            "cancelling the task must not be reported as a physical stop")
        with guard:
            assert state["calls"] == 1

        # A replacement loop may be registered while the old worker runs. Its
        # tick must reach the exclusion guard but must not invoke the pass.
        replacement = loop.create_task(
            automation.org_politics_automation_loop())
        try:
            await clock.tick()
            await asyncio.wait_for(attempts.get(), 2.0)
            with guard:
                assert state["calls"] == 1, (
                    "re-registration must not overlap the surviving worker")
            assert not first_finished.is_set()
        finally:
            # Let the original worker finish, then observe its completion.
            release_worker.set()
            await asyncio.wait_for(first_finished.wait(), 2.0)
            await _stop(replacement)

    asyncio.run(scenario())


def test_worker_notification_is_scheduled_on_the_application_loop(
        automation, monkeypatch):
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        clock = _StepClock()
        _install_clock(monkeypatch, automation, clock)

        delivered = asyncio.Event()
        seen_loops = []

        async def fake_notify(*_args, **_kwargs):
            seen_loops.append(asyncio.get_running_loop())
            delivered.set()

        def pass_that_notifies():
            automation._spawn_notification(
                "org_politics_ready", "title", "message")
            return {}

        monkeypatch.setattr(automation, "_notify", fake_notify)
        monkeypatch.setattr(
            automation, "run_auto_certification", pass_that_notifies)

        task = loop.create_task(automation.org_politics_automation_loop())
        try:
            await clock.tick()
            await asyncio.wait_for(delivered.wait(), 2.0)
            assert seen_loops == [loop], (
                "notification dispatch must return to the application loop, "
                "not run on a worker-private loop")
        finally:
            await _stop(task)

    asyncio.run(scenario())


def test_manual_consumer_shared_boundary_remains_responsive(automation, monkeypatch):
    async def scenario():
        loop = asyncio.get_running_loop()
        heartbeat = threading.Event()
        expected = {"queued": ["controlled-review"], "applied": []}

        def blocking_pass():
            loop.call_soon_threadsafe(heartbeat.set)
            assert heartbeat.wait(1.0), "manual pass blocked the application loop"
            return expected

        monkeypatch.setattr(automation, "run_auto_certification", blocking_pass)
        result = await asyncio.wait_for(
            automation.run_auto_certification_async(), 2.0)
        assert result is expected
        assert automation._notification_loop.get() is None

    asyncio.run(scenario())


def test_public_run_now_awaits_shared_boundary(automation, monkeypatch):
    # Actual public consumer, with only its owned pass and task registration
    # doubled. Authentication itself is not the claim of this control.
    from api import org_politics_routes

    seen = []
    expected = {"queued": ["controlled-review"], "applied": []}

    async def controlled_boundary():
        seen.append("awaited")
        return expected

    monkeypatch.setattr(automation, "run_auto_certification_async", controlled_boundary)
    monkeypatch.setattr(automation, "ensure_automation_task", lambda: seen.append("registered"))
    result = asyncio.run(org_politics_routes.run_now(_admin=None))
    assert result is expected
    assert seen == ["awaited", "registered"]


def test_shutdown_race_closes_unscheduled_notification(automation, monkeypatch):
    from types import SimpleNamespace

    captured = []

    def refuse_schedule(coroutine, _loop):
        captured.append(coroutine)
        raise RuntimeError("controlled loop shutdown")

    loop = SimpleNamespace(is_running=lambda: True, is_closed=lambda: False)
    monkeypatch.setattr(automation.asyncio, "run_coroutine_threadsafe", refuse_schedule)
    token = automation._notification_loop.set(loop)
    try:
        automation._spawn_notification("controlled", "title", "message")
    finally:
        automation._notification_loop.reset(token)
    assert len(captured) == 1
    assert captured[0].cr_frame is None, "failed scheduling must close the coroutine"
