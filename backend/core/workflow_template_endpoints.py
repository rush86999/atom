"""
Workflow Template API Endpoints
REST API for workflow template management and marketplace
"""

from datetime import datetime
import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from .workflow_template_system import (
    TemplateCategory,
    TemplateComplexity,
    TemplateParameter,
    TemplateStep,
    WorkflowTemplate,
    WorkflowTemplateManager,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize template manager
template_manager = WorkflowTemplateManager()

# Request/Response Models
class CreateTemplateRequest(BaseModel):
    name: str
    description: str
    category: TemplateCategory
    complexity: TemplateComplexity
    tags: List[str] = []
    inputs: List[Dict[str, Any]] = []
    steps: List[Dict[str, Any]] = []
    output_schema: Dict[str, Any] = {}
    prerequisites: List[str] = []
    dependencies: List[str] = []
    permissions: List[str] = []
    is_public: bool = False

class UpdateTemplateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[TemplateCategory] = None
    complexity: Optional[TemplateComplexity] = None
    tags: Optional[List[str]] = None
    inputs: Optional[List[Dict[str, Any]]] = None
    steps: Optional[List[Dict[str, Any]]] = None
    output_schema: Optional[Dict[str, Any]] = None
    prerequisites: Optional[List[str]] = None
    dependencies: Optional[List[str]] = None
    permissions: Optional[List[str]] = None
    is_public: Optional[bool] = None

class CreateWorkflowFromTemplateRequest(BaseModel):
    template_id: str
    workflow_name: str
    parameters: Dict[str, Any] = {}
    customizations: Dict[str, Any] = {}

class TemplateSearchRequest(BaseModel):
    query: str = ""
    category: Optional[TemplateCategory] = None
    complexity: Optional[TemplateComplexity] = None
    tags: Optional[List[str]] = None
    author: Optional[str] = None
    is_public: Optional[bool] = None
    limit: int = Field(default=20, ge=1, le=100)

class TemplateResponse(BaseModel):
    template_id: str
    name: str
    description: str
    category: str
    complexity: str
    tags: List[str]
    version: str
    author: str
    created_at: datetime
    updated_at: datetime
    inputs: List[Dict[str, Any]]
    steps: List[Dict[str, Any]]
    output_schema: Dict[str, Any]
    usage_count: int
    rating: float
    review_count: int
    estimated_total_duration: int
    prerequisites: List[str]
    dependencies: List[str]
    permissions: List[str]
    is_public: bool
    is_featured: bool

class WorkflowCreationResponse(BaseModel):
    workflow_id: str
    workflow_definition: Dict[str, Any]
    template_used: str
    template_name: str
    parameters_applied: Dict[str, Any]

# Helper Functions
def serialize_template(template: WorkflowTemplate) -> Dict[str, Any]:
    """Convert template to serializable dict"""
    return {
        "template_id": template.template_id,
        "name": template.name,
        "description": template.description,
        "category": template.category.value,
        "complexity": template.complexity.value,
        "tags": template.tags,
        "version": template.version,
        "author": template.author,
        "created_at": template.created_at.isoformat(),
        "updated_at": template.updated_at.isoformat(),
        "inputs": [param.dict() for param in template.inputs],
        "steps": [step.dict() for step in template.steps],
        "output_schema": template.output_schema,
        "usage_count": template.usage_count,
        "rating": template.rating,
        "review_count": template.review_count,
        "estimated_total_duration": template.estimated_total_duration,
        "prerequisites": template.prerequisites,
        "dependencies": template.dependencies,
        "permissions": template.permissions,
        "is_public": template.is_public,
        "is_featured": template.is_featured,
        "license": template.license
    }

# Template Management Endpoints
@router.post("/templates", response_model=TemplateResponse)
async def create_template(request: CreateTemplateRequest):
    """Create a new workflow template"""
    try:
        template_data = request.dict()

        # Add system fields
        template_data.update({
            "author": "Current User",  # Would get from auth context
            "license": "MIT"
        })

        template = template_manager.create_template(template_data)

        return serialize_template(template)

    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/templates", response_model=List[TemplateResponse])
async def list_templates(
    category: Optional[TemplateCategory] = None,
    complexity: Optional[TemplateComplexity] = None,
    tags: Optional[List[str]] = Query(None),
    author: Optional[str] = None,
    is_public: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """List templates with filtering"""
    try:
        templates = template_manager.list_templates(
            category=category,
            complexity=complexity,
            tags=tags,
            author=author,
            is_public=is_public,
            limit=limit
        )

        # Apply offset
        templates = templates[offset:offset + limit]

        return [serialize_template(template) for template in templates]

    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates/search", response_model=List[TemplateResponse])
async def search_templates(
    query: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Search templates by text query"""
    try:
        templates = template_manager.search_templates(query, limit)
        return [serialize_template(template) for template in templates]

    except Exception as e:
        logger.error(f"Failed to search templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str):
    """Get template details by ID"""
    try:
        template = template_manager.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        return serialize_template(template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(template_id: str, request: UpdateTemplateRequest):
    """Update an existing template"""
    try:
        # Filter out None values
        updates = {k: v for k, v in request.dict().items() if v is not None}

        template = template_manager.update_template(template_id, updates)
        return serialize_template(template)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update template {template_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    """Delete a template"""
    try:
        success = template_manager.delete_template(template_id)
        if not success:
            raise HTTPException(status_code=404, detail="Template not found")

        return {"status": "success", "message": "Template deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Workflow Creation from Templates
@router.post("/templates/{template_id}/create-workflow", response_model=WorkflowCreationResponse)
async def create_workflow_from_template(
    template_id: str,
    request: CreateWorkflowFromTemplateRequest
):
    """Create a new workflow from a template"""
    try:
        result = template_manager.create_workflow_from_template(
            template_id=template_id,
            workflow_name=request.workflow_name,
            template_parameters=request.parameters,
            customizations=request.customizations
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create workflow from template {template_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Template Rating and Analytics
@router.post("/templates/{template_id}/rate")
async def rate_template(template_id: str, rating: Dict[str, float]):
    """Rate a template"""
    try:
        if "rating" not in rating:
            raise HTTPException(status_code=400, detail="Rating value required")

        rating_value = rating["rating"]
        if not (1.0 <= rating_value <= 5.0):
            raise HTTPException(status_code=400, detail="Rating must be between 1.0 and 5.0")

        success = template_manager.rate_template(template_id, rating_value)
        if not success:
            raise HTTPException(status_code=404, detail="Template not found")

        return {"status": "success", "message": "Template rated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rate template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates/statistics")
async def get_template_statistics():
    """Get template marketplace statistics"""
    try:
        stats = template_manager.get_template_statistics()
        return stats

    except Exception as e:
        logger.error(f"Failed to get template statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Template Import/Export
@router.get("/templates/{template_id}/export")
async def export_template(template_id: str):
    """Export template as shareable JSON"""
    try:
        export_data = template_manager.export_template(template_id)

        return {
            "status": "success",
            "template_data": export_data,
            "exported_at": datetime.now().isoformat()
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to export template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/templates/import")
async def import_template(
    template_data: Dict[str, Any],
    overwrite: bool = False
):
    """Import template from JSON"""
    try:
        template = template_manager.import_template(template_data, overwrite)
        return {
            "status": "success",
            "template": serialize_template(template),
            "message": "Template imported successfully"
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to import template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/templates/import-file")
async def import_template_from_file(
    file: UploadFile = File(...),
    overwrite: bool = False
):
    """Import template from uploaded file"""
    try:
        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="Only JSON files are supported")

        content = await file.read()
        template_data = json.loads(content.decode())

        template = template_manager.import_template(template_data, overwrite)
        return {
            "status": "success",
            "template": serialize_template(template),
            "message": f"Template imported successfully from {file.filename}"
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file format")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to import template from file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Template Categories and Metadata
@router.get("/templates/categories")
async def get_template_categories():
    """Get available template categories"""
    return {
        "categories": [
            {
                "value": category.value,
                "label": category.value.replace("_", " ").title(),
                "description": f"Templates for {category.value.replace('_', ' ')}"
            }
            for category in TemplateCategory
        ]
    }

@router.get("/templates/complexity-levels")
async def get_complexity_levels():
    """Get available complexity levels"""
    return {
        "complexity_levels": [
            {
                "value": level.value,
                "label": level.value.title(),
                "description": f"{level.value.title()} difficulty templates"
            }
            for level in TemplateComplexity
        ]
    }

@router.get("/templates/{template_id}/usage")
async def get_template_usage(template_id: str):
    """Get template usage information"""
    try:
        template = template_manager.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        return {
            "template_id": template.template_id,
            "template_name": template.name,
            "usage_count": template.usage_count,
            "rating": template.rating,
            "review_count": template.review_count,
            "last_used": template.updated_at.isoformat(),
            "estimated_duration": template.estimated_total_duration
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get template usage for {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Template Validation
@router.post("/templates/validate")
async def validate_template(template_data: Dict[str, Any]):
    """Validate template structure without creating it"""
    try:
        # Attempt to create WorkflowTemplate instance for validation
        template = WorkflowTemplate(**template_data)

        return {
            "status": "success",
            "valid": True,
            "template_id": template.template_id,
            "estimated_duration": template.estimated_total_duration,
            "validation_errors": []
        }

    except Exception as e:
        return {
            "status": "error",
            "valid": False,
            "validation_errors": [str(e)]
        }

# Template Marketplace Features
@router.get("/templates/featured", response_model=List[TemplateResponse])
async def get_featured_templates(limit: int = Query(10, ge=1, le=50)):
    """Get featured templates"""
    try:
        all_templates = list(template_manager.templates.values())
        featured = [t for t in all_templates if t.is_featured]

        # Sort by rating and usage
        featured.sort(key=lambda t: (t.rating, t.usage_count), reverse=True)

        return [serialize_template(template) for template in featured[:limit]]

    except Exception as e:
        logger.error(f"Failed to get featured templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates/popular", response_model=List[TemplateResponse])
async def get_popular_templates(limit: int = Query(10, ge=1, le=50)):
    """Get most popular templates by usage"""
    try:
        all_templates = list(template_manager.templates.values())
        popular = sorted(all_templates, key=lambda t: t.usage_count, reverse=True)

        return [serialize_template(template) for template in popular[:limit]]

    except Exception as e:
        logger.error(f"Failed to get popular templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates/top-rated", response_model=List[TemplateResponse])
async def get_top_rated_templates(limit: int = Query(10, ge=1, le=50)):
    """Get highest rated templates"""
    try:
        all_templates = list(template_manager.templates.values())
        rated = [t for t in all_templates if t.review_count > 0]
        top_rated = sorted(rated, key=lambda t: t.rating, reverse=True)

        return [serialize_template(template) for template in top_rated[:limit]]

    except Exception as e:
        logger.error(f"Failed to get top rated templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates/recent", response_model=List[TemplateResponse])
async def get_recent_templates(limit: int = Query(10, ge=1, le=50)):
    """Get recently created/updated templates"""
    try:
        all_templates = list(template_manager.templates.values())
        recent = sorted(all_templates, key=lambda t: t.updated_at, reverse=True)

        return [serialize_template(template) for template in recent[:limit]]

    except Exception as e:
        logger.error(f"Failed to get recent templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))