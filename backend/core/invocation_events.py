"""Turn-scoped invocation instrumentation (work order Step 5 / item 1).

Records retrieval and render boundary crossings into the durable
``invocation_events`` table so acceptance counts invocations per
execution/attempt ID instead of inferring them from persisted artifacts,
timestamps, or logs. Writes are best-effort and never break delivery.
No private payloads are stored (counts, IDs, outcomes, revisions only).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SCAN_START = "scan_start"
SCAN_END = "scan_end"
RENDER = "render"


def record(kind: str, *, execution_id: Optional[str] = None,
           request_id: Optional[str] = None,
           attempt_id: Optional[str] = None,
           session_id: Optional[str] = None,
           outcome: Optional[str] = None,
           evidence_revision: Optional[str] = None,
           duration_ms: Optional[float] = None,
           detail: Optional[Dict[str, Any]] = None) -> None:
    """Persist one invocation event. Never raises."""
    try:
        import json as _json

        from core.database import get_db_session
        from core.models import InvocationEvent

        with get_db_session() as db:
            db.add(InvocationEvent(
                kind=str(kind),
                execution_id=str(execution_id) if execution_id else None,
                request_id=str(request_id) if request_id else None,
                attempt_id=str(attempt_id) if attempt_id else None,
                session_id=str(session_id) if session_id else None,
                outcome=str(outcome) if outcome else None,
                evidence_revision=str(evidence_revision)
                if evidence_revision else None,
                duration_ms=float(duration_ms)
                if duration_ms is not None else None,
                detail=_json.dumps(detail or {})[:2000],
            ))
            db.commit()
    except Exception as exc:  # noqa: BLE001 — instrumentation is best-effort
        logger.debug("invocation event skipped: %r", exc)


class Timer:
    """Elapsed-ms helper for boundary durations."""

    def __init__(self) -> None:
        self._t0 = time.monotonic()

    def ms(self) -> float:
        return (time.monotonic() - self._t0) * 1000.0
