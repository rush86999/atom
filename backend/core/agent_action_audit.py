"""
Agent Action Audit — per-decision audit trail for AI agent runs.

Every auditable event in an agent run (tool invocation, LLM call, HITL
decision, execution summary) funnels through ``log_agent_action`` /
``log_llm_call`` here, which writes a row to ``saas_audit_logs`` with
``agent_execution_id`` embedded in the metadata JSON so an accountant can
replay the full decision chain of any execution.

Design constraints:
- Never raises into the agent loop (a broken audit must not kill a run),
  but failures are logged at ERROR — loud, never silently swallowed.
- Run identity (agent_id / execution_id / user_id / workspace_id) travels
  via a ContextVar set once by ``GenericAgent.execute``; LLMService reads
  it so calls made inside an agent run are ledgered with the run they
  belong to, while platform-wide background LLM traffic stays out.
- Payloads are truncated before persistence (no unbounded prompt bodies).
"""

import hashlib
import json
import logging
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Max characters stored for any single audit payload field.
MAX_PAYLOAD_CHARS = 2000
# Max characters for prompt/response digests in LLM call audits.
MAX_LLM_DIGEST_CHARS = 500

AUDIT_EVENT_AGENT_ACTION = "agent_action"
AUDIT_EVENT_LLM_CALL = "llm_call"
AUDIT_EVENT_EXECUTION = "agent_execution"

_audit_context: ContextVar[Optional[Dict[str, Optional[str]]]] = ContextVar(
    "agent_audit_context", default=None
)


@contextmanager
def set_audit_context(
    agent_id: Optional[str],
    execution_id: Optional[str],
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
):
    """Bind run identity for the duration of an agent execution.

    All ``log_*`` calls on this context thread their audit rows to the
    given execution, including LLM calls made by LLMService deep below.
    """
    token = _audit_context.set({
        "agent_id": agent_id,
        "execution_id": execution_id,
        "user_id": user_id,
        "workspace_id": workspace_id,
    })
    try:
        yield
    finally:
        _audit_context.reset(token)


def get_audit_context() -> Optional[Dict[str, Optional[str]]]:
    return _audit_context.get()


def bind_audit_context(
    agent_id: Optional[str],
    execution_id: Optional[str],
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
):
    """Imperative variant of :func:`set_audit_context` for long methods with
    a single exit point (bind at the top, unbind before returning)."""
    return _audit_context.set({
        "agent_id": agent_id,
        "execution_id": execution_id,
        "user_id": user_id,
        "workspace_id": workspace_id,
    })


def unbind_audit_context(token) -> None:
    _audit_context.reset(token)


def _truncate(value: Any, limit: int = MAX_PAYLOAD_CHARS) -> Any:
    """Best-effort JSON-safe truncation of an audit payload."""
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    try:
        text = value if isinstance(value, str) else json.dumps(value, default=str)
    except (TypeError, ValueError):
        text = str(value)
    if len(text) > limit:
        return text[:limit] + f"... [truncated, {len(text)} chars total]"
    return text


def _digest(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()[:16]


def _write_audit_log(
    event_type: str,
    action: str,
    description: str,
    metadata: Dict[str, Any],
    success: bool = True,
    error_message: Optional[str] = None,
    agent_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Optional[str]:
    """Write one AuditLog row. Never raises; returns row id or None."""
    ctx = get_audit_context() or {}
    agent_id = agent_id or ctx.get("agent_id")
    execution_id = execution_id or ctx.get("execution_id")
    user_id = user_id or ctx.get("user_id")
    workspace_id = workspace_id or ctx.get("workspace_id") or "default"

    meta = {k: _truncate(v) for k, v in (metadata or {}).items()}
    if agent_id:
        meta["agent_id"] = agent_id
    if execution_id:
        meta["agent_execution_id"] = execution_id

    try:
        from core.database import get_db_session
        from core.models import AuditLog, SecurityLevel, ThreatLevel

        row = AuditLog(
            id=str(uuid.uuid4()),
            event_type=event_type,
            security_level=SecurityLevel.LOW.value,
            threat_level=ThreatLevel.NONE.value,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            workspace_id=workspace_id,
            resource=agent_id,
            action=action,
            description=description[:2000],
            metadata_json=json.dumps(meta, default=str),
            success=success,
            error_message=error_message,
        )
        with get_db_session() as db:
            db.add(row)
            db.commit()
        return str(row.id)
    except Exception as e:
        # Loud by design: a silent audit gap is exactly what this module
        # exists to prevent. Never propagates into the agent loop.
        logger.error(
            "AUDIT WRITE FAILED (event=%s action=%s execution=%s): %s",
            event_type, action, execution_id, e, exc_info=True,
        )
        return None


# String-result failure classification. Tool dispatchers return prose on
# refusal paths ("Governance blocked: …", "Action X was REJECTED or timed
# out.") — those are failures for audit purposes even without the literal
# word "error".
_ERROR_RESULT_MARKERS = (
    "error",
    "governance blocked",
    "was rejected",
    "rejected or timed out",
    "requires approval",
    "hitl_paused",
)


def is_error_result(result: Any) -> bool:
    """Classify a tool-dispatch string result as a failure outcome."""
    if not isinstance(result, str):
        return False
    low = result.lower()
    return any(marker in low for marker in _ERROR_RESULT_MARKERS)

def log_agent_action(
    action: str,
    metadata: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[str]:
    """Audit one agent action (tool call, HITL decision, execution event)."""
    return _write_audit_log(
        event_type=AUDIT_EVENT_AGENT_ACTION,
        action=action,
        description=description or f"Agent action: {action}",
        metadata=metadata or {},
        success=success,
        error_message=error_message,
    )


def log_llm_call(
    model: str,
    prompt: str,
    response: Any,
    latency_ms: Optional[float] = None,
    provider: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None,
) -> Optional[str]:
    """Ledger one LLM call made inside an agent run.

    No-op (returns None, no row) when no agent-run context is bound, so
    platform-level background LLM traffic is not flooded into the audit
    log — only decisions attributable to an agent execution.
    """
    ctx = get_audit_context()
    if not ctx:
        return None

    prompt_text = prompt if isinstance(prompt, str) else json.dumps(prompt, default=str)
    response_text = response if isinstance(response, str) else _truncate(response, MAX_LLM_DIGEST_CHARS)
    metadata: Dict[str, Any] = {
        "model": model,
        "prompt_digest": _digest(prompt_text),
        "prompt_excerpt": prompt_text[:MAX_LLM_DIGEST_CHARS],
        "response_excerpt": (
        (response_text or "")[:MAX_LLM_DIGEST_CHARS] if isinstance(response_text, str) else response_text
        ),
        "prompt_chars": len(prompt_text),
    }
    if provider:
        metadata["provider"] = provider
    if latency_ms is not None:
        metadata["latency_ms"] = round(latency_ms, 1)

    return _write_audit_log(
        event_type=AUDIT_EVENT_LLM_CALL,
        action=f"llm_call:{model}",
        description=f"LLM call to {provider or 'auto'} model {model}",
        metadata=metadata,
        success=success,
        error_message=error_message,
    )


async def audited_llm_call(model: str, prompt: Any, call, provider: Optional[str] = None):
    """Await ``call()`` and ledger the LLM decision.

    Transparent passthrough outside an agent run (no context bound → no
    row, no overhead beyond a monotonic clock read). Inside a run, both
    successes and failures produce an ``llm_call`` audit row.
    """
    import time as _time

    ctx = get_audit_context()
    start = _time.monotonic()
    try:
        response = await call()
    except Exception as e:
        if ctx:
            log_llm_call(
                model=model, prompt=prompt, response=None, provider=provider,
                success=False, error_message=str(e),
                latency_ms=(_time.monotonic() - start) * 1000,
            )
        raise
    if ctx:
        log_llm_call(
            model=model, prompt=prompt, response=response, provider=provider,
            latency_ms=(_time.monotonic() - start) * 1000,
        )
    return response


def execution_needle(execution_id: str) -> str:
    """Serialization-proof LIKE needle matching how the writer serializes.

    Derived from ``json.dumps`` itself so any change in dump options on
    either side keeps the reader/writer pair consistent (a hand-built
    ``'"key": "value"'`` string silently breaks on separator changes).
    """
    return json.dumps({"agent_execution_id": execution_id})[1:-1]


def count_execution_audits(execution_id: str, db=None) -> int:
    """Count audit rows tied to an execution (agent actions + LLM calls)."""
    from core.models import AuditLog

    needle = execution_needle(execution_id)
    if db is not None:
        return int(
            db.query(AuditLog)
            .filter(AuditLog.event_type.in_([AUDIT_EVENT_AGENT_ACTION, AUDIT_EVENT_LLM_CALL]))
            .filter(AuditLog.metadata_json.like(f"%{needle}%"))
            .count()
        )
    from core.database import get_db_session

    with get_db_session() as session:
        return int(
            session.query(AuditLog)
            .filter(AuditLog.event_type.in_([AUDIT_EVENT_AGENT_ACTION, AUDIT_EVENT_LLM_CALL]))
            .filter(AuditLog.metadata_json.like(f"%{needle}%"))
            .count()
        )


def check_execution_audit_completeness(
    execution_id: str,
    expected_tool_calls: int,
    expected_llm_calls: int = 0,
) -> Dict[str, Any]:
    """Enforcement gate: compare expected vs written audit rows for a run.

    Expected counts come from the run's own ReAct transcript (steps with
    an action); actual counts come from persisted audit rows. A shortfall
    means part of the run happened outside the audit trail.
    """
    try:
        actual = count_execution_audits(execution_id)
    except Exception as e:
        logger.error("AUDIT COMPLETENESS CHECK FAILED for %s: %s", execution_id, e)
        return {
            "complete": False,
            "execution_id": execution_id,
            "expected_events": expected_tool_calls + expected_llm_calls,
            "actual_events": 0,
            "error": str(e),
        }

    expected = expected_tool_calls + expected_llm_calls
    return {
        "complete": actual >= expected and expected >= 0,
        "execution_id": execution_id,
        "expected_events": expected,
        "actual_events": actual,
        "coverage_percentage": round(min(actual / expected, 1.0) * 100, 1) if expected else 100.0,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
