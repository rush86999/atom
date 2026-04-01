"""LLM Registry API routes.

Endpoints for model registry management, health monitoring, and sync operations.

This module provides:
- Provider health monitoring endpoints
- Model quality filtering and search
- Quality score synchronization from LMSYS
- Model capability queries

Author: Atom AI Platform
Created: 2026-03-31
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime

from core.database import get_db
from core.llm.registry.provider_health import ProviderHealthService

router = APIRouter(prefix="/api/llm-registry", tags=["llm-registry"])


@router.get("/provider-health")
async def get_provider_health(
    providers: Optional[str] = None,  # Comma-separated list of providers
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get health status for LLM providers.

    Returns health metrics including success rate, error rate, latency,
    and current state (healthy, degraded, unhealthy, rate_limited).

    Query params:
        providers: Comma-separated list of provider names (optional)
                  If omitted, returns all known providers

    Returns:
        Dict mapping provider name to health metrics:
        {
            "providers": {
                "openai": {
                    "state": "healthy",
                    "success_count": 1234,
                    "error_count": 12,
                    "consecutive_failures": 0,
                    "avg_latency_ms": 245.5,
                    "last_success_ts": "2026-03-22T12:34:56Z",
                    "last_error_ts": null
                },
                ...
            },
            "timestamp": "2026-03-22T12:34:56Z"
        }
    """
    health_service = ProviderHealthService()

    # Default providers to check
    default_providers = ['openai', 'anthropic', 'google', 'meta', 'mistral', 'cohere', 'deepseek']

    if providers:
        provider_list = [p.strip() for p in providers.split(',')]
    else:
        provider_list = default_providers

    health_data = await health_service.get_all_health(provider_list)

    return {
        "providers": health_data,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/models/by-quality")
async def get_models_by_quality(
    min_quality: float = 80.0,
    max_quality: float = 100.0,
    limit: int = 50,
    capabilities: Optional[str] = None,  # Comma-separated
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get models within a quality score range.

    Query params:
        min_quality: Minimum quality score (default 80)
        max_quality: Maximum quality score (default 100)
        limit: Max results (default 50)
        capabilities: Comma-separated capability list (e.g., "tools,vision")

    Returns:
        List of models sorted by quality_score DESC
    """
    from core.llm.registry.queries import get_models_by_quality_range

    # Parse capabilities
    caps = None
    if capabilities:
        caps = [c.strip() for c in capabilities.split(',')]

    models = get_models_by_quality_range(
        db,
        tenant_id="default",  # Open-source uses default tenant
        min_quality=min_quality,
        max_quality=max_quality,
        limit=limit
    )

    # Filter by capabilities if specified
    if caps and models:
        filtered = []
        for m in models:
            model_caps = m.capabilities or []
            if all(c in model_caps for c in caps):
                filtered.append(m)
        models = filtered

    return {
        'min_quality': min_quality,
        'max_quality': max_quality,
        'count': len(models),
        'models': [m.to_dict() for m in models]
    }


@router.post("/sync-quality")
async def sync_quality_scores(
    source: str = "lmsys",  # lmsys, heuristic, or auto
    force_refresh: bool = False,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Sync model quality scores from specified source.

    Args:
        source: Score source ('lmsys', 'heuristic', 'auto')
        force_refresh: Force refresh from API

    Returns:
        Sync results with updated/summary counts
    """
    from core.llm.registry.service import LLMRegistryService

    service = LLMRegistryService(db)

    if source == "lmsys":
        result = await service.update_quality_scores_from_lmsys(
            tenant_id="default",
            use_cache=not force_refresh
        )
    elif source == "heuristic":
        result = service.assign_heuristic_quality_scores(
            tenant_id="default",
            overwrite_existing=True
        )
    elif source == "auto":
        # Try LMSYS first, fall back to heuristic
        lmsys_result = await service.update_quality_scores_from_lmsys(
            tenant_id="default",
            use_cache=not force_refresh
        )
        # Fill in missing with heuristics
        heuristic_result = service.assign_heuristic_quality_scores(
            tenant_id="default",
            overwrite_existing=False
        )
        result = {
            'lmsys_updated': lmsys_result['updated'],
            'heuristic_assigned': heuristic_result['assigned'],
            'total_with_scores': lmsys_result['updated'] + heuristic_result['assigned']
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source: {source}. Use 'lmsys', 'heuristic', or 'auto'"
        )

    return {
        'source': source,
        'result': result,
        'timestamp': datetime.utcnow().isoformat()
    }


@router.get("/models/search")
async def search_models(
    query: Optional[str] = None,
    provider: Optional[str] = None,
    capabilities: Optional[str] = None,
    min_quality: Optional[float] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Search models by name, provider, or capabilities.

    Query params:
        query: Search query (matches model name or description)
        provider: Filter by provider (e.g., "openai", "anthropic")
        capabilities: Comma-separated capabilities (e.g., "tools,vision")
        min_quality: Minimum quality score filter
        limit: Max results (default 20)

    Returns:
        List of matching models
    """
    from core.llm.registry.queries import search_models

    # Parse capabilities
    caps = None
    if capabilities:
        caps = [c.strip() for c in capabilities.split(',')]

    models = search_models(
        db,
        query=query,
        provider=provider,
        capabilities=caps,
        min_quality=min_quality,
        limit=limit
    )

    return {
        'count': len(models),
        'models': [m.to_dict() for m in models]
    }


@router.get("/providers/list")
async def list_providers(
    include_health: bool = True,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """List all available LLM providers.

    Query params:
        include_health: Include health status for each provider (default: true)

    Returns:
        List of providers with optional health status
    """
    from core.models import ModelCatalog
    from sqlalchemy import distinct
    
    # Get unique providers from model catalog
    providers = db.query(distinct(ModelCatalog.provider)).all()
    provider_list = [p[0] for p in providers if p[0]]

    result = {"providers": []}

    if include_health:
        health_service = ProviderHealthService()
        health_data = await health_service.get_all_health(provider_list)
        
        for provider in provider_list:
            health = health_data.get(provider, {})
            result["providers"].append({
                "id": provider,
                "name": provider.capitalize(),
                "health_state": health.get("state", "unknown"),
                "success_rate": health.get("success_rate", 0),
                "avg_latency_ms": health.get("avg_latency_ms", 0)
            })
    else:
        result["providers"] = [{"id": p, "name": p.capitalize()} for p in provider_list]

    return result
