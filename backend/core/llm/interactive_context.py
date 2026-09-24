"""Interactive-call context for provider rate budgets.

RCA 2026-09-22 ("rebuild the draft" turn): during an interactive chat turn,
the per-model rate budgets of the shared fleet were drained by CONCURRENT
BACKGROUND work (ingestion-side draft creation, knowledge extraction,
learning-router updates) — by the time the turn's reply generation ranked
its model, headroom was 0.00 and the cascade had nothing left. The turn
ended in ``turn_budget_exceeded`` with the edit never applied.

The reserve: a FRACTION of every rate window is reserved for calls made
INSIDE an interactive chat request. Background calls (anything not inside
that call context — pollers, ingestion triggers, learning loops) may only
be admitted ABOVE the reserve, so the last slice of every window stays
available for the user-facing turn.

Implementation: an asyncio ContextVar set for the duration of a chat
request (the orchestrator's turn entry) — every provider call made on that
call stack, including the planner, editor and reply generation, is
interactive. Background tasks never set it, so no background call site
needs modification.
"""
import contextvars
import os

_interactive_chat_ctx = contextvars.ContextVar(
    "atom_interactive_chat", default=False)


def mark_interactive_chat() -> contextvars.Token:
    """Mark the current task/context as an interactive chat request.

    Returns the token to pass to :func:`reset_interactive_chat`."""
    return _interactive_chat_ctx.set(True)


def reset_interactive_chat(token: contextvars.Token) -> None:
    """End the interactive scope (fault-tolerant: a bad token is a no-op —
    the worst case is the scope leaking to the caller's task, which only
    makes more calls 'interactive', the fail-open direction)."""
    try:
        _interactive_chat_ctx.reset(token)
    except (ValueError, LookupError):
        pass


def is_interactive_chat() -> bool:
    """True inside an interactive chat request's call context."""
    return bool(_interactive_chat_ctx.get())


def interactive_rate_reserve() -> float:
    """Fraction of each rate window reserved for interactive calls.

    Background calls are admitted only when headroom EXCEEDS this reserve;
    interactive calls use the full window. ``0`` disables the reserve.
    ``ATOM_INTERACTIVE_RATE_RESERVE`` overrides (0.0–1.0)."""
    raw = os.getenv("ATOM_INTERACTIVE_RATE_RESERVE")
    if raw is not None and str(raw).strip() != "":
        try:
            return max(0.0, min(1.0, float(raw)))
        except (TypeError, ValueError):
            pass
    return 0.2


def mark_background_execution() -> contextvars.Token:
    """Explicitly mark the current task/context as BACKGROUND execution.

    asyncio tasks COPY the creating context, so a task forked from inside
    an interactive chat request — the canvas-edit continuation is forked
    mid-turn by ``async_turn_continuation.start_continuation`` — inherits
    ``atom_interactive_chat=True`` for its whole life. Two defects follow:
    the INTERACTIVE-only structured-latency cap (25s) vetoes healthy
    26–30s rungs inside a background tier whose edit bound is 150s (live
    2026-09-23, continuation ab86e7bf attempt 1: zero-dispatch exhaustion
    in 1.3s), and the fork consumes the interactive rate reserve that
    exists to protect user-facing turns. Background tasks forked from a
    request call this at their entry; rate, auth and cooldown restrictions
    are unaffected — only the interactive classification is corrected."""
    return _interactive_chat_ctx.set(False)


_structured_wait_ctx = contextvars.ContextVar(
    "atom_interactive_structured_wait", default=0.0)


def declare_interactive_structured_wait(seconds: float) -> contextvars.Token:
    """Raise the interactive structured-latency cap for calls on THIS
    context only (the planner of a pending-file-task resume turn — a turn
    whose entire purpose is one lookup, and whose caller actually waits
    longer than the default 25s).

    This is a CALLER-DECLARED WAIT, not a relaxation of restrictions:
    rate budgets, the interactive reserve, cooldowns and auth gates are
    untouched — only the latency expectation of the interactive structured
    ladder is raised to what the caller will genuinely wait. Callers MUST
    reset the token when their wait scope ends (task-scoped usage keeps
    the declaration from leaking to the reply generation)."""
    try:
        value = max(0.0, float(seconds))
    except (TypeError, ValueError):
        value = 0.0
    return _structured_wait_ctx.set(value)


def reset_interactive_structured_wait(token: contextvars.Token) -> None:
    """End the declared-wait scope (fault-tolerant, same fail-open
    contract as :func:`reset_interactive_chat`)."""
    try:
        _structured_wait_ctx.reset(token)
    except (ValueError, LookupError):
        pass


def interactive_structured_wait() -> float:
    """Seconds the current context's caller will wait for a structured
    call (0 = no declaration; the default cap applies)."""
    return float(_structured_wait_ctx.get() or 0.0)
