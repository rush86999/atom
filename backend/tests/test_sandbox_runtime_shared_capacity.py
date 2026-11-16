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
