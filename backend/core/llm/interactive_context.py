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
