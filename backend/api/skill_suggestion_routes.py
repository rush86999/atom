"""
Skill Suggestion API Routes

AI-powered skill recommendation engine for entity types.
"""
import logging
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from core.base_routes import BaseAPIRouter
from core.skill_suggestion_service import get_skill_suggestion_service

router = BaseAPIRouter(prefix="/api/skill-suggestions", tags=["Skill Suggestions"])

# --- Request/Response Models ---

class ApproveSuggestionRequest(BaseModel):
    skill_id: str = Field(..., description="Skill UUID to approve and attach")

# --- Route Handlers ---

@router.get("/entity-types/{entity_type_id}")
async def get_skill_suggestions(workspace_id: str, entity_type_id: str):
    """Get AI-powered skill suggestions for an entity type."""
    service = get_skill_suggestion_service()
    try:
        suggestions = await service.suggest_skills_for_entity_type(
            tenant_id=workspace_id,
            entity_type_id=entity_type_id
        )
        return router.success_response(
            data={"suggestions": suggestions},
            message=f"Generated {len(suggestions)} suggestions"
        )
    except ValueError as e:
        raise router.not_found_error("EntityType", entity_type_id)

@router.post("/entity-types/{entity_type_id}/approve")
async def approve_skill_suggestion(
    workspace_id: str,
    entity_type_id: str,
    request_data: ApproveSuggestionRequest
):
    """Approve and attach a suggested skill."""
    service = get_skill_suggestion_service()
    try:
        entity_type = service.approve_suggestion(
            tenant_id=workspace_id,
            entity_type_id=entity_type_id,
            skill_id=request_data.skill_id
        )
        return router.success_response(
            data={"id": entity_type.id, "slug": entity_type.slug},
            message=f"Skill '{request_data.skill_id}' successfully attached"
        )
    except ValueError as e:
        raise router.validation_error("skill_suggestion", str(e))
