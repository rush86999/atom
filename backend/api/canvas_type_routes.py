"""
Canvas Type API Routes

Provides endpoints for managing and querying canvas types,
including validation, metadata lookup, and governance requirements.
"""
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.canvas_type_registry import CanvasType, MaturityLevel, canvas_type_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/canvas/types", tags=["canvas_types"])


# Response Models
class CanvasTypeInfo(BaseModel):
    """Canvas type information."""
    type: str
    display_name: str
    description: str
    components: List[str]
    layouts: List[str]
    min_maturity: str
    permissions: Dict[str, List[str]]
    examples: List[str]


class CanvasTypeListResponse(BaseModel):
    """Response for canvas type list."""
    canvas_types: List[CanvasTypeInfo]
    total: int


class CanvasTypeValidationRequest(BaseModel):
    """Request for canvas type validation."""
    canvas_type: str
    component: Optional[str] = None
    layout: Optional[str] = None
    maturity_level: Optional[str] = None
    action: Optional[str] = "create"


class CanvasTypeValidationResponse(BaseModel):
    """Response for canvas type validation."""
    valid: bool
    canvas_type: str
    component_valid: Optional[bool] = None
    layout_valid: Optional[bool] = None
    governance_permitted: Optional[bool] = None
    min_maturity: Optional[str] = None
    errors: List[str] = []


# Endpoints

@router.get("", response_model=CanvasTypeListResponse)
async def list_canvas_types():
    """
    List all available canvas types.

    Returns comprehensive information about all registered canvas types,
    including supported components, layouts, and governance requirements.
    """
    try:
        canvas_info_list = canvas_type_registry.get_all_canvas_info()

        return CanvasTypeListResponse(
            canvas_types=[CanvasTypeInfo(**info) for info in canvas_info_list],
            total=len(canvas_info_list)
        )
    except Exception as e:
        logger.error(f"Failed to list canvas types: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{canvas_type}", response_model=CanvasTypeInfo)
async def get_canvas_type(canvas_type: str):
    """
    Get detailed information about a specific canvas type.

    Args:
        canvas_type: Canvas type identifier (generic, docs, email, sheets, etc.)

    Returns:
        CanvasTypeInfo with details about the canvas type
    """
    try:
        canvas_info = canvas_type_registry.get_canvas_info(canvas_type)

        if not canvas_info:
            raise HTTPException(
                status_code=404,
                detail=f"Canvas type '{canvas_type}' not found. "
                       f"Available types: {list(canvas_type_registry.get_all_types().keys())}"
            )

        return CanvasTypeInfo(**canvas_info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get canvas type {canvas_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{canvas_type}/components")
async def get_canvas_components(canvas_type: str):
    """
    Get list of supported components for a canvas type.

    Args:
        canvas_type: Canvas type identifier

    Returns:
        List of component names supported by this canvas type
    """
    try:
        if not canvas_type_registry.validate_canvas_type(canvas_type):
            raise HTTPException(
                status_code=404,
                detail=f"Canvas type '{canvas_type}' not found"
            )

        components = canvas_type_registry.get_components_for_type(canvas_type)

        return {
            "canvas_type": canvas_type,
            "components": components,
            "total": len(components)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get components for {canvas_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{canvas_type}/layouts")
async def get_canvas_layouts(canvas_type: str):
    """
    Get list of available layouts for a canvas type.

    Args:
        canvas_type: Canvas type identifier

    Returns:
        List of layout names supported by this canvas type
    """
    try:
        if not canvas_type_registry.validate_canvas_type(canvas_type):
            raise HTTPException(
                status_code=404,
                detail=f"Canvas type '{canvas_type}' not found"
            )

        layouts = canvas_type_registry.get_layouts_for_type(canvas_type)

        return {
            "canvas_type": canvas_type,
            "layouts": layouts,
            "total": len(layouts)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get layouts for {canvas_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", response_model=CanvasTypeValidationResponse)
async def validate_canvas_type(request: CanvasTypeValidationRequest):
    """
    Validate a canvas type configuration.

    Validates canvas type, component, layout, and governance permissions.
    Useful for validating before creating or presenting a canvas.

    Args:
        request: Validation request with canvas_type, component, layout, etc.

    Returns:
        Validation response with validity status and any errors
    """
    try:
        errors = []

        # Validate canvas type
        canvas_type_valid = canvas_type_registry.validate_canvas_type(request.canvas_type)
        if not canvas_type_valid:
            errors.append(f"Invalid canvas type: {request.canvas_type}")
            return CanvasTypeValidationResponse(
                valid=False,
                canvas_type=request.canvas_type,
                errors=errors
            )

        # Get metadata
        metadata = canvas_type_registry.get_type(request.canvas_type)
        min_maturity = metadata.min_maturity.value if metadata else None

        # Validate component if provided
        component_valid = None
        if request.component:
            component_valid = canvas_type_registry.validate_component(
                request.canvas_type,
                request.component
            )
            if not component_valid:
                errors.append(
                    f"Component '{request.component}' not supported for '{request.canvas_type}' canvas. "
                    f"Available: {metadata.components if metadata else []}"
                )

        # Validate layout if provided
        layout_valid = None
        if request.layout:
            layout_valid = canvas_type_registry.validate_layout(
                request.canvas_type,
                request.layout
            )
            if not layout_valid:
                errors.append(
                    f"Layout '{request.layout}' not supported for '{request.canvas_type}' canvas. "
                    f"Available: {metadata.layouts if metadata else []}"
                )

        # Validate governance if maturity level and action provided
        governance_permitted = None
        if request.maturity_level and request.action:
            governance_permitted = canvas_type_registry.check_governance_permission(
                request.canvas_type,
                request.maturity_level,
                request.action
            )
            if not governance_permitted:
                errors.append(
                    f"Maturity level '{request.maturity_level}' not permitted for "
                    f"action '{request.action}' on '{request.canvas_type}' canvas"
                )

        # Overall validity
        valid = (
            canvas_type_valid
            and (component_valid is None or component_valid)
            and (layout_valid is None or layout_valid)
            and (governance_permitted is None or governance_permitted)
        )

        return CanvasTypeValidationResponse(
            valid=valid,
            canvas_type=request.canvas_type,
            component_valid=component_valid,
            layout_valid=layout_valid,
            governance_permitted=governance_permitted,
            min_maturity=min_maturity,
            errors=errors
        )
    except Exception as e:
        logger.error(f"Failed to validate canvas type: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{canvas_type}/permissions/{maturity_level}")
async def get_canvas_permissions(canvas_type: str, maturity_level: str):
    """
    Get permissions for a canvas type at a specific maturity level.

    Args:
        canvas_type: Canvas type identifier
        maturity_level: Agent maturity level (student, intern, supervised, autonomous)

    Returns:
        List of permitted actions for this maturity level
    """
    try:
        # Validate canvas type
        if not canvas_type_registry.validate_canvas_type(canvas_type):
            raise HTTPException(
                status_code=404,
                detail=f"Canvas type '{canvas_type}' not found"
            )

        # Validate maturity level
        try:
            MaturityLevel(maturity_level)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid maturity level: {maturity_level}. "
                       f"Must be one of: [student, intern, supervised, autonomous]"
            )

        # Get metadata
        metadata = canvas_type_registry.get_type(canvas_type)
        if not metadata:
            raise HTTPException(
                status_code=404,
                detail=f"Canvas type '{canvas_type}' not found"
            )

        # Get permissions for this maturity level
        permissions = metadata.permissions.get(maturity_level, [])

        return {
            "canvas_type": canvas_type,
            "maturity_level": maturity_level,
            "permissions": permissions,
            "min_maturity": metadata.min_maturity.value,
            "sufficient_maturity": maturity_level >= metadata.min_maturity.value
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get permissions for {canvas_type} at {maturity_level}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{canvas_type}/examples")
async def get_canvas_examples(canvas_type: str):
    """
    Get example use cases for a canvas type.

    Args:
        canvas_type: Canvas type identifier

    Returns:
        List of example use cases
    """
    try:
        canvas_info = canvas_type_registry.get_canvas_info(canvas_type)

        if not canvas_info:
            raise HTTPException(
                status_code=404,
                detail=f"Canvas type '{canvas_type}' not found"
            )

        return {
            "canvas_type": canvas_type,
            "display_name": canvas_info["display_name"],
            "examples": canvas_info["examples"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get examples for {canvas_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
