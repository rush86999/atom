"""
Deep Link REST API Endpoints

Provides REST endpoints for deep link execution, audit, and generation.
Integrates with the deep link system for atom:// URL scheme support.

Endpoints:
- POST /api/deeplinks/execute - Execute a deep link
- GET /api/deeplinks/audit - Get deep link audit log
- POST /api/deeplinks/generate - Generate a deep link
- GET /api/deeplinks/stats - Get deep link statistics
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.deeplinks import (
    DeepLinkParseException,
    DeepLinkSecurityException,
    execute_deep_link,
    generate_deep_link,
    parse_deep_link,
)
from core.models import AgentRegistry, DeepLinkAudit

logger = logging.getLogger(__name__)

DEEPLINK_ENABLED = os.getenv("DEEPLINK_ENABLED", "true").lower() == "true"

router = BaseAPIRouter(prefix="/api/deeplinks", tags=["Deep Links"])


# Request/Response Models
class DeepLinkExecuteRequest(BaseModel):
    """Request to execute a deep link."""
    deeplink_url: str = Field(..., description="The atom:// deep link URL to execute")
    user_id: str = Field(..., description="User ID executing the deep link")
    source: str = Field(default="external", description="Source of the deep link")


class DeepLinkExecuteResponse(BaseModel):
    """Response from deep link execution."""
    success: bool
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    execution_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: Optional[str] = None
    error: Optional[str] = None
    source: Optional[str] = None


class DeepLinkGenerateRequest(BaseModel):
    """Request to generate a deep link."""
    resource_type: str = Field(..., description="Type of resource: agent, workflow, canvas, tool")
    resource_id: str = Field(..., description="ID of the resource")
    parameters: Dict[str, Any] = Field(default={}, description="Query parameters for the deep link")


class DeepLinkGenerateResponse(BaseModel):
    """Response with generated deep link."""
    deeplink_url: str
    resource_type: str
    resource_id: str
    parameters: Dict[str, Any]


class DeepLinkAuditResponse(BaseModel):
    """Deep link audit entry."""
    id: str
    user_id: str
    agent_id: Optional[str]
    agent_execution_id: Optional[str]
    resource_type: str
    resource_id: str
    action: str
    source: str
    deeplink_url: str
    parameters: Optional[Dict[str, Any]]
    status: str
    error_message: Optional[str]
    governance_check_passed: Optional[bool]
    created_at: datetime


class DeepLinkStatsResponse(BaseModel):
    """Deep link statistics."""
    total_executions: int
    successful_executions: int
    failed_executions: int
    by_resource_type: Dict[str, int]
    by_source: Dict[str, int]
    top_agents: List[Dict[str, Any]]
    last_24h_executions: int
    last_7d_executions: int


@router.post("/execute", response_model=DeepLinkExecuteResponse)
async def execute_deeplink_endpoint(
    request: DeepLinkExecuteRequest,
    db: Session = Depends(get_db)
):
    """
    Execute an atom:// deep link.

    This endpoint parses and executes a deep link URL, routing it to the
    appropriate handler (agent, workflow, canvas, or tool).

    Args:
        request: Deep link execution request with URL and user context
        db: Database session

    Returns:
        DeepLinkExecuteResponse with execution result

    Raises:
        HTTPException: If deep link is invalid or execution fails
    """
    if not DEEPLINK_ENABLED:
        raise router.error_response(
            error_code="SERVICE_UNAVAILABLE",
            message="Deep linking is disabled",
            status_code=503
        )

    try:
        # Execute deep link
        result = await execute_deep_link(
            url=request.deeplink_url,
            user_id=request.user_id,
            db=db,
            source=request.source
        )

        if not result.get("success"):
            raise router.validation_error("deeplink_url", result.get("error", "Deep link execution failed"))

        # Build response
        response = DeepLinkExecuteResponse(
            success=True,
            agent_id=result.get("agent_id"),
            agent_name=result.get("agent_name"),
            execution_id=result.get("execution_id"),
            resource_type=result.get("resource_type"),
            resource_id=result.get("resource_id"),
            action=result.get("action"),
            source=result.get("source")
        )

        logger.info(
            f"Deep link executed successfully: {request.deeplink_url}, "
            f"user={request.user_id}, result={result}"
        )

        return response

    except (DeepLinkParseException, DeepLinkSecurityException) as e:
        logger.error(f"Deep link execution failed: {e}")
        raise router.validation_error("deeplink_url", str(e))
    except Exception as e:
        logger.error(f"Unexpected error executing deep link: {e}")
        raise router.internal_error(f"Internal server error: {str(e)}")


@router.get("/audit", response_model=List[DeepLinkAuditResponse])
async def get_deeplink_audit(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of entries"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    Get deep link audit log.

    Returns audit entries for deep link executions, with optional filters.
    Results are ordered by most recent first.

    Args:
        user_id: Filter by user ID
        agent_id: Filter by agent ID
        resource_type: Filter by resource type (agent, workflow, canvas, tool)
        limit: Maximum number of entries to return
        offset: Offset for pagination
        db: Database session

    Returns:
        List of DeepLinkAuditResponse entries
    """
    query = db.query(DeepLinkAudit)

    # Apply filters
    if user_id:
        query = query.filter(DeepLinkAudit.user_id == user_id)
    if agent_id:
        query = query.filter(DeepLinkAudit.agent_id == agent_id)
    if resource_type:
        query = query.filter(DeepLinkAudit.resource_type == resource_type)

    # Order by most recent first
    query = query.order_by(DeepLinkAudit.created_at.desc())

    # Apply pagination
    audit_entries = query.offset(offset).limit(limit).all()

    # Convert to response models
    response = [
        DeepLinkAuditResponse(
            id=entry.id,
            user_id=entry.user_id,
            agent_id=entry.agent_id,
            agent_execution_id=entry.agent_execution_id,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            action=entry.action,
            source=entry.source,
            deeplink_url=entry.deeplink_url,
            parameters=entry.parameters,
            status=entry.status,
            error_message=entry.error_message,
            governance_check_passed=entry.governance_check_passed,
            created_at=entry.created_at
        )
        for entry in audit_entries
    ]

    logger.info(f"Retrieved {len(response)} deep link audit entries")

    return response


@router.post("/generate", response_model=DeepLinkGenerateResponse)
async def generate_deeplink_endpoint(request: DeepLinkGenerateRequest):
    """
    Generate an atom:// deep link URL.

    This endpoint creates a properly formatted deep link URL for the
    specified resource and parameters.

    Args:
        request: Deep link generation request

    Returns:
        DeepLinkGenerateResponse with generated URL

    Raises:
        HTTPException: If resource type is invalid
    """
    if not DEEPLINK_ENABLED:
        raise router.error_response(
            error_code="SERVICE_UNAVAILABLE",
            message="Deep linking is disabled",
            status_code=503
        )

    try:
        # Validate resource type
        valid_resource_types = ['agent', 'workflow', 'canvas', 'tool']
        if request.resource_type not in valid_resource_types:
            raise router.validation_error(
                "resource_type",
                f"Invalid resource_type: '{request.resource_type}'. "
                f"Must be one of {valid_resource_types}",
                details={"provided": request.resource_type, "valid_types": valid_resource_types}
            )

        # Generate deep link
        deeplink_url = generate_deep_link(
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            **request.parameters
        )

        response = DeepLinkGenerateResponse(
            deeplink_url=deeplink_url,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            parameters=request.parameters
        )

        logger.info(f"Generated deep link: {deeplink_url}")

        return response

    except ValueError as e:
        logger.error(f"Failed to generate deep link: {e}")
        raise router.validation_error("request", str(e))
    except Exception as e:
        logger.error(f"Unexpected error generating deep link: {e}")
        raise router.internal_error(f"Internal server error: {str(e)}")


@router.get("/stats", response_model=DeepLinkStatsResponse)
async def get_deeplink_stats(
    db: Session = Depends(get_db)
):
    """
    Get deep link statistics.

    Returns aggregate statistics about deep link usage including:
    - Total executions
    - Success/failure rates
    - Breakdown by resource type
    - Breakdown by source
    - Top agents by usage
    - Recent activity (24h, 7d)

    Args:
        db: Database session

    Returns:
        DeepLinkStatsResponse with aggregate statistics
    """
    # Total executions
    total_executions = db.query(DeepLinkAudit).count()

    # Successful vs failed
    successful_executions = db.query(DeepLinkAudit).filter(
        DeepLinkAudit.status == "success"
    ).count()

    failed_executions = db.query(DeepLinkAudit).filter(
        DeepLinkAudit.status.in_(["failed", "error"])
    ).count()

    # By resource type
    by_resource_type = {}
    for rt in ['agent', 'workflow', 'canvas', 'tool']:
        count = db.query(DeepLinkAudit).filter(
            DeepLinkAudit.resource_type == rt
        ).count()
        by_resource_type[rt] = count

    # By source
    by_source = {}
    sources = db.query(DeepLinkAudit.source).distinct().all()
    for (source,) in sources:
        count = db.query(DeepLinkAudit).filter(
            DeepLinkAudit.source == source
        ).count()
        by_source[source] = count

    # Top agents by usage
    top_agents_query = db.query(
        DeepLinkAudit.agent_id,
        AgentRegistry.name
    ).join(
        AgentRegistry, DeepLinkAudit.agent_id == AgentRegistry.id
    ).filter(
        DeepLinkAudit.agent_id.isnot(None)
    ).group_by(
        DeepLinkAudit.agent_id, AgentRegistry.name
    ).order_by(
        db.func.count(DeepLinkAudit.id).desc()
    ).limit(10).all()

    top_agents = [
        {"agent_id": agent_id, "agent_name": name, "execution_count": 0}
        for agent_id, name in top_agents_query
    ]

    # Fill in execution counts
    for i, (agent_id, _) in enumerate(top_agents_query):
        count = db.query(DeepLinkAudit).filter(
            DeepLinkAudit.agent_id == agent_id
        ).count()
        top_agents[i]["execution_count"] = count

    # Recent activity
    now = datetime.now()
    last_24h_executions = db.query(DeepLinkAudit).filter(
        DeepLinkAudit.created_at >= now - timedelta(hours=24)
    ).count()

    last_7d_executions = db.query(DeepLinkAudit).filter(
        DeepLinkAudit.created_at >= now - timedelta(days=7)
    ).count()

    response = DeepLinkStatsResponse(
        total_executions=total_executions,
        successful_executions=successful_executions,
        failed_executions=failed_executions,
        by_resource_type=by_resource_type,
        by_source=by_source,
        top_agents=top_agents,
        last_24h_executions=last_24h_executions,
        last_7d_executions=last_7d_executions
    )

    logger.info(f"Retrieved deep link stats: {total_executions} total executions")

    return response
