"""Deterministic offline capacity tests for both mini-app runtimes.

No Docker/Firecracker process, image, network or model is started. The only
process calls are replaced with in-memory barriers; the real driver lifecycle
(spawn -> exchange -> teardown) is exercised.
"""
from __future__ import annotations

import asyncio

import pytest

import core.sandbox_runtime.capacity as capacity
import core.sandbox_runtime.firecracker_runner as fc_mod
import core.sandbox_runtime.miniapp_dev_runner as dev_mod


class _QuietStderr:
    async def readline(self):
        return b""


class FakeProc:
    def __init__(self, cleanup_event=None):
        self.returncode = None
        self.stdout = None
        self.stdin = None
        self.stderr = _QuietStderr()
        self.killed = False
        self._cleanup_event = cleanup_event
        self.cleanup_started = asyncio.Event() if cleanup_event is not None else None
        self.cleanup_count = 0

    def kill(self):
        self.killed = True

    async def wait(self):
        self.cleanup_count += 1
        if self.cleanup_started is not None:
            self.cleanup_started.set()
        if self._cleanup_event is not None:
            await self._cleanup_event.wait()
        self.returncode = 0
        return 0


def _install_proc(p, cleanup_event=None):
    created = []

    async def fake_exec(*args, **kwargs):
        proc = FakeProc(cleanup_event)
        created.append(proc)
        return proc
    p.setattr(asyncio, "create_subprocess_exec", fake_exec)
    return created


@pytest.mark.parametrize("kind", ["dev", "fc"])
def test_cap2_holds_across_new_factory_instances(monkeypatch, kind):
    monkeypatch.setenv("ATOM_SANDBOX_VM_MAX_CONCURRENCY", "2")
    capacity.reset_for_tests()
    _install_proc(monkeypatch)
    started = asyncio.Event()
    release = asyncio.Event()
    state = {"active": 0, "max": 0}

    async def exchange(*args, **kwargs):
        state["active"] += 1
        state["max"] = max(state["max"], state["active"])
        if state["active"] >= 2:
            started.set()
        await release.wait()
        state["active"] -= 1
        return "", "", 0, None, None

    if kind == "dev":
        monkeypatch.setattr(dev_mod, "_guest_exchange", exchange)
        factory = dev_mod.MiniAppDevRuntime
    else:
        monkeypatch.setattr(fc_mod.FirecrackerRuntime, "_exchange", exchange)
        factory = fc_mod.FirecrackerRuntime

    async def run_all():
        tasks = [asyncio.create_task(_one(factory(), kind))
                 for _ in range(6)]
        await asyncio.wait_for(started.wait(), timeout=2)
        assert state["max"] <= 2, state
        release.set()
        return await asyncio.gather(*tasks)

    async def _one(runtime, k):
        if k == "dev":
            return await runtime._run_in_container(
                "print(1)", policy=_Policy(), inputs={}, tag="img")
        return await runtime._run_in_vm(
            "print(1)", policy=_Policy(), inputs={}, rootfs="/tmp/fake.ext4")

    results = asyncio.run(run_all())
    assert all(r.success for r in results)
    assert state["max"] == 2, state
    capacity.reset_for_tests()


@pytest.mark.parametrize("kind", ["dev", "fc"])
def test_permit_retained_through_cleanup(monkeypatch, kind):
    monkeypatch.setenv("ATOM_SANDBOX_VM_MAX_CONCURRENCY", "2")
    capacity.reset_for_tests()
    cleanup_release = asyncio.Event()
    created = _install_proc(monkeypatch, cleanup_release)
    entered = asyncio.Event()
    active = {"n": 0}

    async def exchange(*args, **kwargs):
        active["n"] += 1
        if active["n"] >= 2:
            entered.set()
        return "", "", 0, None, None

    if kind == "dev":
        monkeypatch.setattr(dev_mod, "_guest_exchange", exchange)
        factory = dev_mod.MiniAppDevRuntime
    else:
        monkeypatch.setattr(fc_mod.FirecrackerRuntime, "_exchange", exchange)
        factory = fc_mod.FirecrackerRuntime

    async def run_one(runtime):
        if kind == "dev":
            return await runtime._run_in_container(
                "print(1)", policy=_Policy(), inputs={}, tag="img")
        return await runtime._run_in_vm(
            "print(1)", policy=_Policy(), inputs={}, rootfs="/tmp/fake.ext4")

    async def scenario():
        tasks = [asyncio.create_task(run_one(factory())) for _ in range(2)]
        await asyncio.wait_for(entered.wait(), timeout=2)
        # Both are in process wait(); a third must not spawn yet.
        third = asyncio.create_task(run_one(factory()))
        await asyncio.sleep(0.05)
        assert not third.done()
        assert len(created) == 2, [p.cleanup_count for p in created]
        cleanup_release.set()
        return await asyncio.gather(*tasks, third)

    try:
        results = asyncio.run(scenario())
    finally:
        capacity.reset_for_tests()
    assert all(r.success for r in results)
    assert all(p.cleanup_count == 1 for p in created)


@pytest.mark.parametrize("kind", ["dev", "fc"])
def test_cancellation_releases_permit(monkeypatch, kind):
    monkeypatch.setenv("ATOM_SANDBOX_VM_MAX_CONCURRENCY", "1")
    capacity.reset_for_tests()
    _install_proc(monkeypatch)
    first_started = asyncio.Event()
    second_started = asyncio.Event()
    calls = {"n": 0}

    async def exchange(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            first_started.set()
            await asyncio.sleep(60)
        second_started.set()
        await asyncio.sleep(60)
        return "", "", 0, None, None

    if kind == "dev":
        monkeypatch.setattr(dev_mod, "_guest_exchange", exchange)
        factory = dev_mod.MiniAppDevRuntime
    else:
        monkeypatch.setattr(fc_mod.FirecrackerRuntime, "_exchange", exchange)
        factory = fc_mod.FirecrackerRuntime

    async def run_one(runtime):
        if kind == "dev":
            return await runtime._run_in_container(
                "print(1)", policy=_Policy(), inputs={}, tag="img")
        return await runtime._run_in_vm(
            "print(1)", policy=_Policy(), inputs={}, rootfs="/tmp/fake.ext4")

    async def scenario():
        first = asyncio.create_task(run_one(factory()))
        await asyncio.wait_for(first_started.wait(), timeout=2)
        second = asyncio.create_task(run_one(factory()))
        await asyncio.sleep(0.05)
        assert not second_started.is_set()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        await asyncio.wait_for(second_started.wait(), timeout=2)
        second.cancel()
        with pytest.raises(asyncio.CancelledError):
            await second

    try:
        asyncio.run(scenario())
    finally:
        capacity.reset_for_tests()


class _Policy:
    max_exec_seconds = 1


def test_capacity2_across_two_loops_in_two_threads():
    import threading
    import time
    import uuid

    scope = "test-multiloop-" + uuid.uuid4().hex
    lock = threading.Lock()
    released = threading.Event()
    entered = threading.Event()
    state = {"active": 0, "max": 0}

    async def worker_tasks():
        sem = capacity.get_capacity_semaphore(scope, 2)

        async def one():
            async with sem:
                with lock:
                    state["active"] += 1
                    state["max"] = max(state["max"], state["active"])
                    if state["active"] >= 2:
                        entered.set()
                await asyncio.to_thread(released.wait)
                with lock:
                    state["active"] -= 1
        await asyncio.gather(*(one() for _ in range(3)))

    def run_loop():
        asyncio.run(worker_tasks())

    threads = [threading.Thread(target=run_loop) for _ in range(2)]
    for thread in threads:
        thread.start()
    assert entered.wait(5), "two permits were not acquired"
    time.sleep(0.2)
    assert state["max"] <= 2, state
    released.set()
    for thread in threads:
        thread.join(timeout=5)
    assert state["max"] == 2, state
    assert capacity.snapshot(scope)["in_use"] == 0


def test_queued_waiter_cancellation_releases_no_slot():
    scope = "test-waiter-cancel"
    capacity.reset_for_tests(scope)

    async def scenario():
        sem = capacity.get_capacity_semaphore(scope, 1)
        holder_started = asyncio.Event()
        release_holder = asyncio.Event()

        async def holder():
            async with sem:
                holder_started.set()
                await release_holder.wait()

        async def waiter():
            async with sem:
                return "acquired"

        h = asyncio.create_task(holder())
        await holder_started.wait()
        w = asyncio.create_task(waiter())
        await asyncio.sleep(0.05)
        w.cancel()
        with pytest.raises(asyncio.CancelledError):
            await w
        release_holder.set()
        await h
        second = await asyncio.wait_for(waiter(), timeout=2)
        assert second == "acquired"
        assert capacity.snapshot(scope)["in_use"] == 0

    asyncio.run(scenario())
    capacity.reset_for_tests(scope)


def test_holder_cancellation_releases_slot():
    scope = "test-holder-cancel"
    capacity.reset_for_tests(scope)

    async def scenario():
        sem = capacity.get_capacity_semaphore(scope, 1)
        started = asyncio.Event()

        async def holder():
            async with sem:
                started.set()
                await asyncio.sleep(60)

        h = asyncio.create_task(holder())
        await started.wait()
        h.cancel()
        with pytest.raises(asyncio.CancelledError):
            await h
        async with sem:
            assert capacity.snapshot(scope)["in_use"] == 1
        assert capacity.snapshot(scope)["in_use"] == 0

    asyncio.run(scenario())
    capacity.reset_for_tests(scope)


@pytest.mark.parametrize("kind", ["dev", "fc"])
def test_cancellation_during_blocked_teardown_holds_permit(monkeypatch, kind):
    monkeypatch.setenv("ATOM_SANDBOX_VM_MAX_CONCURRENCY", "1")
    capacity.reset_for_tests()
    cleanup_release = asyncio.Event()
    created = _install_proc(monkeypatch, cleanup_release)
    entered = asyncio.Event()

    async def exchange(*args, **kwargs):
        return "", "", 0, None, None

    if kind == "dev":
        monkeypatch.setattr(dev_mod, "_guest_exchange", exchange)
        factory = dev_mod.MiniAppDevRuntime
    else:
        monkeypatch.setattr(fc_mod.FirecrackerRuntime, "_exchange", exchange)
        factory = fc_mod.FirecrackerRuntime

    async def run_one(runtime):
        if kind == "dev":
            return await runtime._run_in_container(
                "print(1)", policy=_Policy(), inputs={}, tag="img")
        return await runtime._run_in_vm(
            "print(1)", policy=_Policy(), inputs={}, rootfs="/tmp/fake.ext4")

    async def scenario():
        first = asyncio.create_task(run_one(factory()))
        while not created:
            await asyncio.sleep(0)
        # Wait until the first process is in blocked teardown.
        while not created[0].cleanup_started.is_set():
            await asyncio.sleep(0)
        second = asyncio.create_task(run_one(factory()))
        await asyncio.sleep(0.05)
        assert len(created) == 1
        first.cancel()
        # Repeated cancellation must not release the permit or start the next
        # process before the owned process teardown finishes.
        first.cancel()
        await asyncio.sleep(0.05)
        assert len(created) == 1
        cleanup_release.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        result = await asyncio.wait_for(second, timeout=2)
        assert result.success

    try:
        asyncio.run(scenario())
    finally:
        capacity.reset_for_tests()
