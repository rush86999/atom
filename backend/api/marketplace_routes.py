"""
Marketplace API Routes - Local PostgreSQL marketplace with future Atom SaaS sync.

Endpoints:
- GET /marketplace/skills - Search and browse local marketplace
- GET /marketplace/skills/{id} - Get skill details with ratings
- GET /marketplace/categories - List categories
- POST /marketplace/skills/{id}/rate - Rate a skill (1-5 stars)
- POST /marketplace/skills/{id}/install - Install skill

All endpoints use SkillMarketplaceService which queries local PostgreSQL.
Future: Atom SaaS API sync layer will be added when API is available.

Reference: Phase 60 Plan 01 - Local Marketplace with Atom SaaS Integration
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional

from core.database import get_db
from core.skill_marketplace_service import SkillMarketplaceService

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


class SkillSearchResponse(BaseModel):
    skills: List[dict]
    total: int
    page: int
    page_size: int
    total_pages: int
    source: str


class RatingRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")
    comment: Optional[str] = Field(None, max_length=1000, description="Optional review comment")
    user_id: str = Field(..., description="User or agent ID submitting rating")


class InstallRequest(BaseModel):
    agent_id: str = Field(..., description="Agent ID that will use the skill")
    auto_install_deps: bool = Field(True, description="Auto-install dependencies")


@router.get("/skills", response_model=SkillSearchResponse)
def search_marketplace_skills(
    query: str = Query("", description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    skill_type: Optional[str] = Query(None, description="Filter by skill type (prompt_only, python_code, nodejs)"),
    sort_by: str = Query("relevance", description="Sort order: relevance, created, name"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    Search marketplace skills with filtering and pagination.

    Searches local PostgreSQL community skills database.

    - **query**: Full-text search on skill name and description
    - **category**: Filter by skill category (e.g., data, automation, integration)
    - **skill_type**: Filter by type (prompt_only, python_code, nodejs)
    - **sort_by**: Sort order (relevance, created, name)
    - **page**: Page number for pagination
    - **page_size**: Number of results per page (max 100)

    Returns paginated results with metadata.
    """
    service = SkillMarketplaceService(db)
    return service.search_skills(
        query=query,
        category=category,
        skill_type=skill_type,
        sort_by=sort_by,
        page=page,
        page_size=page_size
    )


@router.get("/skills/{skill_id}")
def get_marketplace_skill(
    skill_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed skill information with ratings.

    Returns skill metadata, ratings, and installation information.

    - **skill_id**: Unique skill identifier
    """
    service = SkillMarketplaceService(db)
    skill = service.get_skill_by_id(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    return skill


@router.get("/categories")
def list_marketplace_categories(db: Session = Depends(get_db)):
    """
    Get all marketplace categories with skill counts.

    Returns list of categories with display names and skill counts.
    """
    service = SkillMarketplaceService(db)
    return service.get_categories()


@router.post("/skills/{skill_id}/rate")
def rate_marketplace_skill(
    skill_id: str,
    request: RatingRequest,
    db: Session = Depends(get_db)
):
    """
    Submit a rating for a skill (1-5 stars with optional comment).

    - **skill_id**: Unique skill identifier
    - **rating**: Rating value (1-5 stars)
    - **comment**: Optional review text (max 1000 characters)
    - **user_id**: User or agent ID submitting the rating

    If the user has already rated this skill, the existing rating will be updated.
    """
    service = SkillMarketplaceService(db)
    result = service.rate_skill(
        skill_id=skill_id,
        user_id=request.user_id,
        rating=request.rating,
        comment=request.comment
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/skills/{skill_id}/install")
def install_marketplace_skill(
    skill_id: str,
    request: InstallRequest,
    db: Session = Depends(get_db)
):
    """
    Install a skill from the marketplace.

    - **skill_id**: Unique skill identifier
    - **agent_id**: Agent ID that will use the skill
    - **auto_install_deps**: Automatically install Python/npm dependencies (default: true)

    Returns installation status.
    """
    service = SkillMarketplaceService(db)
    result = service.install_skill(
        skill_id=skill_id,
        agent_id=request.agent_id,
        auto_install_deps=request.auto_install_deps
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result
