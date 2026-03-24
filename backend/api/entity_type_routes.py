"""
Entity Type API Routes

Endpoints for managing dynamic entity type definitions.
"""
import logging
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from core.base_routes import BaseAPIRouter
from core.entity_type_service import get_entity_type_service

router = BaseAPIRouter(prefix="/api/entity-types", tags=["Entity Types"])

# --- Request/Response Models ---

class EntityTypeCreate(BaseModel):
    slug: str
    display_name: str
    json_schema: Dict[str, Any]
    description: Optional[str] = None
    available_skills: Optional[List[str]] = None

class EntityTypeUpdate(BaseModel):
    display_name: Optional[str] = None
    json_schema: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    available_skills: Optional[List[str]] = None

# --- Route Handlers ---

@router.post("")
async def create_entity_type(workspace_id: str, request: EntityTypeCreate):
    """Create a new entity type."""
    service = get_entity_type_service()
    try:
        entity_type = service.create_entity_type(
            tenant_id=workspace_id,
            slug=request.slug,
            display_name=request.display_name,
            json_schema=request.json_schema,
            description=request.description,
            available_skills=request.available_skills
        )
        return router.success_response(
            data={"id": entity_type.id, "slug": entity_type.slug},
            message="Entity type created successfully"
        )
    except ValueError as e:
        raise router.validation_error("entity_type", str(e))

@router.get("")
async def list_entity_types(workspace_id: str, include_system: bool = False):
    """List entity types."""
    service = get_entity_type_service()
    entity_types = service.list_entity_types(tenant_id=workspace_id, include_system=include_system)
    return router.success_response(
        data=[
            {
                "id": et.id,
                "slug": et.slug,
                "display_name": et.display_name,
                "description": et.description,
                "json_schema": et.json_schema,
                "available_skills": et.available_skills,
                "is_system": et.is_system
            }
            for et in entity_types
        ]
    )

@router.get("/{entity_type_id}")
async def get_entity_type(workspace_id: str, entity_type_id: str):
    """Get entity type by ID."""
    service = get_entity_type_service()
    entity_type = service.get_entity_type(tenant_id=workspace_id, entity_type_id=entity_type_id)
    if not entity_type:
        raise router.not_found_error("EntityType", entity_type_id)
    
    return router.success_response(data={
        "id": entity_type.id,
        "slug": entity_type.slug,
        "display_name": entity_type.display_name,
        "description": entity_type.description,
        "json_schema": entity_type.json_schema,
        "available_skills": entity_type.available_skills,
        "is_system": entity_type.is_system
    })

@router.patch("/{entity_type_id}")
async def update_entity_type(workspace_id: str, entity_type_id: str, request: EntityTypeUpdate):
    """Update entity type."""
    service = get_entity_type_service()
    try:
        entity_type = service.update_entity_type(
            tenant_id=workspace_id,
            entity_type_id=entity_type_id,
            display_name=request.display_name,
            json_schema=request.json_schema,
            description=request.description,
            available_skills=request.available_skills
        )
        return router.success_response(
            data={"id": entity_type.id},
            message="Entity type updated successfully"
        )
    except ValueError as e:
        raise router.validation_error("entity_type", str(e))
