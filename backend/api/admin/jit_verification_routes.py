"""
JIT Verification Admin Routes

Administrative API for managing JIT verification cache and background worker.
Provides endpoints for monitoring, controlling, and inspecting the verification system.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import UserRole
from core.security.rbac import require_role
from core.jit_verification_cache import get_jit_verification_cache
from core.jit_verification_worker import (
    get_jit_verification_worker,
    start_jit_verification_worker,
    stop_jit_verification_worker
)

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/admin/governance/jit", tags=["JIT Verification"])


class CacheStatsResponse(BaseModel):
    """Response model for cache statistics"""
    l1_verification_cache_size: int
    l1_query_cache_size: int
    l1_verification_hits: int
    l1_verification_misses: int
    l1_verification_hit_rate: float
    l1_query_hits: int
    l1_query_misses: int
    l1_query_hit_rate: float
    l1_evictions: int
    l2_enabled: bool


class WorkerMetricsResponse(BaseModel):
    """Response model for worker metrics"""
    running: bool
    total_citations: int
    verified_count: int
    failed_count: int
    stale_facts: int
    outdated_facts: int
    last_run_time: Optional[str]
    last_run_duration: float
    average_verification_time: float
    top_citations: List[Dict[str, Any]]


class VerificationRequest(BaseModel):
    """Request model for citation verification"""
    citations: List[str]
    force_refresh: bool = False


class VerificationResponse(BaseModel):
    """Response model for citation verification"""
    results: List[Dict[str, Any]]
    total_count: int
    verified_count: int
    failed_count: int
    duration_seconds: float


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Get JIT verification cache statistics.

    Returns cache hit rates, sizes, and other performance metrics.
    """
    cache = get_jit_verification_cache()
    stats = cache.get_stats()

    return CacheStatsResponse(**stats["l1"], l2_enabled=stats["l2_enabled"])


@router.post("/cache/clear")
async def clear_cache(
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Clear all JIT verification caches (L1 and L2).

    Use this to force fresh verification of all citations.
    """
    cache = get_jit_verification_cache()
    cache.clear_all()

    logger.info("JIT verification cache cleared by admin")

    return {
        "status": "cleared",
        "message": "All JIT verification caches cleared",
        "cleared_at": datetime.now().isoformat()
    }


@router.post("/verify-citations", response_model=VerificationResponse)
async def verify_citations(
    request: VerificationRequest,
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Verify one or more citations (with cache check).

    If citations are already cached, returns cached results.
    Set force_refresh=True to bypass cache and re-verify.
    """
    import time
    try:
        cache = get_jit_verification_cache()

        start_time = time.time()

        # Verify citations (uses cache automatically)
        results = await cache.verify_citations_batch(
            request.citations,
            force_refresh=request.force_refresh
        )

        duration = time.time() - start_time

        # Count results
        verified_count = sum(1 for r in results if r.exists)
        failed_count = len(results) - verified_count

        return VerificationResponse(
            results=[r.to_dict() for r in results],
            total_count=len(results),
            verified_count=verified_count,
            failed_count=failed_count,
            duration_seconds=duration
        )
    except Exception as e:
        logger.error(f"Failed to verify citations: {e}")
        raise HTTPException(status_code=500, detail=f"Citation verification failed: {str(e)}")


@router.get("/worker/metrics", response_model=WorkerMetricsResponse)
async def get_worker_metrics(
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Get JIT verification worker metrics.

    Returns worker status, verification counts, and performance metrics.
    """
    try:
        worker = get_jit_verification_worker()
        metrics = worker.get_metrics()

        return WorkerMetricsResponse(**metrics)
    except Exception as e:
        logger.error(f"Failed to get worker metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get worker metrics: {str(e)}")


@router.post("/worker/start")
async def start_worker(
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Start the JIT verification background worker.

    The worker will periodically verify citations and update the cache.
    """
    worker = await start_jit_verification_worker()

    logger.info("JIT verification worker started by admin")

    return {
        "status": "started",
        "message": "JIT verification worker started",
        "workspace_id": worker.workspace_id,
        "check_interval_seconds": worker.check_interval,
        "started_at": datetime.now().isoformat()
    }


@router.post("/worker/stop")
async def stop_worker(
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Stop the JIT verification background worker.
    """
    await stop_jit_verification_worker()

    logger.info("JIT verification worker stopped by admin")

    return {
        "status": "stopped",
        "message": "JIT verification worker stopped",
        "stopped_at": datetime.now().isoformat()
    }


@router.post("/worker/verify-fact/{fact_id}")
async def verify_fact_citations(
    fact_id: str,
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Verify all citations for a specific fact.

    Forces re-verification and updates the fact's verification status.
    """
    worker = get_jit_verification_worker()
    results = await worker.verify_fact_citations(fact_id)

    return {
        "fact_id": fact_id,
        "citation_count": len(results),
        "results": {k: v.to_dict() for k, v in results.items()},
        "verified_at": datetime.now().isoformat()
    }


@router.get("/worker/top-citations")
async def get_top_citations(
    limit: int = Query(20, ge=1, le=100, description="Number of top citations to return"),
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Get most frequently accessed citations.

    Useful for understanding which citations are most important
    for the verification system.
    """
    worker = get_jit_verification_worker()
    metrics = worker.get_metrics()

    top_citations = metrics["top_citations"][:limit]

    return {
        "top_citations": top_citations,
        "total_unique_citations": len(worker._citation_access_count),
        "retrieved_at": datetime.now().isoformat()
    }


@router.get("/health")
async def get_jit_health(
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Get overall health status of JIT verification system.

    Includes cache health, worker status, and recent performance.
    """
    cache = get_jit_verification_cache()
    worker = get_jit_verification_worker()

    cache_stats = cache.get_stats()
    worker_metrics = worker.get_metrics()

    # Calculate health score
    health_issues = []

    # Check worker running
    if not worker_metrics["running"]:
        health_issues.append("Worker not running")

    # Check cache hit rate
    ver_hit_rate = cache_stats["l1"]["l1_verification_hit_rate"]
    if ver_hit_rate < 0.5:
        health_issues.append(f"Low cache hit rate: {ver_hit_rate:.1%}")

    # Check for stale facts
    if worker_metrics["stale_facts"] > 0:
        health_issues.append(f"{worker_metrics['stale_facts']} stale facts detected")

    # Check for outdated facts
    if worker_metrics["outdated_facts"] > 0:
        health_issues.append(f"{worker_metrics['outdated_facts']} outdated facts detected")

    health_status = "healthy" if not health_issues else "degraded" if len(health_issues) < 3 else "unhealthy"

    return {
        "status": health_status,
        "issues": health_issues,
        "cache": {
            "l1_enabled": True,
            "l2_enabled": cache_stats["l2_enabled"],
            "verification_hit_rate": f"{ver_hit_rate:.1%}",
            "query_hit_rate": f"{cache_stats['l1']['l1_query_hit_rate']:.1%}",
            "total_cached_verifications": cache_stats["l1"]["l1_verification_cache_size"]
        },
        "worker": {
            "running": worker_metrics["running"],
            "last_run": worker_metrics["last_run_time"],
            "verified_count": worker_metrics["verified_count"],
            "failed_count": worker_metrics["failed_count"],
            "avg_verification_time": f"{worker_metrics['average_verification_time']:.3f}s"
        },
        "checked_at": datetime.now().isoformat()
    }


@router.post("/cache/warm")
async def warm_cache(
    limit: int = Query(100, ge=1, le=1000, description="Number of facts to warm cache with"),
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Warm the JIT verification cache by pre-verifying citations.

    Fetches business facts and verifies their citations to populate
    the cache before they're needed by agents.
    """
    import time
    from core.agent_world_model import WorldModelService

    cache = get_jit_verification_cache()
    wm = WorldModelService("default")  # TODO: Get from context

    start_time = time.time()

    # Fetch facts
    facts = await wm.list_all_facts(limit=limit)

    # Extract unique citations
    citations = set()
    for fact in facts:
        citations.update(fact.citations)

    # Verify citations (populates cache)
    results = await cache.verify_citations_batch(list(citations))

    duration = time.time() - start_time
    verified_count = sum(1 for r in results if r.exists)

    logger.info(
        f"Cache warming completed: "
        f"{verified_count}/{len(citations)} citations verified in {duration:.2f}s"
    )

    return {
        "status": "warmed",
        "facts_processed": len(facts),
        "citations_verified": len(citations),
        "verified_count": verified_count,
        "duration_seconds": duration,
        "warmed_at": datetime.now().isoformat()
    }


@router.get("/config")
async def get_jit_config(
    current_user = Depends(get_current_user),
    _ = Depends(require_role(UserRole.ADMIN))
):
    """
    Get current JIT verification configuration.

    Returns cache settings, worker intervals, and other configuration.
    """
    import os

    worker = get_jit_verification_worker()
    cache = get_jit_verification_cache()

    return {
        "worker": {
            "workspace_id": worker.workspace_id,
            "check_interval_seconds": worker.check_interval,
            "batch_size": worker.batch_size,
            "max_concurrent": worker.max_concurrent,
            "running": worker._running
        },
        "cache": {
            "l1": {
                "max_size": cache.l1.max_size,
                "verification_ttl_seconds": cache.l1.verification_ttl,
                "query_ttl_seconds": cache.l1.query_ttl
            },
            "l2": {
                "enabled": cache.l2._enabled,
                "verification_ttl_seconds": cache.l2.verification_ttl,
                "query_ttl_seconds": cache.l2.query_ttl,
                "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0")
            }
        }
    }
