"""Stage/fleet router automation workers and their real run-now routes.

Each owner keeps its own worker boundary and pass gate. These controls use the
actual imported stage/fleet modules and route functions, replacing only the
synchronous owner pass (and, for loop controls, the module's timer binding).
No database, model, network or notification service is touched.
"""
from __future__ import annotations

import asyncio
import contextvars
import importlib
import threading

import pytest

from core.asyncio_compat import notification_loop_var

_PROBE = contextvars.ContextVar("router_automation_test_probe", default="unset")


class _StepClock:
    """An asyncio sleep that only returns when the test releases one tick."""

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
    """Replace only the owner module's asyncio binding for loop timing."""

    def __init__(self, clock: _StepClock) -> None:
        self._clock = clock
        self.CancelledError = asyncio.CancelledError

    async def sleep(self, seconds: float) -> None:
        await self._clock.sleep(seconds)

    def __getattr__(self, name: str):
        return getattr(asyncio, name)


def _install_clock(monkeypatch, module, clock: _StepClock) -> None:
    monkeypatch.setattr(module, "asyncio", _AsyncioProxy(clock))


async def _stop(task: asyncio.Task, timeout: float = 2.0) -> None:
    task.cancel()
    try:
        await asyncio.wait_for(task, timeout)
    except asyncio.CancelledError:
        # Fleet's loop re-raises cancellation; the owner's worker is unaffected.
        pass


async def _wait_until(predicate, timeout: float = 2.0) -> None:
    async def poll():
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(poll(), timeout)


@pytest.fixture(params=["stage", "fleet"])
def owner(request, monkeypatch):
    if request.param == "stage":
        module = importlib.import_module("core.llm.stage_router_automation")
        loop_fn = module.stage_router_automation_loop
        monkeypatch.setattr(module, "_INTERVAL_MIN", 0.5)
    else:
        module = importlib.import_module(
            "core.fleet_orchestration.fleet_router_automation")
        loop_fn = module.fleet_router_automation_loop
        monkeypatch.setattr(module, "_interval_min", 0.5)
    monkeypatch.setattr(module, "_pass_gate", threading.Lock())
    monkeypatch.setattr(
        module,
        "_notification_loop",
        notification_loop_var(f"{request.param}_test_notification_loop"),
    )
    monkeypatch.setattr(module, "_automation_task", None)
    monkeypatch.setattr(module, "automation_interval_min", lambda: 0.5)
    return module, loop_fn


def test_owner_loop_heartbeat_progresses_while_pass_blocks(owner, monkeypatch):
    module, loop_fn = owner

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        clock = _StepClock()
        _install_clock(monkeypatch, module, clock)

        heartbeat = threading.Event()
        pass_finished = asyncio.Event()
        observed = {}

        def blocking_pass():
            loop.call_soon_threadsafe(heartbeat.set)
            observed["heartbeat"] = heartbeat.wait(1.0)
            loop.call_soon_threadsafe(pass_finished.set)
            return {"enabled": True}

        monkeypatch.setattr(module, "run_auto_certification", blocking_pass)
        task = loop.create_task(loop_fn())
        try:
            await clock.tick()
            await asyncio.wait_for(pass_finished.wait(), 2.0)
            assert observed["heartbeat"] is True
        finally:
            await _stop(task)

    asyncio.run(scenario())


def test_owner_worker_context_is_copied_and_isolated(owner, monkeypatch):
    module, loop_fn = owner

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        clock = _StepClock()
        _install_clock(monkeypatch, module, clock)
        _PROBE.set("loop")
        observed = {}
        worker_done = asyncio.Event()

        def probe_pass():
            observed["worker"] = _PROBE.get()
            _PROBE.set("worker")  # local to the copied context only
            loop.call_soon_threadsafe(worker_done.set)
            return {"enabled": True}

        monkeypatch.setattr(module, "run_auto_certification", probe_pass)
        task = loop.create_task(loop_fn())
        try:
            await clock.tick()
            await asyncio.wait_for(worker_done.wait(), 2.0)
            assert observed["worker"] == "loop"
            assert _PROBE.get() == "loop"
        finally:
            await _stop(task)

    asyncio.run(scenario())


def test_owner_passes_are_serial_and_new_call_skips(owner, monkeypatch):
    module, _loop_fn = owner

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        started = asyncio.Event()
        release = threading.Event()
        state = {"calls": 0}

        def blocking_pass():
            state["calls"] += 1
            loop.call_soon_threadsafe(started.set)
            assert release.wait(2.0)
            return {"enabled": True}

        monkeypatch.setattr(module, "run_auto_certification", blocking_pass)
        first = loop.create_task(module.run_auto_certification_async())
        try:
            await asyncio.wait_for(started.wait(), 2.0)
            second = await module.run_auto_certification_async()
            assert second == {"skipped": "pass_in_progress"}
            assert state["calls"] == 1
        finally:
            release.set()
        assert await asyncio.wait_for(first, 2.0) == {"enabled": True}
        assert state["calls"] == 1

    asyncio.run(scenario())


def test_independent_owners_do_not_suppress_each_other(monkeypatch):
    stage = importlib.import_module("core.llm.stage_router_automation")
    fleet = importlib.import_module(
        "core.fleet_orchestration.fleet_router_automation")

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        stage_started = asyncio.Event()
        fleet_started = asyncio.Event()
        release = threading.Event()

        def stage_pass():
            loop.call_soon_threadsafe(stage_started.set)
            assert release.wait(2.0)
            return {"owner": "stage"}

        def fleet_pass():
            loop.call_soon_threadsafe(fleet_started.set)
            assert release.wait(2.0)
            return {"owner": "fleet"}

        monkeypatch.setattr(stage, "_pass_gate", threading.Lock())
        monkeypatch.setattr(fleet, "_pass_gate", threading.Lock())
        monkeypatch.setattr(
            stage, "_notification_loop",
            notification_loop_var("independent_stage_notification_loop"))
        monkeypatch.setattr(
            fleet, "_notification_loop",
            notification_loop_var("independent_fleet_notification_loop"))
        monkeypatch.setattr(stage, "run_auto_certification", stage_pass)
        monkeypatch.setattr(fleet, "run_auto_certification", fleet_pass)

        stage_task = loop.create_task(stage.run_auto_certification_async())
        fleet_task = loop.create_task(fleet.run_auto_certification_async())
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    stage_started.wait(), fleet_started.wait()), 2.0)
            assert not stage_task.done()
            assert not fleet_task.done()
        finally:
            release.set()

        results = await asyncio.wait_for(
            asyncio.gather(stage_task, fleet_task), 2.0)
        assert results == [{"owner": "stage"}, {"owner": "fleet"}]

    asyncio.run(scenario())


def test_cancellation_does_not_release_surviving_worker(owner, monkeypatch):
    module, _loop_fn = owner

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        first_started = asyncio.Event()
        first_finished = asyncio.Event()
        release = threading.Event()
        state = {"calls": 0}

        def blocking_pass():
            state["calls"] += 1
            loop.call_soon_threadsafe(first_started.set)
            try:
                assert release.wait(2.0)
                return {"enabled": True}
            finally:
                loop.call_soon_threadsafe(first_finished.set)

        monkeypatch.setattr(module, "run_auto_certification", blocking_pass)
        first = loop.create_task(module.run_auto_certification_async())
        await asyncio.wait_for(first_started.wait(), 2.0)

        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first

        replacement = await module.run_auto_certification_async()
        assert replacement == {"skipped": "pass_in_progress"}
        assert state["calls"] == 1
        assert not first_finished.is_set()

        release.set()
        await asyncio.wait_for(first_finished.wait(), 2.0)
        await _wait_until(lambda: not module._pass_gate.locked())

        monkeypatch.setattr(
            module, "run_auto_certification",
            lambda: {"enabled": True, "after": "physical-stop"})
        assert await module.run_auto_certification_async() == {
            "enabled": True, "after": "physical-stop"}
        assert state["calls"] == 1

    asyncio.run(scenario())


def test_exception_releases_gate_and_next_pass_runs(owner, monkeypatch):
    module, _loop_fn = owner

    async def scenario() -> None:
        def boom():
            raise RuntimeError("controlled pass failure")

        monkeypatch.setattr(module, "run_auto_certification", boom)
        with pytest.raises(RuntimeError, match="controlled pass failure"):
            await module.run_auto_certification_async()

        monkeypatch.setattr(
            module, "run_auto_certification", lambda: {"enabled": True})
        assert await module.run_auto_certification_async() == {
            "enabled": True}

    asyncio.run(scenario())


def test_stopiteration_becomes_runtimeerror_and_releases_gate(
        owner, monkeypatch):
    module, _loop_fn = owner

    async def scenario() -> None:
        def raises_stopiteration():
            raise StopIteration("controlled stop")

        monkeypatch.setattr(
            module, "run_auto_certification", raises_stopiteration)
        with pytest.raises(RuntimeError) as info:
            await module.run_auto_certification_async()
        assert type(info.value) is RuntimeError

        monkeypatch.setattr(
            module, "run_auto_certification", lambda: {"enabled": True})
        assert await module.run_auto_certification_async() == {
            "enabled": True}

    asyncio.run(scenario())


def test_worker_notification_is_delivered_on_application_loop(
        owner, monkeypatch):
    module, loop_fn = owner

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        clock = _StepClock()
        _install_clock(monkeypatch, module, clock)

        delivered = asyncio.Event()
        seen_loops = []

        async def fake_notify(*_args, **_kwargs):
            seen_loops.append(asyncio.get_running_loop())
            delivered.set()

        def pass_that_notifies():
            module._spawn_notification(
                "router_ready", "title", "message")
            return {"enabled": True}

        monkeypatch.setattr(module, "_notify", fake_notify)
        monkeypatch.setattr(
            module, "run_auto_certification", pass_that_notifies)
        task = loop.create_task(loop_fn())
        try:
            await clock.tick()
            await asyncio.wait_for(delivered.wait(), 2.0)
            assert seen_loops == [loop]
        finally:
            await _stop(task)

    asyncio.run(scenario())


def test_unbound_notification_uses_existing_sync_fallback(
        owner, monkeypatch):
    module, _loop_fn = owner
    captured = []

    class _RunRecorder:
        def run(self, coroutine):
            captured.append(coroutine)
            coroutine.close()

    async def fake_notify(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        module, "_notification_loop",
        notification_loop_var("unbound_notification_loop"))
    monkeypatch.setattr(module, "_notify", fake_notify)
    monkeypatch.setattr(
        module, "asyncio", type("_FakeAsyncio", (), {
            "run": _RunRecorder().run,
        })())
    monkeypatch.setattr(
        module, "get_event_loop",
        lambda: (_ for _ in ()).throw(RuntimeError("no loop")))

    module._spawn_notification("router_ready", "title", "message")
    assert len(captured) == 1
    assert captured[0].cr_frame is None


def test_owner_shutdown_race_closes_unscheduled_coroutine(
        owner, monkeypatch):
    module, _loop_fn = owner
    captured = []

    def refuse_schedule(coroutine, _loop):
        captured.append(coroutine)
        raise RuntimeError("controlled loop shutdown")

    def no_running_loop():
        raise RuntimeError("no running loop")

    fake_asyncio = type("_FakeAsyncio", (), {
        "get_running_loop": staticmethod(no_running_loop),
        "run_coroutine_threadsafe": staticmethod(refuse_schedule),
    })()
    app_loop = type("_AppLoop", (), {
        "is_running": lambda self: True,
        "is_closed": lambda self: False,
    })()
    monkeypatch.setattr(module, "asyncio", fake_asyncio)
    token = module._notification_loop.set(app_loop)
    try:
        module._spawn_notification("router_ready", "title", "message")
    finally:
        module._notification_loop.reset(token)

    assert len(captured) == 1
    assert captured[0].cr_frame is None


_ROUTE_CASES = [
    (
        "api.stage_router_routes",
        "core.llm.stage_router_automation",
        "Automation run failed",
    ),
    (
        "api.fleet_router_routes",
        "core.fleet_orchestration.fleet_router_automation",
        "Automation run failed",
    ),
]


@pytest.mark.parametrize("route_path,owner_path,_detail", _ROUTE_CASES)
def test_run_now_route_awaits_shared_worker_boundary(
        monkeypatch, route_path, owner_path, _detail):
    routes = importlib.import_module(route_path)
    module = importlib.import_module(owner_path)
    monkeypatch.setattr(module, "_pass_gate", threading.Lock())
    monkeypatch.setattr(
        module, "_notification_loop",
        notification_loop_var(f"{route_path}_route_notification_loop"))
    expected = {"enabled": True, "queued": ["controlled-review"]}

    async def scenario():
        loop = asyncio.get_running_loop()
        heartbeat = threading.Event()

        def blocking_pass():
            loop.call_soon_threadsafe(heartbeat.set)
            assert heartbeat.wait(1.0), "run-now route blocked the loop"
            return expected

        monkeypatch.setattr(module, "run_auto_certification", blocking_pass)
        return await routes.run_automation_now(_admin=None)

    assert asyncio.run(scenario()) is expected


@pytest.mark.parametrize("route_path,owner_path,detail", _ROUTE_CASES)
def test_run_now_route_preserves_error_shape(
        monkeypatch, route_path, owner_path, detail):
    from fastapi import HTTPException

    routes = importlib.import_module(route_path)
    module = importlib.import_module(owner_path)
    monkeypatch.setattr(module, "_pass_gate", threading.Lock())
    monkeypatch.setattr(
        module, "_notification_loop",
        notification_loop_var(f"{route_path}_route_error_loop"))

    def boom():
        raise RuntimeError("controlled route failure")

    monkeypatch.setattr(module, "run_auto_certification", boom)
    with pytest.raises(HTTPException) as info:
        asyncio.run(routes.run_automation_now(_admin=None))

    assert info.value.status_code == 500
    assert info.value.detail == detail
