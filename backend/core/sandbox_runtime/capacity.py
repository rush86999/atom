"""Process-wide, loop-scoped capacity semaphores for sandbox runtimes.

Official asyncio guidance: synchronization primitives are not thread-safe and
should be used from one event loop; a Semaphore decrements on acquire and
increments on release (https://docs.python.org/3/library/asyncio-sync.html).
AnyIO similarly recommends a capacity limiter/semaphore around the whole
shared-resource use (https://anyio.readthedocs.io/en/stable/synchronization.html).

Factories construct a new runtime per call, so an instance attribute cannot
bound the real host resource. This registry shares one semaphore per backend
and running loop across all instances; the semaphore is held for the complete
spawn/exchange/teardown lifecycle, not just id creation.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Dict, Optional
from weakref import WeakKeyDictionary

_registry: "WeakKeyDictionary[object, Dict[str, asyncio.Semaphore]]" = (
    WeakKeyDictionary())
_registry_lock = threading.Lock()


def get_capacity_semaphore(scope: str, limit: int) -> asyncio.Semaphore:
    """Return the shared semaphore for ``scope`` on the running loop."""
    loop = asyncio.get_running_loop()
    with _registry_lock:
        per_loop = _registry.get(loop)
        if per_loop is None:
            per_loop = {}
            _registry[loop] = per_loop
        sem = per_loop.get(scope)
        if sem is None:
            sem = asyncio.Semaphore(max(1, int(limit)))
            per_loop[scope] = sem
        return sem


def reset_for_tests(scope: Optional[str] = None) -> None:
    """Clear cached semaphores (tests only; runtime never calls this)."""
    with _registry_lock:
        if scope is None:
            _registry.clear()
            return
        for per_loop in list(_registry.values()):
            per_loop.pop(scope, None)
