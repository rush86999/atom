"""Lightweight span/trace recorder for the Atom observability seam.

This module is the single integration seam for evals/observability tooling:
call sites record spans via :func:`record_span`, spans are kept in an
in-memory bounded ring buffer (max 5000) for the summary endpoint, and —
when Langfuse credentials are configured (``LANGFUSE_PUBLIC_KEY`` +
``LANGFUSE_SECRET_KEY``, optional ``LANGFUSE_HOST`` defaulting to
https://cloud.langfuse.com) — each span is forwarded fire-and-forget to
Langfuse's ingestion API as a trace-event batch. Export failures are logged
at debug level and never raised; export never blocks the caller beyond a
short HTTP timeout.

SEAM NOTE: this is deliberately dependency-light (stdlib + httpx only). An
OpenTelemetry exporter can replace this module's export step by swapping
``_export_to_langfuse`` (or by consuming the same ``record_span`` calls from
a real OTel tracer provider) without touching the instrumented call sites.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
import uuid
from collections import deque
from typing import Any, Deque, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

MAX_SPANS = 5000
DEFAULT_LANGFUSE_HOST = "https://cloud.langfuse.com"
_EXPORT_TIMEOUT_SECONDS = 2.0

# Bounded in-memory ring buffer (seam for a real OTel exporter/collector).
_spans: Deque[Dict[str, Any]] = deque(maxlen=MAX_SPANS)


def langfuse_configured() -> bool:
    """True when both Langfuse keys are present in the environment."""
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY")) and bool(os.getenv("LANGFUSE_SECRET_KEY"))


def _basic_auth(public_key: str, secret_key: str) -> str:
    raw = f"{public_key}:{secret_key}".encode()
    return "Basic " + base64.b64encode(raw).decode()


async def _export_to_langfuse(events: List[Dict[str, Any]]) -> None:
    """POST one batch of trace events to Langfuse ingestion (fire-and-forget).

    Never raises: any failure (network, auth, timeout) is logged at debug.
    """
    import httpx

    host = (os.getenv("LANGFUSE_HOST") or DEFAULT_LANGFUSE_HOST).rstrip("/")
    url = f"{host}/api/public/ingestion"
    headers = {
        "Authorization": _basic_auth(
            os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"]
        ),
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=_EXPORT_TIMEOUT_SECONDS) as client:
            await client.post(url, json={"batch": events}, headers=headers)
    except Exception as exc:  # pragma: no cover - network paths
        logger.debug(f"Langfuse export failed (ignored): {exc}")


def _langfuse_events(trace_id: str, name: str, kind: str, attributes: Dict[str, Any],
                     started_at: float, ended_at: float, status: str) -> List[Dict[str, Any]]:
    """Map one Atom span onto a minimal Langfuse trace + generation batch."""
    import datetime as _dt

    def _iso(ts: float) -> str:
        return _dt.datetime.fromtimestamp(
            ts, tz=_dt.timezone.utc
        ).isoformat().replace("+00:00", "Z")

    trace_event = {
        "id": f"trace-{trace_id}",
        "type": "trace-create",
        "timestamp": _iso(started_at),
        "body": {"id": trace_id, "name": name, "timestamp": _iso(started_at)},
    }
    generation_event = {
        "id": str(uuid.uuid4()),
        "type": "span-create",
        "timestamp": _iso(started_at),
        "body": {
            "traceId": trace_id,
            "name": name,
            "startTime": _iso(started_at),
            "endTime": _iso(ended_at),
            "metadata": {"kind": kind, "status": status, **(attributes or {})},
        },
    }
    return [trace_event, generation_event]


def record_span(
    trace_id: str,
    name: str,
    kind: str,
    attributes: Dict[str, Any],
    started_at: float,
    ended_at: float,
    status: str,
) -> Dict[str, Any]:
    """Record one span locally and (if configured) export it to Langfuse.

    Synchronous and non-blocking on the network: the Langfuse export is
    scheduled as a background task when a running event loop exists,
    otherwise it is skipped (local recording still succeeds).
    """
    span = {
        "trace_id": trace_id,
        "name": name,
        "kind": kind,
        "attributes": dict(attributes or {}),
        "started_at": started_at,
        "ended_at": ended_at,
        "latency_ms": max(0.0, (ended_at - started_at) * 1000.0),
        "status": status,
    }
    _spans.append(span)
    if langfuse_configured():
        events = _langfuse_events(
            trace_id, name, kind, span["attributes"], started_at, ended_at, status
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_export_to_langfuse(events))
        except RuntimeError:
            # No running loop (sync caller): drop the export, keep the span.
            logger.debug("Langfuse export skipped: no running event loop")
    return span


def get_recent_spans(limit: int = 100, name_prefix: Optional[str] = None) -> List[Dict[str, Any]]:
    """Most-recent-first spans, optionally filtered by name prefix."""
    spans = list(_spans)
    if name_prefix:
        spans = [s for s in spans if str(s.get("name", "")).startswith(name_prefix)]
    spans.reverse()  # newest first
    return spans[: max(0, int(limit))]


def aggregate_spans(spans: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Tiny aggregate: count and average latency_ms grouped by span name."""
    groups: Dict[str, Dict[str, Any]] = {}
    for span in spans:
        entry = groups.setdefault(
            span.get("name", "unknown"), {"count": 0, "latency_ms_sum": 0.0}
        )
        entry["count"] += 1
        entry["latency_ms_sum"] += float(span.get("latency_ms", 0.0))
    return {
        name: {
            "count": entry["count"],
            "avg_latency_ms": round(entry["latency_ms_sum"] / entry["count"], 3),
        }
        for name, entry in groups.items()
    }


def clear_spans() -> None:
    """Test helper: reset the in-memory buffer."""
    _spans.clear()
