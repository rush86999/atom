"""
Custom Canvas Components API Endpoints

REST API for managing custom HTML/CSS/JS canvas components with:
- Component CRUD operations
- Version control and rollback
- Usage tracking and statistics
- Security validation and governance

Endpoints:
- POST /api/components/create - Create new component
- GET /api/components - List components (with filters)
- GET /api/components/{id} - Get component by ID
- GET /api/components/by-slug/{slug} - Get component by slug
- PUT /api/components/{id} - Update component
- DELETE /api/components/{id} - Delete component
- GET /api/components/{id}/versions - Get version history
- POST /api/components/{id}/rollback - Rollback to version
- GET /api/components/{id}/stats - Get usage statistics
"""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.custom_components_service import ComponentSecurityError, CustomComponentsService
from core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateComponentRequest(BaseModel):
    """Request to create a custom component."""
    name: str = Field(..., description="Component name")
    html_content: str = Field(..., description="HTML template")
    css_content: Optional[str] = Field(None, description="CSS styles")
    js_content: Optional[str] = Field(None, description="JavaScript behavior (AUTONOMOUS only)")
    description: Optional[str] = Field(None, description="Component description")
    category: str = Field(default="custom", description="Component category")
    props_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema for properties")
    default_props: Optional[Dict[str, Any]] = Field(None, description="Default property values")
    dependencies: Optional[list[str]] = Field(None, description="External library dependencies")
    is_public: bool = Field(default=False, description="Share with other users")
    agent_id: Optional[str] = Field(None, description="Agent creating component (for governance)")


class UpdateComponentRequest(BaseModel):
    """Request to update a component."""
    name: Optional[str] = Field(None, description="Component name")
    html_content: Optional[str] = Field(None, description="HTML template")
    css_content: Optional[str] = Field(None, description="CSS styles")
    js_content: Optional[str] = Field(None, description="JavaScript behavior")
    description: Optional[str] = Field(None, description="Component description")
    props_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema for properties")
    default_props: Optional[Dict[str, Any]] = Field(None, description="Default property values")
    dependencies: Optional[list[str]] = Field(None, description="External library dependencies")
    is_public: Optional[bool] = Field(None, description="Share with other users")
    change_description: Optional[str] = Field(None, description="Description of changes")
    agent_id: Optional[str] = Field(None, description="Agent updating component (for governance)")


class RollbackComponentRequest(BaseModel):
    """Request to rollback a component."""
    target_version: int = Field(..., description="Version number to restore")


class RecordUsageRequest(BaseModel):
    """Request to record component usage."""
    canvas_id: str = Field(..., description="Canvas where component was used")
    session_id: Optional[str] = Field(None, description="Canvas session ID")
    agent_id: Optional[str] = Field(None, description="Agent that rendered component")
    props_passed: Optional[Dict[str, Any]] = Field(None, description="Properties passed to component")
    rendering_time_ms: Optional[int] = Field(None, description="Rendering time in milliseconds")
    error_message: Optional[str] = Field(None, description="Any rendering errors")
    governance_check_passed: Optional[bool] = Field(None, description="Governance check result")
    agent_maturity_level: Optional[str] = Field(None, description="Agent maturity level")


# ============================================================================
# Component CRUD Endpoints
# ============================================================================

@router.post("/create")
async def create_component(
    request: CreateComponentRequest,
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Create a new custom component.

    Creates a custom HTML/CSS/JS component with security validation
    and governance checks.

    **Security Requirements**:
    - HTML/CSS components: SUPERVISED+ maturity
    - JavaScript components: AUTONOMOUS maturity only

    Request Body:
        - name: Component name
        - html_content: HTML template
        - css_content: Optional CSS styles
        - js_content: Optional JavaScript (AUTONOMOUS required)
        - description: Component description
        - category: Component category
        - props_schema: JSON schema for component properties
        - default_props: Default property values
        - dependencies: External library URLs (whitelist enforced)
        - is_public: Share with other users
        - agent_id: Agent creating component (for governance check)

    Query Parameters:
        - user_id: Owner user ID

    Response:
        Created component data with ID, slug, and version
    """
    service = CustomComponentsService(db)

    try:
        result = service.create_component(
            user_id=user_id,
            name=request.name,
            html_content=request.html_content,
            css_content=request.css_content,
            js_content=request.js_content,
            description=request.description,
            category=request.category,
            props_schema=request.props_schema,
            default_props=request.default_props,
            dependencies=request.dependencies,
            is_public=request.is_public,
            agent_id=request.agent_id
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except ComponentSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("")
async def list_components(
    user_id: Optional[str] = Query(None, description="User ID (for private components)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_public: Optional[bool] = Query(None, description="Filter by public/private"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db)
):
    """
    List components with optional filtering.

    Returns user's own components plus public components.

    Query Parameters:
        - user_id: User ID (to include private components)
        - category: Filter by category
        - is_public: Filter by public/private
        - limit: Maximum results

    Response:
        List of components with summary info
    """
    service = CustomComponentsService(db)
    result = service.list_components(
        user_id=user_id,
        category=category,
        is_public=is_public,
        limit=limit
    )

    return result


@router.get("/{component_id}")
async def get_component(
    component_id: str,
    user_id: Optional[str] = Query(None, description="User ID for permission check"),
    db: Session = Depends(get_db)
):
    """
    Get a component by ID.

    Returns component HTML/CSS/JS content. JavaScript content
    is only returned to component owners.

    Path Parameters:
        - component_id: Component ID

    Query Parameters:
        - user_id: User ID (for permission check)

    Response:
        Full component data including code
    """
    service = CustomComponentsService(db)
    result = service.get_component(
        component_id=component_id,
        user_id=user_id
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/by-slug/{slug}")
async def get_component_by_slug(
    slug: str,
    user_id: Optional[str] = Query(None, description="User ID for permission check"),
    db: Session = Depends(get_db)
):
    """
    Get a component by slug.

    Alternative lookup method using URL-friendly slug.

    Path Parameters:
        - slug: Component slug

    Query Parameters:
        - user_id: User ID (for permission check)

    Response:
        Full component data including code
    """
    service = CustomComponentsService(db)
    result = service.get_component(
        slug=slug,
        user_id=user_id
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.put("/{component_id}")
async def update_component(
    component_id: str,
    request: UpdateComponentRequest,
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Update an existing component.

    Creates a new version with the updated content.
    Only component owners can update components.

    Path Parameters:
        - component_id: Component to update

    Query Parameters:
        - user_id: User ID (must be owner)

    Request Body:
        Fields to update (same as create)

    Response:
        Updated component data with new version number
    """
    service = CustomComponentsService(db)

    try:
        result = service.update_component(
            component_id=component_id,
            user_id=user_id,
            name=request.name,
            html_content=request.html_content,
            css_content=request.css_content,
            js_content=request.js_content,
            description=request.description,
            props_schema=request.props_schema,
            default_props=request.default_props,
            dependencies=request.dependencies,
            is_public=request.is_public,
            change_description=request.change_description,
            agent_id=request.agent_id
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except ComponentSecurityError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.delete("/{component_id}")
async def delete_component(
    component_id: str,
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Delete a component (soft delete).

    Sets is_active=False. Only component owners can delete.

    Path Parameters:
        - component_id: Component to delete

    Query Parameters:
        - user_id: User ID (must be owner)

    Response:
        Deletion confirmation
    """
    service = CustomComponentsService(db)
    result = service.delete_component(
        component_id=component_id,
        user_id=user_id
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# ============================================================================
# Version Control Endpoints
# ============================================================================

@router.get("/{component_id}/versions")
async def get_component_versions(
    component_id: str,
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Get version history for a component.

    Returns all versions with change descriptions.
    Only component owners can view version history.

    Path Parameters:
        - component_id: Component ID

    Query Parameters:
        - user_id: User ID (must be owner)

    Response:
        List of versions with metadata
    """
    service = CustomComponentsService(db)
    result = service.get_component_versions(
        component_id=component_id,
        user_id=user_id
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/{component_id}/rollback")
async def rollback_component(
    component_id: str,
    request: RollbackComponentRequest,
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Rollback component to a previous version.

    Creates a new version with content from the target version.
    Only component owners can rollback.

    Path Parameters:
        - component_id: Component to rollback

    Query Parameters:
        - user_id: User ID (must be owner)

    Request Body:
        - target_version: Version number to restore

    Response:
        Rollback result with new version number
    """
    service = CustomComponentsService(db)
    result = service.rollback_component(
        component_id=component_id,
        target_version=request.target_version,
        user_id=user_id
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# ============================================================================
# Usage Tracking Endpoints
# ============================================================================

@router.post("/{component_id}/record-usage")
async def record_component_usage(
    component_id: str,
    request: RecordUsageRequest,
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Record component usage on a canvas.

    Called when a component is rendered on a canvas.

    Path Parameters:
        - component_id: Component that was used

    Query Parameters:
        - user_id: User who rendered component

    Request Body:
        - canvas_id: Canvas where component was used
        - session_id: Optional canvas session
        - agent_id: Optional agent that rendered component
        - props_passed: Properties passed to component
        - rendering_time_ms: Rendering performance
        - error_message: Any rendering errors
        - governance_check_passed: Governance check result
        - agent_maturity_level: Agent maturity level

    Response:
        Usage record confirmation
    """
    service = CustomComponentsService(db)
    result = service.record_component_usage(
        component_id=component_id,
        canvas_id=request.canvas_id,
        user_id=user_id,
        session_id=request.session_id,
        agent_id=request.agent_id,
        props_passed=request.props_passed,
        rendering_time_ms=request.rendering_time_ms,
        error_message=request.error_message,
        governance_check_passed=request.governance_check_passed,
        agent_maturity_level=request.agent_maturity_level
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/{component_id}/stats")
async def get_component_stats(
    component_id: str,
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Get usage statistics for a component.

    Returns detailed usage metrics including render counts,
    success rates, and top canvases.

    Path Parameters:
        - component_id: Component ID

    Query Parameters:
        - user_id: User ID (must be owner)

    Response:
        Usage statistics
    """
    service = CustomComponentsService(db)
    result = service.get_component_usage_stats(
        component_id=component_id,
        user_id=user_id
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result
