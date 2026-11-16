"""Process-wide, cancellation-safe sandbox capacity gates.

Official guidance:
  * asyncio synchronization primitives are NOT thread-safe and are intended
    for one event loop: https://docs.python.org/3/library/asyncio-sync.html
  * a semaphore decrements on acquire and increments on release, ideally with
    ``async with`` around the shared-resource section:
    https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore
  * ``threading.Lock`` is the stdlib tool for state shared by OS threads:
    https://docs.python.org/3/library/threading.html#lock-objects

The backend resource (Docker daemon/VM capacity) is process-wide, not
loop-scoped, and factories construct new runtime instances. This module keeps
one process-wide counter per backend. Waiters are futures on their own loops;
a release hands the permit directly to the next live waiter with
``call_soon_threadsafe``. No event loop blocks on a thread semaphore.
"""
from __future__ import annotations

import asyncio
import contextvars
import threading
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional
from weakref import WeakKeyDictionary

_gates: Dict[str, "_Gate"] = {}
_gates_lock = threading.Lock()
_loop_proxies: "WeakKeyDictionary[object, Dict[str, CapacitySemaphore]]" = (
    WeakKeyDictionary())


class _Permit:
    __slots__ = ("_gate", "_released")

    def __init__(self, gate):
        self._gate = gate
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._gate.release()


@dataclass
class _Waiter:
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future
    granted: bool = False


class _Gate:
    def __init__(self, limit: int):
        self.limit = max(1, int(limit))
        self._lock = threading.Lock()
        self._in_use = 0
        self._waiters: Deque[_Waiter] = deque()

    async def acquire(self) -> _Permit:
        loop = asyncio.get_running_loop()
        with self._lock:
            if self._in_use < self.limit and not self._waiters:
                self._in_use += 1
                return _Permit(self)
            waiter = _Waiter(loop=loop, future=loop.create_future())
            self._waiters.append(waiter)
        try:
            await waiter.future
        except asyncio.CancelledError:
            with self._lock:
                if waiter.granted:
                    # The permit was transferred just before cancellation;
                    # return it rather than leaking the slot.
                    self._release_locked()
                else:
                    try:
                        self._waiters.remove(waiter)
                    except ValueError:
                        pass
            raise
        return _Permit(self)

    def release(self) -> None:
        with self._lock:
            self._release_locked()

    def _release_locked(self) -> None:
        while self._waiters:
            waiter = self._waiters.popleft()
            if waiter.future.done():
                continue
            waiter.granted = True
            try:
                waiter.loop.call_soon_threadsafe(self._grant, waiter)
            except RuntimeError:
                waiter.granted = False
                continue
            return
        if self._in_use > 0:
            self._in_use -= 1

    @staticmethod
    def _grant(waiter: _Waiter) -> None:
        if not waiter.future.done():
            waiter.future.set_result(True)

    def snapshot(self) -> dict:
        with self._lock:
            return {"limit": self.limit, "in_use": self._in_use,
                    "waiters": len(self._waiters)}


async def await_teardown(coro) -> None:
    """Finish owned process teardown before a cancelled caller releases capacity.

    A cancelled task would otherwise abandon an awaited ``proc.wait()`` and
    release the permit while the child is still draining. The teardown runs in
    its own task, shielded from caller cancellation; repeated cancellation is
    absorbed until it finishes, then CancelledError is re-raised.
    """
    task = asyncio.ensure_future(coro)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
            continue
    try:
        task.result()
    except asyncio.CancelledError:
        cancelled = True
    except Exception:  # noqa: BLE001 - teardown is best effort
        pass
    if cancelled:
        raise asyncio.CancelledError()


class CapacitySemaphore:
    """Per-loop adapter over the process-wide gate.

    ``async with`` records THIS task's permit in a ContextVar; concurrent
    tasks on the same loop cannot overwrite one another's permit.
    """

    def __init__(self, gate: _Gate):
        self._gate = gate
        self._permit_var: contextvars.ContextVar = contextvars.ContextVar(
            f"capacity_permit_{id(self)}", default=())

    async def __aenter__(self):
        permit = await self._gate.acquire()
        self._permit_var.set(self._permit_var.get() + (permit,))
        return self

    async def __aexit__(self, exc_type, exc, tb):
        stack = self._permit_var.get()
        if not stack:
            return False
        permit = stack[-1]
        self._permit_var.set(stack[:-1])
        permit.release()
        return False


def get_capacity_semaphore(scope: str, limit: int) -> CapacitySemaphore:
    """Return a loop-bound adapter sharing the process-wide ``scope`` gate."""
    loop = asyncio.get_running_loop()
    with _gates_lock:
        gate = _gates.get(scope)
        if gate is None:
            gate = _Gate(limit)
            _gates[scope] = gate
        per_loop = _loop_proxies.get(loop)
        if per_loop is None:
            per_loop = {}
            _loop_proxies[loop] = per_loop
        proxy = per_loop.get(scope)
        if proxy is None:
            proxy = CapacitySemaphore(gate)
            per_loop[scope] = proxy
        return proxy


def snapshot(scope: str) -> dict:
    with _gates_lock:
        gate = _gates.get(scope)
    return gate.snapshot() if gate is not None else {
        "limit": 0, "in_use": 0, "waiters": 0}


def reset_for_tests(scope: Optional[str] = None) -> None:
    """Clear idle test scopes; refuse to release a live production bound."""
    with _gates_lock:
        scopes = [scope] if scope else list(_gates)
        for name in scopes:
            gate = _gates.get(name)
            if gate is None:
                continue
            state = gate.snapshot()
            if state["in_use"] or state["waiters"]:
                raise RuntimeError(
                    f"capacity scope {name!r} is still in use; refusing reset")
            _gates.pop(name, None)
        for per_loop in list(_loop_proxies.values()):
            for name in scopes:
                per_loop.pop(name, None)
