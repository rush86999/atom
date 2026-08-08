"""
User Workflow Templates API
Enhanced endpoints for user-created workflow templates with database persistence
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid
from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.auth import get_current_user, User
from core.database import get_db
from core.models import TemplateExecution, TemplateVersion, User, UserRole, WorkflowTemplate

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/user/templates", tags=["user-templates"])


# Request/Response Models

class TemplateParameterModel(BaseModel):
    """Template parameter definition"""
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    type: str = "string"
    required: bool = True
    default_value: Any = None
    options: List[str] = []
    validation_rules: Dict[str, Any] = {}
    help_text: Optional[str] = None
    example_value: Optional[Any] = None


class TemplateStepModel(BaseModel):
    """Template step definition"""
    id: str
    name: str
    description: str = ""
    step_type: str = "action"
    service: Optional[str] = None
    action: Optional[str] = None
    parameters: List[TemplateParameterModel] = []
    condition: Optional[str] = None
    depends_on: List[str] = []
    estimated_duration: int = 60
    is_optional: bool = False


class CreateTemplateRequest(BaseModel):
    """Request to create a new template"""
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=1000)
    category: str = Field(..., description="automation, data_processing, ai_ml, etc.")
    complexity: str = Field(..., description="beginner, intermediate, advanced, expert")
    tags: List[str] = []
    template_json: Dict[str, Any] = Field(..., description="Full workflow definition")
    inputs_schema: List[TemplateParameterModel] = []
    steps_schema: List[TemplateStepModel] = []
    output_schema: Dict[str, Any] = {}
    estimated_duration_seconds: int = 0
    prerequisites: List[str] = []
    dependencies: List[str] = []
    permissions: List[str] = []
    license: str = "MIT"
    is_public: bool = False


class UpdateTemplateRequest(BaseModel):
    """Request to update a template"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1, max_length=1000)
    category: Optional[str] = None
    complexity: Optional[str] = None
    tags: Optional[List[str]] = None
    template_json: Optional[Dict[str, Any]] = None
    inputs_schema: Optional[List[TemplateParameterModel]] = None
    steps_schema: Optional[List[TemplateStepModel]] = None
    output_schema: Optional[Dict[str, Any]] = None
    estimated_duration_seconds: Optional[int] = None
    prerequisites: Optional[List[str]] = None
    dependencies: Optional[List[str]] = None
    permissions: Optional[List[str]] = None
    is_public: Optional[bool] = None
    change_description: Optional[str] = None


class TemplateResponse(BaseModel):
    """Template response"""
    id: str
    template_id: str
    name: str
    description: str
    category: str
    complexity: str
    tags: List[str]
    author_id: Optional[str]
    is_public: bool
    is_featured: bool
    template_json: Dict[str, Any]
    inputs_schema: List[TemplateParameterModel]
    steps_schema: List[TemplateStepModel]
    output_schema: Dict[str, Any]
    usage_count: int
    rating: float
    rating_count: int
    version: str
    parent_template_id: Optional[str]
    estimated_duration_seconds: int
    prerequisites: List[str]
    dependencies: List[str]
    permissions: List[str]
    license: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PublishTemplateRequest(BaseModel):
    """Request to publish a template"""
    visibility: str = Field(..., description="public, private, featured")
    featured: bool = False


class TemplateStatisticsResponse(BaseModel):
    """User's template statistics"""
    total_templates: int
    public_templates: int
    private_templates: int
    total_usage: int
    average_rating: float
    most_used_template: Optional[Dict[str, Any]]
    recent_templates: List[TemplateResponse]


class DuplicateTemplateRequest(BaseModel):
    """Request to duplicate/fork a template"""
    name: str
    description: Optional[str] = None


# ============================================================================
# Response mapping — the WorkflowTemplate model is leaner than TemplateResponse:
# map real columns to the API contract with safe defaults (Round 42 repair;
# previously the raw ORM object was returned and serialization 500'd on the
# missing template_id/complexity/tags/is_featured/template_json/... fields).
# ============================================================================

def _template_to_response(template) -> TemplateResponse:
    return TemplateResponse(
        id=template.id,
        template_id=template.id,
        name=template.name,
        description=template.description or "",
        category=template.category,
        complexity="intermediate",
        tags=[],
        author_id=template.author_id,
        is_public=template.is_public,
        is_featured=template.is_approved,
        template_json={"steps": template.steps or []},
        inputs_schema=[],
        steps_schema=[],
        output_schema={},
        usage_count=template.usage_count,
        rating=template.rating,
        rating_count=template.rating_count,
        version=template.version,
        parent_template_id=None,
        estimated_duration_seconds=0,
        prerequisites=[],
        dependencies=[],
        permissions=[],
        license="MIT",
        created_at=template.created_at,
        updated_at=template.updated_at
    )


# API Endpoints

@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_user_template(
    request: CreateTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new user-defined workflow template

    Creates a database-backed template with full metadata, versioning,
    and ownership tracking.
    """
    try:
        # Generate unique template_id
        template_id = f"template_{uuid.uuid4().hex[:12]}"

        # Create template record — ownership always comes from the token;
        # constructor uses the REAL model columns (previously phantom kwargs
        # like template_id/complexity/tags raised TypeError on every create).
        # steps_schema/inputs_schema are pydantic models — dump them to plain
        # dicts (the JSON columns cannot serialize pydantic objects).
        steps = (
            [s.model_dump() for s in request.steps_schema]
            if request.steps_schema
            else (request.template_json or [])
        )
        input_schema = (
            [s.model_dump() for s in request.inputs_schema]
            if request.inputs_schema
            else None
        )
        template = WorkflowTemplate(
            id=template_id,
            name=request.name,
            description=request.description,
            category=request.category,
            icon="default",
            author_id=current_user.id,
            steps=steps,
            input_schema=input_schema,
            is_public=request.is_public,
            version="1.0.0",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        db.add(template)
        db.commit()
        db.refresh(template)

        # Create initial version record (real TemplateVersion columns)
        version = TemplateVersion(
            template_id=template_id,
            version_number=1,
            name=request.name,
            description=request.description,
            steps=[s.model_dump() for s in request.steps_schema] if request.steps_schema else None,
            created_by=current_user.id,
            change_summary="Initial version",
            created_at=datetime.now()
        )
        db.add(version)
        db.commit()

        logger.info(f"Created template {template_id} by user {current_user.id}")
        return _template_to_response(template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        db.rollback()
        raise router.internal_error("Internal error")


@router.get("", response_model=List[TemplateResponse])
async def list_user_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    complexity: Optional[str] = Query(None, description="Filter by complexity"),
    is_public: Optional[bool] = Query(None, description="Filter by visibility"),
    featured_only: bool = Query(False, description="Only featured templates"),
    search: Optional[str] = Query(None, description="Search in name/description"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List workflow templates with filtering

    Always scoped to the authenticated user's own templates plus public ones;
    the client-supplied user_id filter was removed (cross-user private reads).
    """
    try:
        query = db.query(WorkflowTemplate)

        # Ownership scope is ALWAYS applied — own templates + public ones.
        # Previously a missing user_id param returned ALL templates (incl.
        # private) and a supplied user_id read any user's private templates.
        query = query.filter(
            (WorkflowTemplate.author_id == current_user.id) |
            (WorkflowTemplate.is_public == True)
        )

        if category:
            query = query.filter(WorkflowTemplate.category == category)

        # complexity/tags/is_public filters were dropped — the model has no
        # such columns (they raised AttributeError since the Hive model port
        # in 36ed0f548). "featured" maps to is_approved.
        if featured_only:
            query = query.filter(WorkflowTemplate.is_approved == True)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (WorkflowTemplate.name.ilike(search_term)) |
                (WorkflowTemplate.description.ilike(search_term))
            )

        # Order by usage and date
        query = query.order_by(
            WorkflowTemplate.is_approved.desc(),
            WorkflowTemplate.usage_count.desc(),
            WorkflowTemplate.created_at.desc()
        )

        # Apply pagination
        templates = query.offset(offset).limit(limit).all()

        return [_template_to_response(t) for t in templates]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise router.internal_error("Internal error")


@router.get("/stats", response_model=TemplateStatisticsResponse)
async def get_user_template_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get template usage statistics for the current user

    Returns aggregate statistics about user's templates including
    total count, usage, ratings, and most popular templates.
    """
    try:
        # Get all user's templates (identity from token, never query param)
        templates = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.author_id == current_user.id
        ).all()

        total_templates = len(templates)
        public_templates = sum(1 for t in templates if t.is_public)
        private_templates = total_templates - public_templates
        total_usage = sum(t.usage_count for t in templates)

        # Calculate average rating
        rated_templates = [t for t in templates if t.rating_count > 0]
        average_rating = (
            sum(t.rating for t in rated_templates) / len(rated_templates)
            if rated_templates else 0.0
        )

        # Find most used template
        most_used = max(templates, key=lambda t: t.usage_count, default=None)
        most_used_template = None
        if most_used and most_used.usage_count > 0:
            most_used_template = {
                "template_id": most_used.id,
                "name": most_used.name,
                "usage_count": most_used.usage_count,
                "rating": most_used.rating
            }

        # Get recent templates (last 5) — mapped to the API contract; raw ORM
        # objects fail TemplateStatisticsResponse validation (missing
        # template_id/complexity/tags/... fields).
        recent_templates = [
            _template_to_response(t)
            for t in sorted(
                templates,
                key=lambda t: t.created_at,
                reverse=True
            )[:5]
        ]

        return TemplateStatisticsResponse(
            total_templates=total_templates,
            public_templates=public_templates,
            private_templates=private_templates,
            total_usage=total_usage,
            average_rating=round(average_rating, 2),
            most_used_template=most_used_template,
            recent_templates=recent_templates
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template statistics: {e}")
        raise router.internal_error("Internal error")


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific template by ID

    Returns full template details including schema and metadata.
    """
    try:
        template = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == template_id
        ).first()

        if not template:
            raise router.not_found_error("Template", template_id)

        return _template_to_response(template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template {template_id}: {e}")
        raise router.internal_error("Internal error")


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    request: UpdateTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update an existing template

    Updates template metadata and creates a new version entry.
    Only the template owner can update.
    """
    try:
        template = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == template_id
        ).first()

        if not template:
            raise router.not_found_error("Template", template_id)

        # Check ownership against the AUTHENTICATED user (previously the
        # client-supplied user_id query param let anyone pass the victim's
        # id to modify their templates).
        if template.author_id != current_user.id:
            raise router.permission_denied_error(
                action="update_template",
                resource="WorkflowTemplate",
                details={"template_id": template_id, "user_id": current_user.id}
            )

        # MASS ASSIGNMENT FIX: only fields that exist on the real model may be
        # set (complexity/tags/template_json/... were dropped in the Hive model
        # port 36ed0f548 — setattr on them raises AttributeError).
        ALLOWED_UPDATE_FIELDS = {"name", "description", "category", "is_public"}

        # Update fields
        update_data = request.dict(exclude_unset=True, exclude={'change_description'})
        for field, value in update_data.items():
            if field not in ALLOWED_UPDATE_FIELDS:
                logger.info(f"Skipping update of unsupported field '{field}' (not on model)")
                continue
            if value is not None:
                setattr(template, field, value)

        template.updated_at = datetime.now()

        # Create version entry if there are substantive changes (real
        # TemplateVersion columns — version_number/created_by/change_summary).
        if request.change_description or any(key in request.dict() for key in
                                              ['template_json', 'steps_schema', 'inputs_schema']):
            # Increment version (simplified semver)
            current_version = template.version.split('.')
            current_version[2] = str(int(current_version[2]) + 1)
            new_version = ".".join(current_version)

            template.version = new_version

            version = TemplateVersion(
                template_id=template_id,
                version_number=int(current_version[2]),
                name=template.name,
                description=template.description,
                steps=template.steps or None,
                created_by=current_user.id,
                change_summary=request.change_description or "Updated template",
                created_at=datetime.now()
            )
            db.add(version)

        db.commit()
        db.refresh(template)

        logger.info(f"Updated template {template_id} to version {template.version}")
        return _template_to_response(template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating template {template_id}: {e}")
        db.rollback()
        raise router.internal_error("Internal error")


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a template

    Permanently deletes a template. Only the owner can delete.
    """
    try:
        template = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == template_id
        ).first()

        if not template:
            raise router.not_found_error("Template", template_id)

        # Check ownership against the AUTHENTICATED user
        if template.author_id != current_user.id:
            raise router.permission_denied_error(
                action="delete_template",
                resource="WorkflowTemplate",
                details={"template_id": template_id, "user_id": current_user.id}
            )

        # Delete related records
        db.query(TemplateVersion).filter(
            TemplateVersion.template_id == template_id
        ).delete()

        db.query(TemplateExecution).filter(
            TemplateExecution.template_id == template_id
        ).delete()

        # Delete template
        db.delete(template)
        db.commit()

        logger.info(f"Deleted template {template_id}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template {template_id}: {e}")
        db.rollback()
        raise router.internal_error("Internal error")


@router.post("/{template_id}/publish", response_model=TemplateResponse)
async def publish_template(
    template_id: str,
    request: PublishTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Publish a template to the marketplace

    Changes template visibility and can mark as featured (admin only).
    """
    try:
        template = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == template_id
        ).first()

        if not template:
            raise router.not_found_error("Template", template_id)

        # Check ownership against the AUTHENTICATED user
        if template.author_id != current_user.id:
            raise router.permission_denied_error(
                action="publish_template",
                resource="WorkflowTemplate",
                details={"template_id": template_id, "user_id": current_user.id}
            )

        # Update visibility
        if request.visibility == "public":
            template.is_public = True
        elif request.visibility == "private":
            template.is_public = False

        # Only admins can set featured (maps to is_approved on the real model)
        if request.featured:
            # Check if user is an admin (identity from token)
            user = db.query(User).filter(User.id == current_user.id).first()
            if not user or user.role not in [UserRole.SUPER_ADMIN, UserRole.WORKSPACE_ADMIN]:
                raise router.permission_denied_error(
                    action="feature_template",
                    resource="Template",
                    details={"template_id": template_id, "required_role": "SUPER_ADMIN or WORKSPACE_ADMIN"}
                )
            template.is_approved = True

        template.updated_at = datetime.now()
        db.commit()
        db.refresh(template)

        logger.info(f"Published template {template_id} as {request.visibility}")
        return _template_to_response(template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing template {template_id}: {e}")
        db.rollback()
        raise router.internal_error("Internal error")


@router.post("/{template_id}/duplicate", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_template(
    template_id: str,
    request: DuplicateTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Duplicate/fork an existing template

    Creates a copy of a template with a new owner.
    Useful for template customization.
    """
    try:
        original = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == template_id
        ).first()

        if not original:
            raise router.not_found_error("Template", template_id)

        # Check if original is public or user owns it (identity from token)
        if not original.is_public and original.author_id != current_user.id:
            raise router.permission_denied_error(
                action="duplicate_template",
                resource="Template",
                details={"template_id": template_id, "user_id": current_user.id}
            )

        # Create duplicate (real model columns)
        new_template_id = f"template_{uuid.uuid4().hex[:12]}"
        duplicate = WorkflowTemplate(
            id=new_template_id,
            name=request.name,
            description=request.description or original.description,
            category=original.category,
            icon=original.icon,
            author_id=current_user.id,
            steps=original.steps or [],
            input_schema=original.input_schema,
            is_public=False,  # Duplicates start as private
            version="1.0.0",  # Reset version for duplicate
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        db.add(duplicate)
        db.commit()
        db.refresh(duplicate)

        logger.info(f"Duplicated template {template_id} as {new_template_id} for user {current_user.id}")
        return _template_to_response(duplicate)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error duplicating template {template_id}: {e}")
        db.rollback()
        raise router.internal_error("Internal error")


@router.get("/{template_id}/versions", response_model=List[Dict[str, Any]])
async def get_template_versions(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get version history for a template

    Returns all versions with change descriptions and metadata.
    """
    try:
        # Verify template exists
        template = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == template_id
        ).first()

        if not template:
            raise router.not_found_error("Template", template_id)

        # Get versions (real TemplateVersion columns)
        versions = db.query(TemplateVersion).filter(
            TemplateVersion.template_id == template_id
        ).order_by(TemplateVersion.created_at.desc()).all()

        return [
            {
                "id": v.id,
                "version": str(v.version_number),
                "change_description": v.change_summary,
                "changed_by_id": v.created_by,
                "created_at": v.created_at.isoformat()
            }
            for v in versions
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting versions for template {template_id}: {e}")
        raise router.internal_error("Internal error")


@router.post("/{template_id}/rate")
async def rate_template(
    template_id: str,
    rating: int = Query(..., ge=1, le=5, description="Rating from 1-5"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Rate a template

    Submits a user rating for a template.
    """
    try:
        template = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == template_id
        ).first()

        if not template:
            raise router.not_found_error("Template", template_id)

        # Update rating — the lean model has no rating_sum column; recompute
        # the running average from rating/rating_count.
        template.rating = (
            (template.rating * template.rating_count) + rating
        ) / (template.rating_count + 1)
        template.rating_count += 1
        template.updated_at = datetime.now()

        db.commit()

        logger.info(f"Rated template {template_id} with {rating} stars")
        return {
            "message": "Rating submitted successfully",
            "new_rating": template.rating,
            "rating_count": template.rating_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rating template {template_id}: {e}")
        db.rollback()
        raise router.internal_error("Internal error")
