"""Chat-session context carrier for audit attribution.

Canvas/agent actions that happen INSIDE a chat turn (canvas edits, guidance
canvases, view changes) must be attributable to that chat session — training
episodes are segmented per session and pull CanvasAudit rows by session_id.
Tools, however, receive only what the LLM chose to pass, so the session id
cannot reliably arrive as a parameter.

Entry points (chat orchestrator, atom-agent chat, agent execution) set the
contextvars for the duration of the turn; audit writers read them as the
fallback when no explicit session/agent id is supplied.
"""

import uuid
from contextvars import ContextVar
from typing import Optional

_current_session_id: ContextVar[Optional[str]] = ContextVar(
    "atom_chat_session_id", default=None
)
_current_agent_id: ContextVar[Optional[str]] = ContextVar(
    "atom_chat_agent_id", default=None
)


def set_chat_context(session_id: Optional[str], agent_id: Optional[str] = None):
    """Bind the chat turn's session (and agent, when known). Returns reset tokens."""
    return (
        _current_session_id.set(session_id),
        _current_agent_id.set(agent_id),
    )


def reset_chat_context(tokens) -> None:
    try:
        sess_tok, agent_tok = tokens
        _current_session_id.reset(sess_tok)
        _current_agent_id.reset(agent_tok)
    except Exception:
        pass


def current_chat_session_id() -> Optional[str]:
    return _current_session_id.get()


def current_chat_agent_id() -> Optional[str]:
    return _current_agent_id.get()


def audit_session_id(explicit: Optional[str]) -> Optional[str]:
    """Session id for an audit row: explicit param wins, else the chat turn."""
    return explicit or _current_session_id.get()


def audit_agent_id(explicit: Optional[str]) -> Optional[str]:
    return explicit or _current_agent_id.get()


def ensure_session_id(explicit: Optional[str]) -> str:
    """A usable session id for rows that need one: explicit → chat turn → new."""
    return explicit or _current_session_id.get() or str(uuid.uuid4())
