"""
User Workflow Templates API
Enhanced endpoints for user-created workflow templates with database persistence
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
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

    class Config:
        from_attributes = True


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


# API Endpoints

@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_user_template(
    request: CreateTemplateRequest,
    user_id: str = Query(..., description="User ID creating the template"),
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

        # Create template record
        template = WorkflowTemplate(
            template_id=template_id,
            name=request.name,
            description=request.description,
            category=request.category,
            complexity=request.complexity,
            tags=request.tags,
            author_id=user_id,
            is_public=request.is_public,
            is_featured=False,
            template_json=request.template_json,
            inputs_schema=[p.dict() for p in request.inputs_schema],
            steps_schema=[s.dict() for s in request.steps_schema],
            output_schema=request.output_schema,
            version="1.0.0",
            estimated_duration_seconds=request.estimated_duration_seconds,
            prerequisites=request.prerequisites,
            dependencies=request.dependencies,
            permissions=request.permissions,
            license=request.license,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        db.add(template)
        db.commit()
        db.refresh(template)

        # Create initial version record
        version = TemplateVersion(
            template_id=template_id,
            version="1.0.0",
            template_snapshot=request.template_json,
            change_description="Initial version",
            changed_by_id=user_id,
            created_at=datetime.now()
        )
        db.add(version)
        db.commit()

        logger.info(f"Created template {template_id} by user {user_id}")
        return template

    except Exception as e:
        logger.error(f"Error creating template: {e}")
        db.rollback()
        raise router.internal_error(str(e))


@router.get("", response_model=List[TemplateResponse])
async def list_user_templates(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    complexity: Optional[str] = Query(None, description="Filter by complexity"),
    is_public: Optional[bool] = Query(None, description="Filter by visibility"),
    featured_only: bool = Query(False, description="Only featured templates"),
    search: Optional[str] = Query(None, description="Search in name/description"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    List workflow templates with filtering

    Returns templates based on user ownership, visibility, and other filters.
    """
    try:
        query = db.query(WorkflowTemplate)

        # Apply filters
        if user_id:
            query = query.filter(
                (WorkflowTemplate.author_id == user_id) |
                (WorkflowTemplate.is_public == True)
            )

        if category:
            query = query.filter(WorkflowTemplate.category == category)

        if complexity:
            query = query.filter(WorkflowTemplate.complexity == complexity)

        if is_public is not None:
            query = query.filter(WorkflowTemplate.is_public == is_public)

        if featured_only:
            query = query.filter(WorkflowTemplate.is_featured == True)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (WorkflowTemplate.name.ilike(search_term)) |
                (WorkflowTemplate.description.ilike(search_term))
            )

        # Order by usage and date
        query = query.order_by(
            WorkflowTemplate.is_featured.desc(),
            WorkflowTemplate.usage_count.desc(),
            WorkflowTemplate.created_at.desc()
        )

        # Apply pagination
        templates = query.offset(offset).limit(limit).all()

        return templates

    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise router.internal_error(str(e))


@router.get("/stats", response_model=TemplateStatisticsResponse)
async def get_user_template_statistics(
    user_id: str = Query(..., description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Get template usage statistics for a user

    Returns aggregate statistics about user's templates including
    total count, usage, ratings, and most popular templates.
    """
    try:
        # Get all user's templates
        templates = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.author_id == user_id
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
                "template_id": most_used.template_id,
                "name": most_used.name,
                "usage_count": most_used.usage_count,
                "rating": most_used.rating
            }

        # Get recent templates (last 5)
        recent_templates = sorted(
            templates,
            key=lambda t: t.created_at,
            reverse=True
        )[:5]

        return TemplateStatisticsResponse(
            total_templates=total_templates,
            public_templates=public_templates,
            private_templates=private_templates,
            total_usage=total_usage,
            average_rating=round(average_rating, 2),
            most_used_template=most_used_template,
            recent_templates=recent_templates
        )

    except Exception as e:
        logger.error(f"Error getting template statistics: {e}")
        raise router.internal_error(str(e))


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific template by ID

    Returns full template details including schema and metadata.
    """
    try:
        template = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.template_id == template_id
        ).first()

        if not template:
            raise router.not_found_error("Template", template_id)

        return template

    except Exception as e:
        logger.error(f"Error getting template {template_id}: {e}")
        raise router.internal_error(str(e))


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    request: UpdateTemplateRequest,
    user_id: str = Query(..., description="User ID making the update"),
    db: Session = Depends(get_db)
):
    """
    Update an existing template

    Updates template metadata and creates a new version entry.
    Only the template owner can update.
    """
    try:
        template = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.template_id == template_id
        ).first()

        if not template:
            raise router.not_found_error("Template", template_id)

        # Check ownership
        if template.author_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to update this template"
            )

        # Update fields
        update_data = request.dict(exclude_unset=True, exclude={'change_description'})
        for field, value in update_data.items():
            if value is not None:
                if field in ['inputs_schema', 'steps_schema']:
                    setattr(template, field, [item.dict() if hasattr(item, 'dict') else item for item in value])
                else:
                    setattr(template, field, value)

        template.updated_at = datetime.now()

        # Create version entry if there are substantive changes
        if request.change_description or any(key in request.dict() for key in
                                              ['template_json', 'steps_schema', 'inputs_schema']):
            # Increment version (simplified semver)
            current_version = template.version.split('.')
            current_version[2] = str(int(current_version[2]) + 1)
            new_version = ".".join(current_version)

            template.version = new_version

            version = TemplateVersion(
                template_id=template_id,
                version=new_version,
                template_snapshot=template.template_json,
                change_description=request.change_description or "Updated template",
                changed_by_id=user_id,
                created_at=datetime.now()
            )
            db.add(version)

        db.commit()
        db.refresh(template)

        logger.info(f"Updated template {template_id} to version {template.version}")
        return template

    except Exception as e:
        logger.error(f"Error updating template {template_id}: {e}")
        db.rollback()
        raise router.internal_error(str(e))


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    user_id: str = Query(..., description="User ID requesting deletion"),
    db: Session = Depends(get_db)
):
    """
    Delete a template

    Permanently deletes a template. Only the owner can delete.
    """
    try:
        template = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.template_id == template_id
        ).first()

        if not template:
            raise router.not_found_error("Template", template_id)

        # Check ownership
        if template.author_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to delete this template"
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

    except Exception as e:
        logger.error(f"Error deleting template {template_id}: {e}")
        db.rollback()
        raise router.internal_error(str(e))


@router.post("/{template_id}/publish", response_model=TemplateResponse)
async def publish_template(
    template_id: str,
    request: PublishTemplateRequest,
    user_id: str = Query(..., description="User ID publishing the template"),
    db: Session = Depends(get_db)
):
    """
    Publish a template to the marketplace

    Changes template visibility and can mark as featured (admin only).
    """
    try:
        template = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.template_id == template_id
        ).first()

        if not template:
            raise router.not_found_error("Template", template_id)

        # Check ownership
        if template.author_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to publish this template"
            )

        # Update visibility
        if request.visibility == "public":
            template.is_public = True
        elif request.visibility == "private":
            template.is_public = False

        # Only admins can set featured
        if request.featured:
            # Check if user is an admin
            user = db.query(User).filter(User.id == user_id).first()
            if not user or user.role not in [UserRole.SUPER_ADMIN, UserRole.WORKSPACE_ADMIN]:
                raise router.permission_denied_error(
                    action="feature_template",
                    resource="Template",
                    details={"template_id": template_id, "required_role": "SUPER_ADMIN or WORKSPACE_ADMIN"}
                )
            template.is_featured = True

        template.updated_at = datetime.now()
        db.commit()
        db.refresh(template)

        logger.info(f"Published template {template_id} as {request.visibility}")
        return template

    except Exception as e:
        logger.error(f"Error publishing template {template_id}: {e}")
        db.rollback()
        raise router.internal_error(str(e))


@router.post("/{template_id}/duplicate", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_template(
    template_id: str,
    request: DuplicateTemplateRequest,
    user_id: str = Query(..., description="User ID creating the duplicate"),
    db: Session = Depends(get_db)
):
    """
    Duplicate/fork an existing template

    Creates a copy of a template with a new owner.
    Useful for template customization.
    """
    try:
        original = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.template_id == template_id
        ).first()

        if not original:
            raise router.not_found_error("Template", template_id)

        # Check if original is public or user owns it
        if not original.is_public and original.author_id != user_id:
            raise router.permission_denied_error(
                action="duplicate_template",
                resource="Template",
                details={"template_id": template_id, "user_id": user_id}
            )

        # Create duplicate
        new_template_id = f"template_{uuid.uuid4().hex[:12]}"
        duplicate = WorkflowTemplate(
            template_id=new_template_id,
            name=request.name,
            description=request.description or original.description,
            category=original.category,
            complexity=original.complexity,
            tags=original.tags.copy(),
            author_id=user_id,
            is_public=False,  # Duplicates start as private
            is_featured=False,
            template_json=original.template_json.copy(),
            inputs_schema=original.inputs_schema.copy() if original.inputs_schema else [],
            steps_schema=original.steps_schema.copy() if original.steps_schema else [],
            output_schema=original.output_schema.copy() if original.output_schema else {},
            version="1.0.0",  # Reset version for duplicate
            parent_template_id=original.template_id,  # Track origin
            estimated_duration_seconds=original.estimated_duration_seconds,
            prerequisites=original.prerequisites.copy() if original.prerequisites else [],
            dependencies=original.dependencies.copy() if original.dependencies else [],
            permissions=original.permissions.copy() if original.permissions else [],
            license=original.license,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        db.add(duplicate)
        db.commit()
        db.refresh(duplicate)

        logger.info(f"Duplicated template {template_id} as {new_template_id} for user {user_id}")
        return duplicate

    except Exception as e:
        logger.error(f"Error duplicating template {template_id}: {e}")
        db.rollback()
        raise router.internal_error(str(e))


@router.get("/{template_id}/versions", response_model=List[Dict[str, Any]])
async def get_template_versions(
    template_id: str,
    db: Session = Depends(get_db)
):
    """
    Get version history for a template

    Returns all versions with change descriptions and metadata.
    """
    try:
        # Verify template exists
        template = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.template_id == template_id
        ).first()

        if not template:
            raise router.not_found_error("Template", template_id)

        # Get versions
        versions = db.query(TemplateVersion).filter(
            TemplateVersion.template_id == template_id
        ).order_by(TemplateVersion.created_at.desc()).all()

        return [
            {
                "id": v.id,
                "version": v.version,
                "change_description": v.change_description,
                "changed_by_id": v.changed_by_id,
                "created_at": v.created_at.isoformat()
            }
            for v in versions
        ]

    except Exception as e:
        logger.error(f"Error getting versions for template {template_id}: {e}")
        raise router.internal_error(str(e))


@router.post("/{template_id}/rate")
async def rate_template(
    template_id: str,
    rating: int = Query(..., ge=1, le=5, description="Rating from 1-5"),
    db: Session = Depends(get_db)
):
    """
    Rate a template

    Submits a user rating for a template.
    """
    try:
        template = db.query(WorkflowTemplate).filter(
            WorkflowTemplate.template_id == template_id
        ).first()

        if not template:
            raise router.not_found_error("Template", template_id)

        # Update rating
        template.rating_sum += rating
        template.rating_count += 1
        template.updated_at = datetime.now()

        db.commit()

        logger.info(f"Rated template {template_id} with {rating} stars")
        return {
            "message": "Rating submitted successfully",
            "new_rating": template.rating,
            "rating_count": template.rating_count
        }

    except Exception as e:
        logger.error(f"Error rating template {template_id}: {e}")
        db.rollback()
        raise router.internal_error(str(e))
