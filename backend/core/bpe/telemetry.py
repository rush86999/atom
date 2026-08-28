"""Telemetry for BPE workspace actions.

Every harness meta-action (track/commit/recall/note) records one span via
``core.observability.tracing.record_span`` under the ``bpe.`` name prefix so
the consult-value metrics (plan Phase 2: harness-call rate per episode,
recall precision, spam rate) can be computed from the existing observability
seam without new infrastructure.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SPAN_NAME_PREFIX = "bpe"


def record_bpe_span(
    action: str,
    workspace_id: str = "default",
    agent_id: str = "agent",
    scope_key: str = "",
    success: bool = True,
    latency_ms: float = 0.0,
    payload_chars: int = 0,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Record one ``bpe.<action>`` span. Never raises, never blocks."""
    now = time.time()
    attributes: Dict[str, Any] = {
        "bpe_action": action,
        "workspace_id": workspace_id,
        "agent_id": agent_id,
        "scope_key": scope_key,
        "success": success,
        "payload_chars": payload_chars,
    }
    if extra:
        attributes.update(extra)
    try:
        from core.observability.tracing import record_span

        record_span(
            trace_id=f"bpe-{workspace_id}-{agent_id}",
            name=f"{SPAN_NAME_PREFIX}.{action}",
            kind="harness",
            attributes=attributes,
            started_at=now,
            ended_at=now,
            status="ok" if success else "error",
        )
    except Exception as e:  # observability must never break the agent loop
        logger.debug("bpe span recording failed: %s", e)
