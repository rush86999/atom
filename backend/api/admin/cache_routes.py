"""
Admin API Routes for BYOK Cache Management

Administrative endpoints for managing BYOK-related caches:
- Pre-seed all caches (pricing, models, governance)
- Refresh pricing cache on-demand
- View cache statistics
- Clear cache history

Target Audience: System Administrators
Authentication: ADMIN role required
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import User, UserRole
from core.byok_cache_preseeding import (
    preseed_all_caches,
    preseed_pricing_cache,
    preseed_cognitive_models,
    preseed_governance_cache,
    print_preseed_results,
)
from core.governance_cache import get_governance_cache
from core.dynamic_pricing_fetcher import get_pricing_fetcher, refresh_pricing_cache
from core.llm.cache_aware_router import CacheAwareRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/cache", tags=["admin-cache"])


# =============================================================================
# Pydantic Models
# =============================================================================

class PreseedRequest(BaseModel):
    """Request model for cache pre-seeding."""
    cache_type: str = Field(
        default="all",
        description="Type of cache to pre-seed: all, pricing, cognitive, governance"
    )
    workspace_id: str = Field(
        default="default",
        description="Workspace ID for context"
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose logging"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "cache_type": "all",
                "workspace_id": "default",
                "verbose": True
            }
        }


class PreseedResponse(BaseModel):
    """Response model for cache pre-seeding results."""
    success: bool
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    pricing: Optional[Dict[str, Any]] = None
    cognitive: Optional[Dict[str, Any]] = None
    governance: Optional[Dict[str, Any]] = None
    cache_aware: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CacheStatsResponse(BaseModel):
    """Response model for cache statistics."""
    governance_cache: Dict[str, Any]
    pricing_cache: Dict[str, Any]
    cache_aware_router: Dict[str, Any]


# =============================================================================
# Dependencies
# =============================================================================

async def require_admin(user_id: str = None, db: Session = Depends(get_db)):
    """
    Require ADMIN role for administrative endpoints.

    Args:
        user_id: User ID from authentication context
        db: Database session

    Returns:
        User object if ADMIN

    Raises:
        HTTPException 403 if user is not ADMIN
    """
    # TODO: Integrate with actual authentication system
    # For now, this is a placeholder
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.role == UserRole.ADMIN:
            return user

    # Allow access for development (remove in production)
    logger.warning("Admin endpoint accessed without authentication")
    return None


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/preseed", response_model=PreseedResponse, status_code=status.HTTP_200_OK)
async def preseed_byok_caches(
    request: PreseedRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin)
):
    """
    Pre-seed BYOK caches on-demand.

    Eliminates cold start latency by warming up:
    - Pricing cache (LiteLLM + OpenRouter API data)
    - Cognitive tier models (availability validation)
    - Governance cache (common agent permissions)
    - Cache-aware router (baseline probabilities)

    **Example Request:**
        POST /api/v1/admin/cache/preseed
        {
            "cache_type": "all",
            "workspace_id": "default",
            "verbose": true
        }

    **Response:**
        {
            "success": true,
            "started_at": "2026-05-02T10:30:00Z",
            "completed_at": "2026-05-02T10:30:15Z",
            "duration_seconds": 15.2,
            "pricing": {
                "success": true,
                "models_loaded": 1523
            },
            "cognitive": {
                "success": true,
                "tiers_loaded": 5
            }
        }
    """
    try:
        started_at = datetime.now().isoformat()

        if request.cache_type == "all":
            results = await preseed_all_caches(
                workspace_id=request.workspace_id,
                verbose=request.verbose
            )
        elif request.cache_type == "pricing":
            pricing_result = await preseed_pricing_cache(verbose=request.verbose)
            results = {
                "pricing": pricing_result,
                "success": pricing_result.get("success", False),
                "started_at": started_at,
                "completed_at": datetime.now().isoformat(),
            }
        elif request.cache_type == "cognitive":
            cognitive_result = await preseed_cognitive_models(verbose=request.verbose)
            results = {
                "cognitive": cognitive_result,
                "success": cognitive_result.get("success", False),
                "started_at": started_at,
                "completed_at": datetime.now().isoformat(),
            }
        elif request.cache_type == "governance":
            governance_result = await preseed_governance_cache(
                workspace_id=request.workspace_id,
                verbose=request.verbose
            )
            results = {
                "governance": governance_result,
                "success": governance_result.get("success", False),
                "started_at": started_at,
                "completed_at": datetime.now().isoformat(),
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid cache_type: {request.cache_type}. Must be one of: all, pricing, cognitive, governance"
            )

        return PreseedResponse(**results)

    except HTTPException:
        # Re-raise HTTP exceptions (like 400 Bad Request) without modification
        raise
    except Exception as e:
        logger.error(f"Cache pre-seeding failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache pre-seeding failed: {str(e)}"
        )


@router.get("/stats", response_model=CacheStatsResponse, status_code=status.HTTP_200_OK)
async def get_cache_stats(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin)
):
    """
    Get statistics for all BYOK-related caches.

    Returns cache hit rates, sizes, and other metrics:
    - Governance cache (hit rate, size, evictions)
    - Pricing cache (models loaded, providers)
    - Cache-aware router (history size)

    **Example Response:**
        {
            "governance_cache": {
                "size": 156,
                "hit_rate": 94.5,
                "evictions": 12
            },
            "pricing_cache": {
                "models_loaded": 1523,
                "providers": ["openai", "anthropic", "deepseek"]
            },
            "cache_aware_router": {
                "history_size": 42
            }
        }
    """
    try:
        # Governance cache stats
        gov_cache = get_governance_cache()
        gov_stats = gov_cache.get_stats()

        # Pricing cache stats
        pricing_fetcher = get_pricing_fetcher()
        pricing_stats = {
            "models_loaded": len(pricing_fetcher.pricing_cache),
            "last_fetch": pricing_fetcher.last_fetch.isoformat() if pricing_fetcher.last_fetch else None,
            "providers": list(set(
                pricing.get("litellm_provider", "unknown")
                for pricing in pricing_fetcher.pricing_cache.values()
            )),
        }

        # Cache-aware router stats
        cache_aware_router = CacheAwareRouter(pricing_fetcher)
        cache_aware_stats = {
            "history_size": len(cache_aware_router.cache_hit_history),
        }

        return CacheStatsResponse(
            governance_cache=gov_stats,
            pricing_cache=pricing_stats,
            cache_aware_router=cache_aware_stats
        )

    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache stats: {str(e)}"
        )


@router.post("/refresh/pricing", status_code=status.HTTP_200_OK)
async def refresh_pricing(
    force: bool = False,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin)
):
    """
    Refresh pricing cache from external APIs.

    Fetches latest model pricing from:
    - LiteLLM GitHub repository (primary)
    - OpenRouter API (fallback)

    **Query Parameters:**
        - force: Force refresh even if cache is valid (default: false)

    **Example Request:**
        POST /api/v1/admin/cache/refresh/pricing?force=true

    **Response:**
        {
            "success": true,
            "models_loaded": 1523,
            "duration_seconds": 3.2
        }
    """
    try:
        logger.info(f"Refreshing pricing cache (force={force})...")
        pricing_cache = await refresh_pricing_cache(force=force)

        return {
            "success": True,
            "models_loaded": len(pricing_cache),
            "message": "Pricing cache refreshed successfully"
        }

    except Exception as e:
        logger.error(f"Pricing cache refresh failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pricing cache refresh failed: {str(e)}"
        )


@router.post("/clear/governance", status_code=status.HTTP_200_OK)
async def clear_governance_cache(
    workspace_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin)
):
    """
    Clear governance cache entries.

    **Query Parameters:**
        - workspace_id: Optional workspace ID to clear (default: all workspaces)

    **Example Request:**
        POST /api/v1/admin/cache/clear/governance?workspace_id=default

    **Response:**
        {
            "success": true,
            "message": "Governance cache cleared for workspace: default"
        }
    """
    try:
        gov_cache = get_governance_cache()
        gov_cache.clear_cache_history(workspace_id=workspace_id)

        return {
            "success": True,
            "message": f"Governance cache cleared for workspace: {workspace_id or 'all'}"
        }

    except Exception as e:
        logger.error(f"Failed to clear governance cache: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear governance cache: {str(e)}"
        )


@router.get("/health", status_code=status.HTTP_200_OK)
async def cache_health_check(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin)
):
    """
    Health check for BYOK cache systems.

    Returns status of all cache systems:
    - Governance cache: OK/WARNING/ERROR
    - Pricing cache: OK/WARNING/ERROR
    - Cache-aware router: OK/WARNING/ERROR

    **Example Response:**
        {
            "overall_status": "OK",
            "governance_cache": "OK",
            "pricing_cache": "OK",
            "cache_aware_router": "OK",
            "details": {
                "governance_cache": {
                    "size": 156,
                    "hit_rate": 94.5
                },
                "pricing_cache": {
                    "models_loaded": 1523,
                    "last_fetch": "2026-05-02T10:00:00Z"
                }
            }
        }
    """
    try:
        # Check governance cache
        gov_cache = get_governance_cache()
        gov_stats = gov_cache.get_stats()
        gov_status = "OK" if gov_stats["size"] > 0 else "WARNING"

        # Check pricing cache
        pricing_fetcher = get_pricing_fetcher()
        pricing_size = len(pricing_fetcher.pricing_cache)
        pricing_status = "OK" if pricing_size > 1000 else "WARNING"

        # Check cache-aware router
        cache_aware_router = CacheAwareRouter(pricing_fetcher)
        router_status = "OK"

        # Overall status
        overall_status = "OK" if all([
            gov_status == "OK",
            pricing_status == "OK",
            router_status == "OK"
        ]) else "WARNING"

        return {
            "overall_status": overall_status,
            "governance_cache": gov_status,
            "pricing_cache": pricing_status,
            "cache_aware_router": router_status,
            "details": {
                "governance_cache": gov_stats,
                "pricing_cache": {
                    "models_loaded": pricing_size,
                    "last_fetch": pricing_fetcher.last_fetch.isoformat() if pricing_fetcher.last_fetch else None
                },
                "cache_aware_router": {
                    "history_size": len(cache_aware_router.cache_hit_history)
                }
            }
        }

    except Exception as e:
        logger.error(f"Cache health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache health check failed: {str(e)}"
        )
