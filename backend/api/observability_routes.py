"""Observability/evals routes: recent spans summary + Langfuse export status.

Read-only surface over the in-memory span ring buffer in
``core.observability.tracing``. This is the seam an OpenTelemetry exporter
or external evals tooling can take over from.
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends

from core.models import User
from core.observability.tracing import (
    DEFAULT_LANGFUSE_HOST,
    aggregate_spans,
    get_recent_spans,
    langfuse_configured,
)
from core.rbac_service import Permission
from core.security_dependencies import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/observability", tags=["Observability"])


@router.get("/spans")
async def recent_spans(
    limit: int = 100,
    name_prefix: str = None,
    _admin: User = Depends(require_permission(Permission.SYSTEM_ADMIN)),
) -> Dict[str, Any]:
    """Recent spans (newest first) plus a tiny aggregate (counts / avg latency by name)."""
    spans = get_recent_spans(limit=limit, name_prefix=name_prefix)
    return {
        "count": len(spans),
        "spans": spans,
        "aggregate": aggregate_spans(spans),
    }


@router.get("/status")
async def observability_status(
    _admin: User = Depends(require_permission(Permission.SYSTEM_ADMIN)),
) -> Dict[str, Any]:
    """Whether the Langfuse export is configured. Never returns secrets."""
    return {
        "langfuse_export": {
            "configured": langfuse_configured(),
            "default_host": DEFAULT_LANGFUSE_HOST,
        },
        "buffer_max_spans": 5000,
    }
