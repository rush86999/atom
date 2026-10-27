"""System status aggregate for the /system-status dashboard.

`components/SystemStatusDashboard.tsx` has always called `/api/status`, but
no backend route existed — the page was a permanent "Failed to fetch system
status". This endpoint returns the shape the component reads, from real
checks: database, cache, vector store, process/host resources and uptime.
"""
from __future__ import annotations

import os
import platform
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import Depends
from sqlalchemy import text

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db_session

router = BaseAPIRouter(tags=["System Status"])

_STARTED_AT = time.time()


def _db_status() -> str:
    try:
        with get_db_session() as db:
            db.execute(text("SELECT 1"))
        return "operational"
    except Exception:
        return "degraded"


def _redis_status() -> str:
    try:
        from core.cache import cache

        client = getattr(cache, "redis_client", None)
        if client is None:
            return "not_configured"
        return "operational" if client.ping() else "degraded"
    except Exception:
        return "degraded"


def _vector_status() -> str:
    try:
        from core.lancedb_handler import LanceDBHandler

        result = LanceDBHandler(tenant_id="default").test_connection()
        return "operational" if result.get("connected") else "degraded"
    except Exception:
        return "degraded"


def _resources() -> Dict[str, Any]:
    try:
        import psutil
    except Exception:
        return {}

    process = psutil.Process(os.getpid())
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu": {"percent": psutil.cpu_percent(interval=0.1)},
        "memory": {
            "system_used_percent": vm.percent,
            "rss_mb": round(process.memory_info().rss / (1024 * 1024), 1),
        },
        "disk": {
            "percent": disk.percent,
            "free_gb": round(disk.free / (1024 ** 3), 1),
        },
    }


@router.get("/api/status")
async def system_status(_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    services = {
        "database": {"name": "Database", "status": _db_status()},
        "cache": {"name": "Cache", "status": _redis_status()},
        "vector_store": {"name": "Vector Store", "status": _vector_status()},
    }
    statuses = [s["status"] for s in services.values()]
    if "degraded" in statuses:
        overall = "degraded"
    elif all(s == "operational" for s in statuses):
        overall = "healthy"
    else:
        overall = "unknown"

    try:
        import psutil

        system_seconds = max(0, int(time.time() - psutil.boot_time()))
    except Exception:
        system_seconds = 0

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall,
        "system": {
            "platform": {"system": platform.system(), "node": platform.node()},
            "python": {"version": sys.version},
            "process": {"pid": os.getpid()},
        },
        "resources": _resources(),
        "services": services,
        "features": {},
        "uptime": {
            "system_seconds": system_seconds,
            "process_seconds": max(0, int(time.time() - _STARTED_AT)),
        },
        "version": {"backend": "8.0.0"},
    }
