"""Shared stdlib automation-worker mechanisms in ``core.asyncio_compat``.

These are bounded, event-driven controls for the small shared boundary used by
the org-politics, stage-router and fleet-router automation owners. They cover
context propagation, origin-loop binding, thread-gate serialization,
StopIteration conversion and notification scheduling. No database, model,
network, notification service or real timer is touched.
"""
from __future__ import annotations

import asyncio
import contextvars
import threading
from types import SimpleNamespace

import pytest

from core.asyncio_compat import (
    notification_loop_var,
    run_sync_in_worker,
    run_with_thread_gate,
    schedule_notification,
)


def test_worker_receives_copied_context_and_origin_loop():
    loop_var = notification_loop_var("shared_test_origin")
    probe = contextvars.ContextVar("shared_test_probe", default="unset")
    observed = {}

    async def scenario():
        loop = asyncio.get_running_loop()
        probe.set("caller")
        heartbeat = threading.Event()

        def worker():
            observed["probe"] = probe.get()
            observed["origin"] = loop_var.get()
            loop.call_soon_threadsafe(heartbeat.set)
            observed["heartbeat"] = heartbeat.wait(1.0)
            probe.set("worker")  # must stay inside the copied worker context
            return {"ok": True}

        result = await run_sync_in_worker(worker, loop_var)
        # The application-loop copy is untouched by the worker mutation.
        assert probe.get() == "caller"
        assert loop_var.get() is None
        return loop, result

    loop, result = asyncio.run(scenario())
    assert result == {"ok": True}
    assert observed == {
        "probe": "caller",
        "origin": loop,
        "heartbeat": True,
    }


def test_worker_converts_stopiteration_to_runtimeerror():
    loop_var = notification_loop_var("shared_test_stopiteration")

    async def scenario():
        def raises_stopiteration():
            raise StopIteration("controlled stop")

        with pytest.raises(RuntimeError) as info:
            await run_sync_in_worker(raises_stopiteration, loop_var)
        assert type(info.value) is RuntimeError
        assert loop_var.get() is None

    asyncio.run(scenario())


def test_thread_gate_is_serial_per_gate_and_independent_across_gates():
    gate_a = threading.Lock()
    gate_b = threading.Lock()
    started = threading.Event()
    release = threading.Event()
    state = {"calls": 0}
    holder = {}

    def first():
        state["calls"] += 1
        started.set()
        assert release.wait(2.0)
        return "first"

    thread = threading.Thread(
        target=lambda: holder.update(
            result=run_with_thread_gate(gate_a, first)))
    thread.start()
    try:
        assert started.wait(2.0)
        second = run_with_thread_gate(gate_a, lambda: "second")
        assert second == {"skipped": "pass_in_progress"}
        assert state["calls"] == 1
        # A different owner's gate must not be suppressed by gate_a.
        assert run_with_thread_gate(gate_b, lambda: "independent") == (
            "independent")
    finally:
        release.set()
        thread.join(2.0)
    assert not thread.is_alive()
    assert holder["result"] == "first"
    assert run_with_thread_gate(gate_a, lambda: "after") == "after"


def test_schedule_notification_delivers_on_original_loop():
    loop_var = notification_loop_var("shared_test_schedule")
    calls = {"factory": 0}

    async def scenario():
        loop = asyncio.get_running_loop()
        delivered = asyncio.Event()
        seen = []
        token = loop_var.set(loop)
        try:
            async def notify():
                seen.append(asyncio.get_running_loop())
                delivered.set()

            def factory():
                calls["factory"] += 1
                return notify()

            assert schedule_notification(loop_var, factory) is True
            await asyncio.wait_for(delivered.wait(), 2.0)
        finally:
            loop_var.reset(token)
        assert seen == [loop]
        assert calls["factory"] == 1

    asyncio.run(scenario())


def test_schedule_notification_unbound_creates_no_coroutine():
    loop_var = notification_loop_var("shared_test_unbound")
    calls = {"factory": 0}

    async def never():
        await asyncio.sleep(0)

    def factory():
        calls["factory"] += 1
        return never()

    assert schedule_notification(loop_var, factory) is False
    assert calls["factory"] == 0


def test_schedule_notification_threadsafe_refusal_closes_one_coroutine():
    loop_var = notification_loop_var("shared_test_threadsafe_refusal")
    captured = []
    calls = {"factory": 0}

    async def never():
        await asyncio.sleep(0)

    def factory():
        calls["factory"] += 1
        return never()

    def refuse_schedule(coroutine, _loop):
        captured.append(coroutine)
        raise RuntimeError("controlled loop shutdown")

    def no_running_loop():
        raise RuntimeError("no running loop")

    fake_asyncio = SimpleNamespace(
        get_running_loop=no_running_loop,
        run_coroutine_threadsafe=refuse_schedule,
    )
    app_loop = SimpleNamespace(
        is_running=lambda: True, is_closed=lambda: False)
    token = loop_var.set(app_loop)
    try:
        handled = schedule_notification(
            loop_var, factory, asyncio_module=fake_asyncio)
    finally:
        loop_var.reset(token)

    assert handled is True
    assert calls["factory"] == 1
    assert len(captured) == 1
    assert captured[0].cr_frame is None


def test_schedule_notification_create_task_refusal_closes_one_coroutine():
    loop_var = notification_loop_var("shared_test_task_refusal")
    captured = []
    calls = {"factory": 0}

    async def never():
        await asyncio.sleep(0)

    def factory():
        calls["factory"] += 1
        return never()

    def refuse_task(coroutine):
        captured.append(coroutine)
        raise RuntimeError("controlled loop shutdown")

    app_loop = SimpleNamespace(create_task=refuse_task)
    fake_asyncio = SimpleNamespace(get_running_loop=lambda: app_loop)
    token = loop_var.set(app_loop)
    try:
        handled = schedule_notification(
            loop_var, factory, asyncio_module=fake_asyncio)
    finally:
        loop_var.reset(token)

    assert handled is True
    assert calls["factory"] == 1
    assert len(captured) == 1
    assert captured[0].cr_frame is None
