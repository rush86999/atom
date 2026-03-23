from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel

from core.database import get_db
from core.provider_registry import get_provider_registry
from core.provider_auto_discovery import get_auto_discovery
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Response Models
class ProviderResponse(BaseModel):
    provider_id: str
    name: str
    description: Optional[str]
    quality_score: Optional[float]
    supports_vision: bool
    supports_tools: bool
    supports_cache: bool
    is_active: bool
    model_count: int
    discovered_at: str
    last_updated: str

class ModelResponse(BaseModel):
    model_id: str
    provider_id: str
    name: Optional[str]
    input_cost_per_token: Optional[float]
    output_cost_per_token: Optional[float]
    max_tokens: Optional[int]
    mode: Optional[str]
    source: Optional[str]

class SyncResponse(BaseModel):
    success: bool
    message: str
    sync_id: str

# Endpoints

@router.get("/api/ai/providers/registry", response_model=dict)
async def list_providers(
    active_only: bool = Query(True, description="Filter to active providers only"),
    include_inactive: bool = Query(False, description="Include inactive providers")
):
    """List all providers with model counts"""
    try:
        registry = get_provider_registry()
        providers = registry.list_providers(active_only=active_only or include_inactive)

        return {
            "success": True,
            "providers": providers,
            "count": len(providers)
        }
    except Exception as e:
        logger.error(f"Error listing providers: {e}")
        raise HTTPException(status_code=500, detail="Failed to list providers")

@router.get("/api/ai/providers/registry/{provider_id}", response_model=dict)
async def get_provider(provider_id: str):
    """Get single provider with models"""
    try:
        registry = get_provider_registry()
        provider = registry.get_provider(provider_id)

        if not provider:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

        models = registry.get_models_by_provider(provider_id)

        return {
            "success": True,
            "provider": {
                "provider_id": provider.provider_id,
                "name": provider.name,
                "description": provider.description,
                "quality_score": provider.quality_score,
                "supports_vision": provider.supports_vision,
                "supports_tools": provider.supports_tools,
                "supports_cache": provider.supports_cache,
                "is_active": provider.is_active,
                "discovered_at": provider.discovered_at.isoformat() if provider.discovered_at else None,
                "last_updated": provider.last_updated.isoformat() if provider.last_updated else None,
            },
            "models": [
                {
                    "model_id": m.model_id,
                    "name": m.name,
                    "input_cost_per_token": m.input_cost_per_token,
                    "output_cost_per_token": m.output_cost_per_token,
                    "max_tokens": m.max_tokens,
                    "mode": m.mode,
                    "source": m.source,
                }
                for m in models
            ],
            "model_count": len(models)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting provider {provider_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get provider")

@router.get("/api/ai/providers/registry/{provider_id}/models", response_model=dict)
async def list_provider_models(
    provider_id: str,
    supports_vision: Optional[bool] = Query(None),
    min_quality: Optional[int] = Query(None),
    max_cost: Optional[float] = Query(None)
):
    """List models for a provider with optional filters"""
    try:
        registry = get_provider_registry()

        # Verify provider exists
        provider = registry.get_provider(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

        filters = {}
        if supports_vision is not None:
            filters["supports_vision"] = supports_vision
        if min_quality is not None:
            filters["min_quality"] = min_quality
        if max_cost is not None:
            filters["max_cost"] = max_cost

        models = registry.search_models(filters)
        # Filter by provider_id
        models = [m for m in models if m.provider_id == provider_id]

        return {
            "success": True,
            "models": [
                {
                    "model_id": m.model_id,
                    "name": m.name,
                    "input_cost_per_token": m.input_cost_per_token,
                    "output_cost_per_token": m.output_cost_per_token,
                    "max_tokens": m.max_tokens,
                    "mode": m.mode,
                }
                for m in models
            ],
            "count": len(models)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing models for {provider_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list models")

@router.post("/api/ai/providers/registry/sync", response_model=dict)
async def sync_providers(background_tasks: BackgroundTasks):
    """Trigger manual sync from LiteLLM/OpenRouter"""
    import uuid
    sync_id = str(uuid.uuid4())

    async def run_sync():
        try:
            discovery = get_auto_discovery()
            result = await discovery.sync_providers()
            logger.info(f"Sync {sync_id} completed: {result}")
        except Exception as e:
            logger.error(f"Sync {sync_id} failed: {e}")

    background_tasks.add_task(run_sync)

    return {
        "success": True,
        "message": "Provider sync started in background",
        "sync_id": sync_id
    }

@router.get("/api/ai/providers/registry/sync/status", response_model=dict)
async def get_sync_status():
    """Check sync status"""
    # For now, return basic status
    # Could be enhanced with actual sync state tracking
    return {
        "success": True,
        "syncing": False,
        "last_sync": None  # Could be tracked in ProviderAutoDiscovery
    }
