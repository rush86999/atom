"""
Core health-check utilities.

Provides perform_health_checks() — a standardized dependency-health snapshot
used by the /health and /api/health endpoints. Keeps the health logic in one
place so it can be reused by readiness probes, diagnostics, and tests.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _check_database() -> str:
    """Return 'operational' if the DB connection works, else 'degraded'."""
    try:
        from core.database import SessionLocal

        db = SessionLocal()
        try:
            db.execute(__import__("sqlalchemy").text("SELECT 1"))
            return "operational"
        finally:
            db.close()
    except Exception as exc:
        logger.debug("health: database check failed: %s", exc)
        return "degraded"


def _check_redis() -> str:
    """Return 'operational' if Redis is reachable, else 'degraded'."""
    try:
        from core.cache import cache_manager  # type: ignore

        if getattr(cache_manager, "enabled", False):
            return "operational"
        return "degraded"
    except Exception as exc:
        logger.debug("health: redis check failed: %s", exc)
        return "degraded"


def _check_vector_store() -> str:
    """Return 'operational' if the vector store is initialized, else 'degraded'."""
    try:
        from core import lancedb_handler  # type: ignore

        if getattr(lancedb_handler, "_initialized", False) or getattr(
            lancedb_handler, "table", None
        ):
            return "operational"
        return "degraded"
    except Exception as exc:
        logger.debug("health: vector store check failed: %s", exc)
        return "degraded"


def perform_health_checks() -> Dict[str, Any]:
    """Run all dependency health checks and return a status snapshot.

    Returns:
        {"status": "healthy"|"degraded", "services": {service: state}}
    """
    services = {
        "database": _check_database(),
        "redis": _check_redis(),
        "vector_store": _check_vector_store(),
    }
    overall = "healthy" if all(v == "operational" for v in services.values()) else "degraded"
    return {"status": overall, "services": services}
