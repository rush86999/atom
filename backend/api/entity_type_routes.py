"""
Entity Type API Routes

Endpoints for managing dynamic entity type definitions.
"""
import logging
from typing import Dict, List, Any, Optional
from fastapi import Depends
from pydantic import BaseModel, Field

from core.base_routes import BaseAPIRouter
from core.auth import get_current_user, User
from core.entity_type_service import get_entity_type_service
from core.entity_schema_suggestion_service import get_entity_schema_suggestion_service

router = BaseAPIRouter(prefix="/api/entity-types", tags=["Entity Types"])

# --- Request/Response Models ---

class EntityTypeCreate(BaseModel):
    slug: str
    display_name: str
    json_schema: Dict[str, Any]
    description: Optional[str] = None
    available_skills: Optional[List[str]] = None
    is_active: Optional[bool] = None  # None → service default (True)

class EntityTypeUpdate(BaseModel):
    display_name: Optional[str] = None
    json_schema: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    available_skills: Optional[List[str]] = None
    # Activates/deactivates — the ONLY path that promotes auto-discovered
    # drafts (schema discovery creates types as inactive).
    is_active: Optional[bool] = None

class EntityTypeSuggestRequest(BaseModel):
    display_name: str
    description: str = ""

# --- Route Handlers ---

@router.post("")
async def create_entity_type(workspace_id: str, request: EntityTypeCreate, current_user: User = Depends(get_current_user)):
    """Create a new entity type."""
    service = get_entity_type_service()
    try:
        create_kwargs: Dict[str, Any] = dict(
            tenant_id=workspace_id,
            slug=request.slug,
            display_name=request.display_name,
            json_schema=request.json_schema,
            description=request.description,
            available_skills=request.available_skills,
        )
        if request.is_active is not None:
            create_kwargs["is_active"] = request.is_active
        entity_type = service.create_entity_type(**create_kwargs)
        return router.success_response(
            data={"id": entity_type.id, "slug": entity_type.slug},
            message="Entity type created successfully"
        )
    except ValueError as e:
        raise router.validation_error("entity_type", str(e))

@router.get("")
async def list_entity_types(
    workspace_id: str,
    include_system: bool = False,
    include_drafts: bool = False,
    current_user: User = Depends(get_current_user)
):
    """List entity types. Drafts (auto-discovered, inactive) are hidden by
    default; pass ``include_drafts=true`` to review them."""
    service = get_entity_type_service()
    entity_types = service.list_entity_types(
        tenant_id=workspace_id,
        include_system=include_system,
        is_active=None if include_drafts else True,
    )
    return router.success_response(
        data=[
            {
                "id": et.id,
                "slug": et.slug,
                "display_name": et.display_name,
                "description": et.description,
                "json_schema": et.json_schema,
                "available_skills": et.available_skills,
                "is_system": et.is_system,
                "is_active": et.is_active,
            }
            for et in entity_types
        ]
    )

@router.get("/{entity_type_id}")
async def get_entity_type(workspace_id: str, entity_type_id: str, current_user: User = Depends(get_current_user)):
    """Get entity type by ID. Auto-discovered drafts are included — an admin
    must be able to review a draft before activating it."""
    service = get_entity_type_service()
    entity_type = service.get_entity_type(
        tenant_id=workspace_id, entity_type_id=entity_type_id, include_inactive=True
    )
    if not entity_type:
        raise router.not_found_error("EntityType", entity_type_id)

    return router.success_response(data={
        "id": entity_type.id,
        "slug": entity_type.slug,
        "display_name": entity_type.display_name,
        "description": entity_type.description,
        "json_schema": entity_type.json_schema,
        "available_skills": entity_type.available_skills,
        "is_system": entity_type.is_system,
        "is_active": entity_type.is_active,
    })

@router.patch("/{entity_type_id}")
async def update_entity_type(workspace_id: str, entity_type_id: str, request: EntityTypeUpdate, current_user: User = Depends(get_current_user)):
    """Update entity type. Pass ``is_active`` to promote an auto-discovered
    draft (or retire a type)."""
    service = get_entity_type_service()
    try:
        entity_type = service.update_entity_type(
            tenant_id=workspace_id,
            entity_type_id=entity_type_id,
            display_name=request.display_name,
            json_schema=request.json_schema,
            description=request.description,
            available_skills=request.available_skills,
            is_active=request.is_active,
        )
        return router.success_response(
            data={"id": entity_type.id},
            message="Entity type updated successfully"
        )
    except ValueError as e:
        raise router.validation_error("entity_type", str(e))

@router.post("/suggest-schema")
async def suggest_entity_schema(request: EntityTypeSuggestRequest, current_user: User = Depends(get_current_user)):
    """Suggest a JSON Schema for an entity type."""
    service = get_entity_schema_suggestion_service()
    schema = await service.suggest_schema(
        display_name=request.display_name,
        description=request.description
    )
    return router.success_response(data=schema)
