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
        # core/cache.py exports `redis_cache` (not `cache_manager`). The old
        # import always raised ImportError → caught → returned "degraded"
        # unconditionally, so /health permanently reported redis as down.
        from core.cache import redis_cache

        if getattr(redis_cache, "enabled", False):
            return "operational"
        return "degraded"
    except Exception as exc:
        logger.debug("health: redis check failed: %s", exc)
        return "degraded"


def _check_vector_store() -> str:
    """Return 'operational' if the vector store is reachable, else 'degraded'."""
    try:
        from core.lancedb_handler import get_lancedb_handler

        handler = get_lancedb_handler()
        if not handler:
            return "degraded"
        # The handler lazy-loads via _ensure_db() — a healthy but never-used
        # store reported "degraded" forever because nothing had triggered the
        # connect yet. Force the (idempotent, guarded) lazy connect so the
        # check measures reachability, not "did something else run first".
        handler._ensure_db()
        # A lancedb DB connection has no nested `.db` member — the old
        # `handler.db.db is not None` clause could never be satisfied and
        # kept the service permanently "degraded" even when healthy.
        if handler.db is not None:
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
