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
import contextvars
import inspect
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "get_event_loop",
    "iscoroutinefunction",
    "notification_loop_var",
    "run_sync_in_worker",
    "run_with_thread_gate",
    "schedule_notification",
]

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


# ── Shared automation-worker boundary ───────────────────────────────────────
# These helpers are deliberately small stdlib mechanisms, not an executor or
# task framework. Owners keep their own thread gates, pass callables and
# notification contents; only context propagation, gate arbitration and
# origin-loop scheduling are shared.


def notification_loop_var(name: str) -> contextvars.ContextVar:
    """Create the ContextVar naming the application loop that owns a worker."""
    return contextvars.ContextVar(name, default=None)


def _invoke_worker(func):
    try:
        return func()
    except StopIteration as exc:
        # A StopIteration escaping an executor callable can be injected into
        # an asyncio Future in a way that never settles the awaiter. Turn it
        # into an ordinary RuntimeError at the worker boundary.
        raise RuntimeError(
            "synchronous automation worker raised StopIteration"
        ) from exc


async def run_sync_in_worker(func, notification_loop):
    """Run a blocking owner pass in a worker thread with a copied context.

    ``asyncio.to_thread`` copies the caller's context, including ContextVars.
    ``notification_loop`` is bound to the caller's running application loop in
    that copy, so notifications produced by the worker can be scheduled back
    onto the real loop instead of a worker-private, never-running loop.
    """
    loop = get_event_loop()
    token = notification_loop.set(loop)
    try:
        worker = getattr(asyncio, "to_thread", None)
        if worker is not None:
            return await worker(_invoke_worker, func)
        # The compatibility path must carry the same fresh context snapshot
        # as to_thread, including the originating loop and caller scope.
        context = contextvars.copy_context()
        return await loop.run_in_executor(None, context.run, _invoke_worker, func)
    finally:
        notification_loop.reset(token)


def run_with_thread_gate(gate, func, *, label="automation", log=None,
                         in_progress=None):
    """Run ``func`` while owning a process-local thread gate.

    The gate is released only when the worker actually leaves ``func``.
    Cancelling the task awaiting the worker does not release it. A contending
    call gets an explicit in-progress result and never invokes ``func``.
    """
    if not gate.acquire(blocking=False):
        (log or logger).info(
            "%s skipped: previous pass still running", label)
        return dict(in_progress) if in_progress is not None else {
            "skipped": "pass_in_progress"}
    try:
        return func()
    finally:
        gate.release()


def _notification_done(future, log, label):
    try:
        future.result()
    except Exception as exc:  # notification failure is non-fatal
        log.warning("%s notification failed: %s", label, type(exc).__name__)


def schedule_notification(notification_loop, coroutine_factory, *,
                          asyncio_module=asyncio, logger_=None,
                          label="automation", done_callback=None):
    """Schedule one notification on the bound application loop.

    ``coroutine_factory`` is called only when an origin loop is bound, so the
    unbound path creates no coroutine and the caller's existing synchronous
    fallback remains in charge. Returns ``True`` when a bound origin handled
    the request, ``False`` when there is no origin to schedule onto.

    On original-loop ``create_task`` or cross-thread
    ``run_coroutine_threadsafe`` refusal/shutdown, exactly one unscheduled
    coroutine is closed and only the exception class is logged. There is no
    worker-private-loop fallback and no second dispatch.
    """
    app_loop = notification_loop.get()
    if app_loop is None:
        return False
    log = logger_ or logger

    running_loop_fn = getattr(
        asyncio_module, "get_running_loop", asyncio.get_running_loop)
    try:
        running_loop = running_loop_fn()
    except RuntimeError:
        running_loop = None

    if running_loop is app_loop:
        coroutine = coroutine_factory()
        try:
            app_loop.create_task(coroutine)
        except Exception as exc:  # loop shutting down / refusing work
            coroutine.close()
            log.warning(
                "%s notification not scheduled: %s",
                label, type(exc).__name__)
        return True

    if app_loop.is_running() and not app_loop.is_closed():
        coroutine = coroutine_factory()
        schedule = getattr(
            asyncio_module, "run_coroutine_threadsafe",
            asyncio.run_coroutine_threadsafe)
        try:
            future = schedule(coroutine, app_loop)
        except Exception as exc:  # loop shutting down / refusing work
            coroutine.close()
            log.warning(
                "%s notification not scheduled: %s",
                label, type(exc).__name__)
            return True
        if done_callback is not None:
            future.add_done_callback(done_callback)
        else:
            future.add_done_callback(
                lambda fut: _notification_done(fut, log, label))
        return True

    log.warning(
        "%s notification not scheduled: application event loop is no longer "
        "running", label)
    return True
