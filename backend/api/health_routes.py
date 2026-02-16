"""
Health Check Routes for Kubernetes/ECS orchestration

Provides liveness and readiness probes for production orchestration:
- /health/live: Liveness probe (app process is alive)
- /health/ready: Readiness probe (dependencies are accessible)
- /health/metrics: Prometheus metrics endpoint

References:
- 15-RESEARCH.md: Health check patterns
- Kubernetes probes: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- ECS health checks: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/healthcheck_examples.html
"""

import asyncio
import logging
import psutil
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])

# Constants for health checks
MIN_DISK_GB = 1.0  # Minimum 1GB free space required
DB_TIMEOUT_SECONDS = 5.0  # Database query timeout


@router.get(
    "/health/live",
    summary="Liveness Probe",
    description=(
        "Kubernetes/ECS liveness probe - checks if the application process is alive. "
        "Orchestration platforms use this to detect if the container needs restart. "
        "This endpoint should return 200 if the process is running."
    ),
    tags=["Health"],
    responses={
        200: {
            "description": "Application is alive",
            "content": {
                "application/json": {
                    "example": {
                        "status": "alive",
                        "timestamp": "2026-02-16T10:00:00Z"
                    }
                }
            }
        }
    },
    openapi_extra={
        "x-auth-required": False,
        "x-kubernetes-probe": "liveness"
    }
)
async def liveness_probe() -> Dict[str, Any]:
    """
    Liveness probe - checks if the application process is alive.

    Kubernetes/ECS uses this to detect if the container needs restart.
    This endpoint should return 200 if the process is running.

    Returns:
        {"status": "alive", "timestamp": "..."}

    Raises:
        HTTPException 500: Only if critical failure (should never happen)
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get(
    "/health/ready",
    summary="Readiness Probe",
    description=(
        "Kubernetes/ECS readiness probe - checks if the application can handle traffic. "
        "Orchestration platforms use this to determine if the pod should receive requests. "
        "This endpoint checks critical dependencies: database connectivity and disk space."
    ),
    tags=["Health"],
    responses={
        200: {
            "description": "Application is ready to accept traffic",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ready",
                        "timestamp": "2026-02-16T10:00:00Z",
                        "checks": {
                            "database": {
                                "healthy": True,
                                "message": "Database accessible",
                                "latency_ms": 5.23
                            },
                            "disk": {
                                "healthy": True,
                                "message": "25.5GB free",
                                "free_gb": 25.5
                            }
                        }
                    }
                }
            }
        },
        503: {
            "description": "Application not ready - dependency check failed",
            "content": {
                "application/json": {
                    "example": {
                        "status": "not_ready",
                        "timestamp": "2026-02-16T10:00:00Z",
                        "checks": {
                            "database": {
                                "healthy": False,
                                "message": "Database timeout after 5.0s",
                                "latency_ms": 5000.0
                            }
                        }
                    }
                }
            }
        }
    },
    openapi_extra={
        "x-auth-required": False,
        "x-kubernetes-probe": "readiness",
        "x-dependency-checks": ["database", "disk"]
    }
)
async def readiness_probe() -> Dict[str, Any]:
    """
    Readiness probe - checks if the application can handle traffic.

    Kubernetes/ECS uses this to determine if the pod should receive traffic.
    This endpoint checks critical dependencies (database, disk space).

    Returns:
        {"status": "ready", "checks": {...}}

    Raises:
        HTTPException 503: If any dependency check fails
    """
    checks = {}
    all_healthy = True

    # Check database connectivity
    db_status = await _check_database()
    checks["database"] = db_status
    if not db_status["healthy"]:
        all_healthy = False

    # Check disk space
    disk_status = await _check_disk_space()
    checks["disk"] = disk_status
    if not disk_status["healthy"]:
        all_healthy = False

    if all_healthy:
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks,
        }
    else:
        # Return 503 if any dependency is unhealthy
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "timestamp": datetime.utcnow().isoformat(),
                "checks": checks,
            }
        )


async def _check_database() -> Dict[str, Any]:
    """
    Check database connectivity with timeout.

    Executes a simple "SELECT 1" query to verify database is accessible.

    Returns:
        {"healthy": bool, "message": str, "latency_ms": float}
    """
    start_time = datetime.now()
    try:
        # Run database check with timeout
        db = get_db()
        result = await asyncio.wait_for(
            _execute_db_query(db),
            timeout=DB_TIMEOUT_SECONDS
        )

        latency_ms = (datetime.now() - start_time).total_seconds() * 1000

        return {
            "healthy": True,
            "message": "Database accessible",
            "latency_ms": round(latency_ms, 2),
        }

    except asyncio.TimeoutError:
        logger.error(f"Database health check timed out after {DB_TIMEOUT_SECONDS}s")
        return {
            "healthy": False,
            "message": f"Database timeout after {DB_TIMEOUT_SECONDS}s",
            "latency_ms": DB_TIMEOUT_SECONDS * 1000,
        }
    except SQLAlchemyError as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "healthy": False,
            "message": f"Database error: {str(e)}",
            "latency_ms": 0,
        }
    except Exception as e:
        logger.error(f"Unexpected database health check error: {e}")
        return {
            "healthy": False,
            "message": f"Unexpected error: {str(e)}",
            "latency_ms": 0,
        }


async def _execute_db_query(db) -> bool:
    """Execute SELECT 1 query to verify database connectivity."""
    try:
        # Use next() to get the generator value from get_db()
        db_session = next(db)
        result = db_session.execute(text("SELECT 1"))
        return result.fetchone() is not None
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        raise


async def _check_disk_space() -> Dict[str, Any]:
    """
    Check available disk space.

    Verifies that the server has at least MIN_DISK_GB free space.

    Returns:
        {"healthy": bool, "message": str, "free_gb": float}
    """
    try:
        disk = psutil.disk_usage('/')
        free_gb = disk.free / (1024 ** 3)  # Convert bytes to GB

        if free_gb >= MIN_DISK_GB:
            return {
                "healthy": True,
                "message": f"{free_gb:.2f}GB free",
                "free_gb": round(free_gb, 2),
            }
        else:
            logger.warning(f"Low disk space: {free_gb:.2f}GB free (minimum: {MIN_DISK_GB}GB)")
            return {
                "healthy": False,
                "message": f"Low disk space: {free_gb:.2f}GB free (minimum: {MIN_DISK_GB}GB)",
                "free_gb": round(free_gb, 2),
            }
    except Exception as e:
        logger.error(f"Disk space check failed: {e}")
        return {
            "healthy": False,
            "message": f"Disk check error: {str(e)}",
            "free_gb": 0,
        }


@router.get(
    "/health/metrics",
    summary="Prometheus Metrics",
    description=(
        "Prometheus metrics endpoint for monitoring and alerting. "
        "Returns metrics in Prometheus text format for scraping by Prometheus server "
        "or compatible monitoring systems. Includes application performance, "
        "request counts, error rates, and custom business metrics."
    ),
    tags=["Health", "Monitoring"],
    responses={
        200: {
            "description": "Prometheus metrics in text format",
            "content": {
                "text/plain": {
                    "example": "# HELP http_requests_total Total HTTP requests\n# TYPE http_requests_total counter\nhttp_requests_total{method=\"post\",endpoint=\"/api/atom-agent/chat\"} 1234\n"
                }
            }
        }
    },
    openapi_extra={
        "x-auth-required": False,
        "x-prometheus-scrape": True,
        "x-content-type": "text/plain; version=0.0.4; charset=utf-8"
    }
)
async def prometheus_metrics():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.
    Use with Prometheus server or compatible monitoring systems.

    Returns:
        Response with content-type: text/plain; version=0.0.4; charset=utf-8
    """
    from fastapi.responses import Response
    metrics = generate_latest()
    return Response(content=metrics, media_type=CONTENT_TYPE_LATEST)
