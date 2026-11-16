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
    def __init__(self, cleanup_event=None, *, wait_error=None,
                 kill_error=None, exit_code=0):
        self.returncode = None
        self._exit_code = exit_code
        self.stdout = None
        self.stdin = None
        self.stderr = _QuietStderr()
        self.killed = False
        self._cleanup_event = cleanup_event
        self._wait_error = wait_error
        self._kill_error = kill_error
        self.cleanup_started = asyncio.Event() if cleanup_event is not None else None
        self.cleanup_count = 0

    def kill(self):
        if self._kill_error is not None:
            raise self._kill_error
        self.killed = True

    async def wait(self):
        self.cleanup_count += 1
        if self.cleanup_started is not None:
            self.cleanup_started.set()
        if self._wait_error is not None:
            raise self._wait_error
        if self._cleanup_event is not None:
            await self._cleanup_event.wait()
        self.returncode = self._exit_code
        return self._exit_code


class FakeCLI:
    def __init__(self, returncode=0, stdout=b"", stderr=b"", *,
                 communicate_error=None):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self._communicate_error = communicate_error
        self.killed = False

    async def communicate(self):
        if self._communicate_error is not None:
            raise self._communicate_error
        return self.stdout, self.stderr

    def kill(self):
        self.killed = True


def _install_proc(p, cleanup_event=None, *, wait_error=None, kill_error=None):
    created = []

    async def fake_exec(*args, **kwargs):
        proc = FakeProc(cleanup_event, wait_error=wait_error,
                        kill_error=kill_error)
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


@pytest.mark.parametrize("kind", ["dev", "fc"])
def test_unconfirmed_wait_never_succeeds_or_frees_capacity(monkeypatch, kind):
    import uuid
    monkeypatch.setenv("ATOM_SANDBOX_VM_MAX_CONCURRENCY", "1")
    scope = "test-unconfirmed-" + uuid.uuid4().hex
    if kind == "dev":
        monkeypatch.setattr(dev_mod, "CAPACITY_SCOPE", scope)
        monkeypatch.setattr(dev_mod, "_guest_exchange", _ok_exchange)
        factory = dev_mod.MiniAppDevRuntime
    else:
        monkeypatch.setattr(fc_mod, "CAPACITY_SCOPE", scope)
        monkeypatch.setattr(fc_mod.FirecrackerRuntime, "_exchange", _ok_exchange)
        factory = fc_mod.FirecrackerRuntime
    created = _install_proc(monkeypatch, wait_error=OSError("wait failed"))

    first = asyncio.run(_run_one(factory(), kind))
    assert first.success is False
    assert first.exit_code == -1
    assert first.metadata["reason"] == "cleanup_unconfirmed"
    assert capacity.snapshot(scope)["quarantined"]
    assert len(created) == 1

    second = asyncio.run(_run_one(factory(), kind))
    assert second.success is False
    assert second.metadata["reason"] == "capacity_quarantined"
    assert len(created) == 1


@pytest.mark.parametrize("kind", ["dev", "fc"])
def test_unconfirmed_kill_never_succeeds_or_frees_capacity(monkeypatch, kind):
    import uuid
    monkeypatch.setenv("ATOM_SANDBOX_VM_MAX_CONCURRENCY", "1")
    scope = "test-kill-" + uuid.uuid4().hex
    if kind == "dev":
        monkeypatch.setattr(dev_mod, "CAPACITY_SCOPE", scope)
        monkeypatch.setattr(dev_mod, "_guest_exchange", _ok_exchange)
        factory = dev_mod.MiniAppDevRuntime
    else:
        monkeypatch.setattr(fc_mod, "CAPACITY_SCOPE", scope)
        monkeypatch.setattr(fc_mod.FirecrackerRuntime, "_exchange", _ok_exchange)
        factory = fc_mod.FirecrackerRuntime
    created = _install_proc(monkeypatch, kill_error=OSError("kill failed"))

    first = asyncio.run(_run_one(factory(), kind))
    assert first.success is False
    assert first.metadata["reason"] == "cleanup_unconfirmed"
    assert capacity.snapshot(scope)["quarantined"]
    assert len(created) == 1
    second = asyncio.run(_run_one(factory(), kind))
    assert second.success is False
    assert second.metadata["reason"] == "capacity_quarantined"
    assert len(created) == 1


@pytest.mark.parametrize("kind", ["dev", "fc"])
def test_known_exited_wait_error_does_not_poison(monkeypatch, kind):
    import uuid
    monkeypatch.setenv("ATOM_SANDBOX_VM_MAX_CONCURRENCY", "1")
    scope = "test-known-exit-" + uuid.uuid4().hex
    if kind == "dev":
        monkeypatch.setattr(dev_mod, "CAPACITY_SCOPE", scope)
        monkeypatch.setattr(dev_mod, "_guest_exchange", _ok_exchange)
        factory = dev_mod.MiniAppDevRuntime
    else:
        monkeypatch.setattr(fc_mod, "CAPACITY_SCOPE", scope)
        monkeypatch.setattr(fc_mod.FirecrackerRuntime, "_exchange", _ok_exchange)
        factory = fc_mod.FirecrackerRuntime

    async def fake_exec(*a, **k):
        proc = FakeProc(wait_error=OSError("wait failed"))
        proc.returncode = 0
        return proc
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    first = asyncio.run(_run_one(factory(), kind))
    assert first.success is True
    assert first.exit_code == 0
    assert not capacity.snapshot(scope)["quarantined"]
    second = asyncio.run(_run_one(factory(), kind))
    assert second.success is True


async def _ok_exchange(*args, **kwargs):
    return "", "", 0, None, None


async def _run_one(runtime, kind):
    if kind == "dev":
        return await runtime._run_in_container(
            "print(1)", policy=_Policy(), inputs={}, tag="img")
    return await runtime._run_in_vm(
        "print(1)", policy=_Policy(), inputs={}, rootfs="/tmp/fake.ext4")


def _install_docker_cli(monkeypatch, *, exit_code=-9, rm_rc=0,
                        rm_stderr=b"", rm_error=None):
    created = []
    rm_calls = []

    async def fake_exec(*args, **kwargs):
        if args[:2] == ("docker", "rm"):
            target = args[3]
            rm_calls.append(target)
            stderr = rm_stderr.replace(b"{target}", target.encode())
            return FakeCLI(returncode=rm_rc, stderr=stderr,
                           communicate_error=rm_error)
        proc = FakeProc(exit_code=exit_code)
        created.append(proc)
        return proc
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    return created, rm_calls


def _run_dev():
    return dev_mod.MiniAppDevRuntime()._run_in_container(
        "print(1)", policy=_Policy(), inputs={}, tag="img")


@pytest.mark.parametrize("rm_rc,rm_stderr,rm_error,success", [
    (0, b"", None, True),
    (1, b"Error response from daemon: remove target: container is running",
     None, False),
    (1, b"Cannot connect to the Docker daemon", None, False),
    (1, b"Error response from daemon: No such container: other-container",
     None, False),
    (1, b"Error response from daemon: No such container: {target}",
     None, True),
    (0, b"", asyncio.TimeoutError(), False),
])
def test_container_removal_must_be_confirmed(monkeypatch, rm_rc, rm_stderr,
                                             rm_error, success):
    import uuid
    monkeypatch.setenv("ATOM_SANDBOX_VM_MAX_CONCURRENCY", "1")
    scope = "test-rm-" + uuid.uuid4().hex
    monkeypatch.setattr(dev_mod, "CAPACITY_SCOPE", scope)
    async def exchange(*a, **k):
        return "", "", 0, None, None
    monkeypatch.setattr(dev_mod, "_guest_exchange", exchange)
    created, rm_calls = _install_docker_cli(
        monkeypatch, rm_rc=rm_rc, rm_stderr=rm_stderr, rm_error=rm_error)

    result = asyncio.run(_run_dev())
    assert result.success is success, result
    assert len(created) == 1
    assert len(rm_calls) == 1
    snapshot = capacity.snapshot(scope)
    if success:
        assert result.exit_code == 0
        assert not snapshot["quarantined"]
        assert snapshot["in_use"] == 0
    else:
        assert result.exit_code == -1
        assert result.metadata["reason"] == "cleanup_unconfirmed"
        assert snapshot["quarantined"]
        second = asyncio.run(_run_dev())
        assert second.success is False
        assert second.metadata["reason"] == "capacity_quarantined"
        assert len(created) == 1


def test_rm_failure_refuses_queued_caller(monkeypatch):
    import uuid
    monkeypatch.setenv("ATOM_SANDBOX_VM_MAX_CONCURRENCY", "1")
    scope = "test-rm-queue-" + uuid.uuid4().hex
    monkeypatch.setattr(dev_mod, "CAPACITY_SCOPE", scope)

    async def exchange(*a, **k):
        return "", "", 0, None, None
    monkeypatch.setattr(dev_mod, "_guest_exchange", exchange)

    rm_started = asyncio.Event()
    rm_release = asyncio.Event()
    created = []

    class BlockingRm(FakeCLI):
        async def communicate(self):
            rm_started.set()
            await rm_release.wait()
            return b"", b"Error response from daemon: daemon unavailable"

    async def fake_exec(*args, **kwargs):
        if args[:2] == ("docker", "rm"):
            return BlockingRm(returncode=1)
        proc = FakeProc(exit_code=-9)
        created.append(proc)
        return proc
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    async def call():
        return await dev_mod.MiniAppDevRuntime()._run_in_container(
            "print(1)", policy=_Policy(), inputs={}, tag="img")

    async def scenario():
        first = asyncio.create_task(call())
        await asyncio.wait_for(rm_started.wait(), timeout=2)
        second = asyncio.create_task(call())
        await asyncio.sleep(0.05)
        assert not second.done()
        rm_release.set()
        a, b = await asyncio.gather(first, second)
        assert a.success is False and a.metadata["reason"] == "cleanup_unconfirmed"
        assert b.success is False
        assert b.metadata["reason"] == "capacity_quarantined"
        assert len(created) == 1

    asyncio.run(scenario())
