"""Python 3.12+/3.14 asyncio compatibility shims.

`get_event_loop()` lost its implicit loop creation in 3.14 — it now
raises RuntimeError whenever no loop is set for the current thread, breaking
every sync helper that used the old main-thread auto-create behavior. This
module restores the pre-3.14 semantics:

    running loop (async context) -> set loop -> create + set one

`iscoroutinefunction` re-exports `inspect.iscoroutinefunction` —
`asyncio.iscoroutinefunction` was removed in 3.14 and has been a thin alias
for the inspect version since the @asyncio.coroutine decorator was removed
in 3.11, so the swap is behavior-identical on 3.11+.
"""
import asyncio
import atexit
import inspect

__all__ = ["get_event_loop", "iscoroutinefunction"]

# Strong refs: asyncio.set_event_loop stores only a WEAK ref, so a created
# loop dropped by its caller can be GC'd — on 3.14 that surfaces as
# BaseEventLoop.__del__ raising AttributeError ('_UnixSelectorEventLoop' has
# no attribute '_closed') in sys.unraisablehook, which pytest treats as a
# test failure. Holding the ref (and closing at exit) keeps semantics equal
# to pre-3.14 implicit creation without GC noise.
_created_loops: dict = {}


def get_event_loop():
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        pass
    # NOTE: deliberately the REAL asyncio call here — recursing into this
    # shim would loop forever.
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _created_loops[loop] = True
        return loop


def _close_created_loops():
    for loop in list(_created_loops):
        try:
            if not loop.is_closed():
                loop.close()
        except Exception:  # noqa: BLE001 — exit-time cleanup, best effort
            pass
    _created_loops.clear()


atexit.register(_close_created_loops)


def iscoroutinefunction(func):
    return inspect.iscoroutinefunction(func)
