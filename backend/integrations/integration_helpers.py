"""
Integration Helper Module
Standard patterns for governance, error handling, and audit trails
"""
import logging
from typing import Optional, Dict, Any, Tuple
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentExecution, User
from core.database import get_db

logger = logging.getLogger(__name__)

# Standard action complexity mapping
ACTION_COMPLEXITY = {
    # READ operations - STUDENT+
    "search": 1, "read": 1, "get": 1, "list": 1,
    # MODERATE operations - INTERN+
    "analyze": 2, "stream_chat": 2, "post_message": 2, "send": 2,
    # HIGH operations - SUPERVISED+
    "create": 3, "update": 3, "submit_form": 3, "delete": 3,
    # CRITICAL operations - AUTONOMOUS only
    "execute": 4, "payment": 4,
}


async def with_governance_check(
    db: Session,
    user: User,
    action_type: str,
    agent_id: Optional[str] = None
) -> Tuple[Optional[AgentRegistry], Dict[str, Any]]:
    """
    Perform agent resolution and governance check.
    Returns (agent, governance_check_result) tuple.
    """
    resolver = AgentContextResolver(db)
    governance = AgentGovernanceService(db)

    agent, ctx = await resolver.resolve_agent_for_request(
        user_id=user.id,
        requested_agent_id=agent_id,
        action_type=action_type
    )

    if agent:
        check = governance.can_perform_action(agent.id, action_type)
        if not check["allowed"]:
            raise HTTPException(
                status_code=403,
                detail=f"Agent not permitted to {action_type}: {check['reason']}"
            )
        return agent, check

    return None, {"allowed": True}


def create_execution_record(
    db: Session,
    agent_id: Optional[str],
    user_id: str,
    action: str,
    status: str = "running"
) -> AgentExecution:
    """Create agent execution record for audit trail"""
    import uuid
    execution = AgentExecution(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        user_id=user_id,
        workspace_id="default",
        status=status,
        input_summary=f"Integration action: {action}",
        triggered_by="integration_route"
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def standard_error_response(e: Exception, operation: str) -> Dict[str, Any]:
    """Standard error response format"""
    logger.error(f"Error in {operation}: {e}", exc_info=True)
    return {
        "success": False,
        "error": str(e),
        "error_type": type(e).__name__,
        "operation": operation
    }
