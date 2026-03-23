"""
Provider Health Routes API

Health status and manual sync endpoints for LLM provider registry monitoring.

Endpoints:
- GET /api/providers/health - Overall provider registry health status
- GET /api/providers/{provider_id}/health - Per-provider health details
- POST /api/providers/sync - Manual trigger for provider registry sync

References:
- backend/core/provider_health_monitor.py - Health status tracking
- backend/core/provider_auto_discovery.py - Provider sync orchestration
- backend/core/provider_registry.py - Provider registry service
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from datetime import datetime, timezone
import logging

from core.provider_health_monitor import get_provider_health_monitor
from core.provider_auto_discovery import get_auto_discovery
from core.provider_registry import get_provider_registry
from core.database import get_db_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("/health")
async def get_provider_health() -> Dict[str, Any]:
    """
    Get overall provider registry health status.

    Returns aggregate health statistics including:
    - Total provider count
    - Healthy provider count (health_score >= 0.5)
    - Unhealthy provider count
    - Per-provider health scores and model counts

    Returns:
        Health status with provider counts and individual provider scores
    """
    health_monitor = get_provider_health_monitor()
    registry = get_provider_registry()

    with get_db_session() as db:
        providers = registry.list_providers(active_only=True)

    healthy_providers = health_monitor.get_healthy_providers(min_score=0.5)

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_providers": len(providers),
        "healthy_providers": len(healthy_providers),
        "unhealthy_providers": len(providers) - len(healthy_providers),
        "providers": [
            {
                "provider_id": p["provider_id"],
                "health_score": health_monitor.get_health_score(p["provider_id"]),
                "model_count": p["model_count"]
            }
            for p in providers
        ]
    }


@router.get("/{provider_id}/health")
async def get_provider_health_detail(provider_id: str) -> Dict[str, Any]:
    """
    Get detailed health status for a specific provider.

    Args:
        provider_id: Provider identifier (e.g., 'openai', 'anthropic')

    Returns:
        Detailed health status including:
        - Provider ID and name
        - Health score (0.0-1.0)
        - Healthy status (True if score >= 0.5)
        - Last updated timestamp
        - Active status
        - Capability flags (vision, tools)

    Raises:
        HTTPException 404: If provider not found in registry
    """
    health_monitor = get_provider_health_monitor()
    registry = get_provider_registry()

    provider = registry.get_provider(provider_id)
    if not provider:
        raise HTTPException(
            status_code=404,
            detail=f"Provider {provider_id} not found"
        )

    health_score = health_monitor.get_health_score(provider_id)

    return {
        "provider_id": provider_id,
        "name": provider.name,
        "health_score": health_score,
        "is_healthy": health_score >= 0.5,
        "last_updated": provider.last_updated.isoformat() if provider.last_updated else None,
        "is_active": provider.is_active,
        "supports_vision": provider.supports_vision,
        "supports_tools": provider.supports_tools
    }


@router.post("/sync")
async def trigger_provider_sync() -> Dict[str, Any]:
    """
    Trigger manual provider registry sync.

    Initiates an immediate sync from DynamicPricingFetcher to ProviderRegistry,
    updating all provider and model information. Typically run automatically
    every 24 hours by ProviderScheduler.

    Returns:
        Sync result with:
        - Success status
        - Timestamp
        - Number of providers synced
        - Number of models synced

    Raises:
        HTTPException 500: If sync fails
    """
    auto_discovery = get_auto_discovery()

    try:
        result = await auto_discovery.sync_providers()
        logger.info(f"Manual sync completed: {result}")
        return {
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "providers_synced": result.get("providers_synced", 0),
            "models_synced": result.get("models_synced", 0)
        }
    except Exception as e:
        logger.error(f"Manual sync failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Sync failed: {str(e)}"
        )
