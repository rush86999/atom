"""
Local Model Provider API Routes.

Lets users register OpenAI-compatible local LLM backends (Ollama, LM Studio,
vLLM, LocalAI, custom) and configure per-model capabilities. Registered models
become eligible for BPC ranking, cognitive tier assignment, and learning-router
re-ranking — just like cloud models, but at zero cost.

Routes mount at /api/local-models/...
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import LocalModelProvider, LocalModelCapabilities, User
from core.security_dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/local-models", tags=["Local Models"])


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class RegisterProviderRequest(BaseModel):
    name: str = Field(..., description="User-friendly label, e.g. 'My Ollama'")
    provider_type: str = Field("custom", description="ollama | lm_studio | vllm | localai | custom")
    base_url: str = Field(..., description="OpenAI-compatible endpoint, e.g. http://localhost:11434/v1")
    api_key: Optional[str] = Field(None, description="Optional — for backends that require a key")


class SetCapabilitiesRequest(BaseModel):
    model_id: str = Field(..., description="Model name as served by the provider, e.g. 'llama3:8b'")
    supports_tools: bool = False
    supports_vision: bool = False
    supports_reasoning: bool = False
    quality_score: float = Field(0.5, ge=0.0, le=1.0)
    speed_score: float = Field(0.5, ge=0.0, le=1.0)
    context_window: int = Field(4096, gt=0)


class ProviderResponse(BaseModel):
    id: str
    name: str
    provider_type: str
    base_url: str
    is_active: bool
    has_api_key: bool


class CapabilitiesResponse(BaseModel):
    model_id: str
    supports_tools: bool
    supports_vision: bool
    supports_reasoning: bool
    quality_score: float
    speed_score: float
    context_window: int


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("")
async def list_providers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List all registered local model providers for the current user's workspace."""
    ws_id = current_user.workspace_id or "default"
    providers = db.query(LocalModelProvider).filter(
        LocalModelProvider.workspace_id == ws_id,
        LocalModelProvider.is_active == True,  # noqa: E712
    ).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "provider_type": p.provider_type,
            "base_url": p.base_url,
            "is_active": p.is_active,
            "has_api_key": bool(p.api_key),
        }
        for p in providers
    ]


@router.post("")
async def register_provider(
    request: RegisterProviderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Register a new local model provider."""
    ws_id = current_user.workspace_id or "default"
    provider = LocalModelProvider(
        workspace_id=ws_id,
        tenant_id=current_user.tenant_id,
        name=request.name,
        provider_type=request.provider_type,
        base_url=request.base_url.rstrip("/"),
        api_key=request.api_key,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    logger.info(f"Registered local model provider '{request.name}' at {request.base_url}")
    return {"id": provider.id, "name": provider.name, "registered": True}


@router.delete("/{provider_id}")
async def unregister_provider(
    provider_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Unregister a local model provider."""
    provider = db.query(LocalModelProvider).filter(LocalModelProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    db.delete(provider)
    db.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Model discovery
# ---------------------------------------------------------------------------

@router.get("/{provider_id}/models")
async def discover_models(
    provider_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Auto-discover available models from a local provider.

    Calls GET {base_url}/models (the OpenAI-compatible endpoint) and returns
    the model list. Also registers each discovered model into the pricing cache
    so capability detection works.
    """
    provider = db.query(LocalModelProvider).filter(LocalModelProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    try:
        headers = {}
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{provider.base_url}/models", headers=headers)
            resp.raise_for_status()
            data = resp.json()

        models = []
        for m in data.get("data", []):
            model_id = m.get("id") or m.get("name", "")
            if model_id:
                models.append(model_id)
                # Register into the pricing cache so capability detection works.
                _register_in_pricing_cache(model_id, provider)

        return {"models": models, "count": len(models)}
    except Exception as e:
        logger.warning(f"Model discovery failed for {provider.name}: {e}")
        return {"models": [], "count": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

@router.get("/{provider_id}/capabilities")
async def get_capabilities(
    provider_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get configured capabilities for all models under a provider."""
    caps = db.query(LocalModelCapabilities).filter(
        LocalModelCapabilities.provider_id == provider_id
    ).all()
    return [
        {
            "model_id": c.model_id,
            "supports_tools": c.supports_tools,
            "supports_vision": c.supports_vision,
            "supports_reasoning": c.supports_reasoning,
            "quality_score": c.quality_score,
            "speed_score": c.speed_score,
            "context_window": c.context_window,
        }
        for c in caps
    ]


@router.post("/{provider_id}/capabilities")
async def set_capabilities(
    provider_id: str,
    request: SetCapabilitiesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Set capabilities for a specific model under a provider.

    This tells the system what the local model can do (since there's no
    pricing-cache metadata for local models). Feeds into BPC capability
    filtering, cognitive tier assignment, and the learning router registry.
    """
    ws_id = current_user.workspace_id or "default"
    provider = db.query(LocalModelProvider).filter(LocalModelProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Upsert: update if exists, create if not.
    existing = db.query(LocalModelCapabilities).filter(
        LocalModelCapabilities.provider_id == provider_id,
        LocalModelCapabilities.model_id == request.model_id,
    ).first()

    if existing:
        existing.supports_tools = request.supports_tools
        existing.supports_vision = request.supports_vision
        existing.supports_reasoning = request.supports_reasoning
        existing.quality_score = request.quality_score
        existing.speed_score = request.speed_score
        existing.context_window = request.context_window
    else:
        cap = LocalModelCapabilities(
            provider_id=provider_id,
            workspace_id=ws_id,
            model_id=request.model_id,
            supports_tools=request.supports_tools,
            supports_vision=request.supports_vision,
            supports_reasoning=request.supports_reasoning,
            quality_score=request.quality_score,
            speed_score=request.speed_score,
            context_window=request.context_window,
        )
        db.add(cap)

    db.commit()

    # Register into the pricing cache so BPC capability detection works.
    _register_in_pricing_cache(request.model_id, provider, request.model_dump())

    return {"model_id": request.model_id, "set": True}


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------

@router.post("/{provider_id}/test")
async def test_connection(
    provider_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Test whether a local provider is reachable."""
    provider = db.query(LocalModelProvider).filter(LocalModelProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    try:
        headers = {}
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{provider.base_url}/models", headers=headers)
            resp.raise_for_status()
        return {"reachable": True, "status_code": resp.status_code}
    except Exception as e:
        return {"reachable": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_in_pricing_cache(
    model_id: str,
    provider: LocalModelProvider,
    capabilities: Optional[Dict[str, Any]] = None,
) -> None:
    """Inject a local model into the in-memory pricing cache so BPC and
    capability-detection functions work without changing their logic."""
    try:
        from core.dynamic_pricing_fetcher import get_pricing_fetcher
        fetcher = get_pricing_fetcher()
        entry = {
            "model_id": model_id,
            "litellm_provider": provider.provider_type,
            "input_cost": 0.0,
            "output_cost": 0.0,
            "max_input_tokens": (capabilities or {}).get("context_window", 8192),
            "supports_tools": (capabilities or {}).get("supports_tools", True),
            "supports_vision": (capabilities or {}).get("supports_vision", False),
            "supports_reasoning": (capabilities or {}).get("supports_reasoning", False),
            "quality_score": (capabilities or {}).get("quality_score", 0.5),
        }
        fetcher.pricing_cache[model_id] = entry
    except Exception as e:
        logger.debug(f"Could not register local model in pricing cache: {e}")
