"""
Admin cache management routes.

Exposes the BYOK cache pre-seeding service over HTTP:
- POST /api/v1/admin/cache/preseed — warm all or a specific cache
- GET  /api/v1/admin/cache/stats  — current cache statistics
- GET  /api/v1/admin/cache/health — overall cache health status

NOTE: This router is intentionally not mounted in main_api_app.py yet.
Mounting it in production requires an admin-auth dependency (see the
security requirements in CLAUDE.md); the module is importable and tested
standalone via tests/unit/test_byok_cache_preseeding_ORIG.py.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from core.admin_endpoints import get_super_admin
from core.models import User
from pydantic import BaseModel

from core.byok_cache_preseeding import (
    preseed_all_caches,
    preseed_cache_aware_router,
    preseed_cognitive_models,
    preseed_governance_cache,
    preseed_pricing_cache,
)
from core.dynamic_pricing_fetcher import get_pricing_fetcher
from core.governance_cache import get_governance_cache
from core.llm.cache_aware_router import CacheAwareRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/cache", tags=["Admin Cache"])

VALID_CACHE_TYPES = {"all", "pricing", "cognitive", "governance", "cache_aware"}


class CachePreseedRequest(BaseModel):
    cache_type: str = "all"
    workspace_id: str = "default"


@router.post("/preseed")
async def preseed_cache(req: CachePreseedRequest, admin: User = Depends(get_super_admin)) -> Dict[str, Any]:
    """Pre-seed BYOK caches. Returns per-cache results keyed by cache type."""
    if req.cache_type == "all":
        return await preseed_all_caches(workspace_id=req.workspace_id, verbose=False)
    if req.cache_type == "pricing":
        return {"pricing": await preseed_pricing_cache(verbose=False)}
    if req.cache_type == "cognitive":
        return {"cognitive": await preseed_cognitive_models(verbose=False)}
    if req.cache_type == "governance":
        return {"governance": await preseed_governance_cache(workspace_id=req.workspace_id, verbose=False)}
    if req.cache_type == "cache_aware":
        return {"cache_aware": await preseed_cache_aware_router(workspace_id=req.workspace_id, verbose=False)}
    raise HTTPException(status_code=400, detail=f"Invalid cache_type: {req.cache_type}")


@router.get("/stats")
async def cache_stats(admin: User = Depends(get_super_admin)) -> Dict[str, Any]:
    """Return current statistics for governance, pricing, and router caches."""
    governance_cache = get_governance_cache()
    pricing = get_pricing_fetcher()
    router_instance = CacheAwareRouter(pricing)
    return {
        "governance_cache": governance_cache.get_stats(),
        "pricing_cache": {
            "models": len(pricing.pricing_cache),
            "last_fetch": pricing.last_fetch.isoformat() if pricing.last_fetch else None,
        },
        "cache_aware_router": {
            "cache_history_size": len(router_instance.cache_hit_history),
        },
    }


@router.get("/health")
async def cache_health(admin: User = Depends(get_super_admin)) -> Dict[str, Any]:
    """Return overall cache health status."""
    overall_status = "OK"
    details: Dict[str, Any] = {}
    try:
        governance_cache = get_governance_cache()
        stats = governance_cache.get_stats()
        details["governance_cache"] = {
            "size": stats.get("size", 0),
            "hit_rate": stats.get("hit_rate", 0.0),
        }
        if stats.get("size", 0) == 0:
            overall_status = "DEGRADED"
            details["reason"] = "Governance cache is empty"
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        overall_status = "DEGRADED"
        details["reason"] = "Governance cache check failed"
    return {
        "overall_status": overall_status,
        "status": overall_status,
        **details,
    }
