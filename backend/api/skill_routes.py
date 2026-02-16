"""
Community Skills Registry API Endpoints

REST API for importing, managing, and executing OpenClaw community skills
with security scanning and governance integration.

Reference: Phase 14 Plan 03 - Skills Registry & Security
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.skill_registry_service import SkillRegistryService

logger = logging.getLogger(__name__)

# Create router
router = BaseAPIRouter(
    prefix="/api/skills",
    tags=["Community Skills"]
)


# ============================================================================
# Request/Response Models
# ============================================================================

class ImportSkillRequest(BaseModel):
    """Request model for importing a community skill."""
    source: str = Field(
        ...,
        description="Import source: 'github_url', 'file_upload', or 'raw_content'"
    )
    content: str = Field(
        ...,
        description="SKILL.md content or file content"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata (author, tags, etc.)"
    )


class ExecuteSkillRequest(BaseModel):
    """Request model for executing a community skill."""
    skill_id: str = Field(..., description="Skill ID from import")
    inputs: Dict[str, Any] = Field(
        ...,
        description="Input parameters for skill execution"
    )
    agent_id: Optional[str] = Field(
        default="system",
        description="Agent ID executing the skill (default: system)"
    )


class PromoteSkillRequest(BaseModel):
    """Request model for promoting a skill to Active status."""
    skill_id: str = Field(..., description="Skill ID to promote")


class SkillListResponse(BaseModel):
    """Response model for listing skills."""
    skills: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of skills"
    )
    total: int = Field(..., description="Total number of skills")
    page: int = Field(default=1, description="Page number")
    page_size: int = Field(default=100, description="Items per page")


# ============================================================================
# Dependencies
# ============================================================================

def get_skill_service(db: Session = Depends(get_db)) -> SkillRegistryService:
    """
    Dependency to get SkillRegistryService instance.

    Args:
        db: Database session

    Returns:
        SkillRegistryService instance
    """
    return SkillRegistryService(db)


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/import")
async def import_skill(
    request: ImportSkillRequest,
    service: SkillRegistryService = Depends(get_skill_service)
) -> Dict[str, Any]:
    """
    Import a community skill from GitHub URL, file upload, or raw content.

    Args:
        request: Import request with source, content, and optional metadata
        service: Skill registry service

    Returns:
        Dict with:
            - skill_id: Unique identifier for imported skill
            - skill_name: Name of the skill
            - scan_result: Security scan results
            - status: "Untrusted" or "Active"
            - metadata: Skill metadata

    Example:
        POST /api/skills/import
        {
            "source": "raw_content",
            "content": "---\\nname: Calculator\\n---\\n...",
            "metadata": {"author": "community"}
        }
    """
    try:
        result = service.import_skill(
            source=request.source,
            content=request.content,
            metadata=request.metadata
        )

        return router.success_response(
            data=result,
            message=f"Skill '{result['skill_name']}' imported successfully as {result['status']}"
        )

    except ValueError as e:
        logger.error(f"Import validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import skill: {str(e)}"
        )


@router.get("/list")
async def list_skills(
    status: Optional[str] = None,
    skill_type: Optional[str] = None,
    limit: int = 100,
    service: SkillRegistryService = Depends(get_skill_service)
) -> Dict[str, Any]:
    """
    List imported community skills with optional filtering.

    Query Parameters:
        - status: Filter by status - "Untrusted", "Active", or None (all)
        - skill_type: Filter by skill_type - "prompt_only", "python_code", or None (all)
        - limit: Maximum number of skills to return (default: 100)

    Returns:
        Dict with:
            - skills: List of skill metadata
            - total: Total count
            - filters: Applied filters

    Example:
        GET /api/skills/list?status=Active&skill_type=prompt_only&limit=10
    """
    try:
        skills = service.list_skills(
            status=status,
            skill_type=skill_type,
            limit=limit
        )

        return router.success_response(
            data={
                "skills": skills,
                "total": len(skills),
                "filters": {
                    "status": status,
                    "skill_type": skill_type,
                    "limit": limit
                }
            },
            message=f"Retrieved {len(skills)} skills"
        )

    except Exception as e:
        logger.error(f"Failed to list skills: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list skills: {str(e)}"
        )


@router.get("/{skill_id}")
async def get_skill(
    skill_id: str,
    service: SkillRegistryService = Depends(get_skill_service)
) -> Dict[str, Any]:
    """
    Get detailed information about a specific skill.

    Args:
        skill_id: Skill ID from import
        service: Skill registry service

    Returns:
        Dict with:
            - skill_id: Skill ID
            - skill_name: Skill name
            - skill_type: "prompt_only" or "python_code"
            - skill_body: Skill content
            - skill_metadata: Skill metadata
            - status: "Untrusted" or "Active"
            - security_scan_result: Scan results
            - sandbox_enabled: Whether sandbox is enabled
            - created_at: Import timestamp

    Example:
        GET /api/skills/abc-123-def
    """
    try:
        skill = service.get_skill(skill_id)

        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill not found: {skill_id}"
            )

        return router.success_response(
            data=skill,
            message=f"Retrieved skill '{skill['skill_name']}'"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get skill: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get skill: {str(e)}"
        )


@router.post("/execute")
async def execute_skill(
    request: ExecuteSkillRequest,
    service: SkillRegistryService = Depends(get_skill_service)
) -> Dict[str, Any]:
    """
    Execute a community skill with governance checks.

    Args:
        request: Execute request with skill_id, inputs, and optional agent_id
        service: Skill registry service

    Returns:
        Dict with:
            - success: True/False
            - result: Execution result (if successful)
            - error: Error message (if failed)
            - execution_id: Execution record ID

    Governance:
        - STUDENT agents: Cannot execute Python skills
        - INTERN+ agents: Can execute all Active skills
        - Untrusted skills: Require manual promotion first

    Example:
        POST /api/skills/execute
        {
            "skill_id": "abc-123-def",
            "inputs": {"query": "What is 2+2?"},
            "agent_id": "agent-456"
        }
    """
    try:
        result = service.execute_skill(
            skill_id=request.skill_id,
            inputs=request.inputs,
            agent_id=request.agent_id
        )

        if result["success"]:
            return router.success_response(
                data=result,
                message=f"Skill executed successfully (execution_id: {result['execution_id']})"
            )
        else:
            return router.success_response(
                data=result,
                message=f"Skill execution failed: {result.get('error', 'Unknown error')}",
                status_code=status.HTTP_202_ACCEPTED
            )

    except ValueError as e:
        logger.error(f"Execution validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute skill: {str(e)}"
        )


@router.post("/promote")
async def promote_skill(
    request: PromoteSkillRequest,
    service: SkillRegistryService = Depends(get_skill_service)
) -> Dict[str, Any]:
    """
    Promote a skill from Untrusted to Active status.

    Args:
        request: Promote request with skill_id
        service: Skill registry service

    Returns:
        Dict with:
            - status: New status ("Active")
            - previous_status: Previous status
            - message: Confirmation message

    Example:
        POST /api/skills/promote
        {
            "skill_id": "abc-123-def"
        }
    """
    try:
        result = service.promote_skill(request.skill_id)

        return router.success_response(
            data=result,
            message=f"Skill promoted to {result['status']}"
        )

    except ValueError as e:
        logger.error(f"Promote validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Promote failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to promote skill: {str(e)}"
        )


@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: str,
    service: SkillRegistryService = Depends(get_skill_service)
) -> Dict[str, Any]:
    """
    Delete a skill from the registry.

    Args:
        skill_id: Skill ID to delete
        service: Skill registry service

    Returns:
        Dict with deletion confirmation

    Example:
        DELETE /api/skills/abc-123-def
    """
    try:
        # Note: This would need to be implemented in SkillRegistryService
        # For now, return a not implemented error
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Delete operation not yet implemented"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete skill: {str(e)}"
        )
